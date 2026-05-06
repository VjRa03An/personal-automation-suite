"""
Job Alert Digest  (v2.0 — actionable edition)
==============================================
Improvements over v1:
  1. Clickable job links  — fetches full email body, extracts first job URL
  2. Clean job titles     — tighter regex + fallback cleaning
  3. Location             — parsed from subject / body
  4. Salary               — extracted from body when present
  5. Date posted          — from email receive date
  6. Deduplication        — by (title, company) key as before
  7. Relevance scoring    — Claude Haiku scores each role 1-10
  8. Actionable HTML      — clean table with Apply button per row

Secrets used (matches existing repo pattern):
  SMTP_USER              - your Gmail address
  SMTP_PASS              - your Gmail app password
  DIGEST_EMAIL           - recipient (defaults to SMTP_USER)
  GMAIL_TOKEN_JSON       - Gmail OAuth token JSON
  GMAIL_CREDENTIALS_JSON - Gmail OAuth credentials JSON
  ANTHROPIC_API_KEY      - for relevance scoring (optional)
"""

import os, re, json, smtplib, base64, html as html_lib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

SMTP_USER           = os.environ.get("SMTP_USER", "")
SMTP_PASS           = os.environ.get("SMTP_PASS", "")
RECIPIENT_EMAIL     = os.environ.get("DIGEST_EMAIL", SMTP_USER)
ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")

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

# ── Auth ──────────────────────────────────────────────────────────────────────
def authenticate():
    creds = None
    token_json = os.environ.get("GMAIL_TOKEN_JSON")
    creds_json = os.environ.get("GMAIL_CREDENTIALS_JSON")

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


# ── Fetch ─────────────────────────────────────────────────────────────────────
def fetch_todays_job_alerts(service):
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y/%m/%d")
    query = f"({SENDER_QUERY}) after:{since} in:inbox"
    results = service.users().messages().list(userId="me", q=query, maxResults=200).execute()
    return results.get("messages", [])


# ── Parse subject → title / company ──────────────────────────────────────────
def parse_job_from_subject(subject):
    s = subject.strip()

    patterns = [
        # "Title at Company"
        (r"^(.+?)\s+at\s+([A-Z][^,]+?)(?:\s*[-|,].*)?$", 1, 2, "LinkedIn"),
        # "Company is hiring for Title. N more..."
        (r"^(.+?)\s+is hiring for\s+(.+?)\.\s+\d+", 2, 1, "Indeed"),
        # "Company is hiring for Title" (SimplyHired / Jobright)
        (r'^(.+?)\s+is hiring for\s+["\u201c]?(.+?)["\u201d]?$', 2, 1, "SimplyHired"),
        # LinkedIn PMO: '"Keyword": Company - Title posted on...'
        (r'^"[^"]+": (.+?) - (.+?) posted on', 2, 1, "LinkedIn"),
        # "New jobs for Title in Location"
        (r"^New jobs? for (.+?) in (.+)$", 1, None, "Indeed"),
        # "X new Title jobs"
        (r"^\d+ new (.+?) jobs?", 1, None, "Job Alert"),
    ]

    for pattern, title_g, company_g, source in patterns:
        m = re.match(pattern, s, re.IGNORECASE)
        if m:
            title   = m.group(title_g).strip() if title_g else s[:80]
            company = m.group(company_g).strip() if company_g else "Various"
            # Skip if title looks like a subject line artifact
            if len(title) > 5 and not title.lower().startswith("your top"):
                return {"title": title, "company": company, "source": source}

    # Fallback: clean up subject as best we can
    cleaned = re.sub(r"\s*[-|]\s*.*$", "", s).strip()
    if len(cleaned) > 5:
        return {"title": cleaned[:80], "company": "Various", "source": "Job Alert"}
    return None  # skip unparseable subjects


# ── Extract URL + metadata from email body ────────────────────────────────────
def extract_body_text(payload):
    """Recursively extract plain text or HTML from email payload."""
    if payload.get("body", {}).get("data"):
        data = payload["body"]["data"]
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
    for part in payload.get("parts", []):
        text = extract_body_text(part)
        if text:
            return text
    return ""


def extract_job_url(body_text):
    """Extract the first meaningful job application URL from email body."""
    # Prefer direct apply / view job links
    priority_patterns = [
        r'https?://[^\s"<>]+(?:apply|viewjob|jobs?/view|job-detail|position)[^\s"<>]*',
        r'https?://(?:www\.)?(?:indeed|linkedin|simplyhired|jobright)\.(?:com|ai)/[^\s"<>]+',
        r'https?://[^\s"<>]{20,150}',
    ]
    for pattern in priority_patterns:
        matches = re.findall(pattern, body_text, re.IGNORECASE)
        # Filter out unsubscribe / tracking pixel URLs
        for url in matches:
            if not any(x in url.lower() for x in ["unsubscribe", "pixel", "track", "open?", "click?"]):
                return url.rstrip(".,;)")
    return None


