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


## 2025-12-13 — v1.4.0 — Validate Ticker Search + Prevent Navigating to Browse for Invalid Symbols

Source: [Spec_Ticker_Search_Validation_and_Browse_Guard.pdf](file://Spec_Ticker_Search_Validation_and_Browse_Guard.pdf)

### Objective
- Search validates ticker and **only navigates** to `/browse/{ticker}` if resolvable.
- `/browse/{ticker}` is guarded (deep links do not load data or create DB rows for invalid tickers).

### Validation rules (MVP)
- Normalize input: trim + uppercase.
- Reject invalid format (MVP allow: A–Z, 0–9, `.`, `-`).
- Resolve order:
  1) `instruments.canonical_symbol` exact match
  2) `provider_symbol_map` match
  3) Alpha Vantage `SYMBOL_SEARCH` (rate-limited)
- Best-match selection:
  - prefer exact symbol match to query
  - else pick highest score among US-region results (MVP)

### Persistence rules
- **Do not create** instruments for invalid tickers or not-found results.
- Only upsert instrument/provider mappings after successful resolution.
- Persist successful provider resolutions into `provider_symbol_map` with `last_verified_at`.
- Cache provider search results for short TTL (24h) to reduce calls.

### UX requirements
- Search submit calls resolve.
  - success: navigate to canonical ticker returned by backend
  - failure: stay put and show inline error; optionally show clickable suggestions
- Browse route guard:
  - resolve first → if fail show Not Found UI → do not call browse-lite


## 2025-12-13 — v1.5.0 — Overview Tab (Default) + Free Cash Flow + Buffett-style KPI Panels

