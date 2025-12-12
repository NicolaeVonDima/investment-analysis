import React, { useState } from 'react'
import Sidebar from './components/Sidebar'
import MainContent from './components/MainContent'
import './App.css'

function App() {
  const [selectedNav, setSelectedNav] = useState('Browse')
  const [selectedTicker, setSelectedTicker] = useState('AAPL')

  return (
    <div className="app">
      <Sidebar 
        selectedNav={selectedNav} 
        onNavSelect={setSelectedNav}
        onTickerSelect={setSelectedTicker}
      />
      <MainContent 
        ticker={selectedTicker}
        selectedTab="Performance"
      />
    </div>
  )
}

export default App

