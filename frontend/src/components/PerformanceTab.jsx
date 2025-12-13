import React, { useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import './PerformanceTab.css'

const PerformanceTab = ({ data, mockData, loading, priceSeries, overview }) => {
  const [timeRange, setTimeRange] = useState('1Y')
  const [fcfRange, setFcfRange] = useState('Quarterly')
  const [kpiRange, setKpiRange] = useState('Quarterly')

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

  const fmtPct = (v) => (typeof v === 'number' && Number.isFinite(v) ? `${(v * 100).toFixed(1)}%` : '—')
  const fmtNum = (v) => (typeof v === 'number' && Number.isFinite(v) ? v.toLocaleString('en-US', { maximumFractionDigits: 0 }) : '—')

  const fcfPoints = (fcfRange === 'Yearly' ? overview?.fcf_annual : overview?.fcf_quarterly) || []
  const kpiPoints = (kpiRange === 'Yearly' ? overview?.kpis_annual : overview?.kpis_quarterly) || []

  const fcfChartData = useMemo(() => {
    if (!Array.isArray(fcfPoints)) return []
    return fcfPoints
      .filter((p) => p?.period_end)
      .map((p) => ({ period_end: p.period_end, fcf: p.fcf, fcf_margin: p.fcf_margin }))
  }, [fcfPoints])

  const xPeriod = (v) => {
    try {
      return new Date(v).toLocaleDateString('en-US', { year: '2-digit', month: 'short' })
    } catch {
      return v
    }
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
            <h3>Free Cash Flow (FCF)</h3>
            <div className="view-toggle">
              <button
                className={`toggle-btn ${fcfRange === 'Quarterly' ? 'active' : ''}`}
                onClick={() => setFcfRange('Quarterly')}
              >
                Quarterly
              </button>
              <button
                className={`toggle-btn ${fcfRange === 'Yearly' ? 'active' : ''}`}
                onClick={() => setFcfRange('Yearly')}
              >
                Yearly
              </button>
            </div>
          </div>
          <div style={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={fcfChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
                <XAxis dataKey="period_end" tickFormatter={xPeriod} stroke="#666" />
                <YAxis tickFormatter={(v) => fmtNum(v)} stroke="#666" />
                <Tooltip
                  formatter={(value, name) => {
                    if (name === 'fcf_margin') return [fmtPct(value), 'FCF Margin']
                    return [fmtNum(value), 'FCF']
                  }}
                  labelFormatter={(label) => `Period: ${label}`}
                />
                <Line type="monotone" dataKey="fcf" stroke="#0ea5e9" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="return-table">
            {(Array.isArray(fcfPoints) ? [...fcfPoints].slice(-8).reverse() : []).map((p) => (
              <div key={p.period_end} className="return-row">
                <span className="return-year">{p.period_end}</span>
                <span className="return-value">{fmtNum(p.fcf)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="return-heatmap">
          <div className="section-header">
            <h3>Valuation / Quality KPIs</h3>
            <div className="view-toggle">
              <button
                className={`toggle-btn ${kpiRange === 'Quarterly' ? 'active' : ''}`}
                onClick={() => setKpiRange('Quarterly')}
              >
                Quarterly
              </button>
              <button
                className={`toggle-btn ${kpiRange === 'Yearly' ? 'active' : ''}`}
                onClick={() => setKpiRange('Yearly')}
              >
                Yearly
              </button>
            </div>
          </div>
          <div className="return-table">
            {(Array.isArray(kpiPoints) ? [...kpiPoints].slice(-8).reverse() : []).map((p) => (
              <div key={p.period_end} className="return-row" style={{ display: 'grid', gridTemplateColumns: '90px 1fr', gap: 12 }}>
                <span className="return-year">{p.period_end}</span>
                <span className="return-value" style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  <span>ROE: {fmtPct(p.roe)}</span>
                  <span>Net: {fmtPct(p.net_margin)}</span>
                  <span>Op: {fmtPct(p.operating_margin)}</span>
                  <span>FCF: {fmtPct(p.fcf_margin)}</span>
                  <span>D/E: {typeof p.debt_to_equity === 'number' ? p.debt_to_equity.toFixed(2) : '—'}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default PerformanceTab

