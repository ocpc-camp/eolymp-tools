import csv
import os
import random

# Force IPv4 to avoid IPv6 connectivity issues that cause hanging
import socket
old_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = getaddrinfo_ipv4_only

import eolymp.universe.space_service_pb2 as space_service_pb2
import eolymp.community.member_service_pb2 as member_service_pb2
import eolymp.community.member_pb2 as member_pb2
import eolymp.community.member_user_pb2 as member_user_pb2
import eolymp.community.attribute_pb2 as attribute_pb2
from eolymp.core.http_client import HttpClient
from eolymp.universe.space_service_http import SpaceServiceClient
from eolymp.community.member_service_http import MemberServiceClient

print(os.getenv("EOLYMP_TOKEN"))
print(os.getenv("EOLYMP_SPACE"))

client = HttpClient(token=os.getenv("EOLYMP_TOKEN"))
space_service = SpaceServiceClient(client)
lookup_result = space_service.LookupSpace(space_service_pb2.LookupSpaceInput(key=os.getenv("EOLYMP_SPACE")))
community = MemberServiceClient(client, lookup_result.space.url)


def get_members_map():
    mm = {}
    offset = 0

    while True:
        listing = community.ListMembers(member_service_pb2.ListMembersInput(offset=offset, size=100))
        for item in listing.items:
            print("Reading existing member \"{}\" with ID {}".format(item.user.nickname, item.id))
            mm[item.user.nickname] = item

        offset += len(listing.items)
        if offset >= listing.total:
            break

    return mm


def identity_with_password(name, password):
    return member_user_pb2.User(
        issuer=lookup.url,
        nickname=name,
        password=password
    )

def missing(dictionary, field):
    return field not in dictionary or len(dictionary["field"].strip()) == 0

def comma_separated_list(arr):
    return ", ".join(x for x in arr if len(x) != 0)

members = get_members_map()

with open("members_reshaped.csv") as file_in:
    reader = csv.DictReader(file_in)
    header = reader.fieldnames
    rows = [dict(row) for row in reader]

# Reshaped CSV column names (from reshape_members.py output)
NAME = "name"
USERNAME = "username"
PASSWORD = "password"
TEAM_SHORT = "team_short"
MEMBERS = "members"
UNIVERSITY = "university"
ONSITE = "onsite"
ROOM = "room"
EMAIL = "email"
EMAILS = "emails"

# calculated
EOLYMP_ID = "Eolymp ID"

# Username scheme: configurable via env var, e.g. "ocpc{:03}" or "team{:03}"
USERNAME_TEMPLATE = os.getenv("USERNAME_TEMPLATE", "team{:03}")
# Value of the `onsite` column that means a participant is on-site (and so should
# be assigned a room). Anything else is treated as remote / online.
ONSITE_VALUE = os.getenv("ONSITE_VALUE", "onsite").lower()

potential_usernames = [USERNAME_TEMPLATE.format(i) for i in range(1, 1000)]
for name in members.keys():
    if name in potential_usernames:
        potential_usernames.remove(name)
    else:
        print(name)
for row in rows:
    if row.get(USERNAME) in potential_usernames:
        potential_usernames.remove(row.get(USERNAME))

enriched_rows = []
for row in rows:
    data = dict(row)
    
    # Data is already enriched from reshape_members.py, just ensure username is available
    # If username is missing or NOT already taken, generate a new one (shouldn't happen with our CSV)
    if not data.get(USERNAME) or data[USERNAME] not in members:
        # Only generate new username if we don't have one or it doesn't exist in Eolymp yet
        if not data.get(USERNAME):
            data[USERNAME] = potential_usernames[0]
            potential_usernames.pop(0)
    
    # If password is missing, generate one (shouldn't happen from reshape)
    if not data.get(PASSWORD):
        data[PASSWORD] = "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(8))
    
    # Assign room 0 to online (remote) participants
    if data.get(ONSITE, "").lower() != ONSITE_VALUE:
        data[ROOM] = "0"
    
    # Clean full name: remove prefix only if no university is set
    full_name = data.get(NAME, "")
    if not data.get(UNIVERSITY) and ": " in full_name:
        full_name = full_name.split(": ", 1)[1]
        data[NAME] = full_name  # Update data with cleaned name for CSV output
    
    member = member_pb2.Member(
        inactive=False,
        user=member_user_pb2.User(
            issuer=lookup_result.space.issuer_url,
            nickname=data[USERNAME],
            password=data[PASSWORD],
            name=full_name
        ),
        attributes=[
            attribute_pb2.Attribute.Value(attribute_key="team_short", string=data.get(TEAM_SHORT, "")),
            attribute_pb2.Attribute.Value(attribute_key="members", string=data.get(MEMBERS, "")),
            attribute_pb2.Attribute.Value(attribute_key="university", string=data.get(UNIVERSITY, "")),
            attribute_pb2.Attribute.Value(attribute_key="onsite", string=data.get(ONSITE, "")),
            attribute_pb2.Attribute.Value(attribute_key="room", number=int(data.get(ROOM, "0") or "0")),
        ],
        # groups=[data["group"]]
    )

    if data[USERNAME] in members:
        # Update existing member
        ex = members[data[USERNAME]]
        data[EOLYMP_ID] = ex.id
        community.UpdateMember(member_service_pb2.UpdateMemberInput(
            member_id=ex.id,
            member=member
        ))
        print("Member {} ({}) has been updated".format(ex.id, member.user.nickname))
    else:
        # Create new member
        out = community.CreateMember(member_service_pb2.CreateMemberInput(member=member))
        data[EOLYMP_ID] = out.member_id
        print("Member {} ({}) has been added".format(out.member_id, member.user.nickname))

    enriched_rows.append(data)

if TEAM_SHORT not in header:
    header = list(header) + [TEAM_SHORT]
if MEMBERS not in header:
    header = list(header) + [MEMBERS]
if UNIVERSITY not in header:
    header = list(header) + [UNIVERSITY]
if ONSITE not in header:
    header = list(header) + [ONSITE]
if ROOM not in header:
    header = list(header) + [ROOM]
if EOLYMP_ID not in header:
    header = list(header) + [EOLYMP_ID]

with open("credentials.csv", "w") as file_out:
    writer = csv.DictWriter(file_out, fieldnames=header)
    writer.writeheader()
    for row in enriched_rows:
        writer.writerow({field: row.get(field, "") for field in header})