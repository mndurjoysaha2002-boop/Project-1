"""HTTP server for BhumiGate: JSON API + the static dashboard. Standard library only.

    python -m app.server                 # http://127.0.0.1:8000
    python -m app.server --port 9000 --parcels 3000 --host 0.0.0.0

It binds to localhost by default. All data is synthetic.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .service import DEFAULT_PARCELS, DEFAULT_SEED, World

STATIC = Path(__file__).resolve().parent.parent / "static"
MAX_BODY = 64 * 1024
ID_RE = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


class Handler(BaseHTTPRequestHandler):
    world: World = None  # set in main()
    server_version = "BhumiGate/1.0"

    # ---- plumbing ------------------------------------------------------
    def log_message(self, fmt, *args):  # quieter console
        if self.path.startswith("/api/"):
            super().log_message(fmt, *args)

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def _error(self, code: int, msg: str):
        self._json({"error": msg}, code)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("request too large")
        if n == 0:
            return {}
        data = json.loads(self.rfile.read(n).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON object expected")
        return data

    def _ident(self, raw: str) -> str:
        v = unquote(raw)
        if not ID_RE.match(v):
            raise ValueError("bad identifier")
        return v

    # ---- routing --------------------------------------------------------
    def do_GET(self):
        url = urlparse(self.path)
        path, qs = url.path, {k: v[0] for k, v in parse_qs(url.query).items()}
        w = self.world
        try:
            if path.startswith("/api/"):
                return self._get_api(w, path, qs)
            return self._static(path)
        except KeyError:
            self._error(404, "not found")
        except ValueError as e:
            self._error(400, str(e))
        except Exception:  # never leak a traceback to the client
            self.log_error("unhandled error on %s", self.path)
            self._error(500, "internal error")

    def _get_api(self, w: World, path: str, qs: dict):
        if path == "/api/summary":
            return self._json(w.summary())
        if path == "/api/eval":
            return self._json(w.evaluation())
        if path == "/api/scenarios":
            return self._json(w.scenarios())
        if path == "/api/queue":
            return self._json(w.queue(decision=qs.get("decision", ""), code=qs.get("code", ""),
                                      q=qs.get("q", "")[:40], limit=min(int(qs.get("limit", 40)), 200),
                                      offset=max(int(qs.get("offset", 0)), 0)))
        if path == "/api/mutations":
            return self._json(w.mutations())
        if path == "/api/rings":
            return self._json(w.rings())
        if path == "/api/audit":
            return self._json({"entries": w.audit[-100:]})
        if path == "/api/ledger":
            return self._json({"entries": len(w.ledger.entries), "status": w.ledger_status,
                               "head": w.ledger_status.get("head", "")})
        if path == "/api/parcels":
            return self._json(w.find_parcels(qs.get("q", "")[:40]))
        m = re.match(r"^/api/deed/([^/]+)$", path)
        if m:
            return self._json(w.deed_case(self._ident(m.group(1))))
        m = re.match(r"^/api/parcel/([^/]+)$", path)
        if m:
            return self._json(w.parcel(self._ident(m.group(1))))
        raise KeyError(path)

    def do_POST(self):
        path = urlparse(self.path).path
        w = self.world
        try:
            body = self._body()
            if path == "/api/gate":
                return self._json(w.check_draft(body))
            if path == "/api/officer":
                return self._json(w.officer_decision(self._ident(str(body.get("deed_id", ""))),
                                                     str(body.get("action", "")), str(body.get("note", "")),
                                                     str(body.get("officer", ""))))
            if path == "/api/tamper":
                return self._json(w.tamper(str(body.get("kind", "")), self._ident(str(body.get("deed_id", "")))))
            if path == "/api/verify_copy":
                return self._json(w.verify_copy(self._ident(str(body.get("deed_id", ""))),
                                                body.get("changes") or {}))
            if path == "/api/insider":
                return self._json(w.insider_demo())
            raise KeyError(path)
        except KeyError:
            self._error(404, "not found")
        except (ValueError, json.JSONDecodeError) as e:
            self._error(400, str(e))
        except Exception:
            self.log_error("unhandled error on %s", self.path)
            self._error(500, "internal error")

    def _static(self, path: str):
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        if rel.startswith("static/"):
            rel = rel[len("static/"):]
        target = (STATIC / rel).resolve()
        if STATIC.resolve() not in target.parents or not target.is_file():
            raise KeyError(path)
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)


def main():
    ap = argparse.ArgumentParser(description="BhumiGate demo server (synthetic data only)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--parcels", type=int, default=DEFAULT_PARCELS)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    a = ap.parse_args()
    print(f"Generating {a.parcels} synthetic plots (seed {a.seed}) and sealing the ledger ...")
    Handler.world = World(a.parcels, a.seed)
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"BhumiGate ready: http://{a.host}:{a.port}   (all data is synthetic)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
