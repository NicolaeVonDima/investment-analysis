import React, { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import './WatchlistView.css'

const WatchlistView = () => {
  const API_URL = import.meta.env.VITE_API_URL || '/api'
  const userId = 'demo'

  const [watchlists, setWatchlists] = useState([])
  const [selectedWatchlistId, setSelectedWatchlistId] = useState(null)
  const [items, setItems] = useState([])
  const [status, setStatus] = useState(null)
  const [newWatchlistName, setNewWatchlistName] = useState('')
  const [newTicker, setNewTicker] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const headers = useMemo(() => ({ 'X-User-Id': userId }), [userId])

  const loadWatchlists = async () => {
    const res = await axios.get(`${API_URL}/watchlists`, { headers })
    setWatchlists(res.data || [])
    if (!selectedWatchlistId && res.data?.length) {
      setSelectedWatchlistId(res.data[0].id)
    }
  }

  const loadItems = async (watchlistId) => {
    if (!watchlistId) return
    const res = await axios.get(`${API_URL}/watchlists/${watchlistId}/items`, { headers })
    setItems(res.data || [])
  }

  const loadStatus = async (watchlistId) => {
    if (!watchlistId) return
    const res = await axios.get(`${API_URL}/watchlists/${watchlistId}/status`, { headers })
    setStatus(res.data)
  }

  const refreshAll = async () => {
    await axios.post(`${API_URL}/admin/refresh/watchlists/run`)
    // best-effort: reload status shortly after
    setTimeout(() => loadStatus(selectedWatchlistId), 1500)
  }

  useEffect(() => {
    const run = async () => {
      setLoading(true)
      setError(null)
      try {
        await loadWatchlists()
      } catch (e) {
        setError(e?.response?.data?.detail || e.message)
      } finally {
        setLoading(false)
      }
    }
    run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const run = async () => {
      if (!selectedWatchlistId) return
      try {
        await Promise.all([loadItems(selectedWatchlistId), loadStatus(selectedWatchlistId)])
      } catch (e) {
        setError(e?.response?.data?.detail || e.message)
      }
    }
    run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWatchlistId])

  const createWatchlist = async () => {
    if (!newWatchlistName.trim()) return
    setError(null)
    try {
      const res = await axios.post(
        `${API_URL}/watchlists`,
        { name: newWatchlistName.trim(), is_active: true },
        { headers }
      )
      setNewWatchlistName('')
      await loadWatchlists()
      setSelectedWatchlistId(res.data.id)
    } catch (e) {
      setError(e?.response?.data?.detail || e.message)
    }
  }

  const addTicker = async () => {
    if (!newTicker.trim() || !selectedWatchlistId) return
    setError(null)
    try {
      await axios.post(
        `${API_URL}/watchlists/${selectedWatchlistId}/items`,
        { ticker: newTicker.trim().toUpperCase() },
        { headers }
      )
      setNewTicker('')
      await Promise.all([loadItems(selectedWatchlistId), loadStatus(selectedWatchlistId)])
    } catch (e) {
      setError(e?.response?.data?.detail || e.message)
    }
  }

  const removeItem = async (itemId) => {
    setError(null)
    try {
      await axios.delete(`${API_URL}/watchlists/${selectedWatchlistId}/items/${itemId}`, { headers })
      await Promise.all([loadItems(selectedWatchlistId), loadStatus(selectedWatchlistId)])
    } catch (e) {
      setError(e?.response?.data?.detail || e.message)
    }
  }

  const statusByTicker = useMemo(() => {
    const map = new Map()
    if (status?.items) {
      for (const s of status.items) map.set(s.ticker, s)
    }
    return map
  }, [status])

  return (
    <div className="watchlist-view">
      <div className="watchlist-header">
        <div>
          <h2>Watchlists</h2>
          <p className="watchlist-subtitle">
            Data refresh is global: a ticker is fetched at most once per day and shared across all users.
          </p>
        </div>
        <button className="watchlist-btn" onClick={refreshAll}>
          Trigger Refresh
        </button>
      </div>

      {error && <div className="watchlist-error">{error}</div>}
      {loading && <div className="watchlist-loading">Loading…</div>}

      <div className="watchlist-grid">
        <div className="watchlist-panel">
          <div className="watchlist-panel-header">
            <span>My Watchlists</span>
          </div>

          <div className="watchlist-create">
            <input
              className="watchlist-input"
              placeholder="New watchlist name"
              value={newWatchlistName}
              onChange={(e) => setNewWatchlistName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && createWatchlist()}
            />
            <button className="watchlist-btn" onClick={createWatchlist}>
              Create
            </button>
          </div>

          <div className="watchlist-list">
            {watchlists.map((wl) => (
              <div
                key={wl.id}
                className={`watchlist-row ${wl.id === selectedWatchlistId ? 'active' : ''}`}
                onClick={() => setSelectedWatchlistId(wl.id)}
              >
                <span className="watchlist-name">{wl.name}</span>
                <span className={`watchlist-pill ${wl.is_active ? 'ok' : 'off'}`}>
                  {wl.is_active ? 'Active' : 'Paused'}
                </span>
              </div>
            ))}
            {!watchlists.length && !loading && <div className="watchlist-empty">No watchlists yet.</div>}
          </div>
        </div>

        <div className="watchlist-panel">
          <div className="watchlist-panel-header">
            <span>Tickers</span>
            {status?.as_of_date && <span className="watchlist-muted">As of {status.as_of_date}</span>}
          </div>

          <div className="watchlist-create">
            <input
              className="watchlist-input"
              placeholder="Add ticker (e.g. AAPL)"
              value={newTicker}
              onChange={(e) => setNewTicker(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addTicker()}
            />
            <button className="watchlist-btn" onClick={addTicker}>
              Add
            </button>
          </div>

          <div className="watchlist-items">
            {items.map((it) => {
              const s = statusByTicker.get(it.ticker)
              const stale = s?.stale
              return (
                <div key={it.id} className="watchlist-item">
                  <div className="watchlist-item-left">
                    <div className="watchlist-ticker">{it.ticker}</div>
                    <div className="watchlist-meta">
                      <span className={`watchlist-pill ${stale ? 'stale' : 'ok'}`}>
                        {stale ? 'Stale' : 'Fresh'}
                      </span>
                      <span className="watchlist-muted">
                        Last snapshot: {s?.last_snapshot_date || '—'}
                      </span>
                      {s?.last_refresh_job_status && (
                        <span className="watchlist-muted">Job: {s.last_refresh_job_status}</span>
                      )}
                    </div>
                  </div>
                  <button className="watchlist-btn danger" onClick={() => removeItem(it.id)}>
                    Remove
                  </button>
                </div>
              )
            })}
            {!items.length && !loading && <div className="watchlist-empty">No tickers in this watchlist.</div>}
          </div>
        </div>
      </div>
    </div>
  )
}

export default WatchlistView


