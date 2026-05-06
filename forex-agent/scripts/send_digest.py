#!/usr/bin/env python3
"""
ForexWatch – Daily USD→INR Digest Script  (hardened v1.1)
Security fixes applied:
  - FIX #4: AI JSON response validated before use (schema + sane value range)
  - FIX #5: Email address validated with Python's email.utils
  - FIX #7: SMTP uses starttls with SSL context; log files are 0600
  - General: no secrets ever printed; safe path handling for log files
"""

import os
import re
import json
import datetime
import smtplib
import ssl
import argparse
import stat
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parseaddr

try:
    import anthropic
except ImportError:
    print("[error] Run: pip install anthropic", file=sys.stderr)
    raise

# ── Config (all from environment — never hardcode secrets) ────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DIGEST_EMAIL      = os.environ.get("DIGEST_EMAIL", "")
TRANSFER_AMOUNT   = float(os.environ.get("TRANSFER_AMOUNT", "1000"))
ALERT_THRESHOLD   = float(os.environ.get("ALERT_THRESHOLD", "0"))
SMTP_HOST         = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT         = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER         = os.environ.get("SMTP_USER", "")
SMTP_PASS         = os.environ.get("SMTP_PASS", "")

RATE_MIN  = 60.0   # sanity bounds for USD/INR
RATE_MAX  = 120.0
MIN_PROVIDERS = 3  # refuse to send if fewer than this come back

SYSTEM_PROMPT = """You are a forex rate intelligence agent.
Search for the current USD to INR mid-market (interbank) exchange rate from
sources like XE.com, Google Finance, Reuters, or Bloomberg.

Return ONLY valid JSON (no markdown, no preamble):
{
  "date": "YYYY-MM-DD",
  "rates": [
    {"provider": "XE.com",       "rate": 95.10, "fee_note": "mid-market rate"},
    {"provider": "Google Finance","rate": 95.12, "fee_note": "mid-market rate"},
    {"provider": "Reuters",      "rate": 95.08, "fee_note": "mid-market rate"}
  ],
  "analysis": "2-3 sentence summary of USD/INR rate and trend"
}"""

# ── FIX #5 — validate email using Python's own parser ────────────────────────
def validate_email(addr: str) -> str:
    """Return the cleaned address or raise ValueError."""
    name, email = parseaddr(addr.strip())
    # Basic structural check
    if not email or "@" not in email:
        raise ValueError(f"Invalid email address: {addr!r}")
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        raise ValueError(f"Invalid email address: {addr!r}")
    return email

# ── FIX #4 — validate AI JSON before trusting it ─────────────────────────────
def validate_rates(data: dict) -> dict:
    """Raise ValueError if the response doesn't meet our expectations."""
    if not isinstance(data, dict):
        raise ValueError("Response is not a JSON object")
    if not isinstance(data.get("rates"), list):
        raise ValueError("Missing 'rates' list in response")
    if len(data["rates"]) < MIN_PROVIDERS:
        raise ValueError(f"Only {len(data['rates'])} providers returned; expected ≥{MIN_PROVIDERS}")

    cleaned = []
    for i, r in enumerate(data["rates"]):
        if not isinstance(r, dict):
            raise ValueError(f"Rate[{i}] is not an object")
        provider = str(r.get("provider", "")).strip()[:60]
        if not provider:
            raise ValueError(f"Rate[{i}] missing provider name")
        rate = r.get("rate")
        if not isinstance(rate, (int, float)) or rate != rate:  # NaN check
            raise ValueError(f"Rate[{i}] rate is not a valid number")
        if not (RATE_MIN <= rate <= RATE_MAX):
            raise ValueError(
                f"Rate[{i}] value {rate} outside plausible range "
                f"[{RATE_MIN}, {RATE_MAX}] for USD/INR"
            )
        cleaned.append({
            "provider": provider,
            "rate":     float(rate),
            "fee_note": str(r.get("fee_note", ""))[:100],
        })

    data["rates"]    = cleaned
    data["analysis"] = str(data.get("analysis", ""))[:500]
    return data

# ── Fetch rates via Claude ────────────────────────────────────────────────────
def fetch_rates() -> dict:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    print("[agent] Fetching USD→INR rates via Claude + web search…")

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        tools=[{"type": "web_search_20260209", "name": "web_search"}],
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": "Fetch current USD to INR rates for all 7 providers. JSON only."
        }]
    )

    # web_search_20260209 returns server_tool_use/tool_result blocks;
    # the final answer is always in the last text block.
    text_blocks = [b.text for b in response.content if hasattr(b, "text") and b.type == "text"]
    raw_text = text_blocks[-1] if text_blocks else ""
    # Strip markdown fences if present
    clean = re.sub(r"```(?:json)?", "", raw_text).strip()

    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise ValueError(f"Agent returned invalid JSON: {e}") from e

    return validate_rates(data)  # FIX #4

