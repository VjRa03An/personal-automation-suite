"""
Job Curation Agent — Daily Scheduler with New/Reposted Flagging
Venkatesh Subramanyam

Target roles: Director TPM, Director PMO, Chief of Staff (R&D/Eng),
              Director Product Operations, VP Technical Program Management

Primary source: LinkedIn Guest API (most reliable for senior niche roles)
Supplementary: WWR, Remotive, Jobicy
"""

import requests, feedparser, anthropic, csv, json, re, time, os, sys
import smtplib, schedule, hashlib
from datetime import datetime
from email.utils import parsedate_to_datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
CONFIG = {
    "run_at":         "08:00",
    "anthropic_key":  os.environ.get("ANTHROPIC_API_KEY", ""),
    "email_from":     os.environ.get("EMAIL_FROM", ""),
    "email_to":       os.environ.get("EMAIL_TO", ""),
    "email_password": os.environ.get("EMAIL_PASSWORD", ""),
    "smtp_host": "smtp.gmail.com",
    "smtp_port":      587,
    "min_score":      6,
    "max_to_score":   40,
    "seen_db":        "/Users/jv/seen_jobs.json",
    "master_csv":     "/Users/jv/all_jobs_log.csv",
}

PROFILE = """
Technical Program Management and PMO executive, 15+ years experience.
Most recently Director of TPMO at Twilio — led $3B R&D portfolio,
2,000+ engineers, 200+ annual releases. Expert in SaaS platform delivery,
Agile/SAFe, cross-functional governance, platform modernization, and
AI-enabled workflow automation. Background at Nokia, Alcatel-Lucent,
Yahoo/Verizon. Strong in stakeholder management, OKR alignment, building
PMO functions from scratch. Targeting Director-level roles at mid-size
companies (500-5000 employees). Open to relocate anywhere. Want roles
leveraging enterprise governance, technical delivery, and transformation
leadership. NOT interested in pure individual-contributor PM or Product Manager roles.
Target roles: Director TPM, Director PMO, Director Technical Program Management,
Chief of Staff R&D/Engineering, Director Product Operations, VP Technical Program Management.
"""

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ─────────────────────────────────────────────────────────────
# SEEN JOBS DB
# ─────────────────────────────────────────────────────────────
def load_seen():
    p = Path(CONFIG["seen_db"])
    if p.exists():
        try: return json.loads(p.read_text())
        except: pass
    return {}

def save_seen(seen):
    Path(CONFIG["seen_db"]).write_text(json.dumps(seen, indent=2))

def job_id(job):
    key = job.get("url","") or f"{job['title']}|{job['company']}"
    return hashlib.md5(key.encode()).hexdigest()

def classify_jobs(jobs, seen):
    new_jobs, reposted_jobs = [], []
    for j in jobs:
        jid = job_id(j)
        j["_id"] = jid
        if jid in seen:
            record = seen[jid]
            j["status"]     = "REPOSTED"
            j["first_seen"] = record.get("first_seen", "unknown")
            j["score"]      = record.get("score", 0)
            j["reason"]     = record.get("reason", "Previously scored.")
            j["times_seen"] = record.get("times_seen", 1) + 1
            reposted_jobs.append(j)
        else:
            j["status"]     = "NEW"
            j["first_seen"] = datetime.now().strftime("%Y-%m-%d")
            j["times_seen"] = 1
            new_jobs.append(j)
    return new_jobs, reposted_jobs

def update_seen(new_jobs, reposted_jobs, seen):
    today = datetime.now().strftime("%Y-%m-%d")
    for j in new_jobs:
        seen[j["_id"]] = {
            "first_seen": today,
            "score":      j.get("score", 0),
            "reason":     j.get("reason", ""),
            "times_seen": 1,
            "title":      j["title"],
            "company":    j["company"],
        }
    for j in reposted_jobs:
        seen[j["_id"]]["times_seen"] = j["times_seen"]
        seen[j["_id"]]["last_seen"]  = today
    save_seen(seen)

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def strip_html(text):
    text = re.sub(r'<[^>]+>', ' ', text or '')
    for ent, rep in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&nbsp;',' '),('&#39;',"'"),('&quot;','"')]:
        text = text.replace(ent, rep)
    return re.sub(r'\s+', ' ', text).strip()

