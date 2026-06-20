# Eolymp scoreboard / submission download

## download-scoreboard.py

Downloads in-contest submissions from one Eolymp contest into a
`out.dat` file in the legacy ICPC/PCMS scoreboard format used by various
scoreboard renderers.

Each output line is one of:

- `@contest "..."`, `@contlen N`, `@problems N`, `@teams N`,
  `@submissions N` — header
- `@p X,X,20,0` — one per problem (letter, letter, penalty, unknown)
- `@t id,0,1,"name"` — one per team
- `@s team,problem,attempt,seconds,verdict` — one per submission

Configuration via environment variables:

- `EOLYMP_TOKEN`, `EOLYMP_SPACE` — as elsewhere
- `EOLYMP_CONTEST` — ID of the Eolymp contest

The contest length is hard-coded to 18 000 seconds (5 hours) in the
filter and to 300 in the header (the legacy format uses minutes there);
edit at the top of the file if you need a different length.

## extract-ghosts.py

Batch wrapper around `download-scoreboard.py`. Enumerates one or more Eolymp
*spaces* (`ListSpaces` → `ListContests`), keeps the real per-day contests
(those whose name carries a `Day N`, which drops "Test contest" / "test copy"
entries), and writes one `.dat` per contest to
`<out>/<space-key>/day<N>[-sg]-<slug>.dat`. The `-sg` marker is added for
`[SG]` satellite days so they don't collide with the main-track day of the
same number.

Needs an org/admin `EOLYMP_TOKEN` (submission reads are not available to
space-/printer-scoped tokens). It is resumable — existing files are skipped
unless `--force`.

```
EOLYMP_TOKEN=... pypy3 extract-ghosts.py --out ~/ocpc/ghosts
  --spaces ocpc2026w,osijek2025w   # restrict to specific space keys
  --dry-run                        # list planned files, fetch nothing
  --force                          # re-extract even if the file exists
  --window 18000                   # in-contest cutoff seconds (default 5h)
```

With no `--spaces`, it defaults to every `ocpc*` / `osijek*` camp space the
token can see.

## combine_scoreboards.py

Merges two `out.dat` files produced by `download-scoreboard.py` into a
single combined scoreboard, renumbering team IDs so they don't collide.
Useful for showing a combined ranking across multiple days.

```
python combine_scoreboards.py day1.dat day2.dat > combined.dat
```
