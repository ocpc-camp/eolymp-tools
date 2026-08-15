# Eolymp printer client

A small Python daemon to be run on a "teacher's computer" connected to a
physical printer in a classroom. It polls the print job queue of an
Eolymp printer, downloads each pending job's PDF, and sends it to the
local printer (using `gsprint` on Windows, `lp` on Linux/macOS).

Alternatively, set `MANUAL_PRINT_MODE=true` to save every requested PDF
to `MANUAL_PRINT_DIR` for a volunteer. On macOS the client displays a
notification with sound and opens the PDF in Preview. In this mode it
never invokes `gsprint` or `lp`; the Eolymp job is marked complete after
the PDF is saved and the volunteer is notified.

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

### Add another print laptop (macOS)

Everything below is in the repo; per machine you only add the venv, `.env`, and a
CUPS queue:

```sh
git clone https://github.com/ocpc-camp/eolymp-tools.git && cd eolymp-tools
python3 -m venv discord/.venv                      # the venv run_services.sh uses
discord/.venv/bin/pip install -U eolymp python-dotenv requests
cp printing/client/.env.sample printing/client/.env   # then edit it (below)
```

Then, outside the repo:

1. **Add the printer to CUPS** (System Settings → Printers, or `lpadmin`) and note
   the queue name. For a CityUHK follow-me printer the device is
   `smb://ccstung1.ad.cityu.edu.hk/csc_quota_queue`; authenticate it either by
   baking credentials into a dedicated queue or via `kinit` — see *Authenticated
   queues* below. (Paper size is already forced to A4 by `PRINT_MEDIA`.)
2. **Edit `printing/client/.env`**: `EOLYMP_TOKEN`, `EOLYMP_SPACE=ocpc`,
   `EOLYMP_PRINTER_ID`, `PHYSICAL_PRINTER_NAME=<your queue>`,
   `MANUAL_PRINT_MODE=false`, and `PHYSICAL_PRINTER_ID=<room #>` for per-room
   routing (jobs for members without a `room` go to `PHYSICAL_PRINTER_ID=1`).
3. **Run the printer only** (a second pinger would double-post to Discord):

   ```sh
   OCPC_SERVICES=printer ./run_services.sh
   ```

Run it from Terminal.app so notification banners work, and keep the laptop
plugged in with the lid open.

### Quick start (Windows): pre-built USB bundle

The simplest way to run this on a Windows machine in a contest hall is
to grab the pre-built bundle from the
[`latest` release](https://github.com/ocpc-camp/eolymp-tools/releases/tag/latest):

1. Download `printer-client-windows.zip` and extract it onto a USB stick
   or directly onto the teacher's computer. No Python install needed —
   the bundle ships its own embeddable Python with all dependencies
   pre-installed.
2. Copy `.env.sample` to `.env` and fill in just the Eolymp credentials
   and the local printer name. Ghostscript and gsprint are bundled, so
   leave `GHOSTSCRIPT_PATH` and `GSPRINT_PATH` empty.
3. Double-click `run.bat`.

The bundle is rebuilt automatically by GitHub Actions on every push to
`main`, so the rolling release always reflects the current code.

### Manual setup

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

#### Authenticated queues (e.g. CityUHK SMB) and the auto→manual fallback

Some campus printers are SMB/AD queues that require a login, so a bare `lp`
job lands in **"Hold for Authentication"** and never prints. Two ways to cope:

- **Bake the credential into a dedicated queue** so `lp` authenticates silently.
  For an SMB queue that means a device URI of the form
  `smb://USER:PASSWORD@server/share` (URL-encode the password). Point
  `PHYSICAL_PRINTER_NAME` at that queue and set `MANUAL_PRINT_MODE=false`.
  Simple and zero-maintenance, but stores the password in CUPS `printers.conf`
  and breaks if the account password changes. **To create or update that queue
  from one place**, put the login/password in `print_creds.env` (copy from
  `print_creds.env.sample`; gitignored). `run_services.sh` then syncs the queue
  to that file automatically on every start — so after changing credentials you
  just re-run `./run_services.sh` (or run `apply_print_creds.sh` directly). The
  SMB password can only live in the CUPS queue, not be read per-job by `lp`,
  which is why this sync step exists.
- **Use the original `negotiate` (Kerberos) queue with a ticket** — no password
  stored anywhere. Leave `PHYSICAL_PRINTER_NAME` on the original queue and get a
  ticket with [`kinit_print.sh`](kinit_print.sh) (it reuses the password already
  in the login keychain). Then `lp` authenticates via GSSAPI just like the GUI.
  The catch: the ticket lasts ~10 h, so refresh it (re-run the helper, or let
  `run_services.sh` do it: `OCPC_KINIT=1 ./run_services.sh`). Needs the KDCs
  reachable (i.e. on the campus network).
- **Fallback safety net (always on in auto mode):** after `lp`, the client waits
  up to `AUTO_CONFIRM_TIMEOUT` seconds for the job to drain. If it holds for
  authentication or the printer is unreachable, that job is cancelled and
  handed off to the manual Preview flow — so a page prints one way or another.

#### Notifications and secure-release printers

Every new job raises a desktop notification (`DESKTOP_NOTIFY`, macOS
Notification Center / Linux `notify-send`) and plays an attention sound
(`NOTIFY_SOUND`, a macOS system sound repeated `NOTIFY_SOUND_REPEAT` times).

This matters on **secure-release / follow-me** printers (e.g. CityUHK quota
printing): the client only *submits* the job to the central queue — a person
still has to walk to a release station and tap their **ID card** or scan their
**Mobile ID QR** to actually print. One tap releases **all** of that account's
queued jobs, so the practical workflow is: let jobs accumulate, and the
notification/sound tells a helper when to go release the batch. Jobs left
unreleased are purged (overnight, at CityUHK). There is no per-job auto-release
for the quota queue; a badge-free setup would need a dedicated/direct printer
arranged with the campus IT/print service.

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
