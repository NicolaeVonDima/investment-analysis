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

## 2025-12-13 — Status Update (v1.6.0 multi-series FCF chart)

### Current focus
- Add multi-series fundamentals endpoint + UI toggleable overlays (FCF + selected KPIs) and remove the table under the chart.

## 2025-12-13 — Status Update (v1.6.1 Overview layout tweaks)

### Done
- Fixed price chart X-axis tick formatting for daily series.
- Moved FCF overlay chart to the same row as the price chart (responsive layout).

## 2025-12-13 — Status Update (v1.6.2 KPI chart + 3-up layout)

### Done
- Replaced KPI table with a toggleable multi-line KPI chart (percent series + Debt/Equity).
- Overview grid now supports 3-up cards (Price + FCF + KPIs) on wide screens.


## 2025-12-13 — Status Update (v1.7.0 n8n integration)

### Done
- Added **n8n** workflow automation service to `docker-compose.yml`
- Configured n8n with:
  - Persistent Docker volume for workflow storage
  - Basic authentication (configurable via environment variables)
  - Port 5678 exposed
  - Optional PostgreSQL backend (commented out; defaults to file-based storage)
- Updated Architecture.md to document n8n integration
- Added ADR-0007 to Decisions.md explaining the n8n integration decision

### Access
- n8n UI available at `http://localhost:5678` after `docker-compose up`
- Default credentials: `admin` / `changeme` (should be changed via environment variables)

### Notes
- n8n is an optional service; core platform functionality is independent
- Workflows can be used for webhooks, external integrations, and automation
- See Architecture.md v1.7.0 for integration points and usage patterns


## 2025-12-15 — Status Update (v2.0.0 SEC EDGAR ingestion + parse V0)

### What changed
- Implemented **SEC 10-K / 10-Q ingestion and parse pipeline (V0)** per [SEC_Ingestion_Parse_Pipeline_V0_Functional_Spec.pdf](file://SEC_Ingestion_Parse_Pipeline_V0_Functional_Spec.pdf):
  - Added `SecEdgarClient` with:
    - required `SEC_EDGAR_USER_AGENT` header,
    - process-local rate limiting (default 10 rps),
    - retries with exponential backoff for transient SEC errors.
  - Extended `Instrument` with optional `cik` (10-digit padded) and wired CIK resolution into SEC ingestion.
  - Added `sec_artifacts` table/model for SEC filings:
    - RAW_FILING artifacts for primary HTML/iXBRL documents downloaded to `SEC_STORAGE_BASE_PATH`.
    - PARSED_TEXT artifacts for normalized plain-text derived from RAW_FILING.
  - Added `sec_parse_jobs` table/model for SEC parse jobs with idempotency via `parse:{artifact_id}:{parser_version}`.
  - Implemented ingestion orchestration (`ingest_sec_filings_for_ticker`):
    - deterministically selects the last N 10-K and last M 10-Q filings per CIK.
    - downloads primary documents, registers RAW_FILING artifacts, and creates PARSE_FILING jobs when needed.
  - Implemented Celery tasks:
    - `sec_ingest_filings_for_ticker` (idempotent ingestion wrapper).
    - `sec_parse_filing` (HTML/iXBRL → normalized text, PARSED_TEXT artifact persistence).
  - Exposed new API endpoints:
    - `POST /api/sec/{ticker}/ingest` — synchronous per-ticker ingestion.
    - `GET /api/sec/{ticker}/filings` — lists SEC filing artifacts + parse job status for a ticker/CIK.

### Risks / Mitigations
- **SEC rate limits / fair access violations**:
  - Mitigation: process-level rate limiter (`SEC_MAX_REQUEST_RATE`, default 10 rps) + required `SEC_EDGAR_USER_AGENT`.
  - Retries with backoff on 429/403/5xx and network failures; ingestion is safe but may be slow.
- **Local filesystem storage for SEC filings**:
  - Mitigation: deterministic `SEC_STORAGE_BASE_PATH/{cik}/{accession}/{primary_document}` paths and `SecArtifact.storage_path` pointers for reproducibility.
  - Future: swap `storage_backend` to object storage (e.g., S3) while keeping DB schema stable.
- **Parser V0 is simple (HTML tag stripping only)**:
  - Mitigation: store raw bytes + PARSED_TEXT separately with `parser_version` to allow richer parsers in future versions without losing history.

### Tests
- Added unit tests for SEC ingestion helpers (selection logic, artifact/job idempotency) and ran:
  - `pytest`
- Result: **PASS** (all existing + new tests).

### Next tasks
- Add richer SEC text parsing (section detection, table handling, MD&A / risk factor tagging) behind new `parser_version`s.
- Add chunking + embeddings pipeline for PARSED_TEXT artifacts and expose search/RAG over SEC filings.
- Add admin/ops views for SEC ingestion runs and parse job deadletters.


