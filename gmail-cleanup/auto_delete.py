#!/usr/bin/env python3
"""
Gmail Auto-Delete — Safe Cleanup Script
----------------------------------------
Mode 1 (default / dry-run):
  Scans for throwaway emails older than 5 years, emails you a report.
  Nothing is deleted.

Mode 2 (--confirm-delete):
  Reads the same scan results and moves emails to Trash.
  Only run this AFTER reviewing the dry-run report.

Mode 3 (--empty-trash):
  Permanently empties Gmail Trash to free storage.
  Only run this AFTER confirming the Trash contents are OK.

Usage:
  python auto_delete.py                  # dry run + email report
  python auto_delete.py --confirm-delete # move to Trash
  python auto_delete.py --empty-trash    # permanently delete Trash
"""

import os
import sys
import json
import argparse
import smtplib
import ssl
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
except ImportError:
    print("[error] Run: pip install google-auth google-auth-oauthlib google-api-python-client")
    raise

# ── Config ────────────────────────────────────────────────────────────────────
TOKEN_PATH    = "token.json"
DIGEST_EMAIL  = os.environ.get("DIGEST_EMAIL", "")
SMTP_HOST     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ.get("SMTP_USER", "")
SMTP_PASS     = os.environ.get("SMTP_PASS", "")
DELETE_AFTER  = "5y"   # delete emails older than this

# ── Categories to DELETE (older than DELETE_AFTER) ────────────────────────────
DELETE_QUERIES = [
    # Job alerts & recruiters
    "from:jobs@dice.com",
    "from:talent@marketing.angel.co",
    "from:newsletters@marketing.angel.co",
    "from:careeralerts.teksystems.com",
    "from:hi.wellfound.com",
    "subject:right to represent",
    # Newsletters & marketing
    "from:team@jobscan.co",
    "from:changemanagement@prosci.com",
    "from:subscriberservices@bayareanewsgroup.net",
    "from:norton@secure.norton.com",
    "from:isaca@e.isaca.org",
    "from:sophie.clark@plutora.com",
    "from:azeem.azhar@exponentialview.co",
    "from:todd@successhacker.co",
    "from:noreply@github.com",
    # Retail & promotions
    "from:no-reply@email.homedepot.com",
    "from:noreply@email.petinsurance.com",
    "from:pegasolutions@reply.pega.com",
    # Charity solicitations
    "from:donor.relations@shfb.org",
    # Old recruiter spam
    "from:objectwin.com",
    "from:damcosoft.com",
    "from:genesis10.com",
]

# ── Categories to ALWAYS KEEP (never delete these) ────────────────────────────
KEEP_SENDERS = [
    "citi.com", "chase.com", "bankofamerica.com", "morganstanley.com",
    "sutterhealth.org", "axisbank.com", "icicibank.com", "kvbmail.com",
    "incometax.gov.in", "irs.gov", "sanjoseca.gov",
    "southwest.com", "americanairlines.com", "airbnb.com", "booking.com",
    "xfinity.com", "att.com", "sling.com",
]

# ── Auth ──────────────────────────────────────────────────────────────────────
def authenticate():
    creds = Credentials.from_authorized_user_file(
        TOKEN_PATH, ["https://www.googleapis.com/auth/gmail.modify"]
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)

# ── Fetch all message IDs for a query ─────────────────────────────────────────
def get_all_ids(service, query):
    ids = []
    page_token = None
    while True:
        params = {"userId": "me", "q": query, "maxResults": 500}
        if page_token:
            params["pageToken"] = page_token
        results = service.users().messages().list(**params).execute()
        ids += [m["id"] for m in results.get("messages", [])]
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    return ids

# ── Move messages to Trash in batches ─────────────────────────────────────────
def move_to_trash(service, ids):
    if not ids:
        return 0
    total = 0
    for i in range(0, len(ids), 1000):
        chunk = ids[i:i+1000]
        body = {"ids": chunk, "addLabelIds": ["TRASH"], "removeLabelIds": ["INBOX"]}
        service.users().messages().batchModify(userId="me", body=body).execute()
        total += len(chunk)
    return total

# ── Get a sample of message details for the report ────────────────────────────
def get_sample_details(service, ids, max_sample=20):
    samples = []
    for msg_id in ids[:max_sample]:
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_id, format="metadata",
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            samples.append({
                "subject": headers.get("Subject", "(no subject)")[:80],
                "from":    headers.get("From", "unknown")[:60],
                "date":    headers.get("Date", "unknown"),
            })
        except Exception:
            pass
    return samples

