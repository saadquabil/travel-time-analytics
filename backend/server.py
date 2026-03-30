"""
server.py — HTTP API server for NYC Boulevard Traffic Dashboard.

GET /api/segments   → all segments with travel-time stats & color
GET /api/meta       → summary stats and thresholds
GET /api/health     → {"ok": true}

Data is read from MongoDB (populated by the seed service).
"""

import json, os, time, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", 8765))
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/nyc_traffic")

# ── MongoDB connection ────────────────────────────────────────────────────

from pymongo import MongoClient

_client = None
_db = None


def get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(MONGO_URI)
        _db = _client.get_default_database()
    return _db


def wait_for_mongo(retries=15, delay=2):
    for i in range(retries):
        try:
            db = get_db()
            db.client.admin.command("ping")
            count = db["segments"].count_documents({})
            print(f"  Connected to MongoDB ({count} segments)")
            return
        except Exception:
            print(f"  Waiting for MongoDB... ({i+1}/{retries})")
            _reset_db()
            time.sleep(delay)
    raise RuntimeError("Could not connect to MongoDB")


def _reset_db():
    global _client, _db
    _client = None
    _db = None


# ── Data access ───────────────────────────────────────────────────────────

_data = None


def get_data():
    global _data
    if _data is None:
        db = get_db()
        segments = list(db["segments"].find({}, {"_id": 0}))
        segments.sort(key=lambda s: s["avg_tt"], reverse=True)

        meta_doc = db["meta"].find_one({"_id": "main"})
        if meta_doc:
            meta = meta_doc.get("meta", {})
            thresholds = meta_doc.get("thresholds", [])
        else:
            meta = {}
            thresholds = []

        _data = {
            "segments": segments,
            "meta": meta,
            "thresholds": thresholds,
        }
        print(f"  Loaded {len(segments)} segments from MongoDB")
    return _data


# ── HTTP Handler ──────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print("  " + fmt % args)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/api/segments":
                d = get_data()
                status = qs.get("status", [None])[0]
                segs = d["segments"]
                if status and status != "all":
                    segs = [s for s in segs if s["status"] == status]
                self._json(segs)

            elif path == "/api/meta":
                d = get_data()
                self._json({
                    "meta": d["meta"],
                    "thresholds": d["thresholds"],
                    "segments": [
                        {"id": s["id"], "name": s["name"],
                         "status": s["status"], "color": s["color"],
                         "avg_tt": s["avg_tt"], "avg_speed": s["avg_speed"]}
                        for s in d["segments"]
                    ]
                })

            elif path == "/api/health":
                self._json({"ok": True, "segments": len(get_data()["segments"])})

            else:
                self._err(404, f"Not found: {path}")

        except Exception as exc:
            import traceback; traceback.print_exc()
            self._err(500, str(exc))

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code, msg):
        body = json.dumps({"error": msg}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ── Main ──────────────────────────────────────────────────────────────────

def run():
    print("\n" + "=" * 52)
    print("  NYC · Boulevard Traffic Dashboard — API")
    print("=" * 52)
    wait_for_mongo()
    get_data()
    print(f"\n  API running on http://0.0.0.0:{PORT}\n")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    run()
