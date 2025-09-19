const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? '/openfda-insights/api'
  : 'http://localhost:8001'

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
}

export const apiClient = new APIClient()