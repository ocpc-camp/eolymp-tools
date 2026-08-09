import json
import ssl
from urllib import request
from time import sleep
import os
import re
import shutil
import subprocess
import traceback
import datetime
import requests
# import win32api
from dotenv import load_dotenv
from eolymp.core import HttpClient
from eolymp.wellknown import ExpressionEnum
from eolymp.printer import PrinterServiceClient, printer_service_pb2, printer_job_pb2
from eolymp.universe.space_service_http import SpaceServiceClient
from eolymp.universe import space_service_pb2
from eolymp.community.member_service_http import MemberServiceClient
from eolymp.community import member_service_pb2, member_pb2

load_dotenv()

# When this script is shipped as a self-contained "USB bundle" by the
# build-printer-client GitHub Actions workflow, Ghostscript and gsprint
# live next to the script in vendor/. Use those as defaults so the
# operator only has to fill in the Eolymp credentials in .env.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _bundled(*parts):
    path = os.path.join(SCRIPT_DIR, "vendor", *parts)
    return path if os.path.exists(path) else None


GHOSTSCRIPT_PATH = os.getenv("GHOSTSCRIPT_PATH") \
    or _bundled("ghostscript", "bin", "gswin64.exe") \
    or _bundled("ghostscript", "bin", "gswin32.exe")
GSPRINT_PATH = os.getenv("GSPRINT_PATH") or _bundled("gsprint", "gsprint.exe")
PHYSICAL_PRINTER_ID = os.getenv("PHYSICAL_PRINTER_ID")
PHYSICAL_PRINTER_NAME = os.getenv("PHYSICAL_PRINTER_NAME")
EOLYMP_TOKEN = os.getenv("EOLYMP_TOKEN")
EOLYMP_SPACE = os.getenv("EOLYMP_SPACE")
EOLYMP_PRINTER_ID = os.getenv("EOLYMP_PRINTER_ID")
MANUAL_PRINT_MODE = os.getenv("MANUAL_PRINT_MODE", "false").lower() in ("1", "true", "yes")
MANUAL_PRINT_DIR = os.path.expanduser(
    os.getenv("MANUAL_PRINT_DIR", "~/Desktop/OCPC Print Requests")
)
MANUAL_PRINT_OPEN = os.getenv("MANUAL_PRINT_OPEN", "true").lower() in ("1", "true", "yes")
# Auto-print (non-manual) confirmation: after `lp`, wait this long for the job
# to actually drain. If it holds for authentication / the printer is
# unreachable, we cancel it and fall back to the manual handoff for that job.
AUTO_CONFIRM_TIMEOUT = int(os.getenv("AUTO_CONFIRM_TIMEOUT", "20"))
AUTO_CONFIRM_POLL = int(os.getenv("AUTO_CONFIRM_POLL", "2"))
# Paper size passed to `lp` (-o media=...). Campus secure-release queues can
# silently drop jobs whose media doesn't match; `lp` otherwise defaults to the
# PPD's size (often US Letter) while the GUI sends the regional default. CityUHK
# is A4. Empty = don't set media (use the queue/PPD default).
PRINT_MEDIA = os.getenv("PRINT_MEDIA", "A4").strip()
# Alert on every new print job: desktop tray + an attention sound. The helper
# still has to release each batch at the printer with their ID card / Mobile ID,
# so the point of the alert is to summon them.
DESKTOP_NOTIFY = os.getenv("DESKTOP_NOTIFY", "true").lower() in ("1", "true", "yes")
# macOS system sound name (see /System/Library/Sounds), repeated a few times so
# it carries across the room. Empty = silent.
NOTIFY_SOUND = os.getenv("NOTIFY_SOUND", "Sosumi")
NOTIFY_SOUND_REPEAT = int(os.getenv("NOTIFY_SOUND_REPEAT", "3"))

client = HttpClient(token=EOLYMP_TOKEN)
space_service = SpaceServiceClient(client)

