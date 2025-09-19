'use client'

import { useState } from 'react'
import { apiClient, SearchRequest, SearchResponse, DeviceNarrative } from '@/lib/api'

interface SearchFormProps {
  onResults: (results: SearchResponse) => void
  onLoading: (loading: boolean) => void
  onNarrative: (narrative: DeviceNarrative | null) => void
  onAgentProgress?: (show: boolean, deviceName?: string) => void
}

export default function SearchForm({ onResults, onLoading, onNarrative, onAgentProgress }: SearchFormProps) {
  const [query, setQuery] = useState('')
  const [queryType, setQueryType] = useState<'device' | 'manufacturer' | 'recall'>('device')
  const [limit, setLimit] = useState(10)
  const [includeAI, setIncludeAI] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    onNarrative(null)  // Clear previous narrative
    
    try {
      // If it's a device search and AI is enabled, show agent progress
      if (queryType === 'device' && includeAI) {
        // Use parent's agent progress handler if available
        if (onAgentProgress) {
          console.log('Showing agent progress for:', query)
          onAgentProgress(true, query)
          onLoading(false)  // Hide simple spinner
          
          // Simulate delay for animation, then fetch narrative
          setTimeout(async () => {
            const narrative = await apiClient.getDeviceNarrative(query)
            onNarrative(narrative)
            onResults({} as SearchResponse)  // Clear regular results
            onAgentProgress(false)
          }, 11000)  // Match animation duration
        } else {
          // Fallback to old behavior
          onLoading(true)
          const narrative = await apiClient.getDeviceNarrative(query)
          onNarrative(narrative)
          onResults({} as SearchResponse)  // Clear regular results
          onLoading(false)
        }
      } else {
        onLoading(true)
        // Otherwise do normal search
        const params: SearchRequest = {
          query,
          query_type: queryType,
          limit,
          include_ai_analysis: includeAI
        }
        const results = await apiClient.search(params)
        onResults(results)
        onLoading(false)
      }
    } catch (error) {
      console.error('Search failed:', error)
      alert('Search failed. Please check if the backend is running.')
      onLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="search-form">
      <div className="form-group">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for medical devices..."
          className="search-input"
        />
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Type:</label>
          <select 
            value={queryType} 
            onChange={(e) => setQueryType(e.target.value as any)}
          >
            <option value="device">Device</option>
            <option value="manufacturer">Manufacturer</option>
            <option value="recall">Recall</option>
          </select>
        </div>

        <div className="form-group">
          <label>Results:</label>
          <select 
            value={limit} 
            onChange={(e) => setLimit(Number(e.target.value))}
            title="Shows most recent events. AI analysis always examines 100+ events regardless of this setting."
          >
            <option value="10">10 (most recent)</option>
            <option value="25">25 (most recent)</option>
            <option value="50">50 (most recent)</option>
            <option value="100">100 (most recent)</option>
          </select>
        </div>

        <div className="form-group">
          <label title="AI analyzes up to 200 recent events for comprehensive insights">
            <input
              type="checkbox"
              checked={includeAI}
              onChange={(e) => setIncludeAI(e.target.checked)}
            />
            Include AI Analysis (200+ events)
          </label>
        </div>
      </div>

      <button type="submit" className="search-button">
        Search FDA Database
      </button>
    </form>
  )
}