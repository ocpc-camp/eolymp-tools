#!/bin/bash
# Get an Eolymp API token -> $EOLYMP_TOKEN (and <repo>/.env).
#
# Usage:
#   get_token.sh                 # ORG/ADMIN token: opens a browser, you log into
#                                #   console.eolymp.com once; captures the token to
#                                #   ../.env and writes a REDACTED flow log to
#                                #   /tmp/eolymp-flow.log (written incrementally, so
#                                #   closing the window can't lose it).
#   get_token.sh login <url>     # same, but start at <url> (e.g. a space UI).
#   get_token.sh refresh         # renew the access token from the saved refresh
#                                #   token — no login.
#   get_token.sh space <key>     # SPACE-MEMBER token via password grant
#                                #   (e.g. get_token.sh space osijek2025w).
#
# PASSWORD-SAFE: the browser monitor DROPS the sign-in request body entirely and
# redacts password/username fields elsewhere; token values are redacted in the
# flow log (real token only goes to ../.env). Your password is never recorded.
#
# Why a browser for the admin token? Eolymp's organizer/global account only
# supports the OIDC authorization_code flow (client_id=console) — no password
# grant (tested: "unsupported grant_type"), and no self-service access keys.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
FLOW_LOG="/tmp/eolymp-flow.log"
TOKEN_EP_DEFAULT="https://api.eolymp.com/oauth2/token"

find_pw() {
  for d in "$(npm root -g 2>/dev/null || true)" \
           "$HOME/.npm/_npx/9833c18b2d85bc59/node_modules" \
           "$ROOT/node_modules"; do
    [ -n "${d:-}" ] && [ -d "$d/playwright" ] && { printf '%s' "$d"; return 0; }
  done
  return 1
}

cmd="${1:-login}"
case "$cmd" in
login)
  start_url="${2:-https://console.eolymp.com/}"
  pw="$(find_pw)" || { echo "Playwright not found. Install with: npm i -g playwright"; exit 1; }
  set +e
  NODE_PATH="$pw" START_URL="$start_url" ENV_OUT="$ENV_FILE" FLOW_LOG="$FLOW_LOG" node - <<'NODE'
const { chromium } = require('playwright');
const fs = require('fs');
const START_URL = process.env.START_URL, ENV_OUT = process.env.ENV_OUT, FLOW_LOG = process.env.FLOW_LOG;
const cap = { client_id:null, token_endpoint:null, access_token:null, refresh_token:null, scope:null, expires_in:null };
const isTok  = u => /\/oauth2?\/token(\?|$)/.test(u);
const isAuth = u => /\/(authorize|oauth2\/auth)(\?|$)/.test(u);
const hosts = new Set();
let notified = false, done = false;
const redactTok  = s => s ? (s.slice(0,6)+'…'+s.slice(-4)+` (len ${s.length})`) : s;
const redactBody = (host, path, body) => {
  if (!body) return '';
  if (host.includes('accounts.eolymp') || /signin|sign-in|login/i.test(path)) return '[omitted: credential request]';
  let b = String(body).replace(/(password=)[^&]*/gi,'$1<redacted>').replace(/(username=)[^&]*/gi,'$1<redacted>');
  return b.length > 300 ? b.slice(0,300)+'…' : b;
};
try { fs.writeFileSync(FLOW_LOG, '', { mode:0o600 }); } catch(e){}
const rec = line => { try { fs.appendFileSync(FLOW_LOG, line+'\n'); } catch(e){} };