print(f"[DEBUG] Connecting to space: {EOLYMP_SPACE}")
lookup = space_service.LookupSpace(space_service_pb2.LookupSpaceInput(key=EOLYMP_SPACE))
print(f"[DEBUG] Space URL: {lookup.space.url}")
print(f"[DEBUG] Printer ID: {EOLYMP_PRINTER_ID}")
print(f"[DEBUG] Physical Printer ID: {PHYSICAL_PRINTER_ID}")
print(f"[DEBUG] Physical Printer Name: {PHYSICAL_PRINTER_NAME}")
if MANUAL_PRINT_MODE:
    print(f"[INFO] Manual print mode enabled: saving requests to {MANUAL_PRINT_DIR}")
    print("[INFO] Jobs will NOT be sent to a printer")

printer_service = PrinterServiceClient(client, lookup.space.url)
member_service = MemberServiceClient(client, lookup.space.url)

# uncomment this and set as context to request if ssl errors occur
ctx = ssl.create_default_context() # there is something wrong with the python installation here....
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

room_map = {}  # member_id -> room_number
last_room_map_refresh = datetime.datetime.utcfromtimestamp(0)

def refresh_room_map():
    """Fetch all members and build a map of member_id -> room number from Eolymp attributes."""
    global room_map, last_room_map_refresh
    
    print("[DEBUG] Refreshing room map from Eolymp...")
    room_map = {}
    offset = 0
    
    while True:
        # Fetch members in batches with attributes included
        page = member_service.ListMembers(member_service_pb2.ListMembersInput(
            offset=offset,
            size=100,
            extra=[member_pb2.Member.Extra.ATTRIBUTES]
        ))
        
        print(f"[DEBUG] Fetched batch: offset={offset}, count={len(page.items)}, total={page.total}")
        
        for member in page.items:
            # Look for the room attribute directly from the list response
            room_number = None
            for attr in member.attributes:
                if attr.attribute_key == "room" and attr.HasField('number'):
                    room_number = int(attr.number)
                    break
            
            if room_number is not None:
                room_map[member.id] = room_number
        
        offset += len(page.items)
        if offset >= page.total:
            break
    
    last_room_map_refresh = datetime.datetime.now()
    print(f"[DEBUG] Room map refreshed: {len(room_map)} members with room assignments")


def print_file(filename):
    """
    win32api.ShellExecute(0, 'open', GSPRINT_PATH,
                          f'-ghostscript "{GHOSTSCRIPT_PATH}" -printer "{PHYSICAL_PRINTER_NAME}" "{filename}"', '.', 0)
    """
    print(f"[DEBUG] Attempting to print file: {filename}")
    if not os.path.exists(filename):
        print(f"[ERROR] File does not exist: {filename}")
        return False
    import platform
    system = platform.system()
    try:
        if system == "Windows":
            try:
                import win32api
                cmd = f'-ghostscript "{GHOSTSCRIPT_PATH}" -printer "{PHYSICAL_PRINTER_NAME}" "{filename}"'
                print(f"[DEBUG] Using win32api.ShellExecute with gsprint: {GSPRINT_PATH} {cmd}")
                win32api.ShellExecute(0, 'open', GSPRINT_PATH, cmd, '.', 0)
                print(f"[DEBUG] win32api.ShellExecute call issued")
                return True
            except ImportError:
                print(f"[ERROR] win32api not available. Trying os.startfile as fallback.")
                try:
                    os.startfile(filename, "print")
                    print(f"[DEBUG] os.startfile print issued")
                    return True
                except Exception as e:
                    print(f"[ERROR] os.startfile print failed: {e}")
                    return False
        else:
            command = ["lp"]
            if PHYSICAL_PRINTER_NAME:
                command.extend(["-d", PHYSICAL_PRINTER_NAME])
            command.append(filename)
            result = subprocess.run(command, capture_output=True, text=True)
            print(f"[DEBUG] lp stdout: {result.stdout.strip()}")
            if result.returncode != 0:
                print(f"[ERROR] lp failed with code {result.returncode}: {result.stderr.strip()}")
                return False
            print(f"[DEBUG] lp succeeded for {filename}")
            return True
    except Exception as e:
        print(f"[ERROR] Exception while sending to printer: {e}")
        return False


