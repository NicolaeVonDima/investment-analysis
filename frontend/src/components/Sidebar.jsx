import React, { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import axios from 'axios'
import './Sidebar.css'

const Sidebar = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchQuery, setSearchQuery] = useState('')
  const [searchError, setSearchError] = useState(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [suggestions, setSuggestions] = useState([])

  const API_ROOT = (import.meta.env.VITE_API_URL || '').replace(/\/api\/?$/, '')
  const API_URL = `${API_ROOT}/api`

  const navItems = [
    { id: 'Home', icon: '🏠', label: 'Home' },
    { id: 'Browse', icon: '🌐', label: 'Browse' },
    { id: 'Compare', icon: '⚖️', label: 'Compare' },
    { id: 'Portfolio Builder', icon: '💼', label: 'Portfolio Builder' },
    { id: 'Watchlist', icon: '⭐', label: 'Watchlist', badge: 5 },
    { id: 'Articles', icon: '📄', label: 'Articles' },
  ]

  const handleSearch = async (e) => {
    if (e.key !== 'Enter') return
    const q = searchQuery.trim()
    if (!q) return
    const controller = new AbortController()
    setSearchLoading(true)
    setSearchError(null)
    setSuggestions([])
    try {
      const res = await axios.post(`${API_URL}/instruments/resolve`, { query: q }, { signal: controller.signal, timeout: 35000 })
      const ticker = res.data?.ticker || q.toUpperCase()
      navigate(`/browse/${encodeURIComponent(ticker)}`)
    } catch (err) {
      if (axios.isCancel?.(err) || err?.code === 'ERR_CANCELED') return
      const detail = err?.response?.data?.detail
      const msg = detail?.message || 'Ticker not found'
      setSearchError(msg)
      setSuggestions(detail?.suggestions || [])
    } finally {
      setSearchLoading(false)
    }
  }

  const selectedNav = location.pathname.startsWith('/watchlist')
    ? 'Watchlist'
    : location.pathname.startsWith('/browse')
      ? 'Browse'
      : 'Browse'

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <span className="logo-icon">✓</span>
          <span className="logo-text">Focus</span>
        </div>
      </div>

      <div className="search-container">
        <input
          type="text"
          className="search-input"
          placeholder="Q Search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={handleSearch}
          disabled={searchLoading}
        />
        <span className="search-placeholder">/</span>
      </div>
      {searchError && (
        <div style={{ padding: '0 16px 8px 16px', color: '#b91c1c', fontSize: 12 }}>
          {searchError}
          {!!suggestions.length && (
            <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {suggestions.map((s) => (
                <button
                  key={s}
                  style={{
                    border: '1px solid #fecaca',
                    background: '#fff5f5',
                    borderRadius: 999,
                    padding: '4px 8px',
                    cursor: 'pointer',
                    fontSize: 12,
                  }}
                  onClick={() => {
                    setSearchQuery(s)
                    setSearchError(null)
                    setSuggestions([])
                    navigate(`/browse/${encodeURIComponent(s)}`)
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <div
            key={item.id}
            className={`nav-item ${selectedNav === item.id ? 'active' : ''}`}
            onClick={() => {
              if (item.id === 'Watchlist') navigate('/watchlist')
              if (item.id === 'Browse') navigate('/browse/ADBE')
            }}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
            {item.badge && (
              <span className="nav-badge">{item.badge}</span>
            )}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="nav-item">
          <span className="nav-icon">⚙️</span>
          <span className="nav-label">Settings</span>
        </div>
        <div className="nav-item">
          <span className="nav-icon">❓</span>
          <span className="nav-label">Support</span>
        </div>
      </div>
    </div>
  )
}

export default Sidebar

