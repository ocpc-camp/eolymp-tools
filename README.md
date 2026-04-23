# eolymp-tools

A small collection of scripts for running competitive programming
contests and training camps on top of [Eolymp](https://eolymp.com/).
Extracted from the internal tooling of [OCPC](https://ocpc.camp/), an
ICPC-oriented training camp held in various locations and run online,
but should be useful for anyone organizing contests on Eolymp.

## What's here

- [`discord/`](discord/) — pings a Discord channel whenever someone
  files a new question (helpdesk ticket) on Eolymp.
- [`download-scoreboard/`](download-scoreboard/) — downloads in-contest
  submissions from an Eolymp contest into the legacy ICPC `result.dat`
  scoreboard format, plus a helper to merge two such files.
- [`import-members/`](import-members/) — bulk-creates member accounts
  in an Eolymp space from a CSV (team name, members, organization,
  room, etc.) and emits a `credentials.csv` with login info.
- [`printing/client/`](printing/client/) — a daemon meant to run on a
  computer next to a printer in a contest hall: it polls the print
  queue of an Eolymp printer and dispatches each job, optionally
  routing by room based on a per-member `room` attribute in Eolymp.
- [`scripts/get_token.sh`](scripts/get_token.sh) — interactively obtain
  an Eolymp OAuth access token from a username/password.

Each subdirectory has its own README with the details.

## Eolymp API token

Most scripts read `EOLYMP_TOKEN` and `EOLYMP_SPACE` from the environment
(or from a local `.env` file via `python-dotenv`).

For long-running scripts (the Discord pinger, the printer client) you
should create an **access key** at https://developer.eolymp.com/ and use
that as `EOLYMP_TOKEN`. For one-shot scripts a regular OAuth token is
fine, and `scripts/get_token.sh` can fetch one for you.

The Eolymp Python SDK is unstable; if a script suddenly returns HTTP 400,
the first thing to try is `python -m pip install -U eolymp`.

## Installing dependencies

There is no `setup.py` / `pyproject.toml`; just install what each script
needs as you go:

```
python -m pip install -U eolymp python-dotenv requests
```

## License

[MIT](LICENSE).
