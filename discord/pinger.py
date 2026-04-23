import csv
import os
import time
import json

from urllib import request
from dotenv import load_dotenv

import eolymp.universe.space_service_pb2 as space_service_pb2
import eolymp.universe.universe_pb2 as universe_pb2
import eolymp.community.member_pb2 as member_pb2
import eolymp.cognito.cognito_pb2 as cognito_pb2
import eolymp.wellknown.expression_pb2 as expression_pb2
import eolymp.judge.ticket_service_pb2 as judge_pb2
import eolymp.judge.ticket_pb2 as ticket_pb2
import eolymp.judge.ticket_reply_pb2 as ticket_reply_pb2
from eolymp.core.http_client import HttpClient
from eolymp.core.oauth_client import OAuthClient
from eolymp.universe.universe_http import UniverseClient
from eolymp.cognito.cognito_http import CognitoClient
from eolymp.judge.ticket_service_http import TicketServiceClient

load_dotenv()
HOOK_URL = os.getenv("HOOK_URL")
DISCORD_ROLE = os.getenv("DISCORD_ROLE")
EOLYMP_TOKEN = os.getenv("EOLYMP_TOKEN")
EOLYMP_SPACE = os.getenv("EOLYMP_SPACE")

print(EOLYMP_SPACE)

client = HttpClient(token=EOLYMP_TOKEN)
universe = UniverseClient(client)
lookup = universe.LookupSpace(space_service_pb2.LookupSpaceInput(key=EOLYMP_SPACE))
judge = TicketServiceClient(client, lookup.space.url)


def get_all_tickets():
    tickets = []
    offset = 0

    while True:
        page = judge.ListTickets(judge_pb2.ListTicketsInput(
            offset = 0,
            size = 100,
            filters = judge_pb2.ListTicketsInput.Filter(),
            extra = [ticket_pb2.Ticket.MESSAGE_VALUE]
        ))

        for item in page.items:
            tickets.append(item)

        offset += len(page.items)
        if offset >= page.total:
            break

    return tickets


def get_all_replies(ticket_id):
    replies = []
    offset = 0

    while True:
        page = judge.ListReplies(judge_pb2.ListRepliesInput(
            offset = 0,
            size = 100,
            ticket_id = ticket_id,
            extra = [ticket_reply_pb2.Reply.MESSAGE_VALUE]
        ))

        for item in page.items:
            replies.append(item)

        offset += len(page.items)
        if offset >= page.total:
            break

    return replies


def send_discord_message(content):
    payload = json.dumps({"content": content})
    send_req = request.Request(HOOK_URL,
                               data=bytes(payload, "UTF-8"),
                               headers={"Content-Type": "application/json",
                                        "User-Agent": "pingerbot"},
                               method="POST")
    request.urlopen(send_req)


tickets_by_id = {}
seen_reply_ids = set()
print("getting initial tickets...")
init_tickets = get_all_tickets()
for ticket in init_tickets:
    tickets_by_id[ticket.id] = ticket
    print(f"getting initial replies for ticket {ticket.id}...")
    replies = get_all_replies(ticket.id)
    for reply in replies:
        seen_reply_ids.add(reply.id)

print("script is now ready!")
        
last_refresh = 0
while True:
    try:
        current_tickets = get_all_tickets()
        for ticket in current_tickets:
            ticket_url = "https://console.eolymp.com/en/" + EOLYMP_SPACE + "/tickets/" + ticket.id
            should_update_replies = False
            if ticket.id not in tickets_by_id:
                print(f"reading new ticket {ticket.id}")

                ticket = judge.DescribeTicket(judge_pb2.DescribeTicketInput(
                    ticket_id=ticket.id,
                    extra=[ticket_pb2.Ticket.MESSAGE_VALUE]
                )).ticket
                print(ticket)
                print("====")
                message = f"""<@&{DISCORD_ROLE}> There is a new question at <{ticket_url}>
**Subject**: {ticket.subject}
**Message**: {ticket.message.markdown}"""
                print("message", message)
                send_discord_message(message)

                should_update_replies = True
            elif ticket.last_reply_at != tickets_by_id[ticket.id].last_reply_at:
                print(f"loading new replies for ticket {ticket.id}")

                replies = get_all_replies(ticket.id)
                for reply in replies:
                    if reply.id not in seen_reply_ids:
                        if reply.member_id is not None and reply.member_id != "":
                            message = f"""<@&{DISCORD_ROLE}> There is a new follow-up question at <{ticket_url}>
**Subject**: {ticket.subject}
**Orginal question**: {ticket.message.markdown}
**New message**: {reply.message.markdown}"""
                            print("message", message)
                            send_discord_message(message)

                        seen_reply_ids.add(reply.id)
            tickets_by_id[ticket.id] = ticket
 
        time.sleep(5)
    except Exception as ex:
        print(time.ctime(), ex)
