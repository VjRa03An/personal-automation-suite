"""
update_tracker.py
-----------------
Scans all subfolders in job-applications/, parses NOTES.md from each,
and writes tracker.html to the personal-automation-suite/ root.

Usage:
  python job-applications/update_tracker.py

Run manually or triggered by Cowork's evening task.
"""

import os, re
from datetime import date, datetime

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))          # job-applications/
REPO_ROOT   = os.path.dirname(SCRIPT_DIR)                         # personal-automation-suite/
OUTPUT      = os.path.join(REPO_ROOT, "tracker.html")

# ── Parse a single NOTES.md ───────────────────────────────────────────────────
def parse_notes(path):
    try:
        text = open(path, encoding="utf-8").read()
    except Exception as e:
        print(f"  ⚠ Could not read {path}: {e}")
        return None

    def field(label):
        m = re.search(rf"{re.escape(label)}:\s*(.+)", text)
        v = m.group(1).strip() if m else ""
        return "" if v.startswith("[") else v   # treat placeholders as empty

    folder = os.path.basename(os.path.dirname(path))
    label  = folder.replace("_", " ")

    # Split company / role from folder name (first token = company words, rest = role)
    parts   = folder.split("_")
    company = parts[0] if parts else folder
    role    = " ".join(parts[1:]) if len(parts) > 1 else ""

    return {
        "folder":   folder,
        "label":    label,
        "company":  company.replace("-", " "),
        "role":     role.replace("_", " "),
        "date":     field("Date Applied"),
        "status":   field("Status") or "Applied",
        "url":      field("Application URL"),
        "followup": field("Follow up if no response by"),
        "confirm":  field("Application ID/Confirmation"),
    }

# ── Collect all applications ──────────────────────────────────────────────────
def collect():
    apps = []
    for name in sorted(os.listdir(SCRIPT_DIR)):
        folder = os.path.join(SCRIPT_DIR, name)
        notes  = os.path.join(folder, "NOTES.md")
        if os.path.isdir(folder) and os.path.exists(notes):
            data = parse_notes(notes)
            if data:
                apps.append(data)
    # Sort: most recent first
    def sort_key(a):
        try:
            return datetime.strptime(a["date"], "%B %d, %Y")
        except:
            return datetime.min
    apps.sort(key=sort_key, reverse=True)
    return apps

# ── Status badge ──────────────────────────────────────────────────────────────
BADGE_STYLES = {
    "Applied":        ("E6F1FB", "0C447C"),
    "Interview":      ("EEEDFE", "3C3489"),
    "Offer Received": ("EAF3DE", "27500A"),
    "Rejected":       ("FCEBEB", "791F1F"),
    "Ghosted":        ("F1EFE8", "444441"),
}

def badge(status):
    bg, fg = BADGE_STYLES.get(status, ("F1EFE8", "444441"))
    return (f'<span style="background:#{bg};color:#{fg};padding:3px 10px;'
            f'border-radius:20px;font-size:11px;font-weight:500;">{status}</span>')

def is_overdue(followup_str):
    if not followup_str:
        return False
    try:
        fu = datetime.strptime(followup_str, "%B %d, %Y").date()
        return fu < date.today()
    except:
        return False

# ── Table row ─────────────────────────────────────────────────────────────────
def table_row(a, i):
    bg  = "#ffffff" if i % 2 == 0 else "#f9fafb"
    url = a["url"]

    jd_cell = (
        f'<a href="{url}" target="_blank" '
        f'style="color:#185FA5;font-size:12px;text-decoration:none;">View JD ↗</a>'
        if url else '<span style="color:#ccc;font-size:12px;">—</span>'
    )

    fu_style = "color:#A32D2D;font-weight:500;" if is_overdue(a["followup"]) else "color:#666;"
    fu_cell  = f'<span style="{fu_style}">{a["followup"] or "—"}</span>'

    return f"""
    <tr style="background:{bg};">
      <td style="padding:11px 14px;font-weight:500;font-size:13px;color:#1a1a1a;">{a["company"]}</td>
      <td style="padding:11px 14px;font-size:13px;color:#555;">{a["role"]}</td>
      <td style="padding:11px 14px;">{jd_cell}</td>
      <td style="padding:11px 14px;font-size:13px;color:#666;">{a["date"] or "—"}</td>
      <td style="padding:11px 14px;">{badge(a["status"])}</td>
      <td style="padding:11px 14px;font-size:13px;">{fu_cell}</td>
    </tr>"""

