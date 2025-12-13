import React, { useEffect, useState } from 'react'
import { Navigate, Route, Routes, useParams } from 'react-router-dom'
import axios from 'axios'
import Sidebar from './components/Sidebar'
import MainContent from './components/MainContent'
import './App.css'

function App() {
  const BrowseRoute = () => {
    const { ticker } = useParams()
    const [resolvedTicker, setResolvedTicker] = useState(null)
    const [error, setError] = useState(null)
    const [loading, setLoading] = useState(false)

    const API_ROOT = (import.meta.env.VITE_API_URL || '').replace(/\/api\/?$/, '')
    const API_URL = `${API_ROOT}/api`

    useEffect(() => {
      const run = async () => {
        setLoading(true)
        setError(null)
        setResolvedTicker(null)
        try {
          const res = await axios.post(`${API_URL}/instruments/resolve`, { query: ticker })
          setResolvedTicker(res.data?.ticker || ticker)
        } catch (e) {
          const detail = e?.response?.data?.detail
          setError(detail?.message || 'Ticker not found')
        } finally {
          setLoading(false)
        }
      }
      if (ticker) run()
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [ticker])

    if (loading) {
      return (
        <div style={{ padding: 24 }}>
          <div style={{ color: '#666' }}>Validating ticker…</div>
        </div>
      )
    }
    if (error) {
      return (
        <div style={{ padding: 24 }}>
          <h2 style={{ margin: 0 }}>Not Found</h2>
          <div style={{ marginTop: 8, color: '#b91c1c' }}>{error}</div>
          <div style={{ marginTop: 12, color: '#666' }}>Try another ticker in the search box.</div>
        </div>
      )
    }
    return <MainContent ticker={resolvedTicker} selectedNav="Browse" selectedTab="Performance" />
  }

  return (
    <div className="app">
      <Sidebar />
      <Routes>
        <Route path="/" element={<Navigate to="/browse/ADBE" replace />} />
        <Route path="/browse/:ticker" element={<BrowseRoute />} />
        <Route path="/watchlist" element={<MainContent selectedNav="Watchlist" selectedTab="Performance" />} />
        <Route path="*" element={<Navigate to="/browse/ADBE" replace />} />
      </Routes>
    </div>
  )
}

export default App

