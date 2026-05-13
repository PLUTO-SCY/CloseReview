import json
import os
import socket
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from db import init_db
from openreview_sync import OpenReviewImportError, save_openreview_thread, sync_openreview_account
from paths import PUBLIC_DIR, ROOT
from repository import (
    create_manual_paper,
    delete_attempt,
    list_activities,
    list_papers,
    merge_papers,
    move_attempt,
    update_paper_title,
)
from utils import extract_forum_id


def load_env_file() -> None:
    for name in (".env.local", ".env"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/papers":
            self.send_json({"papers": list_papers()})
            return
        if parsed.path == "/api/activities":
            self.send_json({"activities": list_activities()})
            return
        if parsed.path == "/":
            self.serve_file(PUBLIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        candidate = (PUBLIC_DIR / parsed.path.lstrip("/")).resolve()
        if PUBLIC_DIR in candidate.parents and candidate.exists():
            content_type = "text/css" if candidate.suffix == ".css" else "application/javascript"
            self.serve_file(candidate, content_type)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            path = PUBLIC_DIR / "index.html"
            content_type = "text/html; charset=utf-8"
        else:
            path = (PUBLIC_DIR / parsed.path.lstrip("/")).resolve()
            content_type = "text/css" if path.suffix == ".css" else "application/javascript"
        if path.exists() and (path == PUBLIC_DIR / "index.html" or PUBLIC_DIR in path.parents):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(path.stat().st_size))
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        try:
            payload = self.read_json()
            if self.path == "/api/openreview/import-url":
                value = payload.get("url") or payload.get("forum_id") or ""
                forum_id = extract_forum_id(value)
                result = save_openreview_thread(forum_id, value)
                self.send_json({"ok": True, **result})
                return
            if self.path == "/api/openreview/sync-account":
                result = sync_openreview_account()
                self.send_json({"ok": True, **result})
                return
            if self.path == "/api/papers/update-title":
                self.send_json({"ok": True, **update_paper_title(payload)})
                return
            if self.path == "/api/papers/merge":
                self.send_json({"ok": True, **merge_papers(payload)})
                return
            if self.path == "/api/attempts/move":
                self.send_json({"ok": True, **move_attempt(payload)})
                return
            if self.path == "/api/attempts/delete":
                self.send_json({"ok": True, **delete_attempt(payload)})
                return
            if self.path == "/api/papers":
                self.send_json({"ok": True, **create_manual_paper(payload)}, HTTPStatus.CREATED)
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except (ValueError, OpenReviewImportError) as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def serve_file(self, path: Path, content_type: str):
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def find_port(preferred: int) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No available local port found from {preferred} to {preferred + 19}.")


def main() -> None:
    load_env_file()
    init_db()
    port = find_port(int(os.environ.get("PORT", "8000")))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"PaperTrail is running at http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()
