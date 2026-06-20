#!/usr/bin/env python3
"""Batch-extract ICPC/PCMS ghost (.dat) files for every contest in one or more
Eolymp camp spaces.

This is a batch wrapper around the single-contest logic in
``download-scoreboard.py``: it enumerates spaces with ``ListSpaces``, lists each
space's contests, keeps only the real per-day contests (those whose name carries
a ``Day N`` — this drops "Test contest"/"test copy" entries), and writes one
``.dat`` per contest into ``<out>/<space-key>/<name>.dat``.

Filename: ``day<N>[-sg]-<slug-of-title>.dat`` where the ``-sg`` marker is added
for "[SG]" satellite days so they don't collide with the main-track day of the
same number.

Auth: needs an org/admin ``EOLYMP_TOKEN`` (submission reads are not available to
space-/printer-scoped tokens). Get one with ``scripts/get_token.sh``.

Usage:
    EOLYMP_TOKEN=... pypy3 extract-ghosts.py --out ~/ocpc/ghosts
    ... --spaces ocpc2026w,osijek2025w     # restrict to specific space keys
    ... --dry-run                          # list planned files, fetch nothing
    ... --force                            # re-extract even if the file exists
    ... --window 18000                     # in-contest cutoff seconds (default 5h)
"""

import argparse
import os
import re
import socket
import sys

# Force IPv4 to avoid IPv6 connectivity issues that cause hanging (same as
# download-scoreboard.py).
_old_getaddrinfo = socket.getaddrinfo
def _getaddrinfo_ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return _old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _getaddrinfo_ipv4_only

from eolymp.core.http_client import HttpClient
from eolymp.universe.space_service_http import SpaceServiceClient
from eolymp.judge.contest_service_http import ContestServiceClient
from eolymp.judge.participant_service_http import ParticipantServiceClient
from eolymp.judge.problem_service_http import ProblemServiceClient
from eolymp.judge.submission_service_http import SubmissionServiceClient
import eolymp.universe.space_service_pb2 as space_pb
import eolymp.judge.contest_service_pb2 as contest_pb
import eolymp.judge.participant_service_pb2 as participant_pb
import eolymp.judge.problem_service_pb2 as problem_pb
import eolymp.judge.submission_service_pb2 as submission_pb
from eolymp.atlas.submission_pb2 import Submission as ASubmission

VERDICT_MAP = {
    ASubmission.Verdict.ACCEPTED: "OK",
    ASubmission.Verdict.CPU_EXHAUSTED: "TL",
    ASubmission.Verdict.MEMORY_OVERFLOW: "ML",
    ASubmission.Verdict.RUNTIME_ERROR: "RT",
    ASubmission.Verdict.NO_VERDICT: "CE",
    ASubmission.Verdict.TIME_LIMIT_EXCEEDED: "TL",
    ASubmission.Verdict.WRONG_ANSWER: "WA",
}

DAY_RE = re.compile(r"day\s*0*(\d+)", re.IGNORECASE)


