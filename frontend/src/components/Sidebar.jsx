import React, { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import './Sidebar.css'

const Sidebar = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchQuery, setSearchQuery] = useState('')

  const navItems = [
    { id: 'Home', icon: '🏠', label: 'Home' },
    { id: 'Browse', icon: '🌐', label: 'Browse' },
    { id: 'Compare', icon: '⚖️', label: 'Compare' },
    { id: 'Portfolio Builder', icon: '💼', label: 'Portfolio Builder' },
    { id: 'Watchlist', icon: '⭐', label: 'Watchlist', badge: 5 },
    { id: 'Articles', icon: '📄', label: 'Articles' },
  ]

  const handleSearch = (e) => {
    if (e.key === 'Enter' && searchQuery.trim()) {
      const t = searchQuery.toUpperCase().trim()
      navigate(`/browse/${encodeURIComponent(t)}`)
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
          onKeyPress={handleSearch}
        />
        <span className="search-placeholder">/</span>
      </div>

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

