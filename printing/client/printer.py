import json
import ssl
from urllib import request
from time import sleep
import os
import shutil
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

client = HttpClient(token=EOLYMP_TOKEN)
space_service = SpaceServiceClient(client)

print(f"[DEBUG] Connecting to space: {EOLYMP_SPACE}")
lookup = space_service.LookupSpace(space_service_pb2.LookupSpaceInput(key=EOLYMP_SPACE))
print(f"[DEBUG] Space URL: {lookup.space.url}")
print(f"[DEBUG] Printer ID: {EOLYMP_PRINTER_ID}")
print(f"[DEBUG] Physical Printer ID: {PHYSICAL_PRINTER_ID}")
print(f"[DEBUG] Physical Printer Name: {PHYSICAL_PRINTER_NAME}")

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
            import subprocess
            result = subprocess.run(["lp", filename], capture_output=True, text=True)
            print(f"[DEBUG] lp stdout: {result.stdout.strip()}")
            if result.returncode != 0:
                print(f"[ERROR] lp failed with code {result.returncode}: {result.stderr.strip()}")
                return False
            print(f"[DEBUG] lp succeeded for {filename}")
            return True
    except Exception as e:
        print(f"[ERROR] Exception while sending to printer: {e}")
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
        url = job.document_url
        req = request.Request(url)
        try:
            with request.urlopen(req) as response:
                filename = str(job.id) + ".pdf"
                abs_filename = os.path.abspath(filename)
                print(f"[DEBUG]   Downloading to: {abs_filename}")
                with open(abs_filename, "wb") as file:
                    shutil.copyfileobj(response, file)
        except Exception as e:
            print(f"[ERROR]   Failed to download file for job {job.id}: {e}")
            continue

        # Extra debug: check file existence right before printing
        if not os.path.exists(abs_filename):
            print(f"[ERROR]   File does not exist right before printing: {abs_filename}")
            continue

        print(f"[DEBUG]   Sending to printer: {PHYSICAL_PRINTER_NAME}, file: {abs_filename}")
        success = print_file(abs_filename)
        if success:
            print(f"[DEBUG]   Printed job {job.id}")
        else:
            print(f"[ERROR]   Failed to print job {job.id}")
            # Optionally, do not mark as COMPLETE if failed
            continue

        job.status = printer_job_pb2.Job.COMPLETE
        printer_service.UpdatePrinterJob(printer_service_pb2.UpdatePrinterJobInput(
            printer_id = EOLYMP_PRINTER_ID,
            job_id = job.id,
            job = job
        ))

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
 
