"""
Installer Cleanup Script
Finds .dmg, .pkg, and .zip installer files in Downloads and Desktop.
Shows you everything BEFORE deleting — you must type YES to confirm.
"""

import os
from pathlib import Path

# ── Folders to scan ──────────────────────────────────────────────────────────
HOME = Path.home()
SCAN_FOLDERS = [
    HOME / "Downloads",
    HOME / "Desktop",
]

# File types considered installers/temp files
INSTALLER_EXTENSIONS = {".dmg", ".pkg", ".download", ".tmp"}

# ── Find installer files ─────────────────────────────────────────────────────
print("\n🔍 Scanning for installer and temporary files...\n")

found = []
for folder in SCAN_FOLDERS:
    if not folder.exists():
        continue
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in INSTALLER_EXTENSIONS:
            size_mb = p.stat().st_size / (1024 * 1024)
            found.append((p, size_mb))

if not found:
    print("✅ No installer files found. Nothing to delete.")
    exit()

# ── Show what will be deleted ────────────────────────────────────────────────
total_mb = sum(size for _, size in found)
print(f"Found {len(found)} installer/temp files taking up {total_mb:.1f} MB:\n")
print(f"  {'SIZE':>10}   FILE")
print(f"  {'-'*10}   {'-'*50}")
for p, size_mb in sorted(found, key=lambda x: -x[1]):
    print(f"  {size_mb:>8.1f} MB   {p}")

print(f"\n  TOTAL: {total_mb:.1f} MB will be freed\n")

# ── Confirm before deleting ──────────────────────────────────────────────────
print("⚠️  These files will be PERMANENTLY DELETED (not moved to Trash).")
print("    If you want to keep any of them, close this window and move them first.\n")
answer = input("    Type YES to confirm deletion, or anything else to cancel: ").strip()

if answer != "YES":
    print("\n❌ Cancelled. No files were deleted.")
    exit()

# ── Delete ───────────────────────────────────────────────────────────────────
print("\nDeleting...\n")
deleted = []
failed = []

for p, size_mb in found:
    try:
        p.unlink()
        print(f"  ✅ Deleted: {p.name}")
        deleted.append((p, size_mb))
    except Exception as e:
        print(f"  ❌ Could not delete: {p.name}  ({e})")
        failed.append(p)

# ── Summary ──────────────────────────────────────────────────────────────────
freed = sum(size for _, size in deleted)
print(f"\n{'='*60}")
print(f"  Done! Deleted {len(deleted)} files, freed {freed:.1f} MB")
if failed:
    print(f"  Could not delete {len(failed)} files (may be in use or protected)")
print(f"{'='*60}\n")
