const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api'

// Multi-agent system types
export interface AgentState {
  agent_id: string
  agent_name: string
  status: 'waiting' | 'running' | 'completed' | 'failed' | 'skipped'
  progress: number
  message: string
  data_points?: number
  timestamp: string
}

export interface AgentCapability {
  id: string
  name: string
  icon: string
  description: string
  capabilities: string[]
  color: string
}

export interface MultiAgentResult {
  success: boolean
  query: string
  intent: {
    primary_intent: string
    device_names: string[]
    time_range: string | null
    specific_concerns: string[]
    required_agents: string[]
  }
  agent_results: Record<string, any[]>
  timestamp: string
}

export type AgentStreamEvent =
  | { type: 'start'; question: string }
  | { type: 'thinking'; content: string }
  | { type: 'tool_call'; tool: string; args: Record<string, unknown> }
  | { type: 'tool_result'; content: string }
  | { type: 'complete'; answer: string; model?: string; tokens?: number; structured_data?: any }
  | { type: 'error'; message: string }

export interface SearchRequest {
  query: string
  query_type?: 'device' | 'manufacturer' | 'recall'
  limit?: number
  include_ai_analysis?: boolean
}

export interface DeviceEvent {
  report_number: string
  event_date: string
  device: {
    generic_name?: string
    brand_name?: string
    manufacturer_name?: string
  }
  patient?: {
    patient_problem?: string[]
  }
  event_type?: string
}

export interface SearchResponse {
  status: string
  query: string
  query_type: string
  total_results: number
  results_count: number
  results: DeviceEvent[]
  ai_analysis?: {
    summary: string
    key_insights: string[]
    risk_assessment?: {
      level: string
      score: number
      factors: string[]
    }
  }
  metadata?: {
    search_time: number
    processing_time: number
  }
}

export interface DeviceIntelligence {
  device_name: string
  total_events: number
  manufacturer_distribution: Record<string, number>
  temporal_trends: {
    period: string
    event_count: number
  }[]
  risk_assessment?: {
    level: string
    score: number
    factors: string[]
  }
}

export interface DeviceNarrative {
  device_name: string
  summary: {
    total_events: number
    date_range: string
    risk_level: string
    risk_score: number
    top_manufacturer: string[]
    total_recalls: number
  }
  analysis: {
    event_types: Record<string, number>
    temporal_patterns: any
    manufacturer_analysis: any
  }
  narrative: {
    sections: Record<string, string>
  }
  metadata: {
    generation_time: number
    data_sources: string[]
  }
}

class APIClient {
  public baseUrl: string = API_BASE_URL
  
  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      })

      if (!response.ok) {
        const error = await response.text()
        throw new Error(error || `HTTP error! status: ${response.status}`)
      }

      return response.json()
    } catch (error) {
      console.error('API request failed:', error)
      throw error
    }
  }

  async search(params: SearchRequest): Promise<SearchResponse> {
    return this.request<SearchResponse>('/search', {
      method: 'POST',
      body: JSON.stringify(params),
    })
  }

  async getDeviceIntelligence(deviceName: string, lookbackMonths: number = 12): Promise<DeviceIntelligence> {
    return this.request<DeviceIntelligence>('/device/intelligence', {
      method: 'POST',
      body: JSON.stringify({
        device_name: deviceName,
        lookback_months: lookbackMonths,
        include_risk_assessment: true,
      }),
    })
  }

  async compareDevices(deviceNames: string[]): Promise<any> {
    return this.request('/device/compare', {
      method: 'POST',
      body: JSON.stringify({
        device_names: deviceNames,
        lookback_months: 12,
      }),
    })
  }

  async getDeviceNarrative(deviceName: string): Promise<DeviceNarrative> {
    return this.request<DeviceNarrative>('/device/narrative', {
      method: 'POST',
      body: JSON.stringify({
        device_name: deviceName,
      }),
    })
  }

  async streamDeviceNarrative(
    deviceName: string, 
    onProgress: (percentage: number, message: string) => void,
    onComplete: (result: DeviceNarrative) => void,
    onError?: (error: string) => void
  ): Promise<void> {
    const eventSource = new EventSource(`${this.baseUrl}/device/narrative/stream/${encodeURIComponent(deviceName)}`)
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        
        if (data.event === 'progress') {
          onProgress(data.data.percentage, data.data.message)
        } else if (data.event === 'complete') {
          onComplete(data.data)
          eventSource.close()
        } else if (data.event === 'error') {
          if (onError) onError(data.message)
          eventSource.close()
        }
      } catch (error) {
        console.error('Error parsing SSE data:', error)
      }
    }
    
    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error)
      if (onError) onError('Connection error')
      eventSource.close()
    }
  }

  // Multi-agent system methods
  async analyzeWithAgents(query: string): Promise<MultiAgentResult> {
    return this.request<MultiAgentResult>('/agents/analyze', {
      method: 'POST',
      body: JSON.stringify({ query }),
    })
  }

  async getAgentCapabilities(): Promise<{ agents: AgentCapability[] }> {
    return this.request<{ agents: AgentCapability[] }>('/agents/capabilities')
  }

  streamAgentAnalysis(
    query: string,
    onAgentUpdate: (agentStates: Record<string, AgentState>) => void,
    onProgress: (percentage: number, message: string) => void,
    onComplete: (result: MultiAgentResult) => void,
    onError?: (error: string) => void
  ): EventSource {
    const eventSource = new EventSource(`${this.baseUrl}/agents/analyze/stream/${encodeURIComponent(query)}`)
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        
        switch (data.type) {
          case 'agent_states':
          case 'agent_update':
            onAgentUpdate(data.data)
            break
          case 'progress':
            onProgress(data.data.percentage, data.data.message)
            break
          case 'complete':
            onComplete(data.data)
            eventSource.close()
            break
          case 'error':
            if (onError) onError(data.data.message)
            eventSource.close()
            break
        }
      } catch (error) {
        console.error('Error parsing SSE data:', error)
      }
    }
    
    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error)
      if (onError) onError('Connection error')
      eventSource.close()
    }

    return eventSource
  }

  openAgentStream(
    question: string,
    handlers: {
      onEvent?: (event: AgentStreamEvent) => void
      onError?: (err: string) => void
    }
  ): EventSource {
    const es = new EventSource(`${this.baseUrl}/agent/stream/${encodeURIComponent(question)}`)

    es.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as AgentStreamEvent
        handlers.onEvent?.(payload)
      } catch (err) {
        console.error('Failed to parse agent stream event', err)
      }
    }

    es.onerror = () => {
      es.close()
      handlers.onError?.('Connection lost')
    }

    return es
  }
}

export const apiClient = new APIClient()
