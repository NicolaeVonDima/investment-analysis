## 2025-12-13 — v1.1.0 — Watchlists with Global Ticker Refresh

### Overview
The platform is composed of:
- **Frontend** (React/Vite): UI for browse/analyze and watchlists.
- **Web API** (FastAPI): request handling + APIs for watchlists, snapshots, portfolios.
- **Worker** (Celery): background work for analysis and refresh.
- **Database** (Postgres in Docker; SQLite dev fallback): persistence for immutable snapshots and watchlist entities.
- **Redis** (Docker): broker/backend for Celery (local dev fallback can run eager without Redis).

### Key Architectural Principle
**Data snapshots are global and immutable.** Users own watchlists, not the snapshots. Snapshot storage is append-only and uniquely keyed to prevent duplicate work.

### Persistence Layers
- **Snapshot Layer**
  - `data_snapshots`: immutable raw provider payload by `(ticker, snapshot_date)`.
  - Derived artifacts (metrics/evidence/memo) continue to reference snapshots.
- **Watchlist Layer**
  - `watchlists`, `watchlist_items`: user-owned lists.
  - `refresh_jobs`, `refresh_job_items`: auditable refresh runs and per-ticker outcomes.

### Global Refresh Mechanism
- Universe = union of tickers in active watchlists.
- Daily scheduled refresh runs via **Celery beat** (Docker scheduler service).
- DB-level uniqueness for `(ticker, snapshot_date)` ensures refresh is performed **once per day per ticker** globally.

### API Surface (summary)
- `/api/watchlists*`: watchlist CRUD and membership.
- `/api/watchlists/{id}/status`: staleness + last snapshot metadata.
- `/api/admin/refresh/watchlists/run`: manual enqueue of refresh job.
- `/api/admin/watchlists/config`: exposes configured limits and refresh schedule.

### Notes / Current Constraints
- Authentication is not yet implemented; a temporary `X-User-Id` header is used for user scoping.
- Local dev fallback (no Docker): SQLite + Celery eager mode can be used to run the API/UI; production path remains Docker-first.


