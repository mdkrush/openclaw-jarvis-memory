#!/usr/bin/env python3
"""
Email checker for heartbeat using Redis ID tracking.
Tracks seen email IDs in Redis to avoid missing read emails.
Stores emails to Qdrant with sender-specific user_id for memory.
Only alerts on emails from authorized senders.
"""

import imaplib
import email
from email.policy import default
import json
import sys
import redis
import subprocess
from datetime import datetime

# Authorized senders with their user IDs for Qdrant storage
AUTHORIZED_SENDERS = {
    "mdkrushr@gmail.com": "rob",
    "mdkrusha@gmail.com": "jennifer"
}

# Gmail IMAP settings
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993

# Redis config
REDIS_HOST = "10.0.0.36"
REDIS_PORT = 6379
REDIS_KEY = "email:seen_ids"

# Load credentials
CRED_FILE = "/root/.openclaw/workspace/.gmail_imap.json"

def load_credentials():
    try:
        with open(CRED_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        return None

def get_redis():
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        r.ping()  # Test connection
        return r
    except Exception as e:
        return None

def store_email_memory(user_id, sender, subject, body, date):
    """Store email to Qdrant as memory for the user."""
    try:
        # Format as conversation-like entry
        email_text = f"[EMAIL from {sender}]\nSubject: {subject}\n\n{body}"

        # Store using background_store.py (fire-and-forget)
        script_path = "/root/.openclaw/workspace/skills/qdrant-memory/scripts/background_store.py"
        subprocess.Popen([
            "python3", script_path,
            f"[Email] {subject}",
            email_text,
            "--user-id", user_id
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        pass  # Silent fail

def get_user_context(user_id):
    """Fetch recent context from Qdrant for the user."""
    try:
        script_path = "/root/.openclaw/workspace/skills/qdrant-memory/scripts/get_user_context.py"
        result = subprocess.run([
            "python3", script_path,
            "--user-id", user_id,
            "--limit", "3"
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception as e:
        pass
    return None

def check_emails():
    creds = load_credentials()
    if not creds:
        return  # Silent fail
    
    email_addr = creds.get("email")
    app_password = creds.get("app_password")
    
    if not email_addr or not app_password:
        return  # Silent fail
    
    r = get_redis()
    if not r:
        return  # Silent fail if Redis unavailable
    
    try:
        # Connect to IMAP
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(email_addr, app_password)
        mail.select("inbox")
        
        # Get ALL emails (not just unseen)
        status, messages = mail.search(None, "ALL")
        
        if status != "OK" or not messages[0]:
            mail.logout()
            return  # No emails
        
        email_ids = messages[0].split()
        
        # Get already-seen IDs from Redis
        seen_ids = set(r.smembers(REDIS_KEY))
        
        # Check last 10 emails for new ones
        for eid in email_ids[-10:]:
            eid_str = eid.decode() if isinstance(eid, bytes) else str(eid)
            
            # Skip if already seen
            if eid_str in seen_ids:
                continue
            
            status, msg_data = mail.fetch(eid, "(RFC822)")
            if status != "OK":
                continue
            
            msg = email.message_from_bytes(msg_data[0][1], policy=default)
            sender = msg.get("From", "").lower()
            subject = msg.get("Subject", "")
            date = msg.get("Date", "")

            # Extract email body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_content()
                        break
            else:
                body = msg.get_content()

            # Clean up body (limit size)
            body = body.strip()[:2000] if body else ""

            # Check if sender is authorized and get their user_id
            user_id = None
            for auth_email, uid in AUTHORIZED_SENDERS.items():
                if auth_email.lower() in sender:
                    user_id = uid
                    break

            # Mark as seen in Redis regardless of sender (avoid re-checking)
            r.sadd(REDIS_KEY, eid_str)

            if user_id:
                # Store to Qdrant for memory
                store_email_memory(user_id, sender, subject, body, date)
                # Get user context from Qdrant before alerting
                context = get_user_context(user_id)
                # Output for Kimi to respond (with context hint)
                print(f"[EMAIL] User: {user_id} | From: {sender.strip()} | Subject: {subject} | Date: {date}")
                if context:
                    print(f"[CONTEXT] {context}")
        
        # Cleanup old IDs (keep last 100)
        all_ids = r.smembers(REDIS_KEY)
        if len(all_ids) > 100:
            # Convert to int, sort, keep only highest 100
            id_ints = sorted([int(x) for x in all_ids if x.isdigit()])
            to_remove = id_ints[:-100]
            for old_id in to_remove:
                r.srem(REDIS_KEY, str(old_id))
        
        mail.close()
        mail.logout()
        
    except Exception as e:
        # Silent fail - no output
        pass

if __name__ == "__main__":
    check_emails()
    sys.exit(0)