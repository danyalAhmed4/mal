# LogAPI

Flask + PostgreSQL log ingestion API with a dashboard UI.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/data` | Send a log string |
| GET | `/data?user_id=X` | Fetch logs for a user |
| GET | `/users` | List all users |
| GET | `/` | Dashboard UI |

### POST /data — body
```json
{ "user_id": "umer", "data": "...your log string..." }
```

## Deploy to Render (free)

1. Push this folder to a GitHub repo
2. Go to https://render.com → New → Blueprint
3. Connect your repo — Render reads `render.yaml` automatically
4. It creates the web service + PostgreSQL DB for you
5. Copy your app URL and update `send_log.py`

## Send a log file

```bash
pip install requests
python send_log.py log.txt umer
```

## Local development

```bash
pip install -r requirements.txt
DATABASE_URL=sqlite:///logs.db python app.py
```
