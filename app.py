import os
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///logs.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class LogEntry(db.Model):
    __tablename__ = "log_entries"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=False, index=True)
    data = db.Column(db.Text, nullable=False)
    received_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "data": self.data,
            "received_at": self.received_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }


with app.app_context():
    db.create_all()


@app.route("/data", methods=["POST"])
def receive_data():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "JSON body required"}), 400
    user_id = body.get("user_id", "").strip()
    data = body.get("data", "").strip()
    if not user_id or not data:
        return jsonify({"error": "user_id and data are required"}), 400
    entry = LogEntry(user_id=user_id, data=data)
    db.session.add(entry)
    db.session.commit()
    return jsonify({"message": "Stored successfully", "id": entry.id}), 201


@app.route("/data", methods=["GET"])
def get_data():
    user_id = request.args.get("user_id", "").strip()
    if not user_id:
        return jsonify({"error": "user_id query param required"}), 400
    entries = (
        LogEntry.query.filter_by(user_id=user_id)
        .order_by(LogEntry.received_at.desc())
        .all()
    )
    return jsonify({"user_id": user_id, "count": len(entries), "logs": [e.to_dict() for e in entries]})


@app.route("/users", methods=["GET"])
def list_users():
    rows = db.session.query(LogEntry.user_id, db.func.count(LogEntry.id)) \
                     .group_by(LogEntry.user_id).all()
    return jsonify({"users": [{"user_id": r[0], "log_count": r[1]} for r in rows]})


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


if __name__ == "__main__":
    app.run(debug=False)
