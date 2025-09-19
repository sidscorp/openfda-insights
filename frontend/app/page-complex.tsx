'use client'

import { useState } from 'react'
import SearchForm from '@/components/SearchForm'
import ResultsDisplay from '@/components/ResultsDisplay'
import DeviceNarrativeDisplay from '@/components/DeviceNarrativeDisplay'
import AgentProgress from '@/components/AgentProgress'
import { SearchResponse, DeviceNarrative } from '@/lib/api'

export default function Home() {
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null)
  const [deviceNarrative, setDeviceNarrative] = useState<DeviceNarrative | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [showAgentProgress, setShowAgentProgress] = useState(false)
  const [agentDeviceName, setAgentDeviceName] = useState('')

  return (
    <div className="container">
      <header className="header">
        <h1>FDA Explorer</h1>
        <p>Medical Device Intelligence Platform</p>
      </header>

      <main className="main">
        <SearchForm 
          onResults={setSearchResults} 
          onLoading={setIsLoading}
          onNarrative={setDeviceNarrative}
          onAgentProgress={(show: boolean, deviceName?: string) => {
            console.log('Page: onAgentProgress called', { show, deviceName })
            setShowAgentProgress(show)
            if (deviceName) setAgentDeviceName(deviceName)
          }}
        />
        
        {isLoading && !showAgentProgress && (
          <div className="loading">Searching FDA database...</div>
        )}
        
        {showAgentProgress && (
          <div>
            <div style={{padding: '20px', background: '#fef3c7', borderRadius: '8px', marginBottom: '20px'}}>
              <strong>Debug: Agent Progress is ACTIVE for {agentDeviceName}</strong>
            </div>
            <AgentProgress 
              isProcessing={showAgentProgress}
              deviceName={agentDeviceName}
              onComplete={() => setShowAgentProgress(false)}
            />
          </div>
        )}

        {deviceNarrative && !isLoading && (
          <DeviceNarrativeDisplay narrative={deviceNarrative} />
        )}

        {searchResults && !deviceNarrative && !isLoading && (
          <ResultsDisplay 
            results={searchResults}
            onSelectDevice={() => {}}
          />
        )}
      </main>
    </div>
  )
}