# ── Format digest ─────────────────────────────────────────────────────────────
def format_digest(data: dict, amount: float, threshold: float) -> tuple[str, str]:
    rates   = sorted(data["rates"], key=lambda r: r["rate"], reverse=True)
    best    = rates[0]
    date    = data.get("date", datetime.date.today().isoformat())
    receive = amount * best["rate"]

    flag    = "✅" if threshold > 0 and best["rate"] >= threshold else "📊"
    subject = f"{flag} USD→INR Digest · {datetime.date.today().strftime('%a %b %-d')}"

    pad = lambda s, w: s.ljust(w)[:w]
    table = "\n".join(
        f"  {'★' if i==0 else ' '} {pad(r['provider'],20)} ₹{r['rate']:.2f}   {r['fee_note']}"
        for i, r in enumerate(rates)
    )

    alert_line = ""
    if threshold > 0:
        hit = best["rate"] >= threshold
        alert_line = f"\n  {'✅ Rate IS' if hit else '⏳ Not yet'} above your ₹{threshold:.0f} target\n"

    body = (
        f"{'━'*40}\n"
        f"  FOREXWATCH · USD → INR Daily Digest\n"
        f"  {date}\n"
        f"{'━'*40}\n\n"
        f"  BEST RATE TODAY\n"
        f"  ₹{best['rate']:.2f} per $1 via {best['provider']}\n"
        f"  For ${amount:,.0f} → ₹{receive:,.0f}\n"
        f"{alert_line}\n"
        f"  ALL PROVIDERS (best → lowest)\n"
        f"  {'─'*38}\n"
        f"{table}\n"
        f"  {'─'*38}\n\n"
        f"  AGENT INSIGHT\n"
        f"  {data.get('analysis', '')}\n\n"
        f"  {'─'*38}\n"
        f"  💡 Banks (JPMC/BofA) often add $25–$45 wire fees\n"
        f"     on top of less favourable base rates.\n"
        f"  {'─'*38}\n"
        f"  Sent by ForexWatch · Powered by Claude\n"
        f"{'━'*40}"
    )
    return subject, body

# ── FIX #7 — hardened SMTP: explicit SSL context, no legacy fallbacks ─────────
def send_email(to: str, subject: str, body: str) -> None:
    if not SMTP_USER or not SMTP_PASS:
        print("[email] SMTP credentials not set — printing digest to stdout")
        print(f"To: {to}\nSubject: {subject}\n\n{body}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = to
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # FIX #7 — use system CA bundle; verify hostname; require TLS 1.2+
    context = ssl.create_default_context()

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)   # upgrade to TLS before any auth
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [to], msg.as_string())

    print(f"[email] Digest sent to {to}")

# ── Save rate log with restricted permissions ─────────────────────────────────
def save_log(data: dict) -> None:
    os.makedirs("logs", exist_ok=True)
    path = os.path.join(
        "logs",
        f"rates_{datetime.date.today().isoformat()}.json"
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    # FIX #7 — restrict log file to owner read/write only
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    print(f"[log] Rates saved → {path}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="ForexWatch daily digest (hardened)")
    parser.add_argument("--email",     default=DIGEST_EMAIL,    help="Recipient email")
    parser.add_argument("--amount",    type=float, default=TRANSFER_AMOUNT)
    parser.add_argument("--threshold", type=float, default=ALERT_THRESHOLD)
    parser.add_argument("--dry-run",   action="store_true", help="Print digest, skip email")
    args = parser.parse_args()

    # Validate required config — fail loudly rather than silently
    if not ANTHROPIC_API_KEY:
        sys.exit("[error] ANTHROPIC_API_KEY is not set")
    if not args.email:
        sys.exit("[error] Set DIGEST_EMAIL env var or pass --email")

    # FIX #5 — validate email before making any API calls
    try:
        recipient = validate_email(args.email)
    except ValueError as e:
        sys.exit(f"[error] {e}")

    if args.amount <= 0:
        sys.exit("[error] --amount must be a positive number")

    # Fetch & validate
    try:
        data = fetch_rates()
    except (ValueError, json.JSONDecodeError) as e:
        sys.exit(f"[error] Rate fetch failed: {e}")

    save_log(data)

    best_rate = max(r["rate"] for r in data["rates"])
    if args.threshold > 0 and best_rate < args.threshold:
        print(f"[agent] Best rate ₹{best_rate:.2f} below threshold ₹{args.threshold:.2f} — skipping")
        return

    subject, body = format_digest(data, args.amount, args.threshold)
    print(f"\n{body}\n")

    if not args.dry_run:
        try:
            send_email(recipient, subject, body)
        except smtplib.SMTPAuthenticationError:
            sys.exit("[error] SMTP auth failed — check SMTP_USER / SMTP_PASS")
        except smtplib.SMTPException as e:
            sys.exit(f"[error] SMTP error: {e}")

if __name__ == "__main__":
    main()
