'use client'

import { SearchResponse } from '@/lib/api'
import { useMemo } from 'react'

interface ResultsDisplayProps {
  results: SearchResponse
  onSelectDevice: (deviceName: string) => void
}

// Helper function to parse FDA date format (YYYYMMDD)
function parseFDADate(dateStr: string | undefined): string {
  if (!dateStr || dateStr.length !== 8) return 'N/A'
  
  try {
    const year = dateStr.substring(0, 4)
    const month = dateStr.substring(4, 6)
    const day = dateStr.substring(6, 8)
    const date = new Date(`${year}-${month}-${day}`)
    
    if (isNaN(date.getTime())) return 'N/A'
    
    return date.toLocaleDateString('en-US', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric' 
    })
  } catch {
    return 'N/A'
  }
}

export default function ResultsDisplay({ results, onSelectDevice }: ResultsDisplayProps) {
  if (!results.results || results.results.length === 0) {
    return <div className="no-results">No results found</div>
  }

  // Analyze and aggregate the data
  const analysis = useMemo(() => {
    const events = results.results as any[]
    
    // Count event types
    const eventTypes = { Death: 0, Injury: 0, Malfunction: 0, Other: 0 }
    const manufacturers = new Map<string, number>()
    const problems = new Map<string, number>()
    const recentCritical: any[] = []
    
    events.forEach(event => {
      // Count event types
      const eventType = event.event_type || 'Other'
      if (eventType in eventTypes) {
        eventTypes[eventType as keyof typeof eventTypes]++
      } else if (eventType.toLowerCase().includes('death')) {
        eventTypes.Death++
      } else if (eventType.toLowerCase().includes('injury')) {
        eventTypes.Injury++
      } else if (eventType.toLowerCase().includes('malfunction')) {
        eventTypes.Malfunction++
      } else {
        eventTypes.Other++
      }
      
      // Count manufacturers
      const deviceInfo = Array.isArray(event.device) ? event.device[0] : event.device
      const manufacturer = deviceInfo?.manufacturer_d_name || deviceInfo?.manufacturer_name || 'Unknown'
      manufacturers.set(manufacturer, (manufacturers.get(manufacturer) || 0) + 1)
      
      // Count patient problems
      if (event.patient && Array.isArray(event.patient)) {
        event.patient.forEach((p: any) => {
          if (p.patient_problem_description) {
            problems.set(p.patient_problem_description, (problems.get(p.patient_problem_description) || 0) + 1)
          }
        })
      }
      
      // Collect critical events
      if (eventType === 'Death' || eventType === 'Injury') {
        recentCritical.push(event)
      }
    })
    
    // Sort and limit results
    const topManufacturers = Array.from(manufacturers.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
    
    const topProblems = Array.from(problems.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
    
    recentCritical.sort((a, b) => {
      // Parse FDA date format for sorting
      const parseDate = (dateStr: string) => {
        if (!dateStr || dateStr.length !== 8) return 0
        return parseInt(dateStr) // YYYYMMDD format can be compared as integers
      }
      const dateA = parseDate(a.date_of_event || a.date_received || '')
      const dateB = parseDate(b.date_of_event || b.date_received || '')
      return dateB - dateA // Sort descending (newest first)
    })
    
    return {
      eventTypes,
      topManufacturers,
      topProblems,
      recentCritical: recentCritical.slice(0, 10),
      totalEvents: events.length
    }
  }, [results.results])

  return (
    <div className="results-container">
      <div className="results-header">
        <h2>Device Safety Analysis</h2>
        <p>{results.total_results.toLocaleString()} total events in FDA database • Analyzing {results.results_count} most recent</p>
        <p style={{ fontSize: '0.85rem', color: 'rgba(0,0,0,0.6)', marginTop: '4px' }}>
          Events are sorted by date received (newest first)
        </p>
      </div>

      {/* Summary Statistics */}
      <div className="summary-section">
        <h3>Event Severity Breakdown</h3>
        <div className="summary-grid">
          <div className={`stat-box ${analysis.eventTypes.Death > 0 ? 'stat-critical' : ''}`}>
            <span className="stat-value">{analysis.eventTypes.Death}</span>
            <span className="stat-label">🔴 Deaths</span>
          </div>
          <div className={`stat-box ${analysis.eventTypes.Injury > 0 ? 'stat-warning' : ''}`}>
            <span className="stat-value">{analysis.eventTypes.Injury}</span>
            <span className="stat-label">🟠 Injuries</span>
          </div>
          <div className="stat-box">
            <span className="stat-value">{analysis.eventTypes.Malfunction}</span>
            <span className="stat-label">🟡 Malfunctions</span>
          </div>
          <div className="stat-box">
            <span className="stat-value">{analysis.eventTypes.Other}</span>
            <span className="stat-label">⚪ Other</span>
          </div>
        </div>
      </div>

      {/* Two column layout for manufacturers and problems */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginTop: '24px' }}>
        
        {/* Top Manufacturers */}
        {analysis.topManufacturers.length > 0 && (
          <div className="analysis-panel">
            <h3>Top Manufacturers by Event Count</h3>
            <div className="manufacturer-list">
              {analysis.topManufacturers.map(([name, count], i) => (
                <div key={i} className="manufacturer-item">
                  <div className="manufacturer-name" title={name}>
                    {name.length > 40 ? `${name.substring(0, 37)}...` : name}
                  </div>
                  <div className="manufacturer-bar">
                    <div 
                      className="bar-fill"
                      style={{ 
                        width: `${(count / analysis.topManufacturers[0][1]) * 100}%`,
                        background: 'var(--teal)'
                      }}
                    />
                    <span className="bar-label">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Top Problems */}
        {analysis.topProblems.length > 0 && (
          <div className="analysis-panel">
            <h3>Most Common Problems</h3>
            <div className="problems-list">
              {analysis.topProblems.map(([problem, count], i) => (
                <div key={i} className="problem-item">
                  <div className="problem-name">{problem}</div>
                  <div className="problem-count">{count} cases</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Recent Critical Events */}
      <div style={{ marginTop: '32px' }}>
        <h3>Recent Critical Events</h3>
        {analysis.recentCritical.length > 0 ? (
          <div className="critical-events-grid">
            {analysis.recentCritical.map((event: any, index) => {
              const deviceInfo = Array.isArray(event.device) ? event.device[0] : event.device
              const genericName = deviceInfo?.generic_name || 'Unknown Device'
              const brandName = deviceInfo?.brand_name || ''
              const manufacturerName = deviceInfo?.manufacturer_d_name || 'Unknown Manufacturer'
              const eventType = event.event_type || 'Unknown'
              const isDeath = eventType.toLowerCase().includes('death')
              
              return (
                <div 
                  key={event.report_number || index} 
                  className={`result-card ${isDeath ? 'card-critical' : 'card-warning'}`}
                >
                  <div className="severity-indicator">
                    {isDeath ? '🔴 DEATH' : '🟠 INJURY'}
                  </div>
                  <div className="card-header">
                    <h4>{genericName}</h4>
                    {brandName && brandName !== genericName && (
                      <p className="brand-name">{brandName}</p>
                    )}
                  </div>
                  <div className="card-body">
                    <p><strong>Manufacturer:</strong> {manufacturerName}</p>
                    {event.date_of_event && (
                      <p><strong>Date:</strong> {parseFDADate(event.date_of_event)}</p>
                    )}
                    {event.patient && event.patient[0]?.patient_problem_description && (
                      <p><strong>Problem:</strong> {event.patient[0].patient_problem_description}</p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <p style={{ color: 'var(--sage)', fontStyle: 'italic' }}>
            No deaths or injuries reported in this dataset
          </p>
        )}
      </div>

      {/* All Events (collapsed by default) */}
      <details style={{ marginTop: '32px' }}>
        <summary style={{ cursor: 'pointer', padding: '12px', background: 'rgba(0,0,0,0.02)', borderRadius: '8px' }}>
          View All {results.results_count} Events
        </summary>
        <div className="results-grid" style={{ marginTop: '16px' }}>
          {results.results.map((event: any, index) => {
            const deviceInfo = Array.isArray(event.device) ? event.device[0] : event.device
            const genericName = deviceInfo?.generic_name || 'Unknown Device'
            const brandName = deviceInfo?.brand_name || ''
            const manufacturerName = deviceInfo?.manufacturer_d_name || ''
            
            return (
              <div key={event.report_number || index} className="result-card">
                <div className="card-header">
                  <h4>{genericName}</h4>
                  {brandName && brandName !== genericName && (
                    <p className="brand-name">{brandName}</p>
                  )}
                </div>
                <div className="card-body">
                  {manufacturerName && <p><strong>Manufacturer:</strong> {manufacturerName}</p>}
                  {(event.date_of_event || event.date_received) && (
                    <p><strong>Date:</strong> {parseFDADate(event.date_of_event || event.date_received)}</p>
                  )}
                  {event.event_type && (
                    <p><strong>Type:</strong> {event.event_type}</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </details>
    </div>
  )
}