#!/usr/bin/env python3
"""
Job Curation Agent — Daily Scheduler with New/Reposted Flagging
Venkatesh Subramanyam

- NEW jobs: scored by Claude, shown prominently in digest
- REPOSTED jobs: carried forward with original score, shown in a separate section
- ALL jobs: saved to master CSV every run for full history

Setup:
  1. pip install requests feedparser anthropic schedule
  2. Set environment variables:
       export ANTHROPIC_API_KEY=sk-ant-...
       export EMAIL_FROM=you@gmail.com
       export EMAIL_TO=you@gmail.com
       export EMAIL_PASSWORD=your-gmail-app-password
  3. python job_agent_daily.py          # runs on schedule
     python job_agent_daily.py --now    # run immediately
     python job_agent_daily.py --reset  # clear seen-jobs database

Gmail App Password:
  Google Account → Security → 2-Step Verification → App passwords → Mail
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
    "anthropic_key":  _kc("anthropic_key"),
    "email_from":     os.environ.get("EMAIL_FROM", ""),
    "email_to":       os.environ.get("EMAIL_TO", ""),
    "email_password": os.environ.get("EMAIL_PASSWORD", ""),
    "smtp_host":      "smtp.gmail.com",
    "smtp_port":      587,
    "min_score":      6,
    "max_to_score":   40,
    "seen_db":        "seen_jobs.json",
    "master_csv":     "all_jobs_log.csv",
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
leadership. NOT interested in pure individual-contributor PM roles.
"""

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ─────────────────────────────────────────────────────────────
# SEEN JOBS DB
# Schema: { job_id: { "first_seen": "2026-04-24", "score": 7,
#                     "reason": "...", "times_seen": 1 } }
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
    """Split jobs into new, reposted. Attach seen metadata to reposted."""
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
# SCRAPERS
# ─────────────────────────────────────────────────────────────
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def strip_html(text):
    text = re.sub(r'<[^>]+>', ' ', text or '')
    for ent, rep in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&nbsp;',' '),('&#39;',"'"),('&quot;','"')]:
        text = text.replace(ent, rep)
    return re.sub(r'\s+', ' ', text).strip()

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

def scrape_wwr():
    feeds = [
        ("Management & Finance",  "https://weworkremotely.com/categories/remote-management-and-finance-jobs.rss"),
        ("Senior Executive",      "https://weworkremotely.com/categories/remote-senior-executive-jobs.rss"),
        ("Product",               "https://weworkremotely.com/categories/remote-product-jobs.rss"),
        ("Operations",            "https://weworkremotely.com/categories/remote-operations-jobs.rss"),
    ]
    jobs = []
    for name, url in feeds:
        log(f"  WWR → {name}")
        try:
            feed = feedparser.parse(url, request_headers=HEADERS)
            for e in feed.entries:
                title = getattr(e,'title','').strip()
                if not title or len(title) < 4: continue
                desc = strip_html(getattr(e,'summary','') or getattr(e,'description',''))
                jobs.append({'title':title,'company':extract_company(e),'source':'We Work Remotely',
                    'location':'Remote','url':getattr(e,'link','#'),'posted':fmt_date(e),'desc':desc[:400]})
        except Exception as ex: log(f"     ✗ {ex}")
        time.sleep(0.5)
    return jobs

def scrape_indeed():
    queries = [
        "Director Technical Program Management",
        "Director PMO SaaS",
        "Head of Engineering Operations",
        "Director Delivery Management",
        "VP Technical Program Management",
        "Chief of Staff Engineering",
    ]
    jobs = []
    for q in queries:
        url = f"https://www.indeed.com/rss?q={q.replace(' ','+')}&l=&sort=date&limit=20"
        log(f"  Indeed → {q}")
        try:
            feed = feedparser.parse(url, request_headers=HEADERS)
            for e in feed.entries:
                title = getattr(e,'title','').strip()
                if not title: continue
                desc = strip_html(getattr(e,'summary','') or '')
                src = getattr(e,'source',{})
                company = (src.get('title','') if isinstance(src,dict) else '') or extract_company(e)
                loc_m = re.search(r'(?:location|<b>location</b>)[:\s]+([^\n<,]+)', desc, re.I)
                jobs.append({'title':title,'company':company,'source':'Indeed',
                    'location': loc_m.group(1).strip() if loc_m else 'USA',
                    'url':getattr(e,'link','#'),'posted':fmt_date(e),'desc':desc[:400]})
        except Exception as ex: log(f"     ✗ {ex}")
        time.sleep(0.5)
    return jobs

