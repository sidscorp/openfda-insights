'use client'

import { DeviceNarrative } from '@/lib/api'
import { Line, Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

interface Props {
  narrative: DeviceNarrative
}

export default function DeviceNarrativeDisplay({ narrative }: Props) {
  // Safety checks for potentially undefined properties
  const summary = narrative?.summary || {
    total_events: 0,
    risk_score: 0,
    risk_level: 'Unknown',
    total_recalls: 0,
    top_manufacturer: [],
    date_range: 'N/A'
  }
  const analysis = narrative?.analysis || { event_types: {} }
  const narrativeText = narrative?.narrative || { sections: {} }

  // Prepare event types chart data
  const eventTypesData = {
    labels: Object.keys(analysis.event_types || {}),
    datasets: [{
      label: 'Event Count',
      data: Object.values(analysis.event_types || {}),
      backgroundColor: [
        'rgba(255, 107, 107, 0.8)',  // coral
        'rgba(78, 205, 196, 0.8)',   // teal
        'rgba(255, 230, 109, 0.8)',  // orange
        'rgba(168, 230, 207, 0.8)',  // sage
        'rgba(155, 89, 182, 0.8)',   // purple
      ],
      borderColor: [
        'rgba(255, 107, 107, 1)',
        'rgba(78, 205, 196, 1)',
        'rgba(255, 230, 109, 1)',
        'rgba(168, 230, 207, 1)',
        'rgba(155, 89, 182, 1)',
      ],
      borderWidth: 2,
    }]
  }

  // Risk level styling
  const getRiskBadgeClass = (level: string) => {
    switch(level.toLowerCase()) {
      case 'low': return 'risk-low'
      case 'moderate': return 'risk-moderate'
      case 'high': return 'risk-high'
      default: return 'risk-low'
    }
  }

  return (
    <div className="results-container">
      {/* Summary Section */}
      <div className="summary-section">
        <h2>Device Intelligence Summary</h2>
        <h3>{narrative.device_name}</h3>
        
        <div className="summary-grid">
          <div className="stat-box">
            <span className="stat-value">{summary.total_events}</span>
            <span className="stat-label">Total Events</span>
          </div>
          
          <div className="stat-box">
            <span className="stat-value">{summary.risk_score.toFixed(1)}/10</span>
            <span className="stat-label">Risk Score</span>
          </div>
          
          <div className="stat-box">
            <span className="stat-value">{summary.total_recalls}</span>
            <span className="stat-label">Recalls</span>
          </div>
          
          <div className="stat-box">
            <span className="stat-value">{summary.top_manufacturer[0]?.split(' ').slice(0, 2).join(' ') || 'N/A'}</span>
            <span className="stat-label">Top Manufacturer</span>
          </div>
        </div>
        
        <div className={`risk-badge ${getRiskBadgeClass(summary.risk_level)}`}>
          Risk Level: {summary.risk_level}
        </div>
      </div>

      {/* Event Types Chart */}
      {analysis.event_types && Object.keys(analysis.event_types).length > 0 && (
        <div className="timeline-container">
          <h3>Event Type Distribution</h3>
          <Bar 
            data={eventTypesData}
            options={{
              responsive: true,
              plugins: {
                legend: {
                  display: false
                },
                tooltip: {
                  backgroundColor: 'rgba(45, 52, 54, 0.9)',
                  cornerRadius: 8,
                }
              },
              scales: {
                y: {
                  beginAtZero: true,
                  grid: {
                    color: 'rgba(0, 0, 0, 0.05)'
                  }
                },
                x: {
                  grid: {
                    display: false
                  }
                }
              }
            }}
          />
        </div>
      )}

      {/* Narrative Sections */}
      {narrativeText && narrativeText.sections && (
        <div className="narrative-section">
          <h2>📊 Comprehensive Analysis</h2>
          <div className="narrative-content">
            {Object.entries(narrativeText.sections).map(([title, content]) => (
              <div key={title}>
                <h3>{title}</h3>
                <p>{content}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Metadata */}
      {narrative.metadata && (
        <div className="metadata" style={{ 
          marginTop: '32px', 
          padding: '16px', 
          background: 'rgba(0,0,0,0.02)', 
          borderRadius: '8px',
          fontSize: '0.9rem',
          color: 'rgba(0,0,0,0.6)'
        }}>
          {narrative.metadata.generation_time && (
            <p>Generated in {(narrative.metadata.generation_time / 1000).toFixed(2)}s</p>
          )}
          {narrative.metadata.data_sources && (
            <p>Data sources: {narrative.metadata.data_sources.join(', ')}</p>
          )}
          {summary.date_range && (
            <p>Date range: {summary.date_range}</p>
          )}
        </div>
      )}
    </div>
  )
}