'use client'

import { useState } from 'react'
import DeviceNarrativeDisplay from '@/components/DeviceNarrativeDisplay'
import AgentProgress from '@/components/AgentProgress'
import { apiClient, DeviceNarrative } from '@/lib/api'

export default function Home() {
  const [deviceName, setDeviceName] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [narrative, setNarrative] = useState<DeviceNarrative | null>(null)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!deviceName.trim() || isSearching) return

    console.log('Starting search for:', deviceName)
    setNarrative(null)
    setIsSearching(true)

    // Wait for animation to complete, then fetch
    setTimeout(async () => {
      try {
        const result = await apiClient.getDeviceNarrative(deviceName)
        setNarrative(result)
      } catch (error) {
        console.error('Search failed:', error)
        alert('Search failed. Please try again.')
      } finally {
        setIsSearching(false)
      }
    }, 11000) // Match animation duration
  }

  return (
    <div className="container">
      <header className="header">
        <h1>FDA Explorer</h1>
        <p>AI-Powered Medical Device Intelligence</p>
      </header>

      <main className="main">
        <form onSubmit={handleSearch} className="search-form">
          <div className="form-group">
            <input
              type="text"
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
              placeholder="Enter device name (e.g., pacemaker, insulin pump)"
              className="search-input"
              disabled={isSearching}
            />
          </div>
          <button 
            type="submit" 
            className="search-button"
            disabled={isSearching}
          >
            {isSearching ? 'Analyzing...' : 'Analyze Device'}
          </button>
        </form>

        {isSearching && (
          <AgentProgress 
            isProcessing={true}
            deviceName={deviceName}
            onComplete={() => console.log('Animation complete')}
          />
        )}

        {narrative && !isSearching && (
          <DeviceNarrativeDisplay narrative={narrative} />
        )}
      </main>
    </div>
  )
}