def slugify(text):
    """Lowercase ASCII slug: non-alphanumeric runs become single dashes."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def contest_filename(name):
    """Derive ``day<N>[-sg]-<slug>.dat`` from a contest name, or None if the
    name has no ``Day N`` (i.e. it is a test/setup contest we should skip)."""
    m = DAY_RE.search(name)
    if not m:
        return None
    day = int(m.group(1))
    is_sg = "[sg]" in name.lower()
    # Title = text after the first colon if present, else the whole name with
    # the "[SG]"/"Day N" bits removed.
    title = name.split(":", 1)[1] if ":" in name else name
    slug = slugify(title)
    stem = "day{}".format(day) + ("-sg" if is_sg else "")
    return "{}-{}.dat".format(stem, slug) if slug else "{}.dat".format(stem)


def extract_contest(client, space_url, contest, window):
    """Build the .dat content for one contest. Returns (text, n_teams, n_subs)."""
    contest_id = contest.id
    base_url = "{}/contests/{}".format(space_url, contest_id)
    participant_service = ParticipantServiceClient(client, base_url)
    problem_service = ProblemServiceClient(client, base_url)
    submission_service = SubmissionServiceClient(client, base_url)

    parts = participant_service.ListParticipants(
        participant_pb.ListParticipantsInput(contest_id=contest_id, offset=0, size=1000)
    )
    start_time = {p.id: p.started_at.seconds for p in parts.items}

    problems = problem_service.ListProblems(
        problem_pb.ListProblemsInput(offset=0, size=100)
    )
    letter = {p.id: chr(ord("A") + p.index - 1) for p in problems.items}

    # Collect in-contest submissions (team, problem-letter, seconds, verdict).
    collected = []
    offset = 0
    while True:
        subs = submission_service.ListSubmissions(
            submission_pb.ListSubmissionsInput(contest_id=contest_id, size=100, offset=offset)
        )
        if not subs.items:
            break
        offset += 100
        for sub in subs.items:
            started = start_time.get(sub.participant_id)
            if started is None:
                continue  # submission by a non-listed participant (admin/virtual)
            t = sub.submitted_at.seconds - started
            if t < 0 or t > window:
                continue
            if sub.verdict not in VERDICT_MAP:
                print("    ! unknown verdict {} on submission {}".format(sub.verdict, sub.id))
                continue
            collected.append((sub.participant_id, letter[sub.problem_id], t, VERDICT_MAP[sub.verdict]))

    collected.sort(key=lambda s: s[2])

    # Per (team, problem) attempt numbering, in time order.
    attempts = {}
    numbered = []
    for participant_id, plet, t, verdict in collected:
        key = (participant_id, plet)
        attempts[key] = attempts.get(key, 0) + 1
        numbered.append((participant_id, plet, attempts[key], t, verdict))

    # Stable 1-based team ids in participant-list order.
    team_id = {p.id: i + 1 for i, p in enumerate(parts.items)}

    lines = []
    lines.append('@contest "{}"'.format(contest.name))
    lines.append("@contlen 300")
    lines.append("@problems {}".format(len(problems.items)))
    lines.append("@teams {}".format(len(parts.items)))
    lines.append("@submissions {}".format(len(numbered)))
    for p in problems.items:
        let = letter[p.id]
        lines.append("@p {0},{0},20,0".format(let))
    for p in parts.items:
        lines.append('@t {},0,1,"{}"'.format(team_id[p.id], p.display_name))
    for participant_id, plet, attempt, t, verdict in numbered:
        lines.append("@s {},{},{},{},{}".format(team_id[participant_id], plet, attempt, t, verdict))
    return "\n".join(lines) + "\n", len(parts.items), len(numbered)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="output root directory")
    ap.add_argument("--spaces", default="", help="comma-separated space keys (default: all ocpc*/osijek* camp spaces)")
    ap.add_argument("--window", type=int, default=18000, help="in-contest cutoff in seconds (default 18000 = 5h)")
    ap.add_argument("--dry-run", action="store_true", help="list planned files without fetching submissions")
    ap.add_argument("--force", action="store_true", help="re-extract even if the output file already exists")
    args = ap.parse_args()

    token = os.environ.get("EOLYMP_TOKEN")
    if not token:
        sys.exit("EOLYMP_TOKEN not set — run scripts/get_token.sh first.")

    out_root = os.path.expanduser(args.out)
    client = HttpClient(token=token)
    space_service = SpaceServiceClient(client)

    all_spaces = list(space_service.ListSpaces(space_pb.ListSpacesInput(offset=0, size=100)).items)
    if args.spaces:
        wanted = {k.strip() for k in args.spaces.split(",") if k.strip()}
        spaces = [s for s in all_spaces if s.key in wanted]
        missing = wanted - {s.key for s in spaces}
        if missing:
            print("warning: spaces not found / not visible: {}".format(", ".join(sorted(missing))))
    else:
        spaces = [s for s in all_spaces if s.key.startswith("ocpc") or s.key.startswith("osijek")]

    spaces.sort(key=lambda s: s.key)
    print("Spaces: {}".format(", ".join(s.key for s in spaces)))

    total_files = total_subs = failed = skipped_existing = 0
    for space in spaces:
        contest_service = ContestServiceClient(client, space.url)
        contests = list(contest_service.ListContests(contest_pb.ListContestsInput(offset=0, size=200)).items)
        real = [(c, contest_filename(c.name)) for c in contests]
        real = [(c, fn) for c, fn in real if fn]
        print("\n## {} ({}) — {} real contests".format(space.key, space.name, len(real)))
        space_dir = os.path.join(out_root, space.key)

        for contest, fname in sorted(real, key=lambda cf: cf[1]):
            dest = os.path.join(space_dir, fname)
            rel = os.path.join(space.key, fname)
            if args.dry_run:
                print("   would write {:55} <- {!r}".format(rel, contest.name))
                continue
            if os.path.exists(dest) and not args.force:
                print("   skip (exists) {}".format(rel))
                skipped_existing += 1
                continue
            try:
                text, n_teams, n_subs = extract_contest(client, space.url, contest, args.window)
            except Exception as e:  # keep going; report at the end
                print("   FAIL {:50} {}: {}".format(rel, type(e).__name__, str(e)[:160]))
                failed += 1
                continue
            os.makedirs(space_dir, exist_ok=True)
            with open(dest, "w") as f:
                f.write(text)
            print("   wrote {:55} {:>4} teams {:>5} subs {:>6} B".format(rel, n_teams, n_subs, len(text.encode())))
            total_files += 1
            total_subs += n_subs

    print("\n{}: {} files, {} submissions{}{}".format(
        "Planned" if args.dry_run else "Done",
        total_files, total_subs,
        ", {} skipped (existing)".format(skipped_existing) if skipped_existing else "",
        ", {} FAILED".format(failed) if failed else "",
    ))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