def scrape_remotive():
    jobs = []
    for cat in ['management','product','devops']:
        log(f"  Remotive → {cat}")
        try:
            r = requests.get(f"https://remotive.com/api/remote-jobs?category={cat}&limit=50",
                             headers=HEADERS, timeout=10)
            if r.status_code == 200:
                for j in r.json().get('jobs',[]):
                    jobs.append({'title':j.get('title',''),'company':j.get('company_name',''),
                        'source':'Remotive','location':j.get('candidate_required_location','Remote') or 'Remote',
                        'url':j.get('url','#'),'posted':j.get('publication_date','Recent')[:10],
                        'desc':strip_html(j.get('description',''))[:400]})
        except Exception as ex: log(f"     ✗ {ex}")
        time.sleep(0.3)
    return jobs

def scrape_jobicy():
    log("  Jobicy → director program management")
    jobs = []
    try:
        url = "https://jobicy.com/?feed=job_feed&job_categories=eng-tech&job_types=full-time&search_keywords=director+program+management"
        feed = feedparser.parse(url, request_headers=HEADERS)
        for e in feed.entries:
            title = getattr(e,'title','').strip()
            if not title: continue
            desc = strip_html(getattr(e,'summary','') or '')
            jobs.append({'title':title,'company':extract_company(e),'source':'Jobicy',
                'location':getattr(e,'jobicy_joblocation','Remote'),
                'url':getattr(e,'link','#'),'posted':fmt_date(e),'desc':desc[:400]})
    except Exception as ex: log(f"     ✗ {ex}")
    return jobs

RELEVANCE_KW = ['program','pmo','delivery','operations','engineering','director','vp ',
    'vice president','head of','chief of staff','agile','transformation','technical',
    'portfolio','governance','scrum','release','roadmap','platform','tpmo','epmo']

def is_relevant(job):
    text = (job['title']+' '+job['desc']).lower()
    return any(k in text for k in RELEVANCE_KW)

def deduplicate(jobs):
    seen, out = set(), []
    for j in jobs:
        k = (j['title'].lower()[:50], j['company'].lower()[:25])
        if k not in seen:
            seen.add(k); out.append(j)
    return out

# ─────────────────────────────────────────────────────────────
# CLAUDE SCORING
# ─────────────────────────────────────────────────────────────
def score_job(client, job):
    prompt = f"""Score this job fit 1-10 for the candidate. Reply ONLY with JSON, no markdown.

Candidate:
{PROFILE.strip()}

Job — Title: {job['title']} | Company: {job['company']} | Location: {job['location']}
Description: {job['desc']}

JSON: {{"score": 8, "reason": "One sentence."}}"""
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
    repost_info = ""
    if show_repost_badge:
        times = j.get('times_seen',2)
        first = j.get('first_seen','')
        repost_info = f"""
        <span style="font-size:11px;color:#854F0B;background:#FAEEDA;border:1px solid #FAC775;
          padding:2px 8px;border-radius:20px;font-weight:500;">
          REPOSTED · {times}x seen · first {first}
        </span>"""
    else:
        repost_info = """<span style="font-size:11px;color:#3B6D11;background:#EAF3DE;
          border:1px solid #C0DD97;padding:2px 8px;border-radius:20px;font-weight:500;">NEW</span>"""

    score_display = f"{j['score']}/10" if j.get('score',0) > 0 else "—"
    return f"""
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;
      padding:18px;margin-bottom:12px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
        <div style="min-width:0;">
          <a href="{j['url']}" style="font-size:15px;font-weight:600;color:#111;
            text-decoration:none;">{j['title']}</a>
          <div style="font-size:13px;color:#6b7280;margin-top:3px;">{j['company']}</div>
        </div>
        <span style="flex-shrink:0;background:{bg};color:{fg};border:1px solid {border};
          border-radius:20px;font-size:13px;font-weight:600;padding:4px 12px;">{score_display}</span>
      </div>
      <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
        <span style="font-size:11px;color:#6b7280;background:#f3f4f6;
          padding:2px 8px;border-radius:20px;">{j['source']}</span>
        <span style="font-size:11px;color:#6b7280;background:#f3f4f6;
          padding:2px 8px;border-radius:20px;">{j['location']}</span>
        <span style="font-size:11px;color:#6b7280;background:#f3f4f6;
          padding:2px 8px;border-radius:20px;">{j.get('posted','')}</span>
        {repost_info}
      </div>
      <div style="margin-top:10px;font-size:13px;color:#374151;line-height:1.6;
        border-top:1px solid #f3f4f6;padding-top:10px;">{j.get('reason','')}</div>
      <a href="{j['url']}" style="display:inline-block;margin-top:8px;font-size:12px;
        color:#185FA5;text-decoration:none;">View job →</a>
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
          Reposted — still active ({len(reposted_good)} jobs · no action needed)
        </h2>
        {"".join(job_card_html(j, True) for j in reposted_good)}"""

    watch_section = ""
    if reposted_watch:
        watch_section = f"""
        <details style="margin-top:16px;">
          <summary style="font-size:13px;color:#9ca3af;cursor:pointer;padding:8px 0;">
            Show {len(reposted_watch)} more reposted jobs below threshold
          </summary>
          <div style="margin-top:12px;">
            {"".join(job_card_html(j, True) for j in reposted_watch)}
          </div>
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

  <div style="text-align:center;font-size:11px;color:#9ca3af;margin-top:24px;padding-top:16px;
    border-top:1px solid #e5e7eb;">
    Job Curation Agent · Sources: WWR, Indeed, Remotive, Jobicy · {run_date}
  </div>
</div>
</body></html>"""

