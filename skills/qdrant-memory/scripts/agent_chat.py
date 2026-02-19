#!/usr/bin/env python3
"""
Agent Messaging System - Redis Streams
Kimi and Max shared communication channel
"""

import argparse
import json
import time
import sys
from datetime import datetime, timezone

import redis

REDIS_HOST = "10.0.0.36"
REDIS_PORT = 6379
STREAM_NAME = "agent-messages"
LAST_READ_KEY = "agent:last_read:{agent}"

class AgentChat:
    def __init__(self, agent_name):
        self.agent = agent_name
        self.r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    
    def send(self, msg_type, message, reply_to=None, from_user=False):
        """Send a message to the stream"""
        entry = {
            "agent": self.agent,
            "type": msg_type,  # idea, question, update, reply
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reply_to": reply_to or "",
            "from_user": str(from_user).lower()  # "true" if from Rob, "false" if from agent
        }
        
        msg_id = self.r.xadd(STREAM_NAME, entry)
        print(f"[{self.agent}] Sent: {msg_id}")
        return msg_id
    
    def read_new(self, block_ms=1000):
        """Read messages since last check"""
        last_id = self.r.get(LAST_READ_KEY.format(agent=self.agent)) or "0"
        
        result = self.r.xread(
            {STREAM_NAME: last_id},
            block=block_ms
        )
        
        if not result:
            return []
        
        messages = []
        for stream_name, entries in result:
            for msg_id, data in entries:
                messages.append({"id": msg_id, **data})
                # Update last read position
                self.r.set(LAST_READ_KEY.format(agent=self.agent), msg_id)
        
        return messages
    
    def read_all(self, count=50):
        """Read last N messages regardless of read status"""
        entries = self.r.xrevrange(STREAM_NAME, count=count)
        
        messages = []
        for msg_id, data in entries:
            messages.append({"id": msg_id, **data})
        
        return messages
    
    def read_since(self, hours=24):
        """Read messages from last N hours"""
        cutoff = time.time() - (hours * 3600)
        cutoff_ms = int(cutoff * 1000)
        
        # Get messages since cutoff (approximate using ID which is timestamp-based)
        entries = self.r.xrange(STREAM_NAME, min=f"{cutoff_ms}-0", count=1000)
        
        messages = []
        for msg_id, data in entries:
            messages.append({"id": msg_id, **data})
        
        return messages
    
    def wait_for_reply(self, reply_to_id, timeout_sec=30):
        """Block until a reply to a specific message arrives"""
        start = time.time()
        last_check = "0"
        
        while time.time() - start < timeout_sec:
            result = self.r.xread({STREAM_NAME: last_check}, block=timeout_sec*1000)
            
            if result:
                for stream_name, entries in result:
                    for msg_id, data in entries:
                        last_check = msg_id
                        if data.get("reply_to") == reply_to_id:
                            return {"id": msg_id, **data}
            
            time.sleep(0.5)
        
        return None
    
    def format_message(self, msg):
        """Pretty print a message"""
        ts = msg.get("timestamp", "")[11:19]  # HH:MM:SS only
        agent = msg.get("agent", "?")
        msg_type = msg.get("type", "?")
        text = msg.get("message", "")
        reply_to = msg.get("reply_to", "")
        from_user = msg.get("from_user", "false") == "true"
        
        icon = "🤖" if agent == "Max" else "🎙️"
        type_icon = {
            "idea": "💡",
            "question": "❓",
            "update": "📢",
            "reply": "↩️"
        }.get(msg_type, "•")
        
        # Show 📝 if message is from Rob (relayed by agent), otherwise show agent icon only
        source_icon = "📝" if from_user else icon
        
        reply_info = f" [reply to {reply_to[:8]}...]" if reply_to else ""
        return f"[{ts}] {source_icon} {agent} {type_icon} {text}{reply_info}"

def main():
    parser = argparse.ArgumentParser(description="Agent messaging via Redis Streams")
    parser.add_argument("--agent", required=True, choices=["Kimi", "Max"], help="Your agent name")
    
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Send command
    send_p = subparsers.add_parser("send", help="Send a message")
    send_p.add_argument("--type", default="update", choices=["idea", "question", "update", "reply"])
    send_p.add_argument("--message", "-m", required=True, help="Message text")
    send_p.add_argument("--reply-to", help="Reply to message ID")
    send_p.add_argument("--from-user", action="store_true", help="Mark as message from Rob (not from agent)")
    
    # Read command
    read_p = subparsers.add_parser("read", help="Read messages")
    read_p.add_argument("--new", action="store_true", help="Only unread messages")
    read_p.add_argument("--all", action="store_true", help="Last 50 messages")
    read_p.add_argument("--since", type=int, help="Messages from last N hours")
    read_p.add_argument("--wait", action="store_true", help="Wait for new messages (blocking)")
    
    args = parser.parse_args()
    
    chat = AgentChat(args.agent)
    
    if args.command == "send":
        msg_id = chat.send(args.type, args.message, args.reply_to, args.from_user)
        print(f"Message ID: {msg_id}")
        
    elif args.command == "read":
        if args.new or args.wait:
            if args.wait:
                print("Waiting for messages... (Ctrl+C to stop)")
                try:
                    while True:
                        msgs = chat.read_new(block_ms=5000)
                        for m in msgs:
                            print(chat.format_message(m))
                except KeyboardInterrupt:
                    print("\nStopped.")
            else:
                msgs = chat.read_new()
                for m in msgs:
                    print(chat.format_message(m))
                if not msgs:
                    print("No new messages.")
                    
        elif args.since:
            msgs = chat.read_since(args.since)
            for m in msgs:
                print(chat.format_message(m))
            if not msgs:
                print(f"No messages in last {args.since} hours.")
                
        else:  # default --all
            msgs = chat.read_all()
            for m in reversed(msgs):  # Chronological order
                print(chat.format_message(m))
            if not msgs:
                print("No messages in stream.")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
