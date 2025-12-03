'use client';

import React, { useState, useEffect, useRef } from 'react';
import styles from './EnhancedAgentProgress.module.css';

interface AgentState {
  agent_id: string;
  agent_name: string;
  status: 'waiting' | 'running' | 'completed' | 'failed' | 'skipped';
  progress: number;
  message: string;
  data_points?: number;
  timestamp: string;
}

interface AgentCapability {
  id: string;
  name: string;
  icon: string;
  description: string;
  capabilities: string[];
  color: string;
}

interface EnhancedAgentProgressProps {
  query: string;
  isActive: boolean;
  onComplete?: (result: any) => void;
  onError?: (error: string) => void;
}

export default function EnhancedAgentProgress({ 
  query, 
  isActive, 
  onComplete, 
  onError 
}: EnhancedAgentProgressProps) {
  const [agentStates, setAgentStates] = useState<Record<string, AgentState>>({});
  const [overallProgress, setOverallProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('Initializing agents...');
  const [capabilities, setCapabilities] = useState<AgentCapability[]>([]);
  const [dataFlow, setDataFlow] = useState<Array<{from: string, to: string, id: number}>>([]);
  const eventSourceRef = useRef<EventSource | null>(null);
  const dataFlowIdRef = useRef(0);

  // Fetch agent capabilities on mount
  useEffect(() => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api';
    fetch(`${baseUrl}/agents/capabilities`)
      .then(res => res.json())
      .then(data => setCapabilities(data.agents))
      .catch(console.error);
  }, []);

  // Connect to SSE stream when active
  useEffect(() => {
    if (!isActive || !query) return;

    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api';
    const eventSource = new EventSource(
      `${baseUrl}/agents/analyze/stream/${encodeURIComponent(query)}`
    );
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log('Connected to agent stream');
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        switch (data.type) {
          case 'agent_states':
            setAgentStates(data.data);
            break;
            
          case 'agent_update':
            setAgentStates(prev => ({
              ...prev,
              ...data.data
            }));
            
            // Animate data flow between agents
            const updatedAgents = Object.keys(data.data);
            if (updatedAgents.length > 0) {
              const fromAgent = 'orchestrator';
              updatedAgents.forEach(toAgent => {
                if (toAgent !== 'orchestrator') {
                  const flowId = dataFlowIdRef.current++;
                  setDataFlow(prev => [...prev, { from: fromAgent, to: toAgent, id: flowId }]);
                  
                  // Remove flow animation after 2 seconds
                  setTimeout(() => {
                    setDataFlow(prev => prev.filter(f => f.id !== flowId));
                  }, 2000);
                }
              });
            }
            break;
            
          case 'progress':
            setOverallProgress(data.data.percentage);
            setStatusMessage(data.data.message);
            break;
            
          case 'complete':
            if (onComplete) {
              onComplete(data.data);
            }
            break;
            
          case 'error':
            if (onError) {
              onError(data.data.message);
            }
            break;
        }
      } catch (error) {
        console.error('Error parsing SSE data:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      if (onError) {
        onError('Connection to agent system lost');
      }
      eventSource.close();
    };

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [isActive, query, onComplete, onError]);

  // Get agent capability info
  const getAgentInfo = (agentId: string): AgentCapability | undefined => {
    return capabilities.find(cap => cap.id === agentId);
  };

  // Calculate positions for circular layout
  const getAgentPosition = (index: number, total: number) => {
    const angle = (index * 2 * Math.PI) / total - Math.PI / 2;
    const radius = 200;
    const x = Math.cos(angle) * radius + 250;
    const y = Math.sin(angle) * radius + 250;
    return { x, y };
  };

  // Filter visible agents
  const visibleAgents = Object.entries(agentStates).filter(
    ([id, state]) => id !== 'orchestrator' && state.status !== 'skipped'
  );

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3>Multi-Agent Intelligence System</h3>
        <p className={styles.query}>Analyzing: "{query}"</p>
      </div>

      <div className={styles.orchestrationView}>
        {/* Central Orchestrator */}
        <div className={styles.centralOrchestrator}>
          <div className={`${styles.orchestratorNode} ${
            agentStates.orchestrator?.status === 'completed' ? styles.completed : ''
          }`}>
            <span className={styles.icon}>🧠</span>
            <span className={styles.name}>Orchestrator</span>
            <span className={styles.status}>
              {agentStates.orchestrator?.message || 'Initializing...'}
            </span>
          </div>
        </div>

        {/* Specialist Agents in Circle */}
        <svg className={styles.connectionLayer} viewBox="0 0 500 500">
          {/* Draw connections */}
          {visibleAgents.map(([agentId, state], index) => {
            const pos = getAgentPosition(index, visibleAgents.length);
            const isActive = state.status === 'running' || state.status === 'completed';
            
            return (
              <g key={agentId}>
                <line
                  x1="250"
                  y1="250"
                  x2={pos.x}
                  y2={pos.y}
                  stroke={isActive ? '#4ecdc4' : '#e0e0e0'}
                  strokeWidth={isActive ? '3' : '2'}
                  strokeDasharray={state.status === 'running' ? '5,5' : ''}
                  opacity={isActive ? 1 : 0.3}
                >
                  {state.status === 'running' && (
                    <animate
                      attributeName="stroke-dashoffset"
                      values="0;10"
                      dur="1s"
                      repeatCount="indefinite"
                    />
                  )}
                </line>
              </g>
            );
          })}

          {/* Data flow animations */}
          {dataFlow.map(flow => {
            const fromPos = flow.from === 'orchestrator' 
              ? { x: 250, y: 250 }
              : getAgentPosition(
                  visibleAgents.findIndex(([id]) => id === flow.from),
                  visibleAgents.length
                );
            const toPos = getAgentPosition(
              visibleAgents.findIndex(([id]) => id === flow.to),
              visibleAgents.length
            );
            
            return (
              <circle
                key={flow.id}
                r="5"
                fill="#4ecdc4"
                opacity="0.8"
              >
                <animateMotion
                  dur="2s"
                  fill="freeze"
                  path={`M${fromPos.x},${fromPos.y} L${toPos.x},${toPos.y}`}
                />
                <animate
                  attributeName="opacity"
                  values="0;1;1;0"
                  dur="2s"
                />
              </circle>
            );
          })}
        </svg>

        {/* Render Specialist Agents */}
        {visibleAgents.map(([agentId, state], index) => {
          const pos = getAgentPosition(index, visibleAgents.length);
          const info = getAgentInfo(agentId);
          
          return (
            <div
              key={agentId}
              className={`${styles.specialistAgent} ${styles[state.status]}`}
              style={{
                left: `${pos.x - 60}px`,
                top: `${pos.y - 60}px`,
                borderColor: info?.color || '#ccc'
              }}
            >
              <div className={styles.agentIcon}>{info?.icon || '🤖'}</div>
              <div className={styles.agentName}>{state.agent_name}</div>
              <div className={styles.agentStatus}>{state.message}</div>
              {state.data_points !== undefined && (
                <div className={styles.dataPoints}>
                  {state.data_points.toLocaleString()} records
                </div>
              )}
              {state.status === 'running' && (
                <div className={styles.progressBar}>
                  <div 
                    className={styles.progressFill}
                    style={{ 
                      width: `${state.progress}%`,
                      backgroundColor: info?.color || '#4ecdc4'
                    }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Overall Progress */}
      <div className={styles.overallProgress}>
        <div className={styles.progressHeader}>
          <span>{statusMessage}</span>
          <span>{overallProgress}%</span>
        </div>
        <div className={styles.progressBar}>
          <div 
            className={styles.progressFill}
            style={{ width: `${overallProgress}%` }}
          />
        </div>
      </div>

      {/* Agent Capabilities Legend */}
      <div className={styles.capabilities}>
        <h4>Active Specialist Agents</h4>
        <div className={styles.capabilityGrid}>
          {visibleAgents.map(([agentId]) => {
            const info = getAgentInfo(agentId);
            if (!info) return null;
            
            return (
              <div 
                key={agentId} 
                className={styles.capabilityCard}
                style={{ borderColor: info.color }}
              >
                <div className={styles.capabilityHeader}>
                  <span className={styles.capabilityIcon}>{info.icon}</span>
                  <span className={styles.capabilityName}>{info.name}</span>
                </div>
                <p className={styles.capabilityDesc}>{info.description}</p>
                <ul className={styles.capabilityList}>
                  {info.capabilities.slice(0, 2).map((cap, i) => (
                    <li key={i}>{cap}</li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}