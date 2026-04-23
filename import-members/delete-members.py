import os
import sys

# Force IPv4 to avoid IPv6 connectivity issues that cause hanging
import socket
old_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = getaddrinfo_ipv4_only

import eolymp.universe.space_service_pb2 as space_service_pb2
import eolymp.community.member_service_pb2 as member_service_pb2
from eolymp.core.http_client import HttpClient
from eolymp.universe.space_service_http import SpaceServiceClient
from eolymp.community.member_service_http import MemberServiceClient

print(os.getenv("EOLYMP_TOKEN"))
print(os.getenv("EOLYMP_SPACE"))

client = HttpClient(token=os.getenv("EOLYMP_TOKEN"))
space_service = SpaceServiceClient(client)
lookup_result = space_service.LookupSpace(space_service_pb2.LookupSpaceInput(key=os.getenv("EOLYMP_SPACE")))
community = MemberServiceClient(client, lookup_result.space.url)

print("\n=== Fetching all members ===")
members_to_delete = []
offset = 0

while True:
    listing = community.ListMembers(member_service_pb2.ListMembersInput(offset=offset, size=100))
    for item in listing.items:
        members_to_delete.append((item.user.nickname, item.id))
        print(f"Found: {item.user.nickname} (ID: {item.id})")

    offset += len(listing.items)
    if offset >= listing.total:
        break

print(f"\nTotal members to delete: {len(members_to_delete)}")

if len(members_to_delete) == 0:
    print("No members to delete.")
    sys.exit(0)

response = input(f"Delete all {len(members_to_delete)} members? (yes/no): ")
if response.lower() != "yes":
    print("Cancelled.")
    sys.exit(1)

print("\n=== Deleting members ===")
deleted_count = 0
for nickname, member_id in members_to_delete:
    try:
        community.DeleteMember(member_service_pb2.DeleteMemberInput(member_id=member_id))
        print(f"✓ Deleted: {nickname} ({member_id})")
        deleted_count += 1
    except Exception as e:
        print(f"✗ Failed to delete {nickname} ({member_id}): {e}")

print(f"\nDeleted {deleted_count}/{len(members_to_delete)} members")
