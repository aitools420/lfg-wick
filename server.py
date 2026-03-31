#!/usr/bin/env python3
"""lfg.wick.pics — Crypto cliche wall with Telegram shill cannon."""

import json, os, time, urllib.request, urllib.parse
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = int(os.environ.get("PORT", 8896))
DIR = Path(__file__).parent
COUNTS_FILE = DIR / "counts.json"

# WICK announcements bot → WICK community channel
TG_BOT_TOKEN = "8392510530:AAHjJzFdwygfxviKwSrpSXCKJsGN5BwnGZ8"
TG_CHAT_ID = "-1002376855211"

# Rate limiting
GLOBAL_COOLDOWN_S = 30
IP_COOLDOWN_S = 60
last_shill_global = 0
ip_last_shill = {}  # ip -> timestamp


def load_counts():
    if COUNTS_FILE.exists():
        try:
            return json.loads(COUNTS_FILE.read_text())
        except Exception:
            pass
    return {}


def save_counts(counts):
    COUNTS_FILE.write_text(json.dumps(counts, indent=2))


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }).encode()
    req = urllib.request.Request(url, data=data)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.getcode() == 200
    except Exception as e:
        print(f"[TG_ERR] {e}")
        return False


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            html = (DIR / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(html)
        elif self.path == "/api/counts":
            counts = load_counts()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(counts).encode())
        elif self.path == "/favicon.ico":
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.end_headers()
            self.wfile.write(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><text y="28" font-size="28">&#x1F680;</text></svg>')
        else:
            super().do_GET()

    def do_POST(self):
        global last_shill_global
        if self.path == "/api/shill":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length > 0 else {}
            quote = body.get("quote", "").strip()

            if not quote or len(quote) > 200:
                self._json(400, {"ok": False, "error": "Invalid quote"})
                return

            # Rate limit — global
            now = time.time()
            if now - last_shill_global < GLOBAL_COOLDOWN_S:
                left = int(GLOBAL_COOLDOWN_S - (now - last_shill_global))
                self._json(429, {"ok": False, "error": f"Global cooldown: {left}s"})
                return

            # Rate limit — per IP
            ip = self.client_address[0]
            if now - ip_last_shill.get(ip, 0) < IP_COOLDOWN_S:
                left = int(IP_COOLDOWN_S - (now - ip_last_shill.get(ip, 0)))
                self._json(429, {"ok": False, "error": f"Cooldown: {left}s"})
                return

            # Send to Telegram
            msg = f'🚀 <i>"{quote}"</i>\n\n— <a href="https://lfg.wick.pics">lfg.wick.pics</a>'
            ok = send_telegram(msg)
            if ok:
                last_shill_global = now
                ip_last_shill[ip] = now
                # Update counter
                counts = load_counts()
                counts[quote] = counts.get(quote, 0) + 1
                save_counts(counts)
                self._json(200, {"ok": True, "count": counts[quote]})
            else:
                self._json(500, {"ok": False, "error": "Telegram send failed"})
        else:
            self.send_error(404)

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt, *args):
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {fmt % args}")


if __name__ == "__main__":
    print(f"[lfg.wick.pics] Starting on port {PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
