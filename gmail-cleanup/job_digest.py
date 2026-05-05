"""
Job Alert Digest
================
Reads all job alert emails from the past 24 hours,
deduplicates them, and sends ONE clean digest email
every morning via SMTP.

Secrets used (matches existing repo pattern):
  SMTP_USER              - your Gmail address
  SMTP_PASS              - your Gmail app password
  DIGEST_EMAIL           - recipient (defaults to SMTP_USER)
  GMAIL_TOKEN_JSON       - Gmail OAuth token JSON (for reading/archiving)
  GMAIL_CREDENTIALS_JSON - Gmail OAuth credentials JSON (for reading/archiving)
"""

import os, re, json, smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

SMTP_USER       = os.environ.get("SMTP_USER", "csvenky@gmail.com")
SMTP_PASS       = os.environ.get("SMTP_PASS", "")
RECIPIENT_EMAIL = os.environ.get("DIGEST_EMAIL", SMTP_USER)

JOB_ALERT_SENDERS = [
    "donotreply@jobalert.indeed.com",
    "jobalerts-noreply@linkedin.com",
    "jobs-noreply@linkedin.com",
    "jobs-listings@linkedin.com",
    "alerts-noreply@jobs.simplyhired.com",
    "noreply@jobright.ai",
    "emails@efinancialcareers.com",
    "editors-noreply@linkedin.com",
    "newsletters-noreply@linkedin.com",
]

SENDER_QUERY = " OR ".join(f"from:{s}" for s in JOB_ALERT_SENDERS)


def authenticate():
    """Authenticate using env-var JSON secrets (CI) or local files (dev)."""
    creds = None
    token_json   = os.environ.get("GMAIL_TOKEN_JSON")
    creds_json   = os.environ.get("GMAIL_CREDENTIALS_JSON")

    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if creds_json:
                import tempfile
                with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                    f.write(creds_json)
                    tmp = f.name
                flow = InstalledAppFlow.from_client_secrets_file(tmp, SCOPES)
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def fetch_todays_job_alerts(service):
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y/%m/%d")
    query = f"({SENDER_QUERY}) after:{since} in:inbox"
    results = service.users().messages().list(userId="me", q=query, maxResults=200).execute()
    return results.get("messages", [])


def parse_job_from_subject(subject, sender):
    subject = subject.strip()
    # "Title at Company"
    m = re.match(r"^(.+?)\s+at\s+(.+?)$", subject, re.IGNORECASE)
    if m:
        return {"title": m.group(1).strip(), "company": m.group(2).strip(), "source": "LinkedIn"}
    # "Company is hiring for Title. N more..."
    m = re.match(r"^(.+?) is hiring for (.+?)\.", subject, re.IGNORECASE)
    if m:
        return {"title": m.group(2).strip(), "company": m.group(1).strip(), "source": "Indeed"}
    # "Company is hiring for Title" (SimplyHired)
    m = re.match(r"^(.+?) is hiring for (.+?)$", subject, re.IGNORECASE)
    if m:
        return {"title": m.group(2).strip(), "company": m.group(1).strip(), "source": "SimplyHired"}
    # Jobright: 'Company is hiring for "Title" like you'
    m = re.match(r'^(.+?) is hiring for [\u201c"](.+?)[\u201d"]', subject, re.IGNORECASE)
    if m:
        return {"title": m.group(2).strip(), "company": m.group(1).strip(), "source": "Jobright"}
    # LinkedIn PMO alerts: '"Pmo": Company - Title posted on...'
    m = re.match(r'^"[^"]+": (.+?) - (.+?) posted on', subject, re.IGNORECASE)
    if m:
        return {"title": m.group(2).strip(), "company": m.group(1).strip(), "source": "LinkedIn"}
    return {"title": subject[:80], "company": "Unknown", "source": "Job Alert"}


def get_message_details(service, msg_id):
    msg = service.users().messages().get(
        userId="me", id=msg_id, format="metadata",
        metadataHeaders=["Subject", "From"]
    ).execute()
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    return headers.get("Subject", ""), headers.get("From", ""), msg_id


