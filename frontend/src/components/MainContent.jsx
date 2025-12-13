import React, { useState, useEffect } from 'react'
import axios from 'axios'
import PerformanceTab from './PerformanceTab'
import WatchlistView from './WatchlistView'
import './MainContent.css'

const MainContent = ({ ticker, selectedTab: initialTab, selectedNav }) => {
  const [selectedTab, setSelectedTab] = useState(initialTab || 'Performance')
  const [analysisData, setAnalysisData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [addingToWatchlist, setAddingToWatchlist] = useState(false)
  const [watchlistAdded, setWatchlistAdded] = useState(false)
  const [instrument, setInstrument] = useState(null)
  const [lite, setLite] = useState(null)
  const [liteLoading, setLiteLoading] = useState(false)
  const [liteError, setLiteError] = useState(null)
  const [priceSeries, setPriceSeries] = useState(null)
  const [priceSeriesError, setPriceSeriesError] = useState(null)

  const tabs = [
    'Key Data',
    'Performance',
    'Allocation',
    'Risk Analysis',
    'Sustainability',
    'Stock Exchange'
  ]

  const API_ROOT = (import.meta.env.VITE_API_URL || '').replace(/\/api\/?$/, '')
  const API_URL = `${API_ROOT}/api`

  const handleAnalyze = async () => {
    if (!ticker) return
    
    setLoading(true)
    try {
      const response = await axios.post(`${API_URL}/analyze`, {
        ticker: ticker
      })
      setJobId(response.data.job_id)
      // Poll for status
      pollStatus(response.data.job_id)
    } catch (error) {
      console.error('Error submitting analysis:', error)
      setLoading(false)
    }
  }

  const pollStatus = async (id) => {
    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${API_URL}/status/${id}`)
        if (response.data.status === 'completed') {
          clearInterval(interval)
          const result = await axios.get(`${API_URL}/result/${id}/json`)
          setAnalysisData(result.data)
          setLoading(false)
        } else if (response.data.status === 'failed') {
          clearInterval(interval)
          setLoading(false)
          alert('Analysis failed: ' + response.data.error)
        }
      } catch (error) {
        console.error('Error polling status:', error)
        clearInterval(interval)
        setLoading(false)
      }
    }, 2000)
  }

  useEffect(() => {
    // Browse-lite (24h cached, may refresh from provider synchronously)
    const run = async () => {
      if (!ticker) return
      setLiteLoading(true)
      setLiteError(null)
      try {
        const res = await axios.get(`${API_URL}/instruments/${encodeURIComponent(ticker)}/browse-lite`)
        setLite(res.data)
        setInstrument({ id: res.data.instrument_id, canonical_symbol: res.data.ticker, name: res.data.name, currency: res.data.currency, exchange: res.data.exchange })
      } catch (e) {
        setLiteError(e?.response?.data?.detail || e.message)
        setLite(null)
        setInstrument(null)
      } finally {
        setLiteLoading(false)
      }
    }
    run()
  }, [ticker])

  useEffect(() => {
    // Price series for chart (DB-backed, may do one provider fetch if missing)
    const run = async () => {
      if (!ticker) return
      setPriceSeriesError(null)
      try {
        const res = await axios.get(`${API_URL}/instruments/${encodeURIComponent(ticker)}/prices`, { params: { limit: 260 } })
        setPriceSeries(res.data)
      } catch (e) {
        setPriceSeries(null)
        setPriceSeriesError(e?.response?.data?.detail || e.message)
      }
    }
    run()
  }, [ticker])

  const addToWatchlist = async () => {
    if (!ticker) return
    setAddingToWatchlist(true)
    try {
      await axios.post(`${API_URL}/watchlists/default/add`, { ticker }, { headers: { 'X-User-Id': 'demo' } })
      setWatchlistAdded(true)
      setTimeout(() => setWatchlistAdded(false), 2500)
    } catch (e) {
      console.error('Failed to add to watchlist:', e)
      alert('Failed to add to watchlist')
    } finally {
      setAddingToWatchlist(false)
    }
  }

  if (selectedNav === 'Watchlist') {
    return <WatchlistView />
  }

  // Mock data for demonstration
  const companyName =
    lite?.name ||
    instrument?.name ||
    (ticker ? `${ticker} Stock` : 'Unknown')

  const seriesLatest = priceSeries?.points?.length ? priceSeries.points[priceSeries.points.length - 1] : null

  const mockData = {
    company: {
      name: companyName,
      ticker: ticker || 'IE00B4L5Y983'
    },
    // Prefer series (chart) last close to avoid showing stale/cached browse-lite values.
    currentPrice:
      typeof seriesLatest?.close === 'number'
        ? seriesLatest.close
        : (typeof lite?.close === 'number' ? lite.close : null),
    change: null,
    changePercent: typeof lite?.change_pct === 'number' ? lite.change_pct * 100 : null,
    rating: 4.72,
    fundSize: '$99869m',
    ter: '0.20%',
    holdings: "1'395 Holdings"
  }

  return (
    <div className="main-content">
      <div className="breadcrumb">
        Browse &gt; {mockData.company.ticker}
      </div>

      <div className="product-header">
        <div className="product-title-section">
          <h1 className="product-title">{mockData.company.name}</h1>
          <div className="product-rating">
            <span className="rating-value">{mockData.rating}</span>
            <span className="rating-star">⭐</span>
          </div>
          <div style={{ marginTop: 6, fontSize: 12, color: '#666' }}>
            {liteLoading ? 'Loading snapshot…' : liteError ? `Snapshot error: ${liteError}` : null}
            {!liteLoading && !liteError && priceSeriesError ? <span>{` • Chart data error: ${priceSeriesError}`}</span> : null}
            {!liteLoading && !liteError && lite ? (
              <>
                <span>{lite.stale ? 'Stale' : 'Fresh'}</span>
                {lite.as_of_date ? <span>{` • as of ${lite.as_of_date}`}</span> : null}
                {lite.last_refresh_at ? <span>{` • refreshed ${lite.last_refresh_at}`}</span> : null}
                {typeof lite.staleness_hours === 'number' ? <span>{` • ${lite.staleness_hours.toFixed(1)}h old`}</span> : null}
              </>
            ) : null}
          </div>
        </div>

        <div className="product-actions">
          <button className="action-btn">
            <span>⚖️</span> Compare
          </button>
          <button className="action-btn">
            <span>⬇️</span> Download Factsheet
          </button>
          <button
            className="action-btn"
            disabled={!instrument?.id}
            onClick={async () => {
              if (!instrument?.id) return
              await axios.post(`${API_URL}/instruments/${instrument.id}/backfill`)
              alert('Backfill queued')
            }}
          >
            <span>⏳</span> Backfill
          </button>
          <button className="action-btn primary" onClick={addToWatchlist} disabled={addingToWatchlist}>
            {watchlistAdded ? 'Added to Watchlist' : addingToWatchlist ? 'Adding…' : 'Add to Watchlist'}
          </button>
        </div>
      </div>

      <div className="product-meta">
        <div className="meta-item">
          <span className="meta-icon">📊</span>
          <span>Accumulating Distribution</span>
        </div>
        <div className="meta-item">
          <span>{mockData.fundSize} Fund Size</span>
        </div>
        <div className="meta-item">
          <span>{mockData.ter} TER</span>
        </div>
        <div className="meta-item">
          <span>Physical Replication</span>
        </div>
        <div className="meta-item">
          <span>{mockData.holdings} Holdings</span>
        </div>
        <div className="meta-item">
          <span>🇮🇪</span>
          <span>iShares/Ireland Provider/Domicile</span>
        </div>
        <div className="meta-item">
          <span>{mockData.company.ticker} ISIN</span>
          <span className="copy-icon">📋</span>
        </div>
      </div>

      <div className="tabs">
        {tabs.map((tab) => (
          <button
            key={tab}
            className={`tab ${selectedTab === tab ? 'active' : ''}`}
            onClick={() => setSelectedTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {selectedTab === 'Performance' && (
          <PerformanceTab 
            data={analysisData} 
            mockData={mockData}
            loading={loading}
            priceSeries={priceSeries}
          />
        )}
        {selectedTab === 'Key Data' && (
          <div className="placeholder-content">
            <p>Key Data content will be displayed here</p>
          </div>
        )}
        {selectedTab === 'Allocation' && (
          <div className="placeholder-content">
            <p>Allocation content will be displayed here</p>
          </div>
        )}
        {selectedTab === 'Risk Analysis' && (
          <div className="placeholder-content">
            <p>Risk Analysis content will be displayed here</p>
          </div>
        )}
        {selectedTab === 'Sustainability' && (
          <div className="placeholder-content">
            <p>Sustainability content will be displayed here</p>
          </div>
        )}
        {selectedTab === 'Stock Exchange' && (
          <div className="placeholder-content">
            <p>Stock Exchange content will be displayed here</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default MainContent

