import json
import os
import re
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE = os.environ.get("BESZEL_URL", "http://beszel:8090").rstrip("/")
USER = os.environ["BESZEL_USER"]
PASSWORD = os.environ["BESZEL_PASSWORD"]
SYSTEM_NAME = os.environ["BESZEL_SYSTEM"]

_token = None
_token_lock = threading.Lock()
_system_id = os.environ["BESZEL_SYSTEM_ID"]


def _request(path, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    req = urllib.request.Request(f"{BASE}{path}", headers=headers)
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def _auth():
    global _token
    body = json.dumps({"identity": USER, "password": PASSWORD}).encode()
    req = urllib.request.Request(
        f"{BASE}/api/collections/users/auth-with-password",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    _token = json.loads(urllib.request.urlopen(req, timeout=10).read())["token"]


def _call(path):
    global _token
    with _token_lock:
        if _token is None:
            _auth()
        try:
            return _request(path, _token)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                _auth()
                return _request(path, _token)
            raise


def _slug(name):
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return s or "unknown"


def _fetch_stats():
    sid = _system_id
    sys_resp = _call(
        f"/api/collections/system_stats/records?filter=system='{sid}'&sort=-created&perPage=1"
    )
    cont_resp = _call(
        f"/api/collections/container_stats/records?filter=system='{sid}'&sort=-created&perPage=1"
    )
    sys_stats = (sys_resp.get("items") or [{}])[0].get("stats", {}) or {}
    cont_list = (cont_resp.get("items") or [{}])[0].get("stats", []) or []

    out = {
        "system": {
            "cpu": sys_stats.get("cpu"),
            "memory": sys_stats.get("mp"),
            "memory_used_gb": sys_stats.get("mu"),
            "memory_total_gb": sys_stats.get("m"),
            "disk": sys_stats.get("dp"),
            "temp_cpu": (sys_stats.get("t") or {}).get("cpu_thermal"),
        },
        "containers": {
            _slug(c.get("n", "")): {
                "name": c.get("n"),
                "cpu": c.get("c", 0),
                "memory": c.get("m", 0),
            }
            for c in cont_list
            if c.get("n")
        },
    }
    return out


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = json.dumps(_fetch_stats()).encode()
            code = 200
        except Exception as e:
            payload = json.dumps({"error": str(e)}).encode()
            code = 500
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a, **kw):
        pass


HTTPServer(("", 8000), H).serve_forever()
