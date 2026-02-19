#!/usr/bin/env python3
"""
Backfill emails to Qdrant for a specific user.
One-time use to populate memories from existing emails.
"""

import imaplib
import email
from email.policy import default
import json
import sys
import subprocess

# Authorized senders with their user IDs
AUTHORIZED_SENDERS = {
    "mdkrushr@gmail.com": "rob",
    "mdkrusha@gmail.com": "jennifer"
}

# Gmail IMAP settings
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993

# Load credentials
CRED_FILE = "/root/.openclaw/workspace/.gmail_imap.json"

def load_credentials():
    try:
        with open(CRED_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None

def store_email_memory(user_id, sender, subject, body, date):
    """Store email to Qdrant as memory for the user."""
    try:
        # Format as conversation-like entry
        email_text = f"[EMAIL from {sender}]\nSubject: {subject}\nDate: {date}\n\n{body}"

        # Store using auto_store.py (waits for completion)
        script_path = "/root/.openclaw/workspace/skills/qdrant-memory/scripts/auto_store.py"
        result = subprocess.run([
            "python3", script_path,
            f"[Email] {subject}",
            email_text,
            "--user-id", user_id
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print(f"  ✓ Stored: {subject[:50]}")
        else:
            print(f"  ✗ Failed: {subject[:50]}")
    except Exception as e:
        print(f"  ✗ Error: {e}")

def backfill(user_id=None, limit=20):
    """Backfill emails for specific user or all authorized senders."""
    creds = load_credentials()
    if not creds:
        return

    email_addr = creds.get("email")
    app_password = creds.get("app_password")

    if not email_addr or not app_password:
        return

    try:
        # Connect to IMAP
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(email_addr, app_password)
        mail.select("inbox")

        # Get ALL emails
        status, messages = mail.search(None, "ALL")

        if status != "OK" or not messages[0]:
            print("No emails found.")
            mail.logout()
            return

        email_ids = messages[0].split()
        print(f"Found {len(email_ids)} total emails")

        # Filter by user if specified
        target_emails = []
        if user_id:
            # Find email address for this user
            for auth_email, uid in AUTHORIZED_SENDERS.items():
                if uid == user_id:
                    target_emails.append(auth_email.lower())
        else:
            target_emails = [e.lower() for e in AUTHORIZED_SENDERS.keys()]

        # Process emails
        stored_count = 0
        for eid in email_ids[-limit:]:
            status, msg_data = mail.fetch(eid, "(RFC822)")
            if status != "OK":
                continue

            msg = email.message_from_bytes(msg_data[0][1], policy=default)
            sender = msg.get("From", "").lower()
            subject = msg.get("Subject", "")
            date = msg.get("Date", "")

            # Extract body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_content()
                        break
            else:
                body = msg.get_content()
            body = body.strip()[:2000] if body else ""

            # Check if from target sender
            for auth_email, uid in AUTHORIZED_SENDERS.items():
                if auth_email.lower() in sender:
                    if user_id and uid != user_id:
                        continue
                    print(f"\nStoring for {uid}:")
                    store_email_memory(uid, sender, subject, body, date)
                    stored_count += 1
                    break

        print(f"\nDone! Stored {stored_count} emails to Qdrant.")

        mail.close()
        mail.logout()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backfill emails to Qdrant")
    parser.add_argument("--user-id", help="Specific user to backfill (rob or jennifer)")
    parser.add_argument("--limit", type=int, default=20, help="Max emails to process")
    args = parser.parse_args()

    backfill(user_id=args.user_id, limit=args.limit)