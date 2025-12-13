import React, { useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import './PerformanceTab.css'

const PerformanceTab = ({ data, mockData, loading, priceSeries }) => {
  const [timeRange, setTimeRange] = useState('1Y')
  const [viewMode, setViewMode] = useState('Table')

  const formatPrice = (value) => {
    if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
    // Round to 4 decimals (not truncated), then trim trailing zeros.
    const rounded = Number(value.toFixed(4))
    return String(rounded)
  }

  const chartData = useMemo(() => {
    const pts = priceSeries?.points
    if (Array.isArray(pts) && pts.length) {
      return pts
        .filter((p) => p?.as_of_date && typeof p?.close === 'number')
        .map((p) => ({ date: p.as_of_date, price: p.close }))
    }
    // Fallback: empty (avoid random floats that mask real data issues)
    return []
  }, [priceSeries])

  const xTick = (v) => {
    try {
      return new Date(v).toLocaleDateString('en-US', { month: 'short' })
    } catch {
      return v
    }
  }
  const currentPrice = mockData?.currentPrice
  const change = mockData?.change
  const changePercent = mockData?.changePercent

  const returnData = [
    { year: '2025', ytd: '4.66%', color: 'green' },
    { year: '2024', ytd: '28.31%', color: 'green' },
    { year: '2023', ytd: '12.43%', color: 'green' },
    { year: '2022', ytd: '-17.04%', color: 'red' },
    { year: '2021', ytd: '26.33%', color: 'green' },
    { year: '2020', ytd: '6.10%', color: 'green' },
  ]

  const heatmapData = [
    { year: '2025', months: Array(12).fill(null).map(() => Math.random() * 10 - 2) },
    { year: '2024', months: Array(12).fill(null).map(() => Math.random() * 15 + 5) },
    { year: '2023', months: Array(12).fill(null).map(() => Math.random() * 10 + 2) },
    { year: '2022', months: Array(12).fill(null).map(() => Math.random() * -10 - 5) },
    { year: '2021', months: Array(12).fill(null).map(() => Math.random() * 15 + 10) },
    { year: '2020', months: Array(12).fill(null).map(() => Math.random() * 8 + 2) },
  ]

  const monthNames = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']

  const getHeatmapColor = (value) => {
    if (value > 5) return '#22c55e'
    if (value > 0) return '#86efac'
    if (value > -5) return '#fca5a5'
    return '#ef4444'
  }

  if (loading) {
    return (
      <div className="performance-loading">
        <p>Analyzing {mockData?.company?.ticker}...</p>
      </div>
    )
  }

  return (
    <div className="performance-tab">
      <div className="price-section">
        <div className="price-main">
          <span className="price-value">
            {typeof currentPrice === 'number' ? `$${currentPrice.toFixed(2)}` : '—'}
          </span>
          <span className={`price-change ${change >= 0 ? 'positive' : 'negative'}`}>
            {typeof change === 'number' && typeof changePercent === 'number'
              ? `${change >= 0 ? '+' : ''}$${change.toFixed(2)} (${changePercent.toFixed(2)}%)`
              : '—'}
          </span>
        </div>
        <div className="price-timestamp">
          As of {priceSeries?.points?.length ? priceSeries.points[priceSeries.points.length - 1]?.as_of_date : '—'} (EOD)
        </div>
      </div>

      <div className="chart-container">
        <div className="chart-controls">
          <div className="time-range-selector">
            {['1D', '1M', '6M', '1Y', '3Y', 'Max'].map((range) => (
              <button
                key={range}
                className={`time-range-btn ${timeRange === range ? 'active' : ''}`}
                onClick={() => setTimeRange(range)}
              >
                {range}
              </button>
            ))}
          </div>
          <select className="currency-selector">
            <option>USD</option>
            <option>EUR</option>
            <option>GBP</option>
          </select>
        </div>
        <div className="chart-wrapper">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
              <XAxis dataKey="date" stroke="#666" tickFormatter={xTick} />
              <YAxis stroke="#666" tickFormatter={(v) => formatPrice(v)} />
              <Tooltip
                formatter={(value, name) => [formatPrice(value), name]}
                labelFormatter={(label) => `Date: ${label}`}
              />
              <Line 
                type="monotone" 
                dataKey="price" 
                stroke="#ff6b35" 
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="returns-section">
        <div className="return-overview">
          <div className="section-header">
            <h3>Return Overview</h3>
            <div className="view-toggle">
              <button 
                className={`toggle-btn ${viewMode === 'Table' ? 'active' : ''}`}
                onClick={() => setViewMode('Table')}
              >
                Table
              </button>
              <button 
                className={`toggle-btn ${viewMode === 'Chart' ? 'active' : ''}`}
                onClick={() => setViewMode('Chart')}
              >
                Chart
              </button>
            </div>
          </div>
          <div className="return-table">
            {returnData.map((row) => (
              <div key={row.year} className="return-row">
                <span className="return-year">{row.year} {row.year === '2025' && '(YTD)'}</span>
                <span className={`return-value ${row.color}`}>{row.ytd}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="return-heatmap">
          <div className="section-header">
            <h3>Return Heatmap</h3>
            <div className="view-toggle">
              <button className="toggle-btn active">Monthly</button>
              <button className="toggle-btn">Yearly</button>
            </div>
          </div>
          <div className="heatmap-container">
            <div className="heatmap-grid">
              <div className="heatmap-header">
                <div className="heatmap-spacer"></div>
                {monthNames.map((month, idx) => (
                  <div key={`${month}-${idx}`} className="heatmap-month">{month}</div>
                ))}
              </div>
            </div>
            {heatmapData.map((row) => (
              <div key={row.year} className="heatmap-row">
                <div className="heatmap-year">{row.year}</div>
                {row.months.map((value, idx) => (
                  <div
                    key={idx}
                    className="heatmap-cell"
                    style={{ backgroundColor: getHeatmapColor(value) }}
                    title={`${monthNames[idx]} ${row.year}: ${value.toFixed(2)}%`}
                  >
                    {value > 0 ? '+' : ''}{value.toFixed(1)}%
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default PerformanceTab

