import React, { useEffect, useState } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import './InvestmentThesisTab.css'

const InvestmentThesisTab = ({ ticker }) => {
  const [thesis, setThesis] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [secLoading, setSecLoading] = useState(false)
  const [secError, setSecError] = useState(null)
  const [secResult, setSecResult] = useState(null)
  const [fundamentalsSummary, setFundamentalsSummary] = useState(null)
  const [fundamentalsView, setFundamentalsView] = useState('aggregate')
  const [fundamentalsLoading, setFundamentalsLoading] = useState(false)
  const [fundamentalsError, setFundamentalsError] = useState(null)
  const [alertsHistory, setAlertsHistory] = useState([])
  const [alertsHistoryLoading, setAlertsHistoryLoading] = useState(false)
  const [alertsHistoryError, setAlertsHistoryError] = useState(null)
  const [reprocessLoading, setReprocessLoading] = useState(false)
  const [reprocessError, setReprocessError] = useState(null)
  const [reprocessResult, setReprocessResult] = useState(null)

  const API_ROOT = (import.meta.env.VITE_API_URL || '').replace(/\/api\/?$/, '')
  const API_URL = `${API_ROOT}/api`

  useEffect(() => {
    const fetchThesis = async () => {
      if (!ticker) {
        setLoading(false)
        return
      }

      setLoading(true)
      setError(null)
      try {
        const res = await axios.get(`${API_URL}/instruments/${encodeURIComponent(ticker)}/thesis`)
        setThesis(res.data)
      } catch (e) {
        // 404 is expected when no thesis exists - don't treat as error
        if (e?.response?.status === 404) {
          setError(null) // Clear error state for expected 404
          setThesis(null)
        } else {
          setError(e?.response?.data?.detail || e.message || 'Failed to load investment thesis')
          setThesis(null)
        }
      } finally {
        setLoading(false)
      }
    }

    fetchThesis()
  }, [ticker])

  useEffect(() => {
    const fetchFundamentals = async () => {
      if (!ticker) {
        setFundamentalsSummary(null)
        return
      }
      setFundamentalsLoading(true)
      setFundamentalsError(null)
      try {
        const res = await axios.get(
          `${API_URL}/instruments/${encodeURIComponent(ticker)}/sec/fundamentals/perspectives`
        )
        setFundamentalsSummary(res.data)
      } catch (e) {
        setFundamentalsError(e?.response?.data?.detail || e.message || 'Failed to load fundamentals changes')
        setFundamentalsSummary(null)
      } finally {
        setFundamentalsLoading(false)
      }
    }

    fetchFundamentals()
  }, [ticker, secResult, reprocessResult])

  useEffect(() => {
    const fetchAlertsHistory = async () => {
      if (!ticker) {
        setAlertsHistory([])
        return
      }
      setAlertsHistoryLoading(true)
      setAlertsHistoryError(null)
      try {
        const res = await axios.get(
          `${API_URL}/instruments/${encodeURIComponent(ticker)}/sec/fundamentals/alerts?status=all&limit=20`
        )
        setAlertsHistory(res.data?.alerts || [])
      } catch (e) {
        setAlertsHistoryError(e?.response?.data?.detail || e.message || 'Failed to load alert history')
        setAlertsHistory([])
      } finally {
        setAlertsHistoryLoading(false)
      }
    }

    fetchAlertsHistory()
  }, [ticker, secResult, reprocessResult])

  const runSecIngestion = async () => {
    if (!ticker) return
    setSecLoading(true)
    setSecError(null)
    try {
      const res = await axios.post(`${API_URL}/sec/${encodeURIComponent(ticker)}/ingest`)
      setSecResult(res.data)
    } catch (e) {
      const detail = e?.response?.data?.detail
      setSecError(detail || e.message || 'Failed to start SEC ingestion')
      setSecResult(null)
    } finally {
      setSecLoading(false)
    }
  }

  const runReprocess = async () => {
    if (!ticker) return
    setReprocessLoading(true)
    setReprocessError(null)
    setReprocessResult(null)
    try {
      const res = await axios.post(`${API_URL}/sec/${encodeURIComponent(ticker)}/fundamentals/reprocess`)
      setReprocessResult(res.data)
    } catch (e) {
      setReprocessError(e?.response?.data?.detail || e.message || 'Failed to reprocess SEC fundamentals')
    } finally {
      setReprocessLoading(false)
    }
  }

  const formatValue = (value, unit) => {
    if (value === null || value === undefined || Number.isNaN(value)) return 'N/A'
    if (unit === 'PERCENT') return `${(value || 0).toFixed(2)}%`
    if (unit === 'USD') {
      const absValue = Math.abs(value)
      if (absValue >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`
      if (absValue >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`
      if (absValue >= 1_000) return `$${(value / 1_000).toFixed(2)}K`
      return `$${value.toFixed(2)}`
    }
    return `${value}`
  }

  if (loading) {
    return (
      <div className="thesis-loading">
        <p>Loading investment thesis...</p>
      </div>
    )
  }

  // Render SEC controls section (always visible)
  const renderSecControls = () => (
    <div className="thesis-sec-controls">
      <button
        className="thesis-sec-button"
        type="button"
        onClick={runSecIngestion}
        disabled={secLoading || !ticker}
      >
        {secLoading ? 'Starting SEC workflow…' : 'Run SEC 10-K / 10-Q Ingestion'}
      </button>
      {secError && (
        <span className="thesis-sec-status thesis-sec-status-error">
          {String(secError)}
        </span>
      )}
      {!secError && secResult && (
        <span className="thesis-sec-status thesis-sec-status-ok">
          {`CIK ${secResult.cik} • filings: ${secResult.selected_count} • new raw: ${secResult.created_raw_count} • new parse jobs: ${secResult.created_parse_job_count}`}
        </span>
      )}
    </div>
  )

  const renderFundamentalsSection = () => {
    if (fundamentalsLoading) {
      return (
        <section className="thesis-section thesis-fundamentals">
          <h2>Fundamentals Change</h2>
          <div className="thesis-fundamentals-loading">Loading fundamentals changes...</div>
        </section>
      )
    }

    if (fundamentalsError) {
      return (
        <section className="thesis-section thesis-fundamentals">
          <h2>Fundamentals Change</h2>
          <div className="thesis-fundamentals-error">{fundamentalsError}</div>
        </section>
      )
    }

    const viewData = fundamentalsSummary?.[fundamentalsView] || null

    if (!viewData || !viewData.latest_snapshot) {
      return (
        <section className="thesis-section thesis-fundamentals">
          <h2>Fundamentals Change</h2>
          <div className="thesis-fundamentals-tabs">
            <button
              type="button"
              className={`thesis-fundamentals-tab ${fundamentalsView === 'aggregate' ? 'active' : ''}`}
              onClick={() => setFundamentalsView('aggregate')}
            >
              Aggregate
            </button>
            <button
              type="button"
              className={`thesis-fundamentals-tab ${fundamentalsView === '10k' ? 'active' : ''}`}
              onClick={() => setFundamentalsView('10k')}
            >
              10-K
            </button>
            <button
              type="button"
              className={`thesis-fundamentals-tab ${fundamentalsView === '10q' ? 'active' : ''}`}
              onClick={() => setFundamentalsView('10q')}
            >
              10-Q
            </button>
          </div>
          <div className="thesis-fundamentals-controls">
            <button
              className="thesis-fundamentals-button"
              type="button"
              onClick={runReprocess}
              disabled={reprocessLoading || !ticker}
            >
              {reprocessLoading ? 'Reprocessing…' : 'Reprocess SEC Fundamentals'}
            </button>
            {reprocessError && (
              <span className="thesis-fundamentals-status error">{reprocessError}</span>
            )}
            {!reprocessError && reprocessResult && (
              <span className="thesis-fundamentals-status ok">
                {`Queued ${reprocessResult.enqueued} parsed filings`}
              </span>
            )}
          </div>
          <div className="thesis-fundamentals-empty">No SEC fundamentals extracted yet.</div>
        </section>
      )
    }

    const viewLabel = fundamentalsView === 'aggregate'
      ? 'Aggregate'
      : fundamentalsView === '10k'
        ? '10-K'
        : '10-Q'

    return (
      <section className="thesis-section thesis-fundamentals">
        <h2>Fundamentals Change</h2>
        <div className="thesis-fundamentals-tabs">
          <button
            type="button"
            className={`thesis-fundamentals-tab ${fundamentalsView === 'aggregate' ? 'active' : ''}`}
            onClick={() => setFundamentalsView('aggregate')}
          >
            Aggregate
          </button>
          <button
            type="button"
            className={`thesis-fundamentals-tab ${fundamentalsView === '10k' ? 'active' : ''}`}
            onClick={() => setFundamentalsView('10k')}
          >
            10-K
          </button>
          <button
            type="button"
            className={`thesis-fundamentals-tab ${fundamentalsView === '10q' ? 'active' : ''}`}
            onClick={() => setFundamentalsView('10q')}
          >
            10-Q
          </button>
          <span className="thesis-fundamentals-view">{viewLabel}</span>
        </div>
        <div className="thesis-fundamentals-controls">
          <button
            className="thesis-fundamentals-button"
            type="button"
            onClick={runReprocess}
            disabled={reprocessLoading || !ticker}
          >
            {reprocessLoading ? 'Reprocessing…' : 'Reprocess SEC Fundamentals'}
          </button>
          {reprocessError && (
            <span className="thesis-fundamentals-status error">{reprocessError}</span>
          )}
          {!reprocessError && reprocessResult && (
            <span className="thesis-fundamentals-status ok">
              {`Queued ${reprocessResult.enqueued} parsed filings`}
            </span>
          )}
        </div>
        <div className="thesis-fundamentals-meta">
          <span>Form: {viewData.latest_snapshot.form_type}</span>
          <span>Filed: {new Date(viewData.latest_snapshot.filing_date).toLocaleDateString()}</span>
          {viewData.latest_snapshot.period_end && (
            <span>Period End: {new Date(viewData.latest_snapshot.period_end).toLocaleDateString()}</span>
          )}
        </div>

        <div className="thesis-fundamentals-grid">
          <div className="thesis-fundamentals-card">
            <h3>Top Changes</h3>
            {viewData.top_changes.length ? (
              <ul>
                {viewData.top_changes.map((change) => (
                  <li key={`${change.metric_key}-${change.period || 'na'}`}>
                    <div className="thesis-fundamentals-row">
                      <span className="thesis-fundamentals-label">{change.metric_label}</span>
                      <span className={`thesis-fundamentals-badge ${change.severity || 'info'}`}>
                        {(change.severity || 'info').toUpperCase()}
                      </span>
                    </div>
                    <div className="thesis-fundamentals-values">
                      <span>{formatValue(change.prev_value, change.unit)} → {formatValue(change.curr_value, change.unit)}</span>
                      {change.delta_pct !== null && change.delta_pct !== undefined && (
                        <span className="thesis-fundamentals-delta">
                          {(change.delta_pct * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="thesis-fundamentals-empty">No change signals detected yet.</p>
            )}
          </div>

          <div className="thesis-fundamentals-card">
            <h3>Active Alerts</h3>
            {viewData.alerts.length ? (
              <ul>
                {viewData.alerts.map((alert) => (
                  <li key={alert.id}>
                    <div className="thesis-fundamentals-row">
                      <span className="thesis-fundamentals-label">{alert.message}</span>
                      <span className={`thesis-fundamentals-badge ${alert.severity}`}>
                        {alert.severity.toUpperCase()}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="thesis-fundamentals-empty">No active alerts.</p>
            )}
          </div>

          <div className="thesis-fundamentals-card">
            <h3>Alert History</h3>
            {alertsHistoryLoading && (
              <p className="thesis-fundamentals-empty">Loading alert history...</p>
            )}
            {alertsHistoryError && (
              <p className="thesis-fundamentals-error">{alertsHistoryError}</p>
            )}
            {!alertsHistoryLoading && !alertsHistoryError && alertsHistory.length ? (
              <ul>
                {alertsHistory.map((alert) => (
                  <li key={`history-${alert.id}`}>
                    <div className="thesis-fundamentals-row">
                      <span className="thesis-fundamentals-label">{alert.message}</span>
                      <span className={`thesis-fundamentals-badge ${alert.severity}`}>
                        {alert.status.toUpperCase()}
                      </span>
                    </div>
                    <div className="thesis-fundamentals-values">
                      <span>{new Date(alert.triggered_at).toLocaleDateString()}</span>
                      {alert.resolved_at && (
                        <span>Resolved {new Date(alert.resolved_at).toLocaleDateString()}</span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              !alertsHistoryLoading &&
              !alertsHistoryError && <p className="thesis-fundamentals-empty">No alerts yet.</p>
            )}
          </div>
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <div className="investment-thesis">
        <div className="thesis-error">
          <p>{error}</p>
        </div>
        {renderSecControls()}
        {renderFundamentalsSection()}
      </div>
    )
  }

  if (!thesis) {
    return (
      <div className="investment-thesis">
        <div className="thesis-empty">
          <p>No investment thesis available for this ticker.</p>
        </div>
        {renderSecControls()}
        {renderFundamentalsSection()}
      </div>
    )
  }

  return (
    <div className="investment-thesis">
      <div className="thesis-header">
        <h1 className="thesis-title">{thesis.title}</h1>
        <div className="thesis-meta">
          <span className="thesis-date">Date: {thesis.date}</span>
          {thesis.current_price && (
            <span className="thesis-price">Current Price: ${thesis.current_price.toFixed(2)}</span>
          )}
          <span className="thesis-recommendation">Recommendation: {thesis.recommendation}</span>
        </div>
        {renderSecControls()}
      </div>

      <div className="thesis-content">
        <section className="thesis-section">
          <h2>Executive Summary</h2>
          <div className="thesis-text">
            <ReactMarkdown>{thesis.executive_summary}</ReactMarkdown>
          </div>
        </section>

        <section className="thesis-section">
          <h2>Investment Thesis</h2>
          <div className="thesis-text">
            <ReactMarkdown>{thesis.thesis_content}</ReactMarkdown>
          </div>
        </section>

        {thesis.action_plan && (
          <section className="thesis-section">
            <h2>Action Plan</h2>
            <div className="thesis-text">
              <ReactMarkdown>{thesis.action_plan}</ReactMarkdown>
            </div>
          </section>
        )}

        {thesis.conclusion && (
          <section className="thesis-section">
            <h2>Conclusion</h2>
            <div className="thesis-text">
              <ReactMarkdown>{thesis.conclusion}</ReactMarkdown>
            </div>
          </section>
        )}

        {renderFundamentalsSection()}
      </div>

      <div className="thesis-footer">
        <p className="thesis-timestamp">
          Created: {new Date(thesis.created_at).toLocaleString()} | 
          Updated: {new Date(thesis.updated_at).toLocaleString()}
        </p>
      </div>
    </div>
  )
}

export default InvestmentThesisTab
