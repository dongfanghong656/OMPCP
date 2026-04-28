#!/usr/bin/env python
from __future__ import annotations

import argparse
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def safe_name(value: str) -> str:
    name = Path(value).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    if not name:
        name = "download.bin"
    return name


def make_handler(out_dir: Path, token: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # noqa: A003
            return

        def do_POST(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            if params.get("token", [""])[0] != token:
                self.send_response(403)
                self.end_headers()
                return
            if parsed.path != "/save":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length") or "0")
            if length <= 0:
                self.send_response(400)
                self.end_headers()
                return
            filename = safe_name(params.get("name", ["download.bin"])[0])
            target = out_dir / filename
            data = self.rfile.read(length)
            target.write_bytes(data)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(str(target).encode("utf-8"))

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(out_dir, args.token))
    server.serve_forever()


if __name__ == "__main__":
    main()
