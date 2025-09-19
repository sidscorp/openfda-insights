'use client'

import { useEffect, useState } from 'react'

interface AgentStep {
  id: string
  icon: string
  name: string
  description: string
  progress: number
  status: 'waiting' | 'active' | 'complete'
  message?: string
}

interface AgentProgressProps {
  isProcessing: boolean
  onComplete?: (data: any) => void
  deviceName: string
  useRealData?: boolean  // Toggle between simulation and real SSE
}

export default function AgentProgress({ isProcessing, onComplete, deviceName, useRealData = false }: AgentProgressProps) {
  const [agents, setAgents] = useState<AgentStep[]>([
    {
      id: 'collector',
      icon: '🔍',
      name: 'Data Collector',
      description: 'Searching FDA databases',
      progress: 0,
      status: 'waiting',
    },
    {
      id: 'analyzer',
      icon: '🧠',
      name: 'Pattern Analyzer',
      description: 'Finding trends and risks',
      progress: 0,
      status: 'waiting',
    },
    {
      id: 'writer',
      icon: '📝',
      name: 'Narrative Writer',
      description: 'Creating comprehensive report',
      progress: 0,
      status: 'waiting',
    }
  ])
  
  const [currentMessage, setCurrentMessage] = useState('Initializing AI agents...')
  const [particles, setParticles] = useState<number[]>([])

  useEffect(() => {
    if (!isProcessing) return

    // Use real SSE data if available, otherwise simulate
    if (useRealData) {
      // Real SSE implementation would go here
      // For now, fall back to simulation
    }
    
    // Simulate progress updates
    const simulateProgress = async () => {
      const steps = [
        { time: 500, agent: 'collector', progress: 10, status: 'active', message: '🔍 Searching device events...' },
        { time: 1500, agent: 'collector', progress: 20, status: 'active', message: '📊 Found 200 events, searching recalls...' },
        { time: 2500, agent: 'collector', progress: 30, status: 'active', message: '🏭 Collecting manufacturer data...' },
        { time: 3500, agent: 'collector', progress: 100, status: 'complete', message: '✅ Data collection complete!' },
        { time: 4000, agent: 'analyzer', progress: 10, status: 'active', message: '🧠 Calculating risk patterns...' },
        { time: 5000, agent: 'analyzer', progress: 40, status: 'active', message: '📈 Analyzing temporal trends...' },
        { time: 6000, agent: 'analyzer', progress: 70, status: 'active', message: '⚠️ Risk score: 3.1/10 (Low)' },
        { time: 7000, agent: 'analyzer', progress: 100, status: 'complete', message: '✅ Analysis complete!' },
        { time: 7500, agent: 'writer', progress: 20, status: 'active', message: '📝 Writing executive summary...' },
        { time: 8500, agent: 'writer', progress: 60, status: 'active', message: '📋 Creating safety profile...' },
        { time: 9500, agent: 'writer', progress: 90, status: 'active', message: '💡 Generating recommendations...' },
        { time: 10500, agent: 'writer', progress: 100, status: 'complete', message: '✅ Report ready!' },
      ]

      for (const step of steps) {
        await new Promise(resolve => setTimeout(resolve, step.time))
        
        setAgents(prev => prev.map(agent => {
          if (agent.id === step.agent) {
            return { ...agent, progress: step.progress, status: step.status as any }
          }
          // Set previous agents to complete when moving to next
          if (step.agent === 'analyzer' && agent.id === 'collector') {
            return { ...agent, status: 'complete', progress: 100 }
          }
          if (step.agent === 'writer' && agent.id === 'analyzer') {
            return { ...agent, status: 'complete', progress: 100 }
          }
          return agent
        }))
        
        setCurrentMessage(step.message)
        
        // Add particles between agents
        if (step.progress === 100 && step.agent !== 'writer') {
          setParticles(prev => [...prev, Date.now()])
        }
      }

      // Call the real API here and pass the result
      if (onComplete) {
        // In real implementation, this would be the actual API response
        setTimeout(() => onComplete({ success: true }), 11000)
      }
    }

    simulateProgress()
  }, [isProcessing, onComplete])

  if (!isProcessing) return null

  return (
    <div className="agent-progress-container">
      <div className="progress-header">
        <h3>AI Agents Processing: {deviceName}</h3>
        <p className="progress-message">{currentMessage}</p>
      </div>
      
      <div className="agent-pipeline">
        {agents.map((agent, index) => (
          <div key={agent.id} className="agent-wrapper">
            <div className={`agent-card ${agent.status}`}>
              <div className="agent-icon">{agent.icon}</div>
              <div className="agent-info">
                <h4>{agent.name}</h4>
                <p>{agent.description}</p>
              </div>
              <div className="agent-progress">
                <div className="progress-bar">
                  <div 
                    className="progress-fill"
                    style={{ width: `${agent.progress}%` }}
                  />
                </div>
                {agent.status === 'complete' && (
                  <span className="checkmark">✓</span>
                )}
              </div>
            </div>
            
            {/* Arrow between agents */}
            {index < agents.length - 1 && (
              <div className="agent-connector">
                <svg width="40" height="40" viewBox="0 0 40 40">
                  <path 
                    d="M 10 20 L 30 20" 
                    stroke="var(--teal)" 
                    strokeWidth="2"
                    strokeDasharray={agent.status === 'complete' ? '0' : '5,5'}
                    opacity={agent.status === 'complete' ? 1 : 0.3}
                  />
                  <path 
                    d="M 25 15 L 30 20 L 25 25" 
                    stroke="var(--teal)" 
                    strokeWidth="2"
                    fill="none"
                    opacity={agent.status === 'complete' ? 1 : 0.3}
                  />
                </svg>
                
                {/* Data particles */}
                {particles.map((particle, i) => (
                  <div 
                    key={particle}
                    className="data-particle"
                    style={{ animationDelay: `${i * 0.2}s` }}
                  />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      
      <div className="progress-stats">
        <div className="stat-item">
          <span className="stat-label">Events Found:</span>
          <span className="stat-value animating">200</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Risk Level:</span>
          <span className="stat-value">Calculating...</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Time Elapsed:</span>
          <span className="stat-value">10s</span>
        </div>
      </div>
    </div>
  )
}