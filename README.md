# LogAPI

LogAPI is a Flask dashboard and log storage API designed to run on Render with PostgreSQL. The app stores raw log payloads, parses them into structured sections, and serves a browser dashboard for reviewing stored entries.

## What it does

- Stores raw log text per `user_id`
- Lists stored entries and fetches a user’s logs
- Parses the newest entry or a specific entry by ID into system info, recent files, and browser history
- Serves a dashboard at `/` for browsing the parsed output
- Uses the Render service URL for any outbound self-posting behavior

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/data` | Store a raw log payload |
| GET | `/data?user_id=X` | Fetch stored entries for a user |
| GET | `/users` | List all stored entries |
| GET | `/parse?id=ENTRY_ID` | Parse a specific entry |
| GET | `/parse?user_id=X` | Parse the newest entry for a user |
| GET | `/` | Dashboard UI |

### POST /data request body

```json
{
  "user_id": "umer",
  "data": "...raw log text..."
}
```

### Example parse response

```json
{
  "system_info": {},
  "recent_files": [],
  "browser_history": [],
  "browser_profiles": {},
  "meta": {
    "id": 1,
    "user_id": "umer",
    "received_at": "2026-05-09 08:00:00 UTC"
  }
}
```

## Deploy on Render

This repository is configured as a Render Blueprint in [render.yaml](render.yaml).

1. Push the repository to GitHub
2. In Render, choose New -> Blueprint
3. Connect the repository
4. Render creates the web service and PostgreSQL database automatically
5. The service starts with `gunicorn --bind 0.0.0.0:$PORT app:app`

## Runtime notes

- Render injects `DATABASE_URL` from the managed PostgreSQL database
- Render also provides `RENDER_EXTERNAL_URL`, which the app can use when it needs the public service URL
- `postgres://` connection strings are normalized to `postgresql://` in [app.py](app.py)

## Project files

- [app.py](app.py) contains the Flask app, database model, API routes, parsing logic, and startup helpers
- [templates/dashboard.html](templates/dashboard.html) contains the dashboard UI
- [requirements.txt](requirements.txt) lists the Python dependencies
- [render.yaml](render.yaml) defines the Render deployment blueprint
