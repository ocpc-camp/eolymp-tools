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

## combine_scoreboards.py

Merges two `out.dat` files produced by `download-scoreboard.py` into a
single combined scoreboard, renumbering team IDs so they don't collide.
Useful for showing a combined ranking across multiple days.

```
python combine_scoreboards.py day1.dat day2.dat > combined.dat
```
