import React from 'react'
import { Navigate, Route, Routes, useParams } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import MainContent from './components/MainContent'
import './App.css'

function App() {
  const BrowseRoute = () => {
    const { ticker } = useParams()
    return <MainContent ticker={ticker} selectedNav="Browse" selectedTab="Performance" />
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