def extract_salary(body_text):
    """Extract salary range if present."""
    m = re.search(r'\$[\d,]+(?:K)?(?:\s*[-–]\s*\$[\d,]+(?:K)?)?(?:\s*/\s*(?:yr|year|hr|hour))?', body_text)
    if m:
        return m.group(0).strip()
    m = re.search(r'([\d,]+(?:K)?)\s*[-–]\s*([\d,]+(?:K)?)\s*/?\s*(?:yr|year)', body_text, re.IGNORECASE)
    if m:
        return f"${m.group(1)}–${m.group(2)}/yr"
    return None


def extract_location(subject, body_text):
    """Extract location from subject or body."""
    # From subject: "Title in City, ST" or "jobs in City"
    m = re.search(r'\bin\s+([A-Z][a-zA-Z\s]+(?:,\s*[A-Z]{2})?)', subject)
    if m:
        loc = m.group(1).strip()
        if len(loc) > 2:
            return loc
    # Remote keyword
    if re.search(r'\bremote\b', subject + " " + body_text[:500], re.IGNORECASE):
        return "Remote"
    return None


# ── Claude Haiku scoring ──────────────────────────────────────────────────────
def score_jobs_with_claude(jobs):
    """Use Claude Haiku to score each job 1-10 for relevance."""
    if not ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY:
        print("  ⚠ Skipping scoring (no Anthropic API key)")
        for job in jobs:
            job["score"] = None
        return jobs

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    job_list = "\n".join(
        f"{i+1}. {j['title']} at {j['company']}" + (f" ({j.get('location','')})" if j.get('location') else "")
        for i, j in enumerate(jobs)
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"""Score each job 1-10 for a senior technical professional (engineering/product/program management background).
Higher = more senior, strategic, well-known company, or interesting role.
Lower = junior, vague title, unknown company.

Jobs:
{job_list}

Return ONLY a JSON array of integers matching the order above. Example: [8,5,7,...]"""
            }]
        )
        text = response.content[0].text.strip()
        clean = re.sub(r"```(?:json)?", "", text).strip()
        scores = json.loads(clean)
        for i, job in enumerate(jobs):
            job["score"] = scores[i] if i < len(scores) else None
    except Exception as e:
        print(f"  ⚠ Scoring failed: {e}")
        for job in jobs:
            job["score"] = None

    return jobs


# ── Build HTML digest ─────────────────────────────────────────────────────────
def build_digest_html(jobs, date_str, total_raw):
    # Sort by score descending (None last)
    jobs_sorted = sorted(jobs, key=lambda j: j.get("score") or 0, reverse=True)

    by_source = {}
    for job in jobs:
        by_source.setdefault(job["source"], []).append(job)

    rows = ""
    for i, job in enumerate(jobs_sorted):
        bg = "#ffffff" if i % 2 == 0 else "#f9f9f9"
        url     = job.get("url")
        salary  = job.get("salary", "")
        loc     = job.get("location", "")
        score   = job.get("score")
        date    = job.get("date", "")

        title_cell = f'<a href="{html_lib.escape(url)}" style="color:#1a56db;text-decoration:none;font-weight:500;">{html_lib.escape(job["title"])}</a>' \
                     if url else html_lib.escape(job["title"])

        apply_btn = f'<a href="{html_lib.escape(url)}" style="display:inline-block;padding:5px 12px;background:#1a56db;color:#fff;border-radius:4px;text-decoration:none;font-size:12px;font-weight:600;">Apply →</a>' \
                    if url else '<span style="color:#ccc;font-size:12px;">No link</span>'

        score_badge = f'<span style="display:inline-block;padding:2px 7px;border-radius:10px;font-size:11px;font-weight:700;background:{"#dcfce7;color:#166534" if (score or 0) >= 7 else "#fef9c3;color:#854d0e" if (score or 0) >= 4 else "#fee2e2;color:#991b1b"};">{score}/10</span>' \
                      if score else ""

        meta = " · ".join(filter(None, [loc, salary, date]))

        rows += f"""
        <tr style="background:{bg};">
          <td style="padding:10px 14px;">
            <div style="font-size:14px;">{title_cell}</div>
            {f'<div style="font-size:11px;color:#888;margin-top:3px;">{html_lib.escape(meta)}</div>' if meta else ""}
          </td>
          <td style="padding:10px 14px;font-size:14px;color:#444;">{html_lib.escape(job['company'])}</td>
          <td style="padding:10px 14px;font-size:12px;color:#888;">{html_lib.escape(job['source'])}</td>
          <td style="padding:10px 14px;text-align:center;">{score_badge}</td>
          <td style="padding:10px 14px;text-align:center;">{apply_btn}</td>
        </tr>"""

    source_summary = ", ".join(f"{s} ({len(v)})" for s, v in sorted(by_source.items()))
    scored_count = sum(1 for j in jobs if j.get("score"))

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:800px;margin:0 auto;padding:20px;color:#1a1a1a;background:#fafafa;">
  <div style="background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.1);padding:24px;">
    <div style="border-bottom:2px solid #1a1a1a;padding-bottom:12px;margin-bottom:24px;">
      <h1 style="margin:0;font-size:22px;">📋 Job Alert Digest</h1>
      <p style="margin:4px 0 0;font-size:13px;color:#666;">{date_str} &nbsp;·&nbsp; {len(jobs)} unique roles from {total_raw} emails &nbsp;·&nbsp; {source_summary}</p>
      {f'<p style="margin:4px 0 0;font-size:12px;color:#888;">✨ AI-scored {scored_count} roles for relevance</p>' if scored_count else ""}
    </div>
    <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;">
      <thead>
        <tr style="background:#f3f4f6;">
          <th style="padding:10px 14px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;">Role</th>
          <th style="padding:10px 14px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;">Company</th>
          <th style="padding:10px 14px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;">Source</th>
          <th style="padding:10px 14px;text-align:center;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;">Score</th>
          <th style="padding:10px 14px;text-align:center;font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.05em;">Action</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    <p style="margin-top:20px;font-size:11px;color:#9ca3af;">personal-automation-suite · gmail-cleanup · {len(jobs)} roles · {total_raw} emails archived</p>
  </div>