def _job_id_from_lp(stdout):
    """Parse 'request id is <queue>-<n> (1 file(s))' from lp's output."""
    m = re.search(r"request id is (\S+)", stdout or "")
    return m.group(1) if m else None


def _job_still_queued(job_id):
    """True while the job is still pending/held/processing (not yet completed).

    `lpstat -o` takes a DESTINATION, not a job id, so query the queue and match
    the job id in the first column of each line.
    """
    result = subprocess.run(
        ["lpstat", "-W", "not-completed", "-o", PHYSICAL_PRINTER_NAME],
        capture_output=True, text=True,
    )
    return any(line.split()[:1] == [job_id] for line in result.stdout.splitlines())


def _job_held_for_auth():
    """True if the queue currently reports a held-for-authentication job."""
    result = subprocess.run(
        ["lpstat", "-l", "-o", PHYSICAL_PRINTER_NAME],
        capture_output=True, text=True,
    )
    text = (result.stdout + result.stderr).lower()
    return "held for authentication" in text or "cups-held-for-authentication" in text


def submit_and_confirm(filename):
    """`lp` the file, then confirm it actually drained off the queue.

    Returns (status, job_id) where status is one of 'printed', 'held', 'stuck',
    'error'. Anything other than 'printed' means the caller should fall back to
    the manual handoff. Uses only lp/lpstat, so it is identical on macOS/Linux.
    """
    command = ["lp"]
    if PHYSICAL_PRINTER_NAME:
        command.extend(["-d", PHYSICAL_PRINTER_NAME])
    if PRINT_MEDIA:
        command.extend(["-o", f"media={PRINT_MEDIA}"])
    command.append(filename)
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] lp failed with code {result.returncode}: {result.stderr.strip()}")
        return "error", None

    job_id = _job_id_from_lp(result.stdout)
    print(f"[DEBUG] lp submitted job {job_id}")
    if not job_id:
        return "printed", None  # can't track it; assume it went through

    for _ in range(max(1, AUTO_CONFIRM_TIMEOUT // max(1, AUTO_CONFIRM_POLL))):
        if not _job_still_queued(job_id):
            return "printed", job_id
        if _job_held_for_auth():
            return "held", job_id
        sleep(AUTO_CONFIRM_POLL)
    return "stuck", job_id


def validate_pdf(filename):
    """Perform a quick integrity check before handing a PDF to a volunteer."""
    try:
        with open(filename, "rb") as file:
            if file.read(5) != b"%PDF-":
                print(f"[ERROR] Downloaded file is not a PDF: {filename}")
                return False

        pdfinfo = shutil.which("pdfinfo")
        if pdfinfo:
            result = subprocess.run(
                [pdfinfo, filename], capture_output=True, text=True
            )
            if result.returncode != 0:
                print(f"[ERROR] Invalid PDF {filename}: {result.stderr.strip()}")
                return False
        return True
    except Exception as error:
        print(f"[ERROR] Could not validate PDF {filename}: {error}")
        return False


def desktop_notification(title, message):
    """Post to the OS notification tray (macOS Notification Center / Linux)."""
    import platform
    try:
        if platform.system() == "Darwin":
            subprocess.run(
                ["osascript",
                 "-e", "on run argv",
                 "-e", 'display notification (item 1 of argv) with title (item 2 of argv)',
                 "-e", "end run",
                 "--", message, title],
                capture_output=True, text=True,
            )
        elif shutil.which("notify-send"):
            subprocess.run(["notify-send", title, message], capture_output=True, text=True)
    except Exception as error:
        print(f"[WARN] desktop notification failed: {error}")


def play_alert_sound():
    """Play an attention sound (repeated) so a helper across the room notices."""
    if not NOTIFY_SOUND or not NOTIFY_SOUND.isalnum():
        return
    import platform
    try:
        if platform.system() == "Darwin":
            path = f"/System/Library/Sounds/{NOTIFY_SOUND}.aiff"
            subprocess.Popen(
                ["/bin/sh", "-c",
                 f'for i in $(seq {int(NOTIFY_SOUND_REPEAT)}); do afplay "{path}"; done'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            player = shutil.which("paplay") or shutil.which("aplay")
            if player:
                subprocess.Popen(
                    [player, "/usr/share/sounds/alsa/Front_Center.wav"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
    except Exception as error:
        print(f"[WARN] alert sound failed: {error}")


notified_jobs = set()


def announce_new_job(job):
    """Alert helpers once per job (both print modes). They still release the
    batch at the printer with their ID card / Mobile ID QR."""
    if job.id in notified_jobs:
        return
    notified_jobs.add(job.id)
    room = room_map.get(job.member_id)
    where = f" (room {room})" if room else ""
    message = f"New OCPC print request: job {job.id}{where}"
    if DESKTOP_NOTIFY:
        desktop_notification("OCPC print request", message)
    play_alert_sound()


def notify_manual_print(filename):
    """Alert the logged-in macOS user and open the request in Preview."""
    display_name = os.path.basename(filename)
    message = f"New Eolymp print request saved as {display_name}. Print it manually from Preview."

    try:
        notification = subprocess.run(
            [
                "osascript",
                "-e", "on run argv",
                "-e", 'display notification (item 1 of argv) with title "OCPC print request" sound name "Glass"',
                "-e", "end run",
                "--", message,
            ],
            capture_output=True,
            text=True,
        )
        if notification.returncode != 0:
            print(f"[WARN] macOS notification failed: {notification.stderr.strip()}")

        if MANUAL_PRINT_OPEN:
            subprocess.Popen(
                ["open", "-a", "Preview", filename],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return True
    except Exception as error:
        print(f"[ERROR] Could not notify volunteer: {error}")
        return False

def load_pending_jobs():
    jobs = {}
    offset = 0

    expr = ExpressionEnum(value="PENDING")
    setattr(expr, 'is', ExpressionEnum.EQUAL)

    print(f"[DEBUG] Fetching pending jobs for printer_id={EOLYMP_PRINTER_ID}")
    
    while True:
        # TODO: this is somewhat problematic - another script may mark something as complete
        # however, this should be "eventually consistent"
        page = printer_service.ListPrinterJobs(printer_service_pb2.ListPrinterJobsInput(
            printer_id = EOLYMP_PRINTER_ID,
            offset = offset,
            size = 10,
            filters = printer_service_pb2.ListPrinterJobsInput.Filter(
                status = [expr]
            )
        ))

        print(f"[DEBUG] Jobs batch: offset={offset}, count={len(page.items)}, total={page.total}")
        
        for job in page.items:
            print(f"[DEBUG]   Job: id={job.id}, member_id={job.member_id}, status={job.status}")
            jobs[job.id] = job

        offset += len(page.items)
        if offset >= page.total:
            break

    print(f"[DEBUG] Total pending jobs found: {len(jobs)}")
    return jobs


def should_process_job(job):
    """Check if this printer should process the job based on member's room assignment."""
    if job.member_id in room_map:
        member_room = str(room_map[job.member_id])
        printer_room = str(PHYSICAL_PRINTER_ID)
        should_process = member_room == printer_room
        print(f"[DEBUG] Job {job.id}: member_id={job.member_id}, member_room={member_room}, printer_room={printer_room}, process={should_process}")
        return should_process
    else:
        # Default: if no room assignment, route to printer 1
        should_process = PHYSICAL_PRINTER_ID == "1"
        print(f"[DEBUG] Job {job.id}: member_id={job.member_id} NOT in room_map, defaulting to printer 1, process={should_process}")
        return should_process


def process_queue():
    if last_room_map_refresh < datetime.datetime.now() - datetime.timedelta(minutes=1):
        refresh_room_map()

    print(f"[DEBUG] Loading jobs from queue (room_map size={len(room_map)})")
    jobs = load_pending_jobs()
    
    if len(jobs) == 0:
        print("[DEBUG] No pending jobs in queue")
        return
        
    for job_id in jobs:
        job = jobs[job_id]
        if not should_process_job(job):
            print(f"[DEBUG] Skipping job {job.id} (not for this printer)")
            continue

        print(f"[DEBUG] Processing job: {job.id}")
        print(f"[DEBUG]   Document URL: {job.document_url}")
        announce_new_job(job)
        url = job.document_url
        if MANUAL_PRINT_MODE:
            os.makedirs(MANUAL_PRINT_DIR, exist_ok=True)
            abs_filename = os.path.join(
                MANUAL_PRINT_DIR, f"OCPC-print-{job.id}.pdf"
            )
        else:
            abs_filename = os.path.abspath(str(job.id) + ".pdf")

        req = request.Request(url)
        try:
            with request.urlopen(req) as response:
                print(f"[DEBUG]   Downloading to: {abs_filename}")
                with open(abs_filename, "wb") as file:
                    shutil.copyfileobj(response, file)
        except Exception as e:
            print(f"[ERROR]   Failed to download file for job {job.id}: {e}")
            continue

        if not os.path.exists(abs_filename) or not validate_pdf(abs_filename):
            print(f"[ERROR]   PDF handoff failed for job {job.id}")
            continue

        if MANUAL_PRINT_MODE:
            success = notify_manual_print(abs_filename)
            if success:
                print(f"[INFO]   Saved job {job.id} for manual printing: {abs_filename}")
            else:
                print(f"[ERROR]   Failed to notify volunteer for job {job.id}")
        else:
            print(f"[DEBUG]   Sending to printer: {PHYSICAL_PRINTER_NAME}, file: {abs_filename}")
            status, phys_job = submit_and_confirm(abs_filename)
            if status == "printed":
                success = True
                print(f"[DEBUG]   Printed job {job.id}")
            else:
                # Auto-print did not go through (held for auth / unreachable /
                # stuck). Cancel the stalled job and fall back to the manual
                # Preview handoff so the page still gets printed by a volunteer.
                print(f"[WARN]   Auto-print {status} for job {job.id}; "
                      f"falling back to manual handoff")
                if phys_job:
                    subprocess.run(["cancel", phys_job], capture_output=True, text=True)
                manual_path = os.path.join(MANUAL_PRINT_DIR, f"OCPC-print-{job.id}.pdf")
                try:
                    os.makedirs(MANUAL_PRINT_DIR, exist_ok=True)
                    if os.path.abspath(manual_path) != os.path.abspath(abs_filename):
                        shutil.copyfile(abs_filename, manual_path)
                    success = notify_manual_print(manual_path)
                except Exception as error:
                    print(f"[ERROR]   Manual fallback failed for job {job.id}: {error}")
                    success = False

        if not success:
            continue

        job.status = printer_job_pb2.Job.COMPLETE
        printer_service.UpdatePrinterJob(printer_service_pb2.UpdatePrinterJobInput(
            printer_id = EOLYMP_PRINTER_ID,
            job_id = job.id,
            job = job
        ))

        if MANUAL_PRINT_MODE:
            print(f"[INFO] Marked job {job.id} as COMPLETE after manual handoff")
        else:
            print(f"[DEBUG] Marked job {job.id} as COMPLETE")


print("[DEBUG] Starting printer client...")
print(f"[DEBUG] Token: {EOLYMP_TOKEN[:10] if EOLYMP_TOKEN else 'None'}...")

while True:
    try:
        process_queue()
    except Exception:
        print("[ERROR] Exception in process_queue:")
        print(traceback.format_exc())
 
    sleep(1)
 