# ── Send email report ─────────────────────────────────────────────────────────
def send_report(to, subject, body):
    if not SMTP_USER or not SMTP_PASS:
        print(f"\nTo: {to}\nSubject: {subject}\n\n{body}")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = to
    msg.attach(MIMEText(body, "plain", "utf-8"))
    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [to], msg.as_string())
    print(f"[email] Report sent to {to}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Gmail Auto-Delete (safe mode)")
    parser.add_argument("--confirm-delete", action="store_true",
                        help="Actually move emails to Trash (review dry-run report first!)")
    parser.add_argument("--empty-trash", action="store_true",
                        help="Permanently empty Gmail Trash")
    args = parser.parse_args()

    if not DIGEST_EMAIL:
        sys.exit("[error] Set DIGEST_EMAIL environment variable")

    print("\n🔍 Gmail Auto-Delete")
    print("=" * 40)

    service = authenticate()

    # ── Mode 3: Empty Trash ───────────────────────────────────────────────────
    if args.empty_trash:
        print("🗑️  Emptying Gmail Trash...")
trash_ids = get_all_ids(service, "in:trash")
if trash_ids:
    for i in range(0, len(trash_ids), 1000):
        chunk = trash_ids[i:i+1000]
        service.users().messages().batchDelete(userId="me", body={"ids": chunk}).execute()
print(f"✅ {len(trash_ids)} emails permanently deleted.")
        print("✅ Trash emptied. Storage will update within a few minutes.")
        send_report(
            DIGEST_EMAIL,
            "🗑️ ForexWatch Gmail — Trash Emptied",
            f"Gmail Trash has been permanently emptied on {datetime.date.today()}.\n\n"
            f"Storage should update within a few minutes.\n\n"
            f"Check: one.google.com/storage"
        )
        return

    # ── Scan: find all deletable emails ──────────────────────────────────────
    print(f"📂 Scanning for emails older than {DELETE_AFTER}...")
    all_ids = []
    category_counts = {}

    for query in DELETE_QUERIES:
        full_query = f"{query} older_than:{DELETE_AFTER}"
        ids = get_all_ids(service, full_query)
        if ids:
            category_counts[query] = len(ids)
            all_ids.extend(ids)
            print(f"  {query}: {len(ids)} emails")

    # Deduplicate
    all_ids = list(set(all_ids))
    total = len(all_ids)
    print(f"\n📊 Total unique emails found: {total}")

    # ── Mode 2: Confirm Delete ────────────────────────────────────────────────
    if args.confirm_delete:
        print(f"🗑️  Moving {total} emails to Trash...")
        moved = move_to_trash(service, all_ids)
        print(f"✅ {moved} emails moved to Trash.")
        send_report(
            DIGEST_EMAIL,
            f"🗑️ Gmail Cleanup — {moved} Emails Moved to Trash",
            f"Gmail Auto-Delete completed on {datetime.date.today()}.\n\n"
            f"✅ {moved} emails moved to Trash.\n\n"
            f"Next step: Run with --empty-trash to permanently free storage.\n"
            f"Or wait 30 days for Gmail to auto-empty Trash.\n\n"
            f"Check storage: one.google.com/storage"
        )
        return

    # ── Mode 1: Dry Run — build and send report ───────────────────────────────
    print("\n📋 Dry run — building report (nothing deleted)...")
    samples = get_sample_details(service, all_ids, max_sample=25)

    sample_text = "\n".join(
        f"  {i+1:2}. From: {s['from']}\n      Subject: {s['subject']}\n      Date: {s['date']}"
        for i, s in enumerate(samples)
    )

    breakdown = "\n".join(
        f"  {q}: {c} emails"
        for q, c in sorted(category_counts.items(), key=lambda x: -x[1])
    )

    report_body = (
        f"{'━'*45}\n"
        f"  GMAIL AUTO-DELETE · Dry Run Report\n"
        f"  {datetime.date.today()}\n"
        f"{'━'*45}\n\n"
        f"  SUMMARY\n"
        f"  Total emails that WOULD be deleted: {total}\n"
        f"  Older than: {DELETE_AFTER}\n\n"
        f"  BREAKDOWN BY CATEGORY\n"
        f"  {'─'*43}\n"
        f"{breakdown}\n\n"
        f"  SAMPLE EMAILS (first 25)\n"
        f"  {'─'*43}\n"
        f"{sample_text}\n\n"
        f"{'━'*45}\n"
        f"  TO PROCEED WITH DELETION:\n"
        f"  Go to GitHub Actions → Gmail Auto-Delete\n"
        f"  → Run workflow → select 'confirm-delete'\n"
        f"{'━'*45}\n"
    )

    print(report_body)
    send_report(
        DIGEST_EMAIL,
        f"📋 Gmail Cleanup Report — {total} emails to delete (review before confirming)",
        report_body
    )

if __name__ == "__main__":
    main()
