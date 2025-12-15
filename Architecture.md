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


## 2025-12-13 — v1.5.0 — Overview composition (price + fundamentals)

Source: [Spec_Overview_Tab_FCF_and_Valuation_KPIs.pdf](file://Spec_Overview_Tab_FCF_and_Valuation_KPIs.pdf)

### Composition endpoint
- Add `GET /api/instruments/{ticker}/overview` which composes:
  - price (EOD close + as-of date)
  - cash flow-derived FCF series
  - KPI series derived from income statement + balance sheet

### Persistence & auditability
- Fundamentals are stored as immutable `fundamentals_snapshot` rows:
  - keyed by `(instrument_id, statement_type, frequency, period_end)`
  - include provider + fetched-at metadata

### Freshness (24h DB-first)
- Track refresh by dataset type (e.g., fundamentals_quarterly / fundamentals_annual) to avoid repeated provider calls.
- Serve partial data when provider errors occur; UI shows per-panel warnings.


## 2025-12-13 — v1.6.0 — Fundamentals multi-series endpoint (chart overlays)

Source: [Spec_FCF_MultiKPI_Chart_Toggles_NoTable.pdf](file://Spec_FCF_MultiKPI_Chart_Toggles_NoTable.pdf)

### Endpoint
- Add `GET /api/instruments/{ticker}/fundamentals/series` returning aligned multi-series values for a given period (quarterly/annual).

### Data flow
- DB-first: read from `fundamentals_snapshot` when fundamentals refresh is < 24h.
- Otherwise: refresh fundamentals bundle (CF/IS/BS) once, persist immutable snapshots, then compute aligned series.


## 2025-12-13 — v1.7.0 — n8n Workflow Automation Integration

### Overview
Added **n8n** (self-hosted workflow automation platform) as an optional service for orchestrating external integrations, webhooks, and automated workflows that complement the core investment analysis platform.

### Service Configuration
- **n8n** (Docker): Self-hosted workflow automation tool
  - Accessible at `http://localhost:5678`
  - Basic authentication enabled (configurable via environment variables)
  - Persistent storage via Docker volume (`n8n_data`)
  - Optional PostgreSQL backend (commented out; can use file-based storage by default)

### Integration Points
- n8n can be used to:
  - Trigger analysis workflows via webhooks
  - Integrate with external data providers beyond Alpha Vantage
  - Automate notifications and reporting
  - Orchestrate multi-step data pipelines
  - Connect to third-party services (Slack, email, etc.)

### Storage
- Workflows and credentials stored in Docker volume `n8n_data`
- Can optionally use shared PostgreSQL database (requires separate `n8n` database schema)
- File-based storage is the default for simplicity

### Notes
- n8n is an optional service; core platform functionality does not depend on it
- Authentication credentials should be set via environment variables (`N8N_BASIC_AUTH_USER`, `N8N_BASIC_AUTH_PASSWORD`)
- Webhook URLs default to `http://localhost:5678/` (adjust `WEBHOOK_URL` for production deployments)


## 2025-12-15 — v2.0.0 — SEC EDGAR 10-K / 10-Q Ingestion and Parse Pipeline (V0)

Source: [SEC_Ingestion_Parse_Pipeline_V0_Functional_Spec.pdf](file://SEC_Ingestion_Parse_Pipeline_V0_Functional_Spec.pdf)

### Overview
The SEC ingestion pipeline extends the existing snapshot/analysis architecture with a dedicated **artifact + job layer** for SEC filings:
- **SecEdgarClient**: rate-limited, header-compliant client for `company_tickers.json`, company submissions, and primary filing downloads from `data.sec.gov` / `sec.gov`.
- **SEC artifacts** (`sec_artifacts`): immutable records for raw HTML/iXBRL filings and derived normalized text.
- **SEC parse jobs** (`sec_parse_jobs`): asynchronous jobs that convert RAW_FILING artifacts into PARSED_TEXT artifacts.
- **API surface**:
  - `POST /api/sec/{ticker}/ingest` — on-demand ingestion for a ticker.
  - `GET /api/sec/{ticker}/filings` — list raw + parsed artifacts and parse job status for a ticker/CIK.

### Persistence Layer (SEC)
- **sec_artifacts**
  - Represents both raw and parsed SEC filing artifacts.
  - Core fields:
    - `source` = `SEC_EDGAR`
    - `ticker` (optional), `instrument_id` (optional link to `instrument`), `cik` (10-digit padded)
    - `accession_number`, `form_type`, `filing_date`, `period_end`
    - `artifact_kind` ∈ {RAW_FILING, PARSED_TEXT}
    - `storage_backend` (V0: `local_fs`), `storage_path`, `file_name`, `content_hash` (raw only)
    - `parser_version`, `parse_warnings` (parsed only)
  - Relationships:
    - `parent_artifact_id` (nullable self-reference) from PARSED_TEXT → RAW_FILING.
    - `instrument_id` (nullable FK) to canonical `instrument` row.
  - Constraints / indexes:
    - `UNIQUE (cik, accession_number, artifact_kind)` prevents duplicate RAW_FILING and PARSED_TEXT per filing-kind.
    - Index on `(cik, form_type, filing_date)` for deterministic selection and listing.
- **sec_parse_jobs**
  - Tracks asynchronous parsing work separate from analysis/watchlist/provider jobs.
  - Core fields:
    - `job_type` = `PARSE_FILING`
    - `artifact_id` (FK → `sec_artifacts.id` for RAW_FILING)
    - `status` ∈ {queued, running, done, failed, deadletter}
    - `attempt_count`, `max_attempts`
    - `locked_by`, `locked_at` (best-effort concurrency guard)
    - `idempotency_key = parse:{artifact_id}:{parser_version}` (unique)
    - `last_error` (text, for diagnostics and deadletters)
- **instruments.cik**
  - Adds optional `cik` (10-digit, indexed) on `instrument` to:
    - avoid duplicating company identity between EDGAR and market data layers;
    - make it easy to navigate from a ticker in the UI to SEC filings.

### SEC Client / Rate Limiting
- **SecEdgarClient**
  - Wraps `requests` with:
    - process-level rate limiting (`SEC_MAX_REQUEST_RATE`, default 10 rps) to respect SEC guidance.
    - retries with exponential backoff (`SEC_RETRY_MAX_ATTEMPTS`) on 429/403/5xx and network failures.
    - mandatory `SEC_EDGAR_USER_AGENT` header (process will fail fast if not set).
  - Endpoints used:
    - `https://www.sec.gov/files/company_tickers.json` for ticker → CIK resolution.
    - `https://data.sec.gov/submissions/CIK##########.json` for company submissions index.
    - `https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{primary_document}` for primary filing downloads.

### Ingestion Flow (Web API + Worker)
- **API ingestion endpoint**
  - `POST /api/sec/{ticker}/ingest`:
    - Validates ticker format (A–Z, 0–9, `.`, `-`).
    - Resolves CIK using `Instrument.cik` when present; otherwise via `SecEdgarClient` + `company_tickers.json`.
    - Fetches company submissions JSON for CIK.
    - Delegates filing selection to `select_filings` (deterministic filter + sort + N/M lookback).
    - For each selected filing:
      - Downloads primary document bytes.
      - Calls `register_raw_artifact` to:
        - store bytes under `SEC_STORAGE_BASE_PATH/{cik}/{accession}/{primary_document}`;
        - upsert RAW_FILING `SecArtifact` with content hash.
      - Calls `create_parse_job_if_needed` to idempotently enqueue a `SecParseJob` for the (artifact, parser_version).
    - Returns a structured `SecIngestResponse` summary.
- **Worker ingestion wrapper**
  - Celery task `sec_ingest_filings_for_ticker`:
    - Wraps `ingest_sec_filings_for_ticker` for background use (e.g., future schedulers or workflows).
    - Best-effort enqueues `sec_parse_filing` tasks for any newly-created parse jobs.
- **Worker parse task**
  - Celery task `sec_parse_filing`:
    - Loads the `SecParseJob`, acquires a logical lock via `locked_by`/`locked_at`, and transitions to `running`.
    - Reads the RAW_FILING from `storage_path` (V0: local filesystem).
    - Normalizes HTML/iXBRL → plain text via `_normalize_html_to_text` (tag-stripping + whitespace collapsing).
    - Writes a sibling `.txt` file and persists a PARSED_TEXT `SecArtifact` with `parent_artifact_id` and `parser_version`.
    - Updates job status to `done`; on errors increments `attempt_count` and transitions to `failed` or `deadletter`
      based on `max_attempts`, with optional Celery retry/backoff for transient errors.

### API for SEC Filings Listing
- `GET /api/sec/{ticker}/filings`
  - Resolves/ensures `Instrument` and `cik` for the ticker (reusing `resolve_cik_for_ticker`).
  - Queries `sec_artifacts` for the CIK, ordered by `(filing_date desc, accession_number desc, artifact_kind)`.
  - Joins with `sec_parse_jobs` to report latest parse status per artifact.
  - Returns `SecFilingListResponse` with:
    - `artifact_id`, `accession_number`, `form_type`, `filing_date`, `period_end`
    - `artifact_kind`, `parser_version`, and `parse_job_status`.

### Architectural Rationale
- **Separation of concerns**
  - SEC artifacts and jobs live alongside, but separate from:
    - market data (`price_eod`, `fundamentals_snapshot`);
    - watchlist refresh jobs (`refresh_jobs`, `refresh_job_items`);
    - provider jobs (`provider_refresh_jobs`).
  - This avoids overloading existing tables with SEC-specific semantics and keeps idempotency keys explicit.
- **Reuse of canonical instruments**
  - `instrument.canonical_symbol` + `instrument.cik` form the bridge between:
    - market/fundamentals analysis, and
    - SEC filing ingestion.
  - UI and downstream analysis can pivot from ticker → instrument → CIK → SEC filings without additional mapping tables.
- **Append-only and immutable**
  - Raw filing bytes and parsed text are treated as immutable artifacts.
  - Re-parsing with a new parser version will create new PARSED_TEXT artifacts and new `sec_parse_jobs` keyed by parser_version
    (future extension beyond V0).

