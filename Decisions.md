## 2025-12-13 — ADR-0001 — Global per-ticker-per-day snapshot uniqueness

### Decision
Enforce **one `DataSnapshot` per `(ticker, snapshot_date)`** globally using a database-level unique index, and make both:
- the analysis pipeline, and
- the daily watchlist refresh job
follow an **insert-or-reuse** pattern.

### Context
We need “refresh once per ticker globally” even with many users and multiple watchlists, while keeping snapshots immutable and auditable.

### Alternatives considered
- **Per-user snapshot storage**: rejected due to duplicated work/cost and violates “global immutable data” principle.
- **Application-level locking only**: rejected; race conditions still possible without DB constraint.
- **Job-only refresh** (analysis always reads refresh results): rejected for now; analysis needs to work on-demand.

### Consequences
- Duplicate snapshot creation is prevented even under concurrency.
- Inserts may raise uniqueness violations; code must handle `IntegrityError` by re-querying.
- In local dev (SQLite), uniqueness enforcement is best-effort and differs from Postgres behavior; Docker path remains canonical.


## 2025-12-13 — ADR-0002 — Introduce `instrument` + provider-normalized tables and separate provider job tracking

Source: [Spec_DataProvider_AlphaVantage_Composable_Fetch.pdf](file://Spec_DataProvider_AlphaVantage_Composable_Fetch.pdf)

### Decision
Add new canonical data tables:
- `instrument`
- `provider_symbol_map`
- `price_eod`
- `fundamentals_snapshot`

Track Alpha Vantage work using a **new table** `provider_refresh_jobs` rather than reusing the existing watchlist `refresh_jobs`.

### Context
We need provider-normalized “UI-lite” snapshots and heavy backfills that are:
- globally reused (not per user)
- immutable
- idempotent and auditable

The existing `refresh_jobs` table is scoped to the watchlist daily-union refresh and has uniqueness constraints that do not fit instrument backfills.

### Alternatives considered
- Reuse `refresh_jobs` by adding `job_type` and changing uniqueness keys:
  - rejected for now; risks breaking existing semantics and requires data migration.
- Store lite results only in existing `data_snapshots`:
  - rejected; `data_snapshots` is ticker/provider-payload oriented for the analysis pipeline and is not instrument/provider-normalized.

### Consequences
- Clean separation between:
  - watchlist daily refresh audit, and
  - provider/instrument refresh/backfill audit
- Enables stable API contracts for UI-lite endpoints.

## 2025-12-13 — ADR-0003 — Add `instrument_refresh` for 24h browse-lite caching

Source: [Spec_Ticker_Search_Browse_AlphaVantage_24hCache.pdf](file://Spec_Ticker_Search_Browse_AlphaVantage_24hCache.pdf)

### Decision
Introduce a minimal `instrument_refresh` table to track:
- `last_refresh_at` (successful refresh time)
- `last_status` / `last_error`

and use it to enforce a **24-hour DB cache** rule in `GET /api/instruments/{ticker}/browse-lite`.

### Context
Browse-lite needs a deterministic freshness rule independent of UI sessions, and should avoid provider calls when data is still fresh.

### Alternatives considered
- Reuse `provider_refresh_jobs` only:
  - rejected; jobs are request-key oriented and do not provide a stable “last successful refresh” pointer for cache TTL.

### Consequences
- Simple and explicit cache TTL behavior.
- Allows graceful provider failure (serve stale DB if available while recording `last_error`).

## 2025-12-13 — ADR-0004 — Strict ticker resolution + guard (no DB rows for invalid symbols)

Source: [Spec_Ticker_Search_Validation_and_Browse_Guard.pdf](file://Spec_Ticker_Search_Validation_and_Browse_Guard.pdf)

### Decision
Make ticker resolution strict and explicit:
- `/api/instruments/resolve` returns **success** only when the ticker is resolvable from:
  - local instruments, or
  - local provider/alias maps, or
  - Alpha Vantage `SYMBOL_SEARCH` (cached).
- Invalid/not-found tickers return an error response and **do not create** `instruments` rows.

### Context
We must prevent nonsense tickers from navigating to Browse and from polluting the database with invalid instruments.

### Consequences
- UI can block navigation and show errors/suggestions.
- Deep links to `/browse/{ticker}` are safe because the route resolves first and browse-lite will not create rows.
- Successful provider resolutions are cached and persisted into `provider_symbol_map` with `last_verified_at`.


## 2025-12-13 — ADR-0005 — Introduce per-dataset refresh state for Overview fundamentals

Source: [Spec_Overview_Tab_FCF_and_Valuation_KPIs.pdf](file://Spec_Overview_Tab_FCF_and_Valuation_KPIs.pdf)

### Decision
Add a new refresh state table keyed by `(instrument_id, dataset_type)` for 24h DB-first caching of composed datasets, starting with:
- `fundamentals_quarterly`
- `fundamentals_annual`

### Context
Overview composes multiple datasets with different refresh cadences and failure modes. We need deterministic “no extra provider calls within 24h” behavior per dataset type.

### Alternatives considered
- Overloading existing `instrument_refresh` (single-row per instrument):
  - rejected; cannot represent multiple dataset types without a breaking primary key migration.
- Using only `provider_refresh_jobs`:
  - rejected; jobs are request-key oriented, not a stable “last successful refresh pointer” per dataset.

### Consequences
- Fundamentals refresh is explicit and independently cached from price refresh.
- Allows partial UI: price can render while fundamentals panels show stale/warnings.

### Notes
- Alpha Vantage endpoint availability varies by key/tier; for price history we default to free-tier compatible daily series endpoints in the UI layer.


## 2025-12-13 — ADR-0006 — Add fundamentals multi-series endpoint for chart overlays

Source: [Spec_FCF_MultiKPI_Chart_Toggles_NoTable.pdf](file://Spec_FCF_MultiKPI_Chart_Toggles_NoTable.pdf)

### Decision
Expose a dedicated endpoint that returns aligned multi-series fundamentals for charting:
- `GET /api/instruments/{ticker}/fundamentals/series`

### Context
The Overview UI needs multiple KPI lines (FCF + additional KPIs) over the same time axis with toggle controls, without duplicating computation logic in the frontend.

### Consequences
- Keeps mapping logic centralized (statement field names + sign conventions).
- Allows DB-first 24h caching via existing fundamentals refresh tracking.


## 2025-12-13 — ADR-0007 — Add n8n workflow automation platform

### Decision
Add **n8n** (self-hosted workflow automation) as an optional Docker service to enable:
- Webhook-triggered workflows
- External service integrations
- Automated notifications and reporting
- Multi-step data pipeline orchestration

### Context
The platform may benefit from workflow automation for:
- Triggering analysis jobs from external events
- Integrating with additional data providers beyond Alpha Vantage
- Automating notifications (email, Slack, etc.) for watchlist updates or analysis completions
- Orchestrating complex multi-step processes that span multiple services

### Alternatives considered
- **Zapier/Make.com**: rejected; requires external SaaS dependency and may not align with self-hosted, auditability-first principles.
- **Custom workflow engine**: rejected; n8n provides mature, well-maintained solution without reinventing the wheel.
- **Airflow**: rejected; overkill for simple workflows; n8n is more user-friendly for non-technical users.

### Consequences
- Optional service; core platform remains independent
- Adds Docker volume for workflow persistence
- Enables extensibility without modifying core codebase
- Basic authentication required (configurable via environment variables)
- Can optionally use shared PostgreSQL database or file-based storage


