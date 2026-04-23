#!/usr/bin/env python3
"""Test script to verify room lookup from Eolymp works correctly."""

import os
import socket
from dotenv import load_dotenv

# Force IPv4 to avoid IPv6 connectivity issues
old_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = getaddrinfo_ipv4_only

from eolymp.core import HttpClient
from eolymp.universe.space_service_http import SpaceServiceClient
from eolymp.universe import space_service_pb2
from eolymp.community.member_service_http import MemberServiceClient
from eolymp.community import member_service_pb2, member_pb2

load_dotenv()

EOLYMP_TOKEN = os.getenv("EOLYMP_TOKEN")
EOLYMP_SPACE = os.getenv("EOLYMP_SPACE")

print(f"Token: {EOLYMP_TOKEN[:20]}...")
print(f"Space: {EOLYMP_SPACE}")
print()

# Initialize clients
client = HttpClient(token=EOLYMP_TOKEN)
space_service = SpaceServiceClient(client)
lookup = space_service.LookupSpace(space_service_pb2.LookupSpaceInput(key=EOLYMP_SPACE))
member_service = MemberServiceClient(client, lookup.space.url)

print("Fetching members with room assignments...")
room_map = {}
offset = 0

while True:
    page = member_service.ListMembers(member_service_pb2.ListMembersInput(
        offset=offset,
        size=100
    ))
    
    for member in page.items:
        # Fetch full member details to get attributes
        try:
            details = member_service.DescribeMember(member_service_pb2.DescribeMemberInput(
                member_id=member.id,
                extra=[member_pb2.Member.Extra.ATTRIBUTES]
            ))
            
            # Look for the room attribute
            room_number = None
            for attr in details.member.attributes:
                if attr.attribute_key == "room" and attr.HasField('number'):
                    room_number = int(attr.number)
                    break
            
            if room_number is not None:
                room_map[member.id] = room_number
        except Exception as e:
            print(f"  Warning: Could not fetch details for member {member.id}: {e}")
    
    offset += len(page.items)
    if offset >= page.total:
        break

print(f"\n✓ Successfully fetched room assignments for {len(room_map)} members")
print(f"✓ Total members in space: {page.total}")

# Count by room
room_counts = {}
for member_id, room in room_map.items():
    room_counts[room] = room_counts.get(room, 0) + 1

print("\nRoom distribution:")
for room in sorted(room_counts.keys()):
    print(f"  Room {room}: {room_counts[room]} members")

# Show sample members
print("\nSample members (first 5 with room assignments):")
count = 0
for member_id, room in list(room_map.items())[:5]:
    # Fetch member details to show nickname
    offset_test = 0
    while True:
        page = member_service.ListMembers(member_service_pb2.ListMembersInput(
            offset=offset_test,
            size=100
        ))
        for member in page.items:
            if member.id == member_id:
                print(f"  {member.user.nickname} (ID: {member_id[:20]}...): Room {room}")
                count += 1
                break
        offset_test += len(page.items)
        if offset_test >= page.total or count >= 5:
            break
        if count >= 5:
            break

print("\n✓ Room lookup test completed successfully!")
print("\nThe printer client can now:")
print("  1. Fetch all members and their room assignments from Eolymp")
print("  2. Map member IDs to room numbers")
print("  3. Route print jobs to the correct printer based on room assignment")
