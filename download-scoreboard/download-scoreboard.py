import csv
import os

import eolymp.universe.space_service_pb2 as space_service_pb2
import eolymp.judge.participant_service_pb2 as participant_service_pb2
import eolymp.judge.problem_service_pb2 as problem_service_pb2
import eolymp.judge.submission_service_pb2 as submission_service_pb2
import eolymp.judge.contest_service_pb2 as contest_service_pb2
from eolymp.atlas.submission_pb2 import Submission as ASubmission
from eolymp.judge.submission_pb2 import Submission as ESubmission
from eolymp.core.http_client import HttpClient
from eolymp.universe.space_service_http import SpaceServiceClient
from eolymp.judge.contest_service_http import ContestServiceClient
from eolymp.judge.participant_service_http import ParticipantServiceClient
from eolymp.judge.problem_service_http import ProblemServiceClient
from eolymp.judge.submission_service_http import SubmissionServiceClient

EOLYMP_TOKEN = os.getenv("EOLYMP_TOKEN")
EOLYMP_SPACE = os.getenv("EOLYMP_SPACE")
EOLYMP_CONTEST = os.getenv("EOLYMP_CONTEST")

# Force IPv4 to avoid IPv6 connectivity issues that cause hanging
import socket
old_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = getaddrinfo_ipv4_only

print("Initializing client...")
client = HttpClient(token=EOLYMP_TOKEN)
space_service = SpaceServiceClient(client)
print("Looking up space...")
lookup = space_service.LookupSpace(space_service_pb2.LookupSpaceInput(key=EOLYMP_SPACE))
print(f"Space found: {lookup.space.url}")

contest_id = EOLYMP_CONTEST

# Contest service uses space URL (it adds /contests/{id} itself)
contest_service = ContestServiceClient(client, lookup.space.url)

# Other services need the full contest URL path
contest_base_url = f"{lookup.space.url}/contests/{contest_id}"
print(f"Contest base URL: {contest_base_url}")
participant_service = ParticipantServiceClient(client, contest_base_url)
problem_service = ProblemServiceClient(client, contest_base_url)
submission_service = SubmissionServiceClient(client, contest_base_url)

class Submission:
    def __init__ (self, participant_id, problem_id, time, verdict):
        self.participant_id = participant_id
        self.problem_id = problem_id
        self.time = time
        self.verdict = verdict

econtest = contest_service.DescribeContest(contest_service_pb2.DescribeContestInput(
    contest_id = contest_id
)).contest

print(econtest.name)
print("Fetching participants...")

parts = participant_service.ListParticipants(participant_service_pb2.ListParticipantsInput(
    contest_id = contest_id,
    offset = 0,
    size = 1000
))

start_time_map = {}
for part in parts.items:
    print(part.started_at.seconds)
    start_time_map[part.id] = part.started_at.seconds

print("Fetching problems...")
problems = problem_service.ListProblems(problem_service_pb2.ListProblemsInput(
    offset = 0,
    size = 100
))

problem_map = {}
for prob in problems.items:
    problem_map[prob.id] = chr(ord('A') + prob.index - 1)

print(problem_map)

"""
print("accepted", ESubmission.Group.ACCEPTED)
print("blocked", ESubmission.Group.BLOCKED)
print("cpu_exhausted",ESubmission.Group.CPU_EXHAUSTED)
print("memory_overflow", ESubmission.Group.MEMORY_OVERFLOW)
print("pending", ESubmission.Group.PENDING)
print("runtime_error", ESubmission.Group.RUNTIME_ERROR)
print("skipped", ESubmission.Group.SKIPPED)
print("testing", ESubmission.Group.TESTING)
print("timeout", ESubmission.Group.TIMEOUT)
print("unknown", ESubmission.Group.UNKNOWN)
print("verification_error", ESubmission.Group.VERIFICATION_ERROR)
print("wrong_answer", ESubmission.Group.WRONG_ANSWER)
"""

    
verdict_map = {ASubmission.Verdict.ACCEPTED: "OK",
               ASubmission.Verdict.CPU_EXHAUSTED: "TL",
               ASubmission.Verdict.MEMORY_OVERFLOW: "ML",
               ASubmission.Verdict.RUNTIME_ERROR: "RT",
               ASubmission.Verdict.NO_VERDICT: "CE",
               ASubmission.Verdict.TIME_LIMIT_EXCEEDED: "TL",
               ASubmission.Verdict.WRONG_ANSWER: "WA"}
               
               
#               {4: "OK", 5: "TL", 8: "WA", 7: "ML", 9: "RT", 11: "CE"}

downloaded_subs = []

print("====")
print("Fetching submissions...")

offset = 0
while True:
    subs = submission_service.ListSubmissions(submission_service_pb2.ListSubmissionsInput(
        contest_id = contest_id,
        size = 100,
        offset = offset
    ))
    offset += 100

    if len(subs.items) == 0:
        break
    
    for sub in subs.items:
        time = sub.submitted_at.seconds - start_time_map[sub.participant_id]
        if time > 18000:
            continue

        verdict = sub.verdict
        
        if verdict not in verdict_map:
            print("error, unknown status:", verdict, "for submission", sub.id)
            continue
        
        downloaded_subs.append(Submission(sub.participant_id,
                                          problem_map[sub.problem_id],
                                          time,
                                          verdict_map[verdict]))

print(f"Downloaded {len(downloaded_subs)} submissions")
downloaded_subs.sort(key = lambda x: x.time)

attempt_count = {}
for i, sub in enumerate(downloaded_subs):
    key = (sub.participant_id, sub.problem_id)
    if not key in attempt_count:
        attempt_count[key] = 0
    attempt_count[key] += 1

    downloaded_subs[i].attempt_id = attempt_count[key]

out = open("out.dat", "w")

out.write(f"@contest \"{econtest.name}\"\n")
out.write("@contlen 300\n")

out.write("@problems ")
out.write(str(len(problems.items)))
out.write("\n")

out.write("@teams ")
out.write(str(len(parts.items)))
out.write("\n")

out.write("@submissions ")
out.write(str(len(downloaded_subs)))
out.write("\n")

for prob in problems.items:
    out.write("@p ")
    letter = problem_map[prob.id]
    out.write(letter)
    out.write(",")
    out.write(letter)
    out.write(",20,0")
    out.write("\n")

numeric_id_map = {}
cur_numeric_id = 0
for part in parts.items:
    cur_numeric_id += 1
    numeric_id_map[part.id] = cur_numeric_id
    
    line = "@t {},0,1,\"{}\"".format(numeric_id_map[part.id], part.display_name)
    out.write(line)
    out.write("\n")

for sub in downloaded_subs:
    line = "@s {},{},{},{},{}".format(numeric_id_map[sub.participant_id],
                                      sub.problem_id,
                                      sub.attempt_id,
                                      sub.time,
                                      sub.verdict)

    out.write(line)
    out.write("\n")

out.close()

print(f"Output written to out.dat")
