import React, { useEffect, useState } from 'react'
import axios from 'axios'
import './SecFilingsTab.css'

const SecFilingsTab = ({ ticker }) => {
  const [secFilings, setSecFilings] = useState(null)
  const [secFilingsLoading, setSecFilingsLoading] = useState(false)
  const [secFilingsError, setSecFilingsError] = useState(null)
  const [secLoading, setSecLoading] = useState(false)
  const [secError, setSecError] = useState(null)
  const [secResult, setSecResult] = useState(null)

  const API_ROOT = (import.meta.env.VITE_API_URL || '').replace(/\/api\/?$/, '')
  const API_URL = `${API_ROOT}/api`

  useEffect(() => {
    const fetchSecFilings = async () => {
      if (!ticker) {
        setSecFilings(null)
        return
      }

      setSecFilingsLoading(true)
      setSecFilingsError(null)
      try {
        const res = await axios.get(`${API_URL}/sec/${encodeURIComponent(ticker)}/filings`)
        setSecFilings(res.data)
      } catch (e) {
        // 404 is expected when no filings exist - don't treat as error
        if (e?.response?.status === 404) {
          setSecFilingsError(null)
          setSecFilings(null)
        } else {
          setSecFilingsError(e?.response?.data?.detail || e.message || 'Failed to load SEC filings')
          setSecFilings(null)
        }
      } finally {
        setSecFilingsLoading(false)
      }
    }

    fetchSecFilings()
  }, [ticker, secResult])

  const runSecIngestion = async () => {
    if (!ticker) return
    setSecLoading(true)
    setSecError(null)
    try {
      const res = await axios.post(`${API_URL}/sec/${encodeURIComponent(ticker)}/ingest`)
      setSecResult(res.data)
      // Trigger refresh of filings list
      const filingsRes = await axios.get(`${API_URL}/sec/${encodeURIComponent(ticker)}/filings`)
      setSecFilings(filingsRes.data)
    } catch (e) {
      const detail = e?.response?.data?.detail
      setSecError(detail || e.message || 'Failed to start SEC ingestion')
      setSecResult(null)
    } finally {
      setSecLoading(false)
    }
  }

  const getStatusBadgeClass = (status) => {
    if (!status) return 'sec-filings-status-badge-none'
    switch (status.toLowerCase()) {
      case 'done':
        return 'sec-filings-status-badge-done'
      case 'running':
        return 'sec-filings-status-badge-running'
      case 'failed':
      case 'deadletter':
        return 'sec-filings-status-badge-error'
      case 'queued':
        return 'sec-filings-status-badge-queued'
      default:
        return 'sec-filings-status-badge-none'
    }
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A'
    return new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  }

  if (secFilingsLoading) {
    return (
      <div className="sec-filings-container">
        <div className="sec-filings-loading">
          <p>Loading SEC filings...</p>
        </div>
      </div>
    )
  }

  if (secFilingsError) {
    return (
      <div className="sec-filings-container">
        <div className="sec-filings-error">
          <p>{secFilingsError}</p>
        </div>
      </div>
    )
  }

  const rawFilings = secFilings?.filings?.filter(f => f.artifact_kind === 'RAW_FILING') || []
  const parsedFilings = secFilings?.filings?.filter(f => f.artifact_kind === 'PARSED_TEXT') || []

  return (
    <div className="sec-filings-container">
      <div className="sec-filings-header">
        <div className="sec-filings-title-section">
          <h2>SEC Filings</h2>
          {secFilings && (
            <div className="sec-filings-stats">
              <span>CIK: {secFilings.cik}</span>
              <span>Raw: {rawFilings.length}</span>
              <span>Parsed: {parsedFilings.length}</span>
            </div>
          )}
        </div>
        <div className="sec-filings-controls">
          <button
            className="sec-filings-button"
            type="button"
            onClick={runSecIngestion}
            disabled={secLoading || !ticker}
          >
            {secLoading ? 'Starting SEC workflow…' : 'Run SEC 10-K / 10-Q Ingestion'}
          </button>
          {secError && (
            <span className="sec-filings-status sec-filings-status-error">
              {String(secError)}
            </span>
          )}
          {!secError && secResult && (
            <span className="sec-filings-status sec-filings-status-ok">
              {`CIK ${secResult.cik} • filings: ${secResult.selected_count} • new raw: ${secResult.created_raw_count} • new parse jobs: ${secResult.created_parse_job_count}`}
            </span>
          )}
        </div>
      </div>

      {!secFilings || !secFilings.filings || secFilings.filings.length === 0 ? (
        <div className="sec-filings-empty">
          <p>No SEC filings found for this ticker. Run ingestion to fetch filings.</p>
        </div>
      ) : (
        <div className="sec-filings-table">
          <table>
            <thead>
              <tr>
                <th>Form</th>
                <th>Filing Date</th>
                <th>Period End</th>
                <th>Accession</th>
                <th>Status</th>
                <th>Download</th>
              </tr>
            </thead>
            <tbody>
              {rawFilings.map((filing) => (
                <tr key={filing.artifact_id}>
                  <td>
                    <span className={`sec-filings-form-type sec-filings-form-type-${filing.form_type.toLowerCase().replace('/', '-')}`}>
                      {filing.form_type}
                    </span>
                  </td>
                  <td>{formatDate(filing.filing_date)}</td>
                  <td>{formatDate(filing.period_end)}</td>
                  <td className="sec-filings-accession">{filing.accession_number}</td>
                  <td>
                    {filing.parse_job_status && (
                      <span className={`sec-filings-status-badge ${getStatusBadgeClass(filing.parse_job_status)}`}>
                        {filing.parse_job_status}
                      </span>
                    )}
                    {filing.parser_version && (
                      <span className="sec-filings-parser-version">v{filing.parser_version}</span>
                    )}
                  </td>
                  <td>
                    <a
                      href={`${API_URL}/sec/artifacts/${filing.artifact_id}/download`}
                      className="sec-filings-download-link"
                      download
                      title="Download filing document"
                    >
                      ⬇ Download
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default SecFilingsTab