function finalize(err) {
  if (done) return; done = true;
  if (err) rec('FATAL ' + err);
  process.stderr.write(`\nRedacted flow log -> ${FLOW_LOG}\nhosts: ${[...hosts].sort().join(', ')}\n`);
  if (cap.access_token) {
    const lines = [
      `EOLYMP_TOKEN=${cap.access_token}`,
      cap.refresh_token  ? `EOLYMP_REFRESH_TOKEN=${cap.refresh_token}` : null,
      cap.client_id      ? `EOLYMP_CLIENT_ID=${cap.client_id}` : null,
      cap.token_endpoint ? `EOLYMP_TOKEN_ENDPOINT=${cap.token_endpoint}` : null,
    ].filter(Boolean).join('\n') + '\n';
    try { fs.writeFileSync(ENV_OUT, lines, { mode:0o600 }); } catch(e){}
    process.stderr.write(`captured: client_id=${cap.client_id||'-'} scope=${cap.scope||'-'} refresh=${cap.refresh_token?'yes':'no'}\n`);
    process.exit(0);
  }
  process.stderr.write('No bearer token seen in the browser (likely server-side) — see the flow log.\n');
  process.exit(1);
}

(async () => {
  const b = await chromium.launch({ channel:'chrome', headless:false });
  const ctx = await b.newContext();
  const p = await ctx.newPage();
  p.on('close', () => finalize(null));
  b.on('disconnected', () => finalize(null));

  p.on('request', async q => {
    const u = q.url(); let host='', path='';
    try { const U=new URL(u); host=U.host; path=U.pathname; hosts.add(host); } catch(e){}
    if (!/eolymp/.test(host)) return;
    let auth=''; try { auth=(await q.allHeaders())['authorization']||''; } catch(e){}
    if (/^Bearer\s+/i.test(auth)) {
      cap.access_token = auth.replace(/^Bearer\s+/i,'');
      if (!notified) { notified=true; process.stderr.write('\n✓ captured a Bearer token — finishing up (you can close the window).\n'); }
    }
    if (isAuth(u)) { try { const s=new URL(u).searchParams; if(s.get('client_id')) cap.client_id=s.get('client_id'); } catch(e){} }
    if (!cap.client_id && isTok(u) && q.method()==='POST') { try { const s=new URLSearchParams(q.postData()||''); if(s.get('client_id')) cap.client_id=s.get('client_id'); } catch(e){} }
    rec(`REQ  ${q.method().padEnd(4)} ${host}${path}`
      + (auth ? `  [auth: Bearer ${redactTok(auth.replace(/^Bearer\s+/i,''))}]` : '')
      + (q.postData() ? `\n      body: ${redactBody(host,path,q.postData())}` : ''));
  });

  p.on('response', async r => {
    const u = r.url(); let host='', path='';
    try { const U=new URL(u); host=U.host; path=U.pathname; } catch(e){}
    if (!/eolymp/.test(host)) return;
    let extra='';
    if (isTok(u)) {
      try { const j=await r.json();
        if(j.access_token)  cap.access_token  = j.access_token;
        if(j.refresh_token) cap.refresh_token = j.refresh_token;
        if(j.scope)         cap.scope         = j.scope;
        if(j.expires_in)    cap.expires_in    = j.expires_in;
        cap.token_endpoint = u.split('?')[0];
        extra = `  [token resp: access=${j.access_token?redactTok(j.access_token):'-'} refresh=${j.refresh_token?'yes':'no'} scope=${j.scope||'-'}]`;
      } catch(e){}
    }
    rec(`RESP ${String(r.status()).padEnd(4)} ${host}${path}${extra}`);
  });

  await p.goto(START_URL).catch(()=>{});
  process.stderr.write('\n>>> Log in in the browser window, then click into a contest\'s Submissions.\n>>> (Your password is NOT recorded.) Capturing…\n');
  const dl = Date.now()+300000; let firstSeen=0;
  while (Date.now()<dl && !done) {
    if (cap.access_token) { if(!firstSeen) firstSeen=Date.now(); if(cap.refresh_token || Date.now()-firstSeen>5000) break; }
    try { await p.waitForTimeout(500); } catch(e) { break; }
  }
  try { await b.close(); } catch(e){}
  finalize(null);
})().catch(e => finalize(e.message));
NODE
  rc=$?
  set -e
  echo; echo "Flow log: $FLOW_LOG"
  [ "$rc" -eq 0 ] || { echo "(no token captured — share $FLOW_LOG so we can see where it lives)"; exit "$rc"; }
  chmod 600 "$ENV_FILE" 2>/dev/null || true
  # shellcheck disable=SC1090
  [ -f "$ENV_FILE" ] && . "$ENV_FILE" && { echo "✓ Saved to $ENV_FILE"; echo "export EOLYMP_TOKEN='${EOLYMP_TOKEN:-}'"; }
  ;;

