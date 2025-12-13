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


## 2025-12-13 — v1.2.0 — Alpha Vantage + Composable Fetch (UI-lite + Backfill)

Source: [Spec_DataProvider_AlphaVantage_Composable_Fetch.pdf](file://Spec_DataProvider_AlphaVantage_Composable_Fetch.pdf)

### Motivation
The UI needs a lightweight path to show identity/price/freshness without always triggering a heavy analysis run, and without duplicating work across users.

### New persistence layer: Instruments + Provider-normalized market data
- `instrument`: canonical symbol + identity fields
- `provider_symbol_map`: provider-specific symbol aliases mapping onto a canonical instrument
- `price_eod`: immutable EOD price rows per instrument/day
- `fundamentals_snapshot`: immutable fundamental statement snapshots per instrument/period

### Composable endpoints
- **Resolve**: map user symbol input -> canonical instrument id
- **Latest-lite snapshot**: return DB snapshot if present; else return last value + stale + enqueue refresh
- **Backfill**: enqueue heavy job for >=5y daily adjusted prices + fundamentals

### Work tracking (idempotency/retries)
We introduce `provider_refresh_jobs` to track provider operations (lite/backfill), separate from `refresh_jobs` used for watchlist daily refresh, to avoid semantic conflicts and to support different uniqueness keys.

### Rate limiting strategy
- Worker tasks are rate limited per provider (Alpha Vantage free tier constraints).
- Retries with backoff; UI remains functional by serving last known snapshots with `stale=true`.

## 2025-12-13 — v1.3.0 — Browse-lite 24h cache + ticker routing

Source: [Spec_Ticker_Search_Browse_AlphaVantage_24hCache.pdf](file://Spec_Ticker_Search_Browse_AlphaVantage_24hCache.pdf)

### Backend cache state
- Introduces `instrument_refresh` as the canonical per-instrument cache state:
  - `last_refresh_at`, `last_status`, `last_error`
- Browse-lite endpoint uses this table to enforce the 24h freshness rule.

### Concurrency control
- For Postgres: per-ticker **advisory transaction lock** to avoid concurrent refresh-lite calls duplicating work.
- For other engines: best-effort (uniqueness constraints still protect `price_eod`).

### Frontend routing
- UI uses `/browse/:ticker` route and the sidebar search navigates there.
- Browse view calls `GET /api/instruments/{ticker}/browse-lite`.


## 2025-12-13 — v1.4.0 — Ticker validation + browse guard

Source: [Spec_Ticker_Search_Validation_and_Browse_Guard.pdf](file://Spec_Ticker_Search_Validation_and_Browse_Guard.pdf)

### Resolution sources
- **db**: exact instrument match
- **alias**: provider/alias mapping (`provider_symbol_map`)
- **provider**: Alpha Vantage `SYMBOL_SEARCH` (cached)

### Guarding invariants
- Invalid/unresolvable tickers must not:
  - create `instruments` rows, or
  - trigger browse-lite/provider refresh paths.

### Caching
- Provider symbol search results cached in DB for 24h to reduce calls.

