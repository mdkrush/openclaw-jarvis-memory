#!/usr/bin/env python3
"""Send email via Gmail SMTP with attachment support."""

import smtplib
import json
import sys
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

CRED_FILE = "/root/.openclaw/workspace/.gmail_imap.json"

def load_credentials():
    with open(CRED_FILE) as f:
        return json.load(f)

def send_email(to_email, subject, body, reply_to=None, attachment_path=None):
    creds = load_credentials()
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    
    msg = MIMEMultipart()
    msg['From'] = f"Kimi <{creds['email']}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    if reply_to:
        msg['In-Reply-To'] = reply_to
        msg['References'] = reply_to
    
    # Attach body
    msg.attach(MIMEText(body, 'plain'))
    
    # Attach file if provided
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, 'rb') as f:
            mime_base = MIMEBase('application', 'octet-stream')
            mime_base.set_payload(f.read())
        
        encoders.encode_base64(mime_base)
        filename = os.path.basename(attachment_path)
        mime_base.add_header('Content-Disposition', f'attachment; filename={filename}')
        msg.attach(mime_base)
        print(f"📎 Attached: {filename}")
    
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(creds['email'], creds['app_password'])
        server.send_message(msg)
    
    print(f"✉️ Sent to {to_email}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--reply-to")
    parser.add_argument("--attach", help="Path to file to attach")
    args = parser.parse_args()
    
    send_email(args.to, args.subject, args.body, args.reply_to, args.attach)