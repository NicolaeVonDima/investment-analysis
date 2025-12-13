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


