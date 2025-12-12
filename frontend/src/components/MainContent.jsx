import React, { useState, useEffect } from 'react'
import axios from 'axios'
import PerformanceTab from './PerformanceTab'
import './MainContent.css'

const MainContent = ({ ticker, selectedTab: initialTab }) => {
  const [selectedTab, setSelectedTab] = useState(initialTab || 'Performance')
  const [analysisData, setAnalysisData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [jobId, setJobId] = useState(null)

  const tabs = [
    'Key Data',
    'Performance',
    'Allocation',
    'Risk Analysis',
    'Sustainability',
    'Stock Exchange'
  ]

  const API_URL = import.meta.env.VITE_API_URL || '/api'

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
    if (ticker && ticker !== 'IE00B4L5Y983') {
      handleAnalyze()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker])

  // Mock data for demonstration
  const mockData = {
    company: {
      name: ticker ? `${ticker} Stock` : 'iShares Core MSCI World UCITS ETF USD (Acc)',
      ticker: ticker || 'IE00B4L5Y983'
    },
    currentPrice: 111.98,
    change: 15.76,
    changePercent: 16.53,
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
        </div>

        <div className="product-actions">
          <button className="action-btn">
            <span>⚖️</span> Compare
          </button>
          <button className="action-btn">
            <span>⬇️</span> Download Factsheet
          </button>
          <button className="action-btn primary">
            ✓ Added to Watchlist
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

