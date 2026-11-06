#!/home/arosu/venv/bin/python
"""Dump KitchenOwl's recipe export as gzipped JSON to /mnt/ssd/kitchenowl/backups/.

Skips writing when the export matches the newest dump, so identical copies
don't get uploaded. Touches LAST_EXPORT_FILE on every successful run, which is
what rclone_discord.py checks for staleness.

Keeps the most recent 30 dumps; older ones are deleted.

Usage:
  kitchenowl-export-recipes.py

Override household with HOUSEHOLD_ID=2 in the env.
"""

import glob
import gzip
import json
import os
import re
import sys
import zlib
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

KEEP = 30

ENV_FILE = "/home/arosu/stuypi-services/.env"
if os.path.isfile(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            m = re.match(
                r'\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)\s*=\s*"?([^"\n]*)"?\s*$', line
            )
            if m:
                os.environ.setdefault(m.group(1), m.group(2))

TOKEN = os.environ["KITCHENOWL_TOKEN"]
HOUSEHOLD_ID = os.environ.get("HOUSEHOLD_ID", "1")
URL = f"http://localhost:9926/api/household/{HOUSEHOLD_ID}/export/recipes"
BACKUP_DIR = "/mnt/ssd/kitchenowl/backups"
# Lives outside BACKUP_DIR so rclone never uploads it.
LAST_EXPORT_FILE = "/mnt/ssd/kitchenowl/last-export"


def list_dumps():
    return sorted(glob.glob(os.path.join(BACKUP_DIR, "kitchenowl-recipes-*.json.gz")))


def matches_newest_dump(data):
    dumps = list_dumps()
    if not dumps:
        return False
    try:
        with gzip.open(dumps[-1], "rt", encoding="utf-8") as gz:
            return json.load(gz) == data
    except (OSError, EOFError, ValueError, zlib.error):
        return False


req = urllib.request.Request(URL, headers={"Authorization": f"Bearer {TOKEN}"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode(errors='replace')}", file=sys.stderr)
    sys.exit(1)

os.makedirs(BACKUP_DIR, exist_ok=True)

n = len(data.get("recipes", []))
if matches_newest_dump(data):
    Path(LAST_EXPORT_FILE).touch()
    print(f"unchanged ({n} recipes), skipping dump")
    sys.exit(0)

ts = datetime.now().strftime("%Y%m%dT%H%M%S")
path = os.path.join(BACKUP_DIR, f"kitchenowl-recipes-{ts}.json.gz")

with gzip.open(path, "wt", encoding="utf-8") as gz:
    json.dump(data, gz, ensure_ascii=False)

Path(LAST_EXPORT_FILE).touch()
size = os.path.getsize(path)
print(f"wrote {path} ({n} recipes, {size:,} bytes)")

for old in list_dumps()[:-KEEP]:
    os.remove(old)
    print(f"pruned {old}")
