"""
Client script — reads your log file and sends it to the API.
Usage:  python send_log.py log.txt umer
"""
import sys
import requests

API_URL = "https://YOUR-APP.onrender.com/data"   # <-- replace after deploy

def send(filepath: str, user_id: str):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    resp = requests.post(API_URL, json={"user_id": user_id, "data": content})
    if resp.status_code == 201:
        print(f"[OK] Stored as entry #{resp.json()['id']}")
    else:
        print(f"[ERR] {resp.status_code}: {resp.text}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python send_log.py <file> <user_id>")
        sys.exit(1)
    send(sys.argv[1], sys.argv[2])
