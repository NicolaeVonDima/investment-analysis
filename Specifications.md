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