def send_email(subject, html_body):
    cfg = CONFIG
    if not all([cfg["email_from"], cfg["email_to"], cfg["email_password"]]):
        log("Email not configured — skipping (set EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD)")
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
def run_agent():
    run_date = datetime.now().strftime("%A, %B %d %Y")
    print(f"\n{'='*60}")
    print(f"  Job Curation Agent — {run_date}")
    print(f"{'='*60}\n")

    client = anthropic.Anthropic(api_key=CONFIG["anthropic_key"])
    seen   = load_seen()
    log(f"Seen DB: {len(seen)} jobs on record\n")

    # 1. Scrape all sources
    log("Scraping sources...")
    raw = scrape_wwr() + scrape_indeed() + scrape_remotive() + scrape_jobicy()
    log(f"\nRaw total: {len(raw)}")

    # 2. Filter + dedup
    relevant = [j for j in raw if is_relevant(j)]
    deduped  = deduplicate(relevant)
    log(f"After filter+dedup: {len(deduped)}")

    # 3. Classify as NEW or REPOSTED
    new_jobs, reposted_jobs = classify_jobs(deduped, seen)
    log(f"New: {len(new_jobs)}  |  Reposted: {len(reposted_jobs)}\n")

    # 4. Score only NEW jobs with Claude
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

    # 5. Update seen DB
    update_seen(new_jobs, reposted_jobs, seen)

    # 6. Separate good vs watch-only
    min_s = CONFIG["min_score"]
    new_good        = sorted([j for j in to_score     if j.get('score',0) >= min_s], key=lambda x: -x['score'])
    reposted_good   = sorted([j for j in reposted_jobs if j.get('score',0) >= min_s], key=lambda x: -x['score'])
    reposted_watch  = sorted([j for j in reposted_jobs if j.get('score',0) < min_s],  key=lambda x: -x.get('score',0))

    # 7. Append everything to master CSV
    all_today = to_score + reposted_jobs
    append_to_master_csv(all_today)

    # 8. Print summary
    print(f"\n{'='*60}")
    print(f"  NEW good matches ({min_s}+): {len(new_good)}")
    print(f"  REPOSTED good matches:      {len(reposted_good)}")
    print(f"{'='*60}\n")
    for j in new_good:
        print(f"  [NEW {j['score']}/10] {j['title']}")
        print(f"    {j['company']} · {j['source']} · {j['location']}")
        print(f"    {j['reason']}\n")
    for j in reposted_good:
        times = j.get('times_seen',2)
        print(f"  [REPOSTED {j['score']}/10 · {times}x seen] {j['title']}")
        print(f"    {j['company']} · first seen {j['first_seen']}\n")

    # 9. Send digest
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
        print("ERROR: ANTHROPIC_API_KEY not set.\n"
              "  export ANTHROPIC_API_KEY=sk-ant-...\n"
              "  Get your key: https://console.anthropic.com/\n")
        sys.exit(1)

    if "--reset" in sys.argv:
        Path(CONFIG["seen_db"]).unlink(missing_ok=True)
        print("Seen-jobs database cleared. Starting fresh next run.\n")
        return

    if "--now" in sys.argv:
        run_agent()
        return

    run_time = CONFIG["run_at"]
    print(f"\nJob Curation Agent — Daily Scheduler")
    print(f"Runs every day at {run_time}  (edit CONFIG['run_at'] to change)")
    print(f"Commands:")
    print(f"  python {sys.argv[0]} --now    run immediately")
    print(f"  python {sys.argv[0]} --reset  clear seen-jobs DB")
    print(f"Press Ctrl+C to stop.\n")

    schedule.every().day.at(run_time).do(run_agent)

    now = datetime.now().strftime("%H:%M")
    if now >= run_time:
        log(f"Already past {run_time} — running now, then daily from tomorrow.")
        run_agent()

    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
