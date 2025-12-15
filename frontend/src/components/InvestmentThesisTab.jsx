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

  if (error) {
    return (
      <div className="investment-thesis">
        <div className="thesis-error">
          <p>{error}</p>
        </div>
        {renderSecControls()}
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

