import json
import os
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.environ["KO_TOKEN"]
BASE = "http://kitchenowl:8080/api"


def fetch(path):
    req = urllib.request.Request(
        f"{BASE}{path}", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            body = json.dumps(
                {
                    "recipes": len(fetch("/household/1/recipe")),
                    "groceries": len(fetch("/shoppinglist/1/items")),
                }
            ).encode()
            code = 200
        except Exception as e:
            body = json.dumps({"error": str(e)}).encode()
            code = 500
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a, **kw):
        pass


HTTPServer(("", 8000), H).serve_forever()