def archive_alerts(service, message_ids):
    for mid in message_ids:
        service.users().messages().modify(
            userId="me", id=mid,
            body={"removeLabelIds": ["INBOX"]}
        ).execute()
    print(f"  ✓ Archived {len(message_ids)} job alert emails")


def build_digest_html(jobs, date_str, total_raw):
    by_source = {}
    for job in jobs:
        by_source.setdefault(job["source"], []).append(job)

    rows = ""
    for i, job in enumerate(jobs):
        bg = "#ffffff" if i % 2 == 0 else "#f9f9f9"
        rows += f"""
        <tr style="background:{bg};">
          <td style="padding:10px 14px;font-size:14px;color:#1a1a1a;">{job['title']}</td>
          <td style="padding:10px 14px;font-size:14px;color:#444;">{job['company']}</td>
          <td style="padding:10px 14px;font-size:12px;color:#888;">{job['source']}</td>
        </tr>"""

    source_summary = ", ".join(f"{s} ({len(v)})" for s, v in sorted(by_source.items()))

    return f"""<!DOCTYPE html><html><body style="font-family:-apple-system,sans-serif;max-width:700px;margin:0 auto;padding:20px;color:#1a1a1a;">
  <div style="border-bottom:2px solid #1a1a1a;padding-bottom:12px;margin-bottom:24px;">
    <h1 style="margin:0;font-size:22px;">📋 Job Alert Digest</h1>
    <p style="margin:4px 0 0;font-size:14px;color:#666;">{date_str} &nbsp;·&nbsp; {len(jobs)} unique roles from {total_raw} emails &nbsp;·&nbsp; {source_summary}</p>
  </div>
  <table style="width:100%;border-collapse:collapse;border:1px solid #e0e0e0;">
    <thead><tr style="background:#f0f0f0;">
      <th style="padding:10px 14px;text-align:left;font-size:12px;color:#555;text-transform:uppercase;">Role</th>
      <th style="padding:10px 14px;text-align:left;font-size:12px;color:#555;text-transform:uppercase;">Company</th>
      <th style="padding:10px 14px;text-align:left;font-size:12px;color:#555;text-transform:uppercase;">Source</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="margin-top:24px;font-size:12px;color:#aaa;">personal-automation-suite · gmail-cleanup · {len(jobs)} roles · {total_raw} emails archived</p>
</body></html>"""


def send_digest_smtp(html_body, job_count, date_str):
    """Send via SMTP using existing SMTP_USER / SMTP_PASS secrets."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📋 Job Digest: {job_count} roles — {date_str}"
    msg["From"]    = SMTP_USER
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, RECIPIENT_EMAIL, msg.as_string())
    print(f"  ✓ Digest sent to {RECIPIENT_EMAIL}")


def run_digest(archive=True):
    print("\n📋 Job Alert Digest")
    print("=" * 40)
    date_str = datetime.now().strftime("%B %d, %Y")

    service = authenticate()

    print("🔍 Fetching today's job alerts...")
    messages = fetch_todays_job_alerts(service)
    print(f"  Found {len(messages)} job alert emails")

    if not messages:
        print("  Nothing to digest today.")
        return

    print("🔎 Parsing and deduplicating...")
    jobs, seen, message_ids = [], set(), []
    for msg in messages:
        subject, sender, mid = get_message_details(service, msg["id"])
        message_ids.append(mid)
        job = parse_job_from_subject(subject, sender)
        key = (job["title"].lower(), job["company"].lower())
        if key not in seen:
            seen.add(key)
            jobs.append(job)

    print(f"  {len(jobs)} unique roles (from {len(messages)} emails)")

    print("📤 Sending digest via SMTP...")
    html = build_digest_html(jobs, date_str, len(messages))
    send_digest_smtp(html, len(jobs), date_str)

    if archive:
        print("🗄️  Archiving alerts from inbox...")
        archive_alerts(service, message_ids)

    with open("digest_log.json", "w") as f:
        json.dump({"date": date_str, "emails_processed": len(messages),
                   "unique_jobs": len(jobs), "jobs": jobs}, f, indent=2)

    print(f"\n✅ Done! {len(jobs)} jobs digested, {len(messages)} emails archived.")


if __name__ == "__main__":
    import sys
    run_digest(archive="--no-archive" not in sys.argv)
