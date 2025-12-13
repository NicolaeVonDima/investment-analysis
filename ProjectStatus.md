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


