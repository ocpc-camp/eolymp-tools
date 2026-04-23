# Eolymp member import

Bulk-creates (or updates) member accounts in an Eolymp space from a CSV
of teams.

## Input format

`members_reshaped.csv` should have at least these columns:

| Column        | Meaning                                                     |
|---------------|-------------------------------------------------------------|
| `name`        | Display name shown in scoreboards                           |
| `username`    | Login (nickname). Generated if missing.                     |
| `password`    | Login password. Generated if missing.                       |
| `team_short`  | Team short name (without org or members)                    |
| `members`     | Comma-separated list of team members' names                 |
| `university`  | Organization name                                           |
| `onsite`      | Compared to `ONSITE_VALUE` env var; remote teams get room 0 |
| `room`        | Numeric room ID; ignored for remote teams                   |

Producing this CSV from a registration form export is event-specific and
out of scope for this script.

## Configuration

Environment variables:

- `EOLYMP_TOKEN` — Eolymp access token
- `EOLYMP_SPACE` — short name of the Eolymp space
- `USERNAME_TEMPLATE` (optional, default `team{:03}`) — Python format
  string used to allocate usernames for rows that don't have one. The
  `{}` is filled with a sequential integer.
- `ONSITE_VALUE` (optional, default `onsite`) — value of the `onsite`
  column meaning the team is on-site. Anything else is treated as
  remote (and assigned room 0).

## Run

```
python import-members.py
```

Members already present in Eolymp (matched by nickname) are updated;
new ones are created. The full row plus the assigned `Eolymp ID` is
written to `credentials.csv`.

## delete-members.py

Helper to bulk-delete every member of a space. Asks for confirmation
before doing anything.
