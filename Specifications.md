## 2025-12-13 — v1.1.0 — Watchlists with Global Ticker Refresh

### Scope
- Add **Watchlists** that users can create/manage (multiple per user).
- Ensure **market/fundamental data refresh** is performed **once per ticker globally per day**, shared across all users.
- Store **immutable, append-only snapshots** and expose refresh status (including staleness).
- Provide an **admin-triggerable refresh** and a **scheduled daily refresh**.

### Core Principles
- **Ticker data is global and immutable**; users own watchlists, not ticker data.
- Any ticker present in at least one **active watchlist** is included in the **daily refresh universe** (union of tickers).
- **At most one snapshot per ticker per day** is permitted (DB-level uniqueness).
- If refresh fails, the **last successful snapshot remains**; UI shows **stale** state.

### Capabilities
- **User**
  - Create/watchlists (within admin-configured limits).
  - Add/remove tickers within watchlists (optional per-watchlist ticker limit).
  - View per-ticker refresh status: last snapshot date/time and staleness.
- **Admin**
  - Configure limits: max watchlists per user, optional max tickers per watchlist.
  - Configure schedule (daily time, UTC).
  - Trigger refresh run manually.

### Data Model (logical)
- **watchlist**: user-owned container
- **watchlist_item**: membership of ticker in a watchlist
- **data_snapshot**: immutable market/fundamental data snapshot per ticker per as-of date
- **refresh_job**: daily job for union universe
- **refresh_job_item**: per-ticker status within a refresh job (auditable)

### Refresh Logic
- Each day:
  - Determine universe = union of tickers across **active** watchlists.
  - For each ticker:
    - If (ticker, today) snapshot exists: **skip** (work already done globally).
    - Else fetch provider payload and insert snapshot.
- DB uniqueness prevents duplicate work across concurrent refresh/analyze flows.

### Failure Handling & Staleness
- Refresh failures are recorded per ticker; overall job can be marked failed.
- UI staleness rule:
  - stale = no snapshot exists for ticker, or latest snapshot date < today (UTC).

### APIs (high level)
- Watchlist CRUD & item management
- Status endpoints (last refresh time, staleness, job status)
- Admin endpoints for config + manual refresh trigger

### Non-goals
- Full authentication/authorization (temporary user identity shim acceptable for now).
- Provider fallback routing beyond current provider.
- Exchange-aware schedules (future extension).

### Data Impact
- Adds new tables for watchlists and refresh audit logs.
- Enforces uniqueness of snapshot creation per ticker/day.
- Snapshots are append-only and should never be mutated in place.


## 2025-12-13 — v1.2.0 — Alpha Vantage (Free Tier) + Composable Fetch Requests

Source: [Spec_DataProvider_AlphaVantage_Composable_Fetch.pdf](file://Spec_DataProvider_AlphaVantage_Composable_Fetch.pdf)

### Goals
- Provide **UI-lite** data for company identity + latest price + freshness.
- Provide a heavier **async backfill** operation to fetch/store:
  - >= 5 years daily adjusted EOD prices
  - fundamentals snapshots where available
- Store immutable snapshots reused globally (not per user).
- Keep Docker-first and cloud-ready.

### Provider choice (MVP)
- Provider: **Alpha Vantage** (free tier for now).
- Constraint: **rate limited** free tier (must queue/cap calls, graceful stale behavior).

### Composable fetch model
- **Lite** endpoint:
  - Serve from DB if present for today; else return last stored value with `stale=true`
  - Queue a refresh task when stale/missing (best-effort)
- **Backfill** endpoint:
  - Async job that fetches multi-year daily adjusted series and fundamentals
  - Idempotent: repeated calls do not create duplicates

### Data model changes (MVP)
- Add canonical instruments + provider symbol mapping:
  - `instrument`
  - `provider_symbol_map`
- Store EOD prices:
  - `price_eod` unique by `(instrument_id, as_of_date)`
- Store fundamentals:
  - `fundamentals_snapshot` unique by `(instrument_id, statement_type, period_end, frequency)`
- Track provider work for idempotency/retry:
  - `provider_refresh_jobs` (separate from watchlist refresh jobs)

### Initial instruments (seed)
- Load **ADBE** and **GOOGL** (allow **GOOG** alias mapping to the same instrument).

### Acceptance criteria
- UI-lite snapshot for ADBE and GOOGL shows:
  - company identity
  - latest price
  - freshness/staleness
- Backfill enqueues job; worker stores >=5y EOD history and fundamentals when available.
- No duplicates on repeated runs (DB uniqueness + idempotent jobs).
- Graceful degradation on provider limit (stale preserved; retries/backoff).
- All stored data includes provider + retrieval metadata.


## 2025-12-13 — v1.3.0 — Ticker Search → Browse (Alpha Vantage) with 24h DB Cache

Source: [Spec_Ticker_Search_Browse_AlphaVantage_24hCache.pdf](file://Spec_Ticker_Search_Browse_AlphaVantage_24hCache.pdf)

### Objective
- Search box resolves ticker and navigates to `/browse/{ticker}`.
- Browse page is populated from Alpha Vantage-backed **browse-lite** data.
- Enforce **24-hour freshness**:
  - if refreshed within last 24h: serve from DB only (no provider call)
  - else: refresh from Alpha Vantage, persist, update refresh timestamp, return updated snapshot

### Scope
- UI: Search submit + Browse routing + data binding for a single ticker.
- Backend: Resolve ticker, serve browse-lite from DB, conditional refresh based on freshness, timestamp management.
- Database: minimal additional fields/tables to support cache rule.

### Non-scope (v1)
- Historical/fundamentals backfill UI flow (separate from this browse-lite cache).
- Watchlist refresh universe scheduling.

### API (internal)
- `POST /api/instruments/resolve` body `{ query: "AAPL" }` (also accepts `{ symbol: "AAPL" }`)
- `GET /api/instruments/{ticker}/browse-lite`
- Optional debug/admin: `POST /api/instruments/{ticker}/refresh-lite`

### Data freshness rule
- `fresh = (now - last_refresh_at) < 24h`
- Update `last_refresh_at` only after a successful provider refresh.

### Concurrency & idempotency
- Per-ticker lock during refresh-lite.
- `price_eod` uniqueness prevents duplicate daily rows.
- Refresh timestamp updates are atomic with successful provider fetch.

