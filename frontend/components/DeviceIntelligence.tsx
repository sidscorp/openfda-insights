'use client'

import { useQuery } from '@tanstack/react-query'
import { apiClient, DeviceIntelligence as DeviceIntelligenceType } from '@/lib/api'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts'

interface DeviceIntelligenceProps {
  deviceName: string
}

export default function DeviceIntelligence({ deviceName }: DeviceIntelligenceProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['device-intelligence', deviceName],
    queryFn: () => apiClient.getDeviceIntelligence(deviceName, 12),
  })

  if (isLoading) return <div className="loading">Loading device intelligence...</div>
  if (error) return <div className="error">Failed to load device intelligence</div>
  if (!data) return null

  const manufacturerData = Object.entries(data.manufacturer_distribution || {})
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10)

  return (
    <div className="device-intelligence">
      <h2>Device Intelligence: {data.device_name}</h2>
      
      <div className="stats-grid">
        <div className="stat-card">
          <h3>Total Events</h3>
          <p className="stat-value">{data.total_events.toLocaleString()}</p>
        </div>

        {data.risk_assessment && (
          <div className="stat-card">
            <h3>Risk Assessment</h3>
            <div className={`risk-badge risk-${data.risk_assessment.level.toLowerCase()}`}>
              {data.risk_assessment.level} ({data.risk_assessment.score}/10)
            </div>
            <ul className="risk-factors">
              {data.risk_assessment.factors.slice(0, 3).map((factor, i) => (
                <li key={i}>{factor}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {data.temporal_trends && data.temporal_trends.length > 0 && (
        <div className="chart-section">
          <h3>Temporal Trends</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.temporal_trends}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="period" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="event_count" stroke="#2563eb" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {manufacturerData.length > 0 && (
        <div className="chart-section">
          <h3>Top Manufacturers</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={manufacturerData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}