refresh)
  [ -f "$ENV_FILE" ] || { echo "No $ENV_FILE — run 'get_token.sh' (login) first."; exit 1; }
  set -a; . "$ENV_FILE"; set +a
  : "${EOLYMP_REFRESH_TOKEN:?no refresh_token in .env}"; : "${EOLYMP_CLIENT_ID:?no client_id in .env}"
  ep="${EOLYMP_TOKEN_ENDPOINT:-$TOKEN_EP_DEFAULT}"
  resp=$(curl -s -X POST "$ep" -H 'content-type: application/x-www-form-urlencoded' \
    --data-urlencode grant_type=refresh_token --data-urlencode "refresh_token=$EOLYMP_REFRESH_TOKEN" --data-urlencode "client_id=$EOLYMP_CLIENT_ID")
  at=$(echo "$resp" | grep -oE '"access_token":"[^"]*"'  | head -1 | sed -E 's/.*:"([^"]*)"/\1/')
  rt=$(echo "$resp" | grep -oE '"refresh_token":"[^"]*"' | head -1 | sed -E 's/.*:"([^"]*)"/\1/')
  [ -n "$at" ] || { echo "❌ refresh failed: $resp"; exit 1; }
  umask 177
  { echo "EOLYMP_TOKEN=$at"; echo "EOLYMP_REFRESH_TOKEN=${rt:-$EOLYMP_REFRESH_TOKEN}"; echo "EOLYMP_CLIENT_ID=$EOLYMP_CLIENT_ID"; echo "EOLYMP_TOKEN_ENDPOINT=$ep"; } > "$ENV_FILE"
  chmod 600 "$ENV_FILE"; echo "✓ Access token refreshed (no login needed)."
  ;;

space)
  key="${2:-${EOLYMP_SPACE:-}}"; [ -n "$key" ] || { echo "usage: get_token.sh space <space-key>"; exit 1; }
  echo "Resolving space '$key'…"
  sid=$(curl -s -A "Mozilla/5.0" "https://api.eolymp.com/spaces/__lookup/$key" | grep -oE '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
  [ -n "$sid" ] || { echo "❌ couldn't resolve space '$key'"; exit 1; }
  echo "Space id: $sid"
  read -p "Username (member of $key): " u; read -rsp "Password: " pwd; echo
  resp=$(curl -s -X POST "https://api.eolymp.com/spaces/$sid/oauth2/token" -H 'content-type: application/x-www-form-urlencoded' \
    --data-urlencode grant_type=password --data-urlencode "username=$u" --data-urlencode "password=$pwd" --data-urlencode scope=)
  at=$(echo "$resp" | grep -oE '"access_token":"[^"]*"' | head -1 | sed -E 's/.*:"([^"]*)"/\1/')
  [ -n "$at" ] || { echo "❌ failed: $resp"; exit 1; }
  umask 177; { echo "EOLYMP_TOKEN=$at"; echo "EOLYMP_SPACE=$key"; } > "$ENV_FILE"; chmod 600 "$ENV_FILE"
  echo; echo "✓ space token for '$key' saved to $ENV_FILE"; echo "export EOLYMP_TOKEN='$at'"
  ;;

*) echo "usage: get_token.sh [login [url] | refresh | space <key>]"; exit 1;;
esac
