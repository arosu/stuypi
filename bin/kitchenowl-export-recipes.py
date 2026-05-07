#!/home/arosu/venv/bin/python
"""Dump KitchenOwl's recipe export as gzipped JSON to /mnt/ssd/kitchenowl/backups/.

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
import urllib.error
import urllib.request
from datetime import datetime

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

req = urllib.request.Request(URL, headers={"Authorization": f"Bearer {TOKEN}"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode(errors='replace')}", file=sys.stderr)
    sys.exit(1)

os.makedirs(BACKUP_DIR, exist_ok=True)
ts = datetime.now().strftime("%Y%m%dT%H%M%S")
path = os.path.join(BACKUP_DIR, f"kitchenowl-recipes-{ts}.json.gz")

with gzip.open(path, "wt", encoding="utf-8") as gz:
    json.dump(data, gz, ensure_ascii=False)

n = len(data.get("recipes", []))
size = os.path.getsize(path)
print(f"wrote {path} ({n} recipes, {size:,} bytes)")

dumps = sorted(glob.glob(os.path.join(BACKUP_DIR, "kitchenowl-recipes-*.json.gz")))
for old in dumps[:-KEEP]:
    os.remove(old)
    print(f"pruned {old}")
