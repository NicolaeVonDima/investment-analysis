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