# ── Stat card ─────────────────────────────────────────────────────────────────
def stat_card(label, value, accent=None):
    color = f"color:{accent};" if accent else ""
    return f"""
    <div style="background:#f3f4f6;border-radius:8px;padding:14px 16px;">
      <div style="font-size:11px;color:#888;margin-bottom:4px;text-transform:uppercase;letter-spacing:.05em;">{label}</div>
      <div style="font-size:24px;font-weight:500;{color}">{value}</div>
    </div>"""

# ── Build full HTML ───────────────────────────────────────────────────────────
def build_html(apps):
    counts = {s: sum(1 for a in apps if a["status"] == s)
              for s in ["Applied", "Interview", "Offer Received", "Rejected", "Ghosted"]}

    stats = (
        stat_card("Total", len(apps)) +
        stat_card("Interviews", counts["Interview"], "#3C3489" if counts["Interview"] else None) +
        stat_card("Offers", counts["Offer Received"], "#27500A" if counts["Offer Received"] else None) +
        stat_card("Rejected", counts["Rejected"]) +
        stat_card("Ghosted", counts["Ghosted"])
    )

    rows   = "".join(table_row(a, i) for i, a in enumerate(apps))
    today  = date.today().strftime("%B %d, %Y")
    empty  = '<tr><td colspan="6" style="text-align:center;padding:32px;color:#aaa;">No applications yet</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Application Tracker — Venkatesh Subramanyam</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #fafafa; color: #1a1a1a; padding: 40px 20px; }}
  .wrap {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ font-size: 20px; font-weight: 500; margin-bottom: 2px; }}
  .sub {{ font-size: 12px; color: #999; margin-bottom: 24px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 10px; margin-bottom: 24px; }}
  .controls {{ display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }}
  .controls input, .controls select {{
    font-size: 13px; padding: 7px 10px; border: 1px solid #e5e7eb;
    border-radius: 6px; background: #fff; color: #1a1a1a; height: 34px; }}
  .controls input {{ flex: 1; min-width: 180px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }}
  th {{ padding: 10px 14px; text-align: left; font-size: 11px; color: #6b7280;
        text-transform: uppercase; letter-spacing: .05em;
        background: #f9fafb; border-bottom: 1px solid #e5e7eb; }}
  tr:last-child td {{ border-bottom: none; }}
  td {{ border-bottom: 1px solid #f3f4f6; }}
  .footer {{ margin-top: 16px; font-size: 11px; color: #ccc; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Job application tracker</h1>
  <p class="sub">Venkatesh Subramanyam &nbsp;·&nbsp; Updated {today} &nbsp;·&nbsp; {len(apps)} applications</p>

  <div class="stats">{stats}</div>

  <div class="controls">
    <input type="text" id="search" placeholder="Search company or role…" oninput="filter()">
    <select id="status-filter" onchange="filter()">
      <option value="">All statuses</option>
      <option>Applied</option>
      <option>Interview</option>
      <option>Offer Received</option>
      <option>Rejected</option>
      <option>Ghosted</option>
    </select>
  </div>

  <table>
    <thead>
      <tr>
        <th>Company</th>
        <th>Role</th>
        <th>JD</th>
        <th>Applied</th>
        <th>Status</th>
        <th>Follow-up</th>
      </tr>
    </thead>
    <tbody id="tbody">
      {rows if apps else empty}
    </tbody>
  </table>

  <p class="footer">personal-automation-suite · auto-generated by update_tracker.py · {today}</p>
</div>

<script>
const rows = document.querySelectorAll('#tbody tr');
function filter() {{
  const q  = document.getElementById('search').value.toLowerCase();
  const sf = document.getElementById('status-filter').value.toLowerCase();
  rows.forEach(r => {{
    const text   = r.textContent.toLowerCase();
    const matchQ = !q  || text.includes(q);
    const matchS = !sf || text.includes(sf);
    r.style.display = matchQ && matchS ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n📊 Job Application Tracker")
    print("=" * 40)
    print(f"  Scanning: {SCRIPT_DIR}")

    apps = collect()
    print(f"  Found {len(apps)} applications\n")

    for a in apps:
        overdue = " ⚠ follow-up overdue" if is_overdue(a["followup"]) else ""
        print(f"  [{a['status']:15}] {a['label']}{overdue}")

    html = build_html(apps)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ tracker.html written to {OUTPUT}")
    print(f"   Open in browser: open {OUTPUT}")
