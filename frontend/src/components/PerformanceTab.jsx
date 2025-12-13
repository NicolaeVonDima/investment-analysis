import React, { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import './PerformanceTab.css'

const PerformanceTab = ({ data, mockData, loading, priceSeries, overview, ticker, companyInfo }) => {
  const [timeRange, setTimeRange] = useState('1Y') // Price range: 1Y | Max
  const [fcfRange, setFcfRange] = useState('Quarterly')
  const [kpiRange, setKpiRange] = useState('Quarterly')
  const [fundSeries, setFundSeries] = useState(null)
  const [fundSeriesError, setFundSeriesError] = useState(null)
  const [visibleSeries, setVisibleSeries] = useState(() => new Set(['fcf']))
  const [visibleKpis, setVisibleKpis] = useState(() => new Set(['roe', 'net_margin']))

  const formatPrice = (value) => {
    if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
    // Round to 4 decimals (not truncated), then trim trailing zeros.
    const rounded = Number(value.toFixed(4))
    return String(rounded)
  }

  const formatPriceAxis = (value) => {
    if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
    // Keep axis labels readable; still respects "max 4 decimals" (we show <= 2).
    return value.toLocaleString('en-US', { maximumFractionDigits: 2 })
  }

  const chartDataAll = useMemo(() => {
    const pts = priceSeries?.points
    if (Array.isArray(pts) && pts.length) {
      return pts
        .filter((p) => p?.as_of_date && typeof p?.close === 'number')
        .map((p) => ({ date: p.as_of_date, price: p.close }))
    }
    // Fallback: empty (avoid random floats that mask real data issues)
    return []
  }, [priceSeries])

  const chartData = useMemo(() => {
    if (!Array.isArray(chartDataAll) || chartDataAll.length === 0) return []
    if (timeRange === 'Max') return chartDataAll
    // 1Y default
    const last = chartDataAll[chartDataAll.length - 1]
    const lastDate = last?.date ? new Date(last.date) : null
    if (!lastDate || Number.isNaN(lastDate.getTime())) return chartDataAll
    const cutoff = new Date(lastDate)
    cutoff.setDate(cutoff.getDate() - 365)
    return chartDataAll.filter((p) => {
      const d = p?.date ? new Date(p.date) : null
      return d && !Number.isNaN(d.getTime()) && d >= cutoff
    })
  }, [chartDataAll, timeRange])

  const priceYAxisDomain = useMemo(() => {
    if (!Array.isArray(chartData) || chartData.length === 0) return undefined
    const vals = chartData.map((p) => p?.price).filter((v) => typeof v === 'number' && Number.isFinite(v))
    if (!vals.length) return undefined
    const min = Math.min(...vals)
    const max = Math.max(...vals)
    if (!Number.isFinite(min) || !Number.isFinite(max)) return undefined
    // Avoid anchoring to 0; pad to keep the line readable and consistent with other panels.
    const range = Math.max(1e-9, max - min)
    const pad = range * 0.08
    const lo = min - pad
    const hi = max + pad
    // Round bounds to "nice" steps so tick labels aren't awkward decimals.
    const span = Math.max(1e-9, hi - lo)
    const step =
      span >= 200 ? 20 :
      span >= 100 ? 10 :
      span >= 50 ? 5 :
      span >= 20 ? 2 :
      1
    const loR = Math.floor(lo / step) * step
    const hiR = Math.ceil(hi / step) * step
    return [loR, hiR]
  }, [chartData])

  const xTick = (v) => {
    try {
      // Avoid repeated month labels for daily data (e.g. Jul Jul Jul ...).
      return new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    } catch {
      return v
    }
  }
  const currentPrice = mockData?.currentPrice
  const change = mockData?.change
  const changePercent = mockData?.changePercent

  const fmtPct = (v) => (typeof v === 'number' && Number.isFinite(v) ? `${(v * 100).toFixed(1)}%` : '—')
  const fmtNum = (v) => (typeof v === 'number' && Number.isFinite(v) ? v.toLocaleString('en-US', { maximumFractionDigits: 0 }) : '—')
  const fmtPctNumber = (v) =>
    typeof v === 'number' && Number.isFinite(v) ? `${v.toFixed(1).replace(/\.0$/, '')}%` : '—'
  const fmtRatio = (v) => (typeof v === 'number' && Number.isFinite(v) ? v.toFixed(2) : '—')

  const fcfPoints = (fcfRange === 'Yearly' ? overview?.fcf_annual : overview?.fcf_quarterly) || []
  const kpiPoints = (kpiRange === 'Yearly' ? overview?.kpis_annual : overview?.kpis_quarterly) || []

  const API_ROOT = (import.meta.env.VITE_API_URL || '').replace(/\/api\/?$/, '')
  const API_URL = `${API_ROOT}/api`

  useEffect(() => {
    const run = async () => {
      if (!ticker) return
      setFundSeriesError(null)
      try {
        const period = fcfRange === 'Yearly' ? 'annual' : 'quarterly'
        const res = await axios.get(`${API_URL}/instruments/${encodeURIComponent(ticker)}/fundamentals/series`, {
          params: { period, series: 'fcf,sbc,netIncome,debt,dividends,buybacks' },
        })
        setFundSeries(res.data)
      } catch (e) {
        setFundSeries(null)
        setFundSeriesError(e?.response?.data?.detail || e.message)
      }
    }
    run()
  }, [ticker, fcfRange])

  useEffect(() => {
    // Reset visible lines on ticker change (keep default FCF on).
    setVisibleSeries(new Set(['fcf']))
  }, [ticker])

  useEffect(() => {
    // Reset KPI selections on ticker change.
    setVisibleKpis(new Set(['roe', 'net_margin']))
  }, [ticker])

  const toggleSeries = (key) => {
    setVisibleSeries((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      // Keep at least one series visible, but only if available
      if (next.size === 0) {
        const u = new Set(fundSeries?.unavailable || [])
        const firstAvailable = seriesMeta.find((m) => !u.has(m.key))
        if (firstAvailable) next.add(firstAvailable.key)
      }
      return next
    })
  }

  const toggleKpi = (key) => {
    setVisibleKpis((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      // Keep at least one KPI visible, but only if available
      if (next.size === 0) {
        const firstAvailable = kpiMeta.find((m) => !kpiUnavailable.has(m.key))
        if (firstAvailable) next.add(firstAvailable.key)
      }
      return next
    })
  }

  const compactMoney = (v) => {
    if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
    const abs = Math.abs(v)
    const sign = v < 0 ? '-' : ''
    const fmt = (n) => (Number.isFinite(n) ? n.toFixed(2).replace(/\.?0+$/, '') : '—')
    if (abs >= 1e12) return `${sign}${fmt(abs / 1e12)}T`
    if (abs >= 1e9) return `${sign}${fmt(abs / 1e9)}B`
    if (abs >= 1e6) return `${sign}${fmt(abs / 1e6)}M`
    if (abs >= 1e3) return `${sign}${fmt(abs / 1e3)}K`
    return `${sign}${fmt(abs)}`
  }

  const seriesMeta = [
    { key: 'fcf', label: 'FCF', color: '#0ea5e9' },
    { key: 'sbc', label: 'SBC', color: '#a855f7' },
    { key: 'netIncome', label: 'Net Income', color: '#22c55e' },
    { key: 'debt', label: 'Debt', color: '#ef4444' },
    { key: 'dividends', label: 'Dividends', color: '#f59e0b' },
    { key: 'buybacks', label: 'Buybacks', color: '#64748b' },
  ]

  const unavailable = new Set(fundSeries?.unavailable || [])

  useEffect(() => {
    // If a series becomes unavailable after fetch, ensure it is not kept "active".
    if (!fundSeries) return
    const u = new Set(fundSeries?.unavailable || [])
    setVisibleSeries((prev) => {
      const next = new Set([...prev].filter((k) => !u.has(k)))
      // If all were filtered out, add the first available series (if any)
      if (next.size === 0) {
        const firstAvailable = seriesMeta.find((m) => !u.has(m.key))
        if (firstAvailable) next.add(firstAvailable.key)
      }
      return next
    })
  }, [fundSeries])

  const overlayData = useMemo(() => {
    const s = fundSeries?.series
    if (!s || typeof s !== 'object') return []
    const byDate = new Map()
    for (const [key, pts] of Object.entries(s)) {
      if (!Array.isArray(pts)) continue
      for (const p of pts) {
        if (!p?.period_end) continue
        const row = byDate.get(p.period_end) || { period_end: p.period_end }
        row[key] = typeof p.value === 'number' ? p.value : null
        byDate.set(p.period_end, row)
      }
    }
    return Array.from(byDate.values()).sort((a, b) => String(a.period_end).localeCompare(String(b.period_end)))
  }, [fundSeries])

  const kpiMeta = [
    { key: 'roe', label: 'ROE', color: '#0ea5e9', axis: 'left', fmt: fmtPctNumber },
    { key: 'net_margin', label: 'Net Margin', color: '#22c55e', axis: 'left', fmt: fmtPctNumber },
    { key: 'operating_margin', label: 'Op Margin', color: '#a855f7', axis: 'left', fmt: fmtPctNumber },
    { key: 'fcf_margin', label: 'FCF Margin', color: '#f59e0b', axis: 'left', fmt: fmtPctNumber },
    { key: 'debt_to_equity', label: 'Debt/Equity', color: '#ef4444', axis: 'right', fmt: fmtRatio },
  ]

  const kpiChartData = useMemo(() => {
    if (!Array.isArray(kpiPoints)) return []
    return kpiPoints
      .filter((p) => p?.period_end)
      .map((p) => ({
        period_end: p.period_end,
        roe: typeof p.roe === 'number' ? p.roe * 100 : null,
        net_margin: typeof p.net_margin === 'number' ? p.net_margin * 100 : null,
        operating_margin: typeof p.operating_margin === 'number' ? p.operating_margin * 100 : null,
        fcf_margin: typeof p.fcf_margin === 'number' ? p.fcf_margin * 100 : null,
        debt_to_equity: typeof p.debt_to_equity === 'number' ? p.debt_to_equity : null,
      }))
  }, [kpiPoints])

  const kpiUnavailable = useMemo(() => {
    const out = new Set()
    for (const m of kpiMeta) {
      const vals = kpiChartData.map((r) => r?.[m.key]).filter((v) => typeof v === 'number')
      if (!vals.length) out.add(m.key)
    }
    return out
  }, [kpiChartData])

  useEffect(() => {
    // Drop unavailable KPIs from active set.
    setVisibleKpis((prev) => {
      const next = new Set([...prev].filter((k) => !kpiUnavailable.has(k)))
      // If all were filtered out, add the first available KPI (if any)
      if (next.size === 0) {
        const firstAvailable = kpiMeta.find((m) => !kpiUnavailable.has(m.key))
        if (firstAvailable) next.add(firstAvailable.key)
      }
      return next
    })
  }, [kpiUnavailable])

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

  // Keep plot areas aligned across cards (consistent axis widths + chart margins)
  // Keep axis labels from being clipped (price ticks can be wider than %/compact units).
  const AXIS_W = 78
  const CHART_MARGIN = { top: 8, right: 12, bottom: 0, left: 6 }

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

      {companyInfo && (
        <div className="company-summary">
          <h2 className="company-summary-title">{companyInfo.name || companyInfo.ticker}</h2>
          <div className="company-summary-details">
            {companyInfo.exchange && (
              <span className="company-detail-item">
                <span className="detail-label">Exchange:</span>
                <span className="detail-value">{companyInfo.exchange}</span>
              </span>
            )}
            {companyInfo.currency && (
              <span className="company-detail-item">
                <span className="detail-label">Currency:</span>
                <span className="detail-value">{companyInfo.currency}</span>
              </span>
            )}
            {companyInfo.ticker && (
              <span className="company-detail-item">
                <span className="detail-label">Ticker:</span>
                <span className="detail-value">{companyInfo.ticker}</span>
              </span>
            )}
          </div>
          <div className="company-summary-description">
            <p>
              {companyInfo.description || 
                `${companyInfo.name || companyInfo.ticker} is a publicly traded company${companyInfo.exchange ? ` listed on the ${companyInfo.exchange}` : ''}. ` +
                `This overview provides key financial metrics, free cash flow trends, and valuation indicators to help assess the company's financial health and investment potential.`
              }
            </p>
          </div>
        </div>
      )}

      <div className="overview-grid">
        <div className="chart-container price-card">
          <div className="section-header">
            <h3>Price</h3>
            <div className="view-toggle">
              {['1Y', 'Max'].map((r) => (
                <button
                  key={r}
                  className={`toggle-btn ${timeRange === r ? 'active' : ''}`}
                  onClick={() => setTimeRange(r)}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
          <div className="chip-row" />
          <div className="panel-error" />
          <div className="chart-wrapper">
            <ResponsiveContainer width="100%" height={344}>
              <LineChart data={chartData} margin={CHART_MARGIN}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
                <XAxis dataKey="date" stroke="#666" tickFormatter={xTick} minTickGap={24} tickMargin={8} />
                <YAxis
                  stroke="#666"
                  tickFormatter={(v) => formatPriceAxis(v)}
                  width={AXIS_W}
                  tickMargin={6}
                  domain={priceYAxisDomain}
                  tickCount={5}
                />
                <Tooltip
                  formatter={(value, name) => [formatPrice(value), name]}
                  labelFormatter={(label) => `Date: ${label}`}
                />
                <Line type="monotone" dataKey="price" stroke="#ff6b35" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="return-overview fcf-card">
          <div className="section-header">
            <h3>
              Free Cash Flow (FCF)
              {fundSeries?.currency ? <span className="panel-currency">{` · ${fundSeries.currency}`}</span> : null}
            </h3>
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
          <div className="chip-row">
            {seriesMeta.map((m) => {
              const isUnavailable = unavailable.has(m.key)
              const active = visibleSeries.has(m.key)
              return (
                <button
                  key={m.key}
                  className={`toggle-btn ${active ? 'active' : ''}`}
                  style={{
                    opacity: isUnavailable ? 0.45 : 1,
                    cursor: isUnavailable ? 'not-allowed' : 'pointer',
                  }}
                  onClick={() => {
                    if (isUnavailable) return
                    toggleSeries(m.key)
                  }}
                  title={isUnavailable ? 'Unavailable' : 'Toggle'}
                >
                  {m.label}{isUnavailable ? ' (Unavailable)' : ''}
                </button>
              )
            })}
          </div>
          <div className="panel-error">{fundSeriesError ? String(fundSeriesError) : ''}</div>
          <div className="chart-wrapper">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={overlayData} margin={CHART_MARGIN}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
                <XAxis dataKey="period_end" tickFormatter={xPeriod} stroke="#666" tickMargin={8} />
                <YAxis tickFormatter={(v) => compactMoney(v)} stroke="#666" width={AXIS_W} tickMargin={6} />
                <Tooltip
                  formatter={(value, name) => [compactMoney(value), name]}
                  labelFormatter={(label) => `Period: ${label}`}
                />
                {seriesMeta
                  .filter((m) => visibleSeries.has(m.key) && !unavailable.has(m.key))
                  .map((m) => (
                    <Line key={m.key} type="monotone" dataKey={m.key} name={m.label} stroke={m.color} strokeWidth={2} dot={false} />
                  ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="return-heatmap kpi-card">
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
          <div className="chip-row">
            {kpiMeta.map((m) => {
              const isUnavailable = kpiUnavailable.has(m.key)
              const active = visibleKpis.has(m.key)
              return (
                <button
                  key={m.key}
                  className={`toggle-btn ${active ? 'active' : ''}`}
                  style={{
                    opacity: isUnavailable ? 0.45 : 1,
                    cursor: isUnavailable ? 'not-allowed' : 'pointer',
                  }}
                  onClick={() => {
                    if (isUnavailable) return
                    toggleKpi(m.key)
                  }}
                  title={isUnavailable ? 'Unavailable' : 'Toggle'}
                >
                  {m.label}{isUnavailable ? ' (Unavailable)' : ''}
                </button>
              )
            })}
          </div>
          <div className="panel-error" />
          <div className="chart-wrapper">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={kpiChartData} margin={CHART_MARGIN}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
                <XAxis dataKey="period_end" tickFormatter={xPeriod} stroke="#666" tickMargin={8} />
                <YAxis yAxisId="left" tickFormatter={(v) => fmtPctNumber(v)} stroke="#666" width={AXIS_W} tickMargin={6} />
                <YAxis yAxisId="right" orientation="right" tickFormatter={(v) => fmtRatio(v)} stroke="#666" width={AXIS_W} tickMargin={6} />
                <Tooltip
                  formatter={(value, name, props) => {
                    const key = props?.dataKey
                    const meta = kpiMeta.find((m) => m.key === key)
                    return [meta ? meta.fmt(value) : value, name]
                  }}
                  labelFormatter={(label) => `Period: ${label}`}
                />
                {kpiMeta
                  .filter((m) => visibleKpis.has(m.key) && !kpiUnavailable.has(m.key))
                  .map((m) => (
                    <Line
                      key={m.key}
                      type="monotone"
                      dataKey={m.key}
                      name={m.label}
                      stroke={m.color}
                      strokeWidth={2}
                      dot={false}
                      yAxisId={m.axis}
                    />
                  ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}

export default PerformanceTab

