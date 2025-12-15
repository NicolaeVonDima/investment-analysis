## 2025-12-13 — Alpha Vantage (MVP provider)

Source: [Spec_DataProvider_AlphaVantage_Composable_Fetch.pdf](file://Spec_DataProvider_AlphaVantage_Composable_Fetch.pdf)

### Provider
- **Name**: Alpha Vantage
- **Mode**: free-tier key (MVP)

### Access / Configuration
- **Env var**: `ALPHAVANTAGE_API_KEY`
- **Local config**: keep secrets in a local env file (not committed), e.g. `config/alpha_vantage.secrets.env`

### Local debugging (no-credit mock mode)
- **Env var**: `ALPHAVANTAGE_MOCK=1`
- When enabled, the app uses deterministic local fixtures for Alpha Vantage endpoints (no network calls; no API key required).
- Intended for UI/API debugging without consuming free-tier credits.

### Refresh cadence
- **UI-lite**: serve from DB if present; otherwise queue refresh and return last snapshot with staleness.
- **Backfill**: on-demand async job; stores >=5y daily adjusted EOD and fundamentals where available.

### Constraints / Limitations
- **Free-tier rate limiting** (call volume constraints).
- Expect intermittent throttling; system must degrade gracefully by serving last-known values and marking staleness.

### Data stored (MVP)
- `instrument`: canonical symbols + identity fields
- `provider_symbol_map`: provider aliases to instrument
- `price_eod`: daily prices unique by instrument/date
- `fundamentals_snapshot`: statement snapshots unique by instrument/period
- `provider_refresh_jobs`: auditable, idempotent work tracking


## 2025-12-15 — SEC EDGAR (10-K / 10-Q Ingestion V0)

Source: [SEC_Ingestion_Parse_Pipeline_V0_Functional_Spec.pdf](file://SEC_Ingestion_Parse_Pipeline_V0_Functional_Spec.pdf)

### Provider
- **Name**: SEC EDGAR
- **Mode**: public HTTP APIs with fair use constraints

### Access / Configuration
- **Env vars**:
  - `SEC_INTEGRATION_ENABLED` (default `1`): global toggle for SEC ingestion.
  - `SEC_EDGAR_USER_AGENT` (required): identity + contact string for all SEC requests.
  - `SEC_MAX_REQUEST_RATE` (default `10`): max requests per second (client-side rate limiting).
  - `SEC_RETRY_MAX_ATTEMPTS` (default `3`): transient error retry attempts.
  - `SEC_10K_LOOKBACK` (default `2`): number of most recent 10-K filings per ticker.
  - `SEC_10Q_LOOKBACK` (default `8`): number of most recent 10-Q filings per ticker.
  - `SEC_INCLUDE_AMENDMENTS` (default `0`): when `1`, include 10-K/A and 10-Q/A in eligible forms.
  - `SEC_STORAGE_BASE_PATH` (default `./sec_filings`): base directory for downloaded filings and parsed text.
  - `SEC_PARSER_VERSION` (default `v0`): label for parsing logic, used in job idempotency keys.
  - `SEC_PARSE_MAX_ATTEMPTS` (default `3`): max attempts per parse job before deadletter.

### Endpoints used
- `https://www.sec.gov/files/company_tickers.json` — ticker → CIK resolution (10-digit padded).
- `https://data.sec.gov/submissions/CIK##########.json` — company submissions index by CIK.
- `https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{primary_document}` — primary filing documents (HTML/iXBRL).

### Data stored (V0)
- `sec_artifacts`:
  - Raw filings (HTML/iXBRL) with storage path, file name, and content hash.
  - Parsed text artifacts (plain text) linked back to raw via `parent_artifact_id`.
  - Provenance fields: `source=SEC_EDGAR`, `ticker`, `instrument_id`, `cik`, `accession_number`, `form_type`, `filing_date`, `period_end`.
- `sec_parse_jobs`:
  - Asynchronous parse jobs with `idempotency_key=parse:{artifact_id}:{parser_version}`, status, attempts, and error details.
- `instruments`:
  - Extended with optional `cik` (10-digit padded) to tie SEC filings to canonical instruments used across the platform.

### Constraints / Limitations
- SEC rate limits and fair access policies must be respected:
  - At most **10 requests/second** (client-enforced).
  - Required **User-Agent** header with contact info.
  - Backoff on 429/403/5xx; ingestion may be slow but should not hammer SEC endpoints.
- V0 does **not** handle:
  - OCR for image-only filings.
  - XBRL-specific semantic parsing beyond best-effort HTML/iXBRL text extraction.


