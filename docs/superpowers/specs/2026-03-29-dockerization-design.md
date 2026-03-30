# NYC Boulevard Traffic Dashboard — Dockerization Design

## Context

The project is a full-stack traffic analysis dashboard showing travel time data for NYC boulevards. It currently works as:

- **Frontend**: Single `index.html` (vanilla HTML/CSS/JS, Leaflet map, Chart.js graphs)
- **Backend**: Python `http.server` serving frontend files + 3 JSON API endpoints
- **Data pipeline**: `traffic.csv` (5460 rows) → `build_segments.py` → `segments.json` (16 pre-calculated segments) → backend reads JSON at startup

Goal: Dockerize the entire project with MongoDB, keeping it simple and suitable for an academic demonstration.

## Architecture

```
Browser :3000
    │
    ▼
frontend (Nginx) ── serves index.html, proxies /api/* to backend
    │
    ▼
backend (Python) :8765 ── API only, reads from MongoDB
    │
    ▼
mongo (MongoDB) :27017 ── stores segments + meta data

seed (Python, one-shot) ── CSV → compute segments → insert into MongoDB
```

**4 Docker services:**
- `mongo` — persistent, stores data
- `backend` — persistent, API server
- `frontend` — persistent, Nginx serving static files + reverse proxy
- `seed` — ephemeral, runs once to import data then exits

## File Structure

```
nyc_v4/
├── frontend/
│   ├── index.html          (unchanged)
│   ├── nginx.conf          (NEW — proxy config)
│   └── Dockerfile          (NEW — Nginx image)
├── backend/
│   ├── server.py           (MODIFIED — reads MongoDB instead of JSON file)
│   ├── Dockerfile          (NEW)
│   └── requirements.txt    (NEW — pymongo)
├── seed/
│   ├── seed.py             (NEW — CSV → MongoDB import)
│   ├── Dockerfile          (NEW)
│   └── requirements.txt    (NEW — pymongo)
├── data/
│   ├── traffic.csv         (unchanged, source data)
│   └── build_segments.py   (unchanged, kept as reference)
├── docker-compose.yml      (NEW)
├── .env.example            (NEW)
├── .dockerignore           (NEW)
├── run.py                  (unchanged, non-Docker entrypoint)
└── README.md               (NEW)
```

## Service Details

### mongo

- Image: `mongo:7`
- Port: 27017 (exposed for debugging)
- Volume: `mongo_data` for persistence
- Database name: `nyc_traffic`
- No authentication (academic project)

### frontend

- Image: Nginx Alpine
- Port: 3000 (user-facing)
- `nginx.conf`: serves `/` → `index.html`, proxies `/api/*` → `http://backend:8765/api/*`
- No changes to `index.html` — it already fetches `/api/meta` and `/api/segments` with relative URLs, which Nginx will proxy transparently

### backend

- Image: Python 3.11 slim
- Port: 8765 (internal, also exposed for debugging)
- Dependencies: `pymongo`
- Modifications to `server.py`:
  - `get_data()` reads from MongoDB instead of `segments.json`
  - Retry loop at startup to wait for MongoDB readiness
  - Removes static file serving (frontend handles that now)
  - All API endpoints (`/api/segments`, `/api/meta`, `/api/health`) keep identical response format
- Environment: `MONGO_URI=mongodb://mongo:27017/nyc_traffic`

### seed

- Image: Python 3.11 slim
- One-shot container (runs then exits)
- Mounts `./data` as read-only volume
- `seed.py` logic:
  1. Read `traffic.csv`
  2. Parse and validate GPS points (same logic as `build_segments.py`)
  3. Calculate segment stats (avg_tt, avg_speed, min/max, percentiles, status, color)
  4. Calculate meta and thresholds
  5. Upsert segments into `segments` collection (keyed by `id` to avoid duplicates)
  6. Upsert meta/thresholds into `meta` collection
  7. Exit
- Idempotent: can be re-run safely with `docker compose run seed`
- Environment: `MONGO_URI=mongodb://mongo:27017/nyc_traffic`

## MongoDB Collections

### `segments` collection

Each document = one road segment (16 total). Fields match the current `segments.json` structure exactly:

```json
{
  "id": "4616328",
  "name": "FDR N Catherine Slip - 25th St",
  "pts": [[40.71141, -73.97866], ...],
  "n_pts": 13,
  "avg_speed": 8.07,
  "avg_tt": 1198.0,
  "min_tt": 1198.0,
  "max_tt": 1198.0,
  "p10_tt": 1198.0,
  "p90_tt": 1198.0,
  "n_samples": 1,
  "status": "critical",
  "color": "#ff3b3b",
  "weight": 6.5
}
```

### `meta` collection

Single document containing summary stats and thresholds:

```json
{
  "_id": "main",
  "meta": { "total": 16, "tt_min": 54.0, "tt_max": 1198.0, "tt_mean": 433.2, "tt_median": 362.0 },
  "thresholds": [
    { "label": "free", "color": "#22d07a", "max_tt": 200, "count": 3 },
    ...
  ]
}
```

## docker-compose.yml

```yaml
services:
  mongo:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    environment:
      MONGO_INITDB_DATABASE: nyc_traffic

  seed:
    build: ./seed
    volumes:
      - ./data:/data:ro
    depends_on:
      - mongo
    environment:
      MONGO_URI: mongodb://mongo:27017/nyc_traffic

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports:
      - "8765:8765"
    depends_on:
      mongo:
        condition: service_started
      seed:
        condition: service_completed_successfully
    environment:
      MONGO_URI: mongodb://mongo:27017/nyc_traffic

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  mongo_data:
```

## What Changes, What Doesn't

| File | Change |
|------|--------|
| `frontend/index.html` | NONE |
| `data/traffic.csv` | NONE |
| `data/build_segments.py` | NONE (kept as reference) |
| `run.py` | NONE (still works for non-Docker usage) |
| `backend/server.py` | MODIFIED: `get_data()` reads MongoDB; static file serving removed |

## Usage

```bash
# Start everything
docker compose up --build

# Access dashboard
open http://localhost:3000

# Re-import data
docker compose run seed

# Stop
docker compose down

# Stop and delete data
docker compose down -v
```
