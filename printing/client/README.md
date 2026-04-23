# Eolymp printer client

A small Python daemon to be run on a "teacher's computer" connected to a
physical printer in a classroom. It polls the print job queue of an
Eolymp printer, downloads each pending job's PDF, and sends it to the
local printer (using `gsprint` on Windows, `lp` on Linux/macOS).

## How printing works in Eolymp

Eolymp has a single logical "printer" per space, with a queue of pending
jobs. Each contestant's "Print" button in the IDE creates a job there.
There is no concept of multiple physical printers in Eolymp itself; you
have to fan out the queue yourself.

This client supports per-room routing: each Eolymp member can have a
numeric `room` attribute (added in the Members → Profile section of the
admin UI). One instance of the client runs per physical printer, with
`PHYSICAL_PRINTER_ID` set to the room number it serves. Jobs without a
room assignment are routed to the printer with `PHYSICAL_PRINTER_ID=1`.

If you don't want per-room routing, just set every member's `room` to
the same number (or skip the attribute entirely and run a single client
with `PHYSICAL_PRINTER_ID=1`).

## Setup

### 1. Configure the Eolymp side

In the Eolymp admin console:

- under "Printers", add a printer and remember its ID (the random
  string in the URL); that's your `EOLYMP_PRINTER_ID`;
- in each contest's settings, choose this printer so that the "Print"
  icon appears for participants;
- (optional) under Members → Profile, add a numeric attribute with key
  `room`, then set it for each member.

### 2. Install Ghostscript and gsprint (Windows only)

`gsprint` is a tiny wrapper around Ghostscript that prints PDFs on
Windows. Download Ghostscript from https://www.ghostscript.com/ and
gsprint from http://www.ghostgum.com.au/software/gsview.htm — note the
absolute paths to `gswin32.exe` and `gsprint.exe`.

On Linux/macOS the client uses `lp` instead, so no setup is needed
beyond having CUPS configured for your printer.

### 3. Install Python dependencies

```
python -m pip install -U eolymp python-dotenv requests
```

On Windows, also install `pywin32` (for `win32api.ShellExecute`):

```
python -m pip install pywin32
```

### 4. Configure `.env`

Copy `.env.sample` to `.env` and fill in the values. See `.env.sample`
for the description of each variable.

### 5. Run

```
python printer.py
```

This is a long-running daemon; it polls the queue every second.

## test_room_lookup.py

A small helper that fetches all members of the space and prints out the
room distribution. Use it to sanity-check that the `room` attribute is
correctly set before the contest starts.