def clean_wwr_title(title):
    """WWR titles are formatted as 'Company: Job Title' — strip the company prefix."""
    if ':' in title:
        parts = title.split(':', 1)
        return parts[1].strip()
    return title.strip()

def fmt_date(entry):
    for f in ['published','updated']:
        v = getattr(entry, f, None)
        if not v: continue
        try:
            d = parsedate_to_datetime(v)
            delta = (datetime.now(d.tzinfo) - d).days
            if delta == 0: return "Today"
            if delta == 1: return "Yesterday"
            if delta < 7: return f"{delta}d ago"
            return d.strftime("%b %d")
        except: pass
    return "Recent"

def extract_company(entry):
    v = getattr(entry, 'author', '')
    if isinstance(v, str) and v.strip(): return v.strip()
    t = getattr(entry, 'title', '')
    m = re.search(r'\bat\s+(.+?)(\s*[-–|(<]|$)', t, re.I)
    return m.group(1).strip() if m else 'Unknown'

# ─────────────────────────────────────────────────────────────
# SCRAPERS
# ─────────────────────────────────────────────────────────────

def scrape_linkedin():
    """
    LinkedIn guest API — no login required.
    HTML structure confirmed from live response:
      - Title:   <h3 class="base-search-card__title">...</h3>
      - Company: <a class="hidden-nested-link" ...>CompanyName</a>  (inside __subtitle h4)
      - URL:     <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/...">
      - Location:<span class="job-search-card__location">...</span>
    f_E=4 = Director, f_E=5 = VP, f_TPR=r86400 = last 24h
    """
    queries = [
        ("Director Technical Program Manager", "f_E=4"),
        ("Director PMO",                        "f_E=4"),
        ("Director Program Management",         "f_E=4"),
        ("Chief of Staff Engineering",          "f_E=4,5"),
        ("Chief of Staff RD",                   "f_E=4,5"),
        ("Director Product Operations",         "f_E=4"),
        ("VP Technical Program Management",     "f_E=5"),
        ("Head of Engineering Operations",      "f_E=4,5"),
        ("Director Technical Delivery",         "f_E=4"),
        ("Director TPMO",                       "f_E=4"),
    ]
    jobs = []
    base = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    for q, seniority in queries:
        encoded = q.replace(' ', '%20')
        url = f"{base}?keywords={encoded}&location=United%20States&{seniority}&f_TPR=r86400&start=0"
        log(f"  LinkedIn → {q}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code == 429:
                log(f"     ✗ LinkedIn rate limited — skipping remaining queries")
                break
            if r.status_code != 200:
                log(f"     ✗ status {r.status_code}")
                continue

            html = r.text

            # Split into individual job cards on <li> boundaries
            cards = re.split(r'(?=<li>)', html)
            found = 0
            for card in cards:
                # Job URL — base-card__full-link href
                url_m = re.search(
                    r'base-card__full-link[^>]*href="(https://www\.linkedin\.com/jobs/view/[^"?]+)',
                    card
                )
                if not url_m:
                    continue

                # Title — inside <h3 class="base-search-card__title">
                title_m = re.search(
                    r'base-search-card__title[^>]*>\s*([^<]{3,120}?)\s*<',
                    card
                )

                # Company — inside hidden-nested-link (first text node after >)
                company_m = re.search(
                    r'hidden-nested-link[^>]*>\s*([^<]{2,80}?)\s*(?:<|\Z)',
                    card
                )

                # Location — inside job-search-card__location
                loc_m = re.search(
                    r'job-search-card__location[^>]*>\s*([^<]{2,80}?)\s*<',
                    card
                )

                job_url = url_m.group(1).strip()
                title   = strip_html(title_m.group(1))   if title_m   else ''
                company = strip_html(company_m.group(1)) if company_m else 'Unknown'
                loc     = strip_html(loc_m.group(1))     if loc_m     else 'USA'

                if not title:
                    continue

                jobs.append({
                    'title':    title,
                    'company':  company,
                    'source':   'LinkedIn',
                    'location': loc,
                    'url':      job_url,
                    'posted':   'Today',
                    'desc':     '',
                })
                found += 1

            log(f"     → {found} jobs extracted")

        except Exception as ex:
            log(f"     ✗ {ex}")
        time.sleep(1.5)

    log(f"  LinkedIn total: {len(jobs)} jobs")
    return jobs

def scrape_wwr():
    feeds = [
        ("Management & Finance", "https://weworkremotely.com/categories/remote-management-and-finance-jobs.rss"),
        ("Senior Executive",     "https://weworkremotely.com/categories/remote-senior-executive-jobs.rss"),
        ("Operations",           "https://weworkremotely.com/categories/remote-operations-jobs.rss"),
    ]
    jobs = []
    for name, url in feeds:
        log(f"  WWR → {name}")
        try:
            feed = feedparser.parse(url, request_headers=HEADERS)
            for e in feed.entries:
                raw_title = getattr(e,'title','').strip()
                if not raw_title or len(raw_title) < 4: continue
                title = clean_wwr_title(raw_title)
                desc = strip_html(getattr(e,'summary','') or getattr(e,'description',''))
                jobs.append({'title':title,'company':extract_company(e),'source':'We Work Remotely',
                    'location':'Remote','url':getattr(e,'link','#'),'posted':fmt_date(e),'desc':desc[:500]})
        except Exception as ex: log(f"     ✗ {ex}")
        time.sleep(0.5)
    return jobs

def scrape_remotive():
    jobs = []
    log("  Remotive → management")
    try:
        r = requests.get("https://remotive.com/api/remote-jobs?category=management&limit=100",
                         headers=HEADERS, timeout=10)
        if r.status_code == 200:
            for j in r.json().get('jobs',[]):
                jobs.append({
                    'title':    j.get('title',''),
                    'company':  j.get('company_name',''),
                    'source':   'Remotive',
                    'location': j.get('candidate_required_location','Remote') or 'Remote',
                    'url':      j.get('url','#'),
                    'posted':   j.get('publication_date','Recent')[:10],
                    'desc':     strip_html(j.get('description',''))[:500],
                })
    except Exception as ex: log(f"     ✗ {ex}")
    return jobs

def scrape_jobicy():
    queries = [
        ("director+technical+program+manager", "Director TPM"),
        ("director+pmo",                       "Director PMO"),
        ("chief+of+staff+engineering",         "Chief of Staff Eng"),
        ("director+product+operations",        "Director Product Ops"),
    ]
    jobs = []
    for kw, label in queries:
        log(f"  Jobicy → {label}")
        try:
            url = f"https://jobicy.com/?feed=job_feed&job_categories=eng-tech&job_types=full-time&search_keywords={kw}"
            feed = feedparser.parse(url, request_headers=HEADERS)
            for e in feed.entries:
                title = getattr(e,'title','').strip()
                if not title: continue
                desc = strip_html(getattr(e,'summary','') or '')
                jobs.append({'title':title,'company':extract_company(e),'source':'Jobicy',
                    'location':getattr(e,'jobicy_joblocation','Remote'),
                    'url':getattr(e,'link','#'),'posted':fmt_date(e),'desc':desc[:500]})
        except Exception as ex: log(f"     ✗ {ex}")
        time.sleep(0.3)
    return jobs

# ─────────────────────────────────────────────────────────────
# RELEVANCE FILTER
# ─────────────────────────────────────────────────────────────
EXCLUDE_TITLE_KW = [
    'product manager', 'product management', 'senior product manager',
    'associate product', 'principal product manager', 'staff product manager',
    'group product manager', 'product owner',
    'software engineer', 'software developer', 'staff engineer',
    'data scientist', 'data engineer', 'machine learning', 'ml engineer',
    'devops engineer', 'site reliability', 'sre ',
    'financial analyst', 'finance analyst', 'accountant', 'controller',
    'recruiter', 'talent acquisition', 'hr ', 'hrbp',
    'sales', 'account executive', 'account manager', 'customer success',
    'marketing', 'designer', 'ux ', 'ui ',
    'business analyst', 'solutions architect', 'solutions engineer',
    'product designer', 'product marketing',
]

SENIORITY_KW = [
    'director', 'senior director', 'sr. director', 'sr director',
    'vp ', 'vp,', 'vice president', 'svp', 'evp',
    'head of', 'chief of staff',
    'senior manager', 'sr. manager',
    'senior technical program', 'senior program manager',
]

TITLE_FUNCTION_KW = [
    'technical program', 'program management', 'program manager',
    'program, r&d', 'program operations',
    'tpm', 'pmo', 'tpmo', 'epmo',
    'delivery management', 'delivery manager',
    'engineering operations', 'engineering program',
    'product operations',
    'portfolio management',
    'chief of staff',
    'transformation',
    'technical delivery',
]

DESC_FUNCTION_KW = [
    'technical program management', 'program management office',
    'tpmo', 'epmo', 'pmo',
    'engineering operations', 'portfolio governance',
    'delivery management', 'cross-functional program',
    'agile transformation', 'r&d portfolio',
]

def is_relevant(job):
    title = job['title'].lower()
    desc  = job.get('desc','').lower()

    if any(k in title for k in EXCLUDE_TITLE_KW):
        return False
    if not any(k in title for k in SENIORITY_KW):
        return False
    if any(k in title for k in TITLE_FUNCTION_KW):
        return True
    if any(k in desc for k in DESC_FUNCTION_KW):
        return True
    return False

def deduplicate(jobs):
    seen, out = set(), []
    for j in jobs:
        k = (j['title'].lower()[:50], j['company'].lower()[:25])
        if k not in seen:
            seen.add(k); out.append(j)
    return out

def debug_filter(raw):
    passing, failing = [], []
    for j in raw:
        (passing if is_relevant(j) else failing).append(j)
    print(f"\n--- PASSING FILTER ({len(passing)}) ---")
    for j in passing:
        print(f"  ✓ {j['title']} @ {j['company']} [{j['source']}]")
    print(f"\n--- FAILING FILTER (sample of {min(len(failing),30)}) ---")
    for j in failing[:30]:
        print(f"  ✗ {j['title']} @ {j['company']} [{j['source']}]")

# ─────────────────────────────────────────────────────────────
# CLAUDE SCORING
# ─────────────────────────────────────────────────────────────
def score_job(client, job):
    prompt = f"""Score this job fit 1-10 for the candidate. Reply ONLY with JSON, no markdown.

Candidate:
{PROFILE.strip()}

Job — Title: {job['title']} | Company: {job['company']} | Location: {job['location']}
Description: {job['desc'] or 'Not available — score based on title and company only.'}

Scoring guide:
- 8-10: Strong match — Director/VP TPM, PMO, Chief of Staff R&D/Eng, Director Product Operations
- 6-7:  Decent match — adjacent senior delivery/program role worth reviewing
- 1-5:  Poor match — Product Manager, IC engineer, finance, sales, or unrelated role

JSON: {{"score": 8, "reason": "One sentence why."}}"""
    try:
        msg = client.messages.create(model="claude-opus-4-5", max_tokens=150,
            messages=[{"role":"user","content":prompt}])
        text = re.sub(r'```json|```','', msg.content[0].text).strip()
        r = json.loads(text)
        return int(r.get('score',5)), r.get('reason','')
    except Exception as e:
        log(f"    Scoring error: {e}")
        return 5, "Could not score."

# ─────────────────────────────────────────────────────────────
# CSV LOGGING
# ─────────────────────────────────────────────────────────────
def append_to_master_csv(jobs):
    path = CONFIG["master_csv"]
    fields = ['date_run','status','times_seen','first_seen','score','title',
              'company','source','location','posted','reason','url']
    exists = Path(path).exists()
    today  = datetime.now().strftime("%Y-%m-%d")
    with open(path, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        if not exists: w.writeheader()
        for j in jobs:
            w.writerow({**j, 'date_run': today})
    log(f"Appended {len(jobs)} rows to {path}")

# ─────────────────────────────────────────────────────────────
# EMAIL DIGEST
# ─────────────────────────────────────────────────────────────
def score_color(s):
    if s >= 8: return "#3B6D11","#EAF3DE","#C0DD97"
    if s >= 6: return "#854F0B","#FAEEDA","#FAC775"
    return "#A32D2D","#FCEBEB","#F7C1C1"

def job_card_html(j, show_repost_badge=False):
    fg,bg,border = score_color(j.get('score',0))
    if show_repost_badge:
        times = j.get('times_seen',2)
        first = j.get('first_seen','')
        badge = f'<span style="font-size:11px;color:#854F0B;background:#FAEEDA;border:1px solid #FAC775;padding:2px 8px;border-radius:20px;font-weight:500;">REPOSTED · {times}x seen · first {first}</span>'
    else:
        badge = '<span style="font-size:11px;color:#3B6D11;background:#EAF3DE;border:1px solid #C0DD97;padding:2px 8px;border-radius:20px;font-weight:500;">NEW</span>'

    score_display = f"{j['score']}/10" if j.get('score',0) > 0 else "—"
    return f"""
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:18px;margin-bottom:12px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
        <div style="min-width:0;">
          <a href="{j['url']}" style="font-size:15px;font-weight:600;color:#111;text-decoration:none;">{j['title']}</a>
          <div style="font-size:13px;color:#6b7280;margin-top:3px;">{j['company']}</div>
        </div>
        <span style="flex-shrink:0;background:{bg};color:{fg};border:1px solid {border};border-radius:20px;font-size:13px;font-weight:600;padding:4px 12px;">{score_display}</span>
      </div>
      <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
        <span style="font-size:11px;color:#6b7280;background:#f3f4f6;padding:2px 8px;border-radius:20px;">{j['source']}</span>
        <span style="font-size:11px;color:#6b7280;background:#f3f4f6;padding:2px 8px;border-radius:20px;">{j['location']}</span>
        <span style="font-size:11px;color:#6b7280;background:#f3f4f6;padding:2px 8px;border-radius:20px;">{j.get('posted','')}</span>
        {badge}
      </div>
      <div style="margin-top:10px;font-size:13px;color:#374151;line-height:1.6;border-top:1px solid #f3f4f6;padding-top:10px;">{j.get('reason','')}</div>
      <a href="{j['url']}" style="display:inline-block;margin-top:8px;font-size:12px;color:#185FA5;text-decoration:none;">View job →</a>
    </div>"""

def build_email_html(new_good, reposted_good, reposted_watch,
                     total_scraped, n_new, n_reposted, run_date):
    new_section = "".join(job_card_html(j, False) for j in new_good) if new_good else \
        '<p style="color:#6b7280;font-size:14px;padding:16px 0;">No new strong matches today.</p>'

    reposted_section = ""
    if reposted_good:
        reposted_section = f"""
        <h2 style="font-size:14px;font-weight:600;color:#854F0B;margin:28px 0 12px;
          padding:10px 14px;background:#FAEEDA;border-radius:8px;border-left:3px solid #FAC775;">
          Reposted — still active ({len(reposted_good)} jobs)
        </h2>{"".join(job_card_html(j, True) for j in reposted_good)}"""

    watch_section = ""
    if reposted_watch:
        watch_section = f"""
        <details style="margin-top:16px;">
          <summary style="font-size:13px;color:#9ca3af;cursor:pointer;padding:8px 0;">
            Show {len(reposted_watch)} more reposted jobs below threshold
          </summary>
          <div style="margin-top:12px;">{"".join(job_card_html(j, True) for j in reposted_watch)}</div>
        </details>"""

    return f"""<!DOCTYPE html><html>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:620px;margin:0 auto;padding:24px 16px;">
  <div style="background:#fff;border-radius:12px;border:1px solid #e5e7eb;padding:24px;margin-bottom:20px;">
    <div style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;">Daily Job Digest</div>
    <h1 style="font-size:20px;font-weight:600;color:#111;margin:0 0 16px;">{run_date}</h1>
    <div style="display:flex;gap:12px;">
      <div style="text-align:center;flex:1;background:#f9fafb;border-radius:8px;padding:12px;">
        <div style="font-size:20px;font-weight:600;color:#111;">{total_scraped}</div>
        <div style="font-size:11px;color:#6b7280;margin-top:2px;">Scraped</div>
      </div>
      <div style="text-align:center;flex:1;background:#EAF3DE;border-radius:8px;padding:12px;">
        <div style="font-size:20px;font-weight:600;color:#3B6D11;">{n_new}</div>
        <div style="font-size:11px;color:#3B6D11;margin-top:2px;">New today</div>
      </div>
      <div style="text-align:center;flex:1;background:#FAEEDA;border-radius:8px;padding:12px;">
        <div style="font-size:20px;font-weight:600;color:#854F0B;">{n_reposted}</div>
        <div style="font-size:11px;color:#854F0B;margin-top:2px;">Reposted</div>
      </div>
      <div style="text-align:center;flex:1;background:#E6F1FB;border-radius:8px;padding:12px;">
        <div style="font-size:20px;font-weight:600;color:#185FA5;">{len(new_good)}</div>
        <div style="font-size:11px;color:#185FA5;margin-top:2px;">Good matches</div>
      </div>
    </div>
  </div>
  <h2 style="font-size:14px;font-weight:600;color:#3B6D11;margin:0 0 12px;
    padding:10px 14px;background:#EAF3DE;border-radius:8px;border-left:3px solid #C0DD97;">
    New jobs — scored today ({len(new_good)} match{'es' if len(new_good)!=1 else ''})
  </h2>
  {new_section}
  {reposted_section}
  {watch_section}
  <div style="text-align:center;font-size:11px;color:#9ca3af;margin-top:24px;padding-top:16px;border-top:1px solid #e5e7eb;">
    Job Curation Agent · Sources: LinkedIn, WWR, Remotive, Jobicy · {run_date}
  </div>
</div>
</body></html>"""

def send_email(subject, html_body):
    cfg = CONFIG
    if not all([cfg["email_from"], cfg["email_to"], cfg["email_password"]]):
        log("Email not configured — skipping")
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = cfg["email_from"]
        msg['To']      = cfg["email_to"]
        msg.attach(MIMEText(html_body, 'html'))
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as s:
            s.starttls()
            s.login(cfg["email_from"], cfg["email_password"])
            s.sendmail(cfg["email_from"], cfg["email_to"], msg.as_string())
        log(f"Email sent → {cfg['email_to']}")
        return True
    except Exception as e:
        log(f"Email error: {e}")
        return False

# ─────────────────────────────────────────────────────────────
# MAIN RUN
# ─────────────────────────────────────────────────────────────
def run_agent(debug=False):
    run_date = datetime.now().strftime("%A, %B %d %Y")
    print(f"\n{'='*60}")
    print(f"  Job Curation Agent — {run_date}")
    print(f"{'='*60}\n")

    client = anthropic.Anthropic(api_key=CONFIG["anthropic_key"])
    seen   = load_seen()
    log(f"Seen DB: {len(seen)} jobs on record\n")

    log("Scraping sources...")
    raw = scrape_linkedin() + scrape_wwr() + scrape_remotive() + scrape_jobicy()
    log(f"\nRaw total: {len(raw)}")

    if debug:
        debug_filter(raw)

    relevant = [j for j in raw if is_relevant(j)]
    deduped  = deduplicate(relevant)
    log(f"After filter+dedup: {len(deduped)}")

    new_jobs, reposted_jobs = classify_jobs(deduped, seen)
    log(f"New: {len(new_jobs)}  |  Reposted: {len(reposted_jobs)}\n")

    to_score = new_jobs[:CONFIG["max_to_score"]]
    if to_score:
        log(f"Scoring {len(to_score)} new jobs with Claude...\n")
        for i, job in enumerate(to_score):
            log(f"[{i+1}/{len(to_score)}] {job['title'][:55]} @ {job['company'][:25]}")
            score, reason = score_job(client, job)
            job.update({'score': score, 'reason': reason})
            log(f"        {score}/10 — {reason[:90]}")
            time.sleep(0.2)
    else:
        log("No new jobs to score today.")

    update_seen(new_jobs, reposted_jobs, seen)

    min_s = CONFIG["min_score"]
    new_good       = sorted([j for j in to_score      if j.get('score',0) >= min_s], key=lambda x: -x['score'])
    reposted_good  = sorted([j for j in reposted_jobs if j.get('score',0) >= min_s], key=lambda x: -x['score'])
    reposted_watch = sorted([j for j in reposted_jobs if j.get('score',0) < min_s],  key=lambda x: -x.get('score',0))

    append_to_master_csv(to_score + reposted_jobs)

    print(f"\n{'='*60}")
    print(f"  NEW good matches ({min_s}+): {len(new_good)}")
    print(f"  REPOSTED good matches:      {len(reposted_good)}")
    print(f"{'='*60}\n")
    for j in new_good:
        print(f"  [NEW {j['score']}/10] {j['title']}")
        print(f"    {j['company']} · {j['source']} · {j['location']}")
        print(f"    {j['reason']}\n")

    n_new_good = len(new_good)
    subj = (f"Job Digest {datetime.now().strftime('%b %d')} — "
            f"{n_new_good} new match{'es' if n_new_good!=1 else ''} 🎯"
            if n_new_good else
            f"Job Digest {datetime.now().strftime('%b %d')} — No new matches today")
    html = build_email_html(new_good, reposted_good, reposted_watch,
                            len(raw), len(new_jobs), len(reposted_jobs), run_date)
    send_email(subj, html)
    log("Run complete.\n")

# ─────────────────────────────────────────────────────────────
# SCHEDULER + CLI
# ─────────────────────────────────────────────────────────────
def main():
    if not CONFIG["anthropic_key"]:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    if "--reset" in sys.argv:
        Path(CONFIG["seen_db"]).unlink(missing_ok=True)
        print("Seen-jobs database cleared.\n")
        return

    debug = "--debug" in sys.argv

    if "--now" in sys.argv:
        run_agent(debug=debug)
        return

    run_time = CONFIG["run_at"]
    print(f"\nJob Curation Agent — runs daily at {run_time}")
    print(f"  --now     run immediately")
    print(f"  --debug   show filter pass/fail for every job")
    print(f"  --reset   clear seen-jobs DB\n")

    schedule.every().day.at(run_time).do(run_agent)
    now = datetime.now().strftime("%H:%M")
    if now >= run_time:
        run_agent(debug=debug)

    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