Source: [Spec_Overview_Tab_FCF_and_Valuation_KPIs.pdf](file://Spec_Overview_Tab_FCF_and_Valuation_KPIs.pdf)

### Objective
- Rename tab **Performance → Overview** and make it the **default** tab on `/browse/{ticker}`.
- In Overview, keep headline price + as-of date, and add:
  - **Panel A (FCF)**: quarterly + yearly Free Cash Flow view
  - **Panel B (KPIs)**: Buffett-style KPI panel with **Quarterly/Yearly** toggle (Quarterly default)

### Data requirements
- FCF derived from cash flow statement fields:
  - `FreeCashFlow = operatingCashflow - capitalExpenditures`
- KPIs derived from statements:
  - ROE, Net Margin, Operating Margin, FCF Margin, Debt/Equity
- Raw statements are stored as immutable `fundamentals_snapshot` rows with provider metadata.

### API (internal)
- `GET /api/instruments/{ticker}/overview`
  - returns latest price snapshot + FCF series + KPI values/series + as-of metadata per dataset

### Refresh policy
- DB-first: if refreshed within 24h per dataset type, serve from DB and do not call provider.
- If stale/missing: call provider, persist immutable snapshots, return updated view.


## 2025-12-13 — v1.6.0 — Multi-KPI Overlay Chart in FCF Container (Toggle Lines) + Remove Table

Source: [Spec_FCF_MultiKPI_Chart_Toggles_NoTable.pdf](file://Spec_FCF_MultiKPI_Chart_Toggles_NoTable.pdf)

### Objective
- Enhance the FCF chart to support **multiple KPI lines** on one time axis with click-to-toggle visibility.
- Remove the table beneath the chart (chart-only view).

### KPI series (v1)
- `fcf` (operating cash flow - capex)
- `sbc` (stock-based compensation, if available)
- `netIncome`
- `debt` (total debt or short+long term debt)
- `dividends` (abs cash spent)
- `buybacks` (abs cash spent)

### API
- `GET /api/instruments/{ticker}/fundamentals/series?period=quarterly|annual&series=fcf,sbc,netIncome,debt,dividends,buybacks`
- Response returns aligned series; missing series are omitted/marked unavailable (no fabricated values).

### Refresh policy
- Reuse fundamentals refresh tracking: DB-first within 24h, otherwise provider fetch and snapshot persistence.


## 2025-12-13 — v1.6.1 — Overview layout: price + FCF on same row, improve price chart ticks

### Objective
- Place **FCF multi-series chart** on the **same row** as the **price chart** in Overview for better comparability.
- Fix price chart axis rendering for daily data (avoid repeated month tick labels).


## 2025-12-13 — v1.6.2 — Overview: KPI chart with toggles + 3-up layout

### Objective
- Move **Valuation / Quality KPIs** onto the same row as **Price** and **FCF** on wide screens.
- Replace KPI table with a **multi-line KPI chart** and **toggle chips** (like the FCF panel).

## 2025-12-15 — v2.0.0 — SEC 10-K / 10-Q Ingestion and Parse Pipeline (V0)

Source: [SEC_Ingestion_Parse_Pipeline_V0_Functional_Spec.pdf](file://SEC_Ingestion_Parse_Pipeline_V0_Functional_Spec.pdf)

### Purpose
- For a specified ticker, discover and download the most recent 10-K and 10-Q filings from SEC EDGAR.
- Register each filing as an immutable artifact (raw + parsed text) and create parse jobs.
- Enable later steps such as chunking, embeddings, RAG, and accounting review by providing normalized text artifacts keyed by filing.

### Scope (V0)
- **Includes**
  - CIK resolution for a ticker using SEC company_tickers.json.
  - Filings discovery and deterministic selection:
    - last **N** 10-K filings (default `SEC_10K_LOOKBACK=2`)
    - last **M** 10-Q filings (default `SEC_10Q_LOOKBACK=8`)
    - Optional inclusion of amendments (10-K/A, 10-Q/A) via `SEC_INCLUDE_AMENDMENTS`.
  - File download of the primary filing document (HTML/iXBRL) to local filesystem under a deterministic folder structure.
  - Artifact registry updates:
    - RAW_FILING artifact for each (cik, accession_number).
    - PARSED_TEXT artifact linked by `parent_artifact_id` after parsing.
  - Parse job creation and execution:
    - `SecParseJob` rows for each new/changed RAW_FILING and parser_version.
    - Worker task that normalizes HTML/iXBRL → plain text and stores it as PARSED_TEXT.
  - Status reporting via API endpoints for ingestion run summary and per-filing status.
- **Excludes (V0)**
  - OCR for scanned images.
  - Embeddings/vector DB and search.
  - Accounting agent reasoning and memo generation from SEC text.
  - PDF export of parsed SEC filings.

### Core Principles
- **Idempotent reruns**
  - No duplicate RAW_FILING artifacts for the same (cik, accession_number, artifact_kind).
  - No duplicate PARSE_FILING jobs for the same (artifact_id, parser_version).
  - Re-ingestion reuses existing artifacts and jobs when nothing changed.
- **Deterministic selection**
  - Eligible forms filtered to {10-K, 10-Q} (+/A when enabled).
  - Sort by filing_date (desc), accession_number (desc).
  - Take `N` most recent 10-K and `M` most recent 10-Q; combined list sorted again by filing_date (desc).
- **Reproducibility**
  - Raw filing bytes stored on local filesystem with deterministic path: `SEC_STORAGE_BASE_PATH/{cik}/{accession}/primary_document`.
  - `SecArtifact` rows capture storage_backend, storage_path, file_name, and a content hash of raw bytes.
  - Parsed text stored as derived artifact with explicit `parser_version` and optional `parse_warnings`.
- **Operational safety**
  - Global request rate limiter (default 10 requests/sec) enforced client-side for SEC endpoints.
  - Required `SEC_EDGAR_USER_AGENT` header with contact information for all SEC calls.
  - Retry with exponential backoff on transient errors (429/403/5xx/network timeouts), bounded by `SEC_RETRY_MAX_ATTEMPTS`.
  - Per-ticker ingestion endpoint returns structured summary, including selected filings, created artifacts, and created parse jobs.

### Data Model (logical, V0)
- **sec_artifacts**
  - Represents both raw and parsed SEC filing artifacts.
  - Key fields:
    - `source = SEC_EDGAR`
    - `ticker`, `instrument_id`, `cik` (10-digit padded), `accession_number`, `form_type`, `filing_date`, `period_end`
    - `artifact_kind` = RAW_FILING or PARSED_TEXT
    - `storage_backend` (V0: `local_fs`), `storage_path`, `file_name`, `content_hash` (raw only)
    - `parser_version`, `parse_warnings` (parsed only)
  - Relationships:
    - Optional `parent_artifact_id` from PARSED_TEXT → RAW_FILING.
    - Optional `instrument_id` to link filings to platform instruments (via ticker + CIK).
- **sec_parse_jobs**
  - Asynchronous parse jobs for filing artifacts.
  - Key fields:
    - `job_type` = `PARSE_FILING`
    - `artifact_id` (references RAW_FILING)
    - `status` = queued/running/done/failed/deadletter
    - `attempt_count`, `max_attempts`
    - `locked_by`, `locked_at` (simple optimistic locking)
    - `idempotency_key` = `parse:{artifact_id}:{parser_version}`
    - `last_error` (string, for debugging and deadletters)
- **instruments**
  - Extended with optional `cik` (10-digit, indexed) to reuse existing canonical instrument layer and avoid duplicate company identifiers.

### Worker / API Behavior
- **Ingestion**
  - API: `POST /api/sec/{ticker}/ingest`
    - Validates ticker format (A–Z, 0–9, `.`, `-`).
    - Resolves CIK (reuses `Instrument.cik` when present; otherwise via SEC company_tickers.json).
    - Fetches company submissions index for CIK.
    - Applies deterministic selection rules for 10-K/10-Q.
    - Downloads primary filing documents, registers RAW_FILING artifacts, and creates PARSE_FILING jobs.
    - Returns `SecIngestResponse` with CIK, selected_count, artifact_ids, parse_job_ids.
- **Parse jobs**
  - Worker task: `sec_parse_filing`
    - Locks job (best-effort) via `locked_by`/`locked_at`.
    - Reads RAW_FILING from local filesystem.
    - Normalizes HTML/iXBRL into plain text (strip tags, collapse whitespace).
    - Writes `.txt` sibling file and persists PARSED_TEXT `SecArtifact`.
    - Marks job status as done / failed / deadletter based on attempts.
  - Orchestrator task: `sec_ingest_filings_for_ticker`
    - Runs ingestion and best-effort enqueues `sec_parse_filing` for newly created jobs.

### Status & Listing
- **API: `GET /api/sec/{ticker}/filings`**
  - Lists `SecArtifact` rows for the ticker's CIK (both RAW_FILING and PARSED_TEXT).
  - Summarizes per-filing state:
    - `artifact_kind`
    - `parser_version` (when parsed)
    - most recent `SecParseJob.status` (if any) for each artifact.

### Non-goals / Future Extensions
- Section-level parsing, semantic labeling (MD&A, risk factors, etc.).
- Table and XBRL normalization beyond best-effort plain text.
- Multi-version parsing (multiple parser versions per filing) beyond V0 single-version support.
- Scheduling ingestion across watchlists or portfolios (V0 is per-ticker on-demand).

