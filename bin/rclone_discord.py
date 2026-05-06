#!/home/arosu/venv/bin/python

import os
import glob
import re
import requests
from datetime import datetime

# --- CONFIG ---
# Load .env so this script works under cron without a sourced shell.
ENV_FILE = "/home/arosu/stuypi-services/.env"
if os.path.isfile(ENV_FILE):
    with open(ENV_FILE) as _f:
        for _line in _f:
            _m = re.match(
                r'\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)\s*=\s*"?([^"\n]*)"?\s*$', _line
            )
            if _m:
                os.environ.setdefault(_m.group(1), _m.group(2))

WEBHOOK_URL = os.environ["RCLONE_DISCORD_WEBHOOK_URL"]
KUMA_PUSH_URL = os.environ["KUMA_PUSH_URL_BACKBLAZE"]
LOG_DIR = "/home/arosu/logs/backblaze-rclone-sync/"


def send_to_discord(title: str, fields: str, color: int) -> None:
    payload = {
        "username": "bot",
        "embeds": [
            {
                "title": title,
                "color": color,
                "fields": fields,
                "timestamp": datetime.utcnow().isoformat(),
            }
        ],
    }
    requests.post(WEBHOOK_URL, json=payload)


def push_kuma(status: str, msg: str) -> None:
    try:
        requests.get(
            KUMA_PUSH_URL,
            params={"status": status, "msg": msg, "ping": ""},
            timeout=10,
        )
    except requests.RequestException:
        pass


def main():
    today_str = datetime.now().strftime("%Y%m%d")
    log_pattern = os.path.join(LOG_DIR, f"auto-{today_str}*.log")
    matching_files = glob.glob(log_pattern)

    if not matching_files:
        push_kuma("down", f"missing log for {today_str}")
        return

    latest_file = max(matching_files, key=os.path.getctime)
    with open(latest_file, "r") as f:
        log_content = f.read()

    sections = re.split(r"\[\d{2}:\d{2}:\d{2}\] STARTING SYNC:", log_content)
    embed_fields = []
    total_changes = 0
    has_errors = "ERROR" in log_content

    for section in sections[1:]:
        bucket_name = re.search(r"-> ([\w-]+)", section).group(1)
        new = len(re.findall(r": Copied \(new\)", section))
        deleted = len(re.findall(r": Deleted", section))

        if new > 0 or deleted > 0:
            total_changes += new + deleted

            # ANSI Color Codes:
            # [32m is Green, [31m is Red, [0m is Reset
            # This looks like: +1 (green) / -0 (red)
            ansi_stats = f"```ansi\n\u001b[32m+{new}\u001b[0m / \u001b[31m-{deleted}\u001b[0m\n```"

            embed_fields.append(
                {"name": bucket_name, "value": ansi_stats, "inline": True}
            )

    if has_errors:
        push_kuma("down", f"rclone errors detected: {latest_file}")
    else:
        if total_changes > 0:
            send_to_discord("✅ Sync Successful", embed_fields, 3066993)
        push_kuma("up", "OK")


if __name__ == "__main__":
    main()
