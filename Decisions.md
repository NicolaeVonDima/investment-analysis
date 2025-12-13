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


