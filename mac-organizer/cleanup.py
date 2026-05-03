#!/usr/bin/env python3
import os
import sys
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from collections import defaultdict

HOME = Path.home()
DESKTOP = HOME / "Desktop"
DOCUMENTS = HOME / "Documents"
TRASH = HOME / ".Trash"
DRY_RUN = "--execute" not in sys.argv

KEEP_BOTH = [
    "scan_my_files.py",
    "scan_my_files 1.py",
    "Venkatesh_Subramanyam_Resume.docx",
]

def log(msg): print(msg)

def to_trash(path):
    dest = TRASH / path.name
    if dest.exists():
        dest = TRASH / f"{path.stem}_{datetime.now().strftime('%H%M%S')}{path.suffix}"
    if DRY_RUN:
        log(f"  [DRY RUN] Would trash: {path}")
    else:
        shutil.move(str(path), str(dest))
        log(f"  Trashed: {path}")

def move_file(src, dest_dir):
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        log(f"  [SKIP] Already exists: {dest}")
        return
    if DRY_RUN:
        log(f"  [DRY RUN] Would move: {src.name} -> {dest_dir}")
    else:
        shutil.move(str(src), str(dest))
        log(f"  Moved: {src.name} -> {dest_dir}")

def file_hash(path):
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except:
        return None

print("\n" + "="*60)
print("  STEP 1: DESKTOP CLEANUP")
print("="*60)

FINANCE_DIR = DOCUMENTS / "03_Finance" / "Taxes"
ARCHIVE_DIR = DOCUMENTS / "05_Archive" / "Old_Desktop"

TRASH_PATTERNS = ["file_scan_report.txt", "configdstate", "MB-Mac-Uninstall-Reinstall", "job-agent.log"]
RENAME_FOLDERS = {"untitled folder 2": "Desktop_Misc_2", "untitled folder": "Desktop_Misc_1"}

for item in DESKTOP.iterdir():
    if item.name in TRASH_PATTERNS:
        print(f"\n  Trashing junk: {item.name}")
        to_trash(item)
    elif item.name == "Google Chrome alias":
        print(f"\n  Trashing duplicate alias: {item.name}")
        to_trash(item)
    elif item.is_dir() and item.name in RENAME_FOLDERS:
        new_name = DESKTOP / RENAME_FOLDERS[item.name]
        if DRY_RUN:
            print(f"\n  [DRY RUN] Would rename: {item.name} -> {RENAME_FOLDERS[item.name]}")
        else:
            item.rename(new_name)
            print(f"\n  Renamed: {item.name} -> {RENAME_FOLDERS[item.name]}")
    elif item.is_file():
        name = item.name.lower()
        if "tax" in name or "ani tax" in name:
            print(f"\n  Moving to Finance: {item.name}")
            move_file(item, FINANCE_DIR)
        elif name.startswith("screenshot") or item.suffix.lower() == ".zip":
            print(f"\n  Moving to Archive: {item.name}")
            move_file(item, ARCHIVE_DIR)

print("\n" + "="*60)
print("  STEP 2: DUPLICATE REMOVAL")
print("="*60)

SCAN_DIRS = [
    DOCUMENTS / "05_Archive",
    DOCUMENTS / "03_Finance",
    DOCUMENTS / "02_Personal",
    DOCUMENTS / "04_AI_Projects",
]

print("\nScanning for duplicates (this may take a minute)...")
hash_map = defaultdict(list)

for scan_dir in SCAN_DIRS:
    if not scan_dir.exists():
        continue
    for fpath in scan_dir.rglob("*"):
        if fpath.is_file() and ".git" not in fpath.parts and fpath.name not in KEEP_BOTH:
            h = file_hash(fpath)
            if h:
                hash_map[h].append(fpath)

dupes_found = 0
space_saved = 0

for h, files in hash_map.items():
    if len(files) < 2:
        continue
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    keep = files[0]
    print(f"\n  KEEP: {keep}")
    for f in files[1:]:
        space_saved += f.stat().st_size
        print(f"    Duplicate: {f}")
        to_trash(f)
        dupes_found += 1

print(f"\n{'='*60}")
print(f"  Duplicates found : {dupes_found}")
print(f"  Space recoverable: {space_saved / 1024 / 1024:.1f} MB")
if DRY_RUN:
    print("\n  DRY RUN - nothing changed.")
    print("  To apply: python3 cleanup.py --execute")
print(f"{'='*60}\n")
