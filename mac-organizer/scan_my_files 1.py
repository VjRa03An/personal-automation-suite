"""
File Scanner - SAFE MODE (no files are moved or deleted)
Scans Desktop, Downloads, and Documents and creates a report.
"""

import os
import hashlib
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ── Folders to scan ──────────────────────────────────────────────────────────
HOME = Path.home()
SCAN_FOLDERS = [
    HOME / "Desktop",
    HOME / "Downloads",
    HOME / "Documents",
]

# ── Helpers ──────────────────────────────────────────────────────────────────
def file_hash(path, chunk=65536):
    """Return MD5 hash of a file (used to detect true duplicates)."""
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while chunk_data := f.read(chunk):
                h.update(chunk_data)
        return h.hexdigest()
    except (PermissionError, OSError):
        return None

def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"

def mod_time(path):
    return datetime.fromtimestamp(path.stat().st_mtime)

# ── Scan ─────────────────────────────────────────────────────────────────────
print("Scanning… this may take a minute for large folders.\n")

all_files = []
for folder in SCAN_FOLDERS:
    if not folder.exists():
        continue
    for p in folder.rglob("*"):
        if p.is_file() and not p.name.startswith("."):
            all_files.append(p)

# Group by hash to find duplicates
hash_groups = defaultdict(list)
for p in all_files:
    h = file_hash(p)
    if h:
        hash_groups[h].append(p)

duplicates = {h: paths for h, paths in hash_groups.items() if len(paths) > 1}

# ── Build report ─────────────────────────────────────────────────────────────
report_path = HOME / "Desktop" / "file_scan_report.txt"
total_size = sum(p.stat().st_size for p in all_files)

lines = []
lines.append("=" * 60)
lines.append("  FILE SCAN REPORT  —  Safe Mode (nothing was changed)")
lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
lines.append("=" * 60)
lines.append(f"\nTotal files found : {len(all_files):,}")
lines.append(f"Total size        : {human_size(total_size)}")
lines.append(f"Duplicate groups  : {len(duplicates)}")

# Per-folder summary
lines.append("\n── Files per folder ─────────────────────────────────────")
for folder in SCAN_FOLDERS:
    count = sum(1 for p in all_files if str(p).startswith(str(folder)))
    lines.append(f"  {folder.name:<15} {count:>5} files")

# File type breakdown
lines.append("\n── File types ───────────────────────────────────────────")
ext_count = defaultdict(int)
for p in all_files:
    ext_count[p.suffix.lower() or "(no extension)"] += 1
for ext, count in sorted(ext_count.items(), key=lambda x: -x[1])[:20]:
    lines.append(f"  {ext:<20} {count:>5}")

# Duplicate details
if duplicates:
    lines.append("\n── Duplicate files (same content, multiple copies) ──────")
    lines.append("  The NEWEST copy is marked with  ★  (suggested keep)")
    lines.append("")
    dup_size_saved = 0
    for h, paths in sorted(duplicates.items()):
        paths_sorted = sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
        size = paths_sorted[0].stat().st_size
        dup_size_saved += size * (len(paths) - 1)
        lines.append(f"  Group ({human_size(size)} each):")
        for i, p in enumerate(paths_sorted):
            marker = "★ KEEP" if i == 0 else "  copy"
            lines.append(f"    [{marker}]  {p}  (modified {mod_time(p).strftime('%Y-%m-%d')})")
        lines.append("")
    lines.append(f"  Potential space recovered if duplicates removed: {human_size(dup_size_saved)}")
else:
    lines.append("\n── No duplicate files found ─────────────────────────────")

# Large files
lines.append("\n── Largest files (top 15) ───────────────────────────────")
large = sorted(all_files, key=lambda p: p.stat().st_size, reverse=True)[:15]
for p in large:
    lines.append(f"  {human_size(p.stat().st_size):<10}  {p}")

lines.append("\n" + "=" * 60)
lines.append("  END OF REPORT  —  No files were moved, renamed, or deleted.")
lines.append("=" * 60)

report_text = "\n".join(lines)
print(report_text)

with open(report_path, "w") as f:
    f.write(report_text)

print(f"\n✅ Report saved to: {report_path}")
