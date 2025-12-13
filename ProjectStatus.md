## 2025-12-13 — Status Update

### What changed
- Implemented **Watchlists with Global Ticker Refresh** (v1.1.0):
  - Watchlist + watchlist items data model
  - Global daily refresh universe + audit logs
  - UI for managing watchlists and viewing staleness
  - Admin/manual refresh trigger endpoint
  - Daily scheduler service in `docker-compose.yml` (Celery beat)

- Implemented **Alpha Vantage + composable fetch (UI-lite + backfill)** (v1.2.0):
  - New canonical instrument layer (`instruments`, `provider_symbol_map`)
  - New immutable provider-normalized storage (`price_eod`, `fundamentals_snapshot`)
  - New auditable provider job tracking (`provider_refresh_jobs`)
  - Endpoints:
    - `POST /api/instruments/resolve`
    - `GET /api/instruments/{instrument_id}/snapshot/latest-lite`
    - `POST /api/instruments/{instrument_id}/backfill`
  - Worker tasks:
    - `refresh_instrument_lite` (rate limited)
    - `backfill_instrument_data` (rate limited)
  - Seeded initial instruments: ADBE, GOOGL (+ GOOG alias)

### Current focus
- Stabilize provider-backed UI-lite refresh under rate limits and make the frontend consume lite snapshots for identity/price/freshness.

### Risks / Mitigations
- **Provider rate limits (429)**:
  - Mitigation: retries/backoff for refresh; preserve last snapshot and mark stale; consider caching and/or provider fallback in future.
- **No auth**:
  - Mitigation: temporary `X-User-Id` header shim; replace with real auth later.
- **Local dev without Docker differs from prod**:
  - Mitigation: keep Docker compose as primary path; fallback is for local convenience only.

### Next tasks
- Add authentication and real user identity.
- Add admin-configurable watchlist limits UI + enforcement tests.
- Add refresh monitoring (job history view) and richer per-ticker failure details.
- Wire Browse UI header/price to `latest-lite` endpoint instead of mock data (MVP).


## 2025-12-13 — Status Update (follow-up)

### Done
- Browse UI now resolves instruments and displays **UI-lite snapshot** freshness (`Fresh`/`Stale`) and price when available via:
  - `POST /api/instruments/resolve`
  - `GET /api/instruments/{instrument_id}/snapshot/latest-lite`

## 2025-12-13 — Status Update (key rotation)

### Done
- Rotated local Alpha Vantage API key configuration (still read via `ALPHAVANTAGE_API_KEY` env var).

## 2025-12-13 — Status Update (v1.3.0 browse-lite)

### Done
- Search box now navigates to `/browse/:ticker`.
- Backend provides `GET /api/instruments/{ticker}/browse-lite` with **24h DB cache** and **per-ticker lock**.
- Added `instrument_refresh` table to track `last_refresh_at` and refresh status.

### Tests
- `pytest`: PASS

## 2025-12-13 — Status Update (v1.4.0 validation + browse guard)

### Done
- Search now validates tickers via `POST /api/instruments/resolve` before navigating.
- Invalid tickers show an inline error and do not navigate.
- `/browse/:ticker` is guarded: invalid deep links show Not Found and do not call browse-lite.
- Backend no longer creates instruments in browse-lite for unknown tickers.
- Added provider symbol search caching (24h) and `last_verified_at` on provider symbol maps.

### Tests
- `pytest`: PASS

### Notes
- Existing Postgres installs are upgraded best-effort on startup via `init_db()` DDL for v1.4.0 tables/columns (no Alembic yet).

## 2025-12-13 — Status Update (debugging: mock Alpha Vantage)

### Done
- Added `ALPHAVANTAGE_MOCK=1` mode to return deterministic local fixtures (no network calls; no API key required).
- Intended for UI/API debugging without consuming provider credits.

### Tests
- `pytest`: PASS

## 2025-12-13 — Status Update (v1.5.0 Overview + FCF + KPI panels)

### Done
- UI: renamed **Performance → Overview**, made it the default tab on `/browse/:ticker`.
- Overview now shows:
  - price headline + EOD as-of date
  - **FCF** panel (Quarterly/Yearly)
  - **Buffett-style KPI** panel (Quarterly default; Yearly toggle)
- Backend: added `GET /api/instruments/{ticker}/overview` composing price + fundamentals + KPI series with 24h DB-first caching per dataset.
- Persistence: added per-dataset refresh tracking for fundamentals via `instrument_dataset_refresh`.

### Tests
- `pytest`: PASS