</body></html>"""


# ── SMTP send ─────────────────────────────────────────────────────────────────
def send_digest_smtp(html_body, job_count, date_str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📋 Job Digest: {job_count} roles — {date_str}"
    msg["From"]    = SMTP_USER
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, RECIPIENT_EMAIL, msg.as_string())
    print(f"  ✓ Digest sent to {RECIPIENT_EMAIL}")


# ── Archive ───────────────────────────────────────────────────────────────────
def archive_alerts(service, message_ids):
    for mid in message_ids:
        service.users().messages().modify(
            userId="me", id=mid,
            body={"removeLabelIds": ["INBOX"]}
        ).execute()
    print(f"  ✓ Archived {len(message_ids)} job alert emails")


# ── Main ──────────────────────────────────────────────────────────────────────
def run_digest(archive=True):
    print("\n📋 Job Alert Digest v2.0")
    print("=" * 40)
    date_str = datetime.now().strftime("%B %d, %Y")

    service = authenticate()

    print("🔍 Fetching today's job alerts...")
    messages = fetch_todays_job_alerts(service)
    print(f"  Found {len(messages)} job alert emails")

    if not messages:
        print("  Nothing to digest today.")
        return

    print("🔎 Parsing emails (full body for links)...")
    jobs, seen, message_ids = [], set(), []

    for msg in messages:
        # Fetch full message to get body + headers
        full_msg = service.users().messages().get(
            userId="me", id=msg["id"], format="full"
        ).execute()

        headers  = {h["name"]: h["value"] for h in full_msg["payload"]["headers"]}
        subject  = headers.get("Subject", "").strip()
        date_hdr = headers.get("Date", "")
        message_ids.append(msg["id"])

        job = parse_job_from_subject(subject)
        if not job:
            continue

        key = (job["title"].lower(), job["company"].lower())
        if key in seen:
            continue
        seen.add(key)

        # Extract body for URL, salary, location
        body_text = extract_body_text(full_msg["payload"])
        job["url"]      = extract_job_url(body_text)
        job["salary"]   = extract_salary(body_text)
        job["location"] = extract_location(subject, body_text)

        # Parse date
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_hdr)
            job["date"] = dt.strftime("%b %d")
        except Exception:
            job["date"] = ""

        jobs.append(job)

    print(f"  {len(jobs)} unique roles (from {len(messages)} emails)")

    print("🤖 Scoring roles with Claude Haiku...")
    jobs = score_jobs_with_claude(jobs)

    print("📤 Sending digest via SMTP...")
    html = build_digest_html(jobs, date_str, len(messages))
    send_digest_smtp(html, len(jobs), date_str)

    if archive:
        print("🗄️  Archiving alerts from inbox...")
        archive_alerts(service, message_ids)

    with open("digest_log.json", "w") as f:
        json.dump({
            "date": date_str,
            "emails_processed": len(messages),
            "unique_jobs": len(jobs),
            "jobs": [{k: v for k, v in j.items()} for j in jobs]
        }, f, indent=2)

    print(f"\n✅ Done! {len(jobs)} jobs digested, {len(messages)} emails archived.")


if __name__ == "__main__":
    import sys
    run_digest(archive="--no-archive" not in sys.argv)
