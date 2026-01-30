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
  | { type: 'clear' }
  | { type: 'thinking'; content: string }
  | { type: 'delta'; content: string }
  | { type: 'tool_call'; tool: string; args: Record<string, unknown> }
  | { type: 'tool_result'; content: string }
  | { type: 'complete'; answer: string; model?: string; tokens?: number; input_tokens?: number; output_tokens?: number; cost?: number; structured_data?: any }
  | { type: 'error'; message: string }

export interface QueryDetail {
  id: string
  tool: string
  dataSource: string
  args: Record<string, unknown>
  status: 'pending' | 'complete' | 'error'
  resultSummary?: string
  timestamp: number
}

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

// Lookup API types for disambiguation
export type EntityType = 'device' | 'manufacturer'
export type IdentifierType = 'product_code' | 'primary_di' | 'fei_number' | 'k_number' | 'pma_number' | 'company_name' | 'device_name'

export interface LookupCandidate {
  entity_type: EntityType
  identifier: string
  identifier_type: IdentifierType
  display_name: string
  description?: string
  device_count?: number
  device_class?: string  // "1", "2", or "3" for FDA device classification
}

export interface IdentifyResponse {
  input: string
  needs_disambiguation: boolean
  entity_type?: EntityType
  identifier?: string
  identifier_type?: IdentifierType
  candidates: LookupCandidate[]
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
    },
    sessionId?: string
  ): EventSource {
    let url = `${this.baseUrl}/agent/stream/${encodeURIComponent(question)}`
    if (sessionId) {
      url += `?session_id=${encodeURIComponent(sessionId)}`
    }
    const es = new EventSource(url)

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

  async getUsage(): Promise<UsageStats> {
    return this.request<UsageStats>('/usage')
  }

  async identify(input: string): Promise<IdentifyResponse> {
    return this.request<IdentifyResponse>('/lookup/identify', {
      method: 'POST',
      body: JSON.stringify({ input }),
    })
  }

  async generateSessionTitle(firstUserMessage: string, firstAssistantResponse: string): Promise<{ title: string }> {
    return this.request<{ title: string }>('/sessions/generate-title', {
      method: 'POST',
      body: JSON.stringify({
        first_user_message: firstUserMessage,
        first_assistant_response: firstAssistantResponse,
      }),
    })
  }

  async extendUsageLimit(passphrase: string): Promise<{ success: boolean; new_limit: number }> {
    return this.request<{ success: boolean; new_limit: number }>('/usage/extend', {
      method: 'POST',
      body: JSON.stringify({ passphrase }),
    })
  }

  async getDeviceReport(identifier: string, type: string = 'product_code'): Promise<DeviceReportResponse> {
    return this.request<DeviceReportResponse>(
      `/lookup/device/${encodeURIComponent(identifier)}?type=${encodeURIComponent(type)}`
    )
  }

  async getManufacturerReport(identifier: string, type: string = 'company_name'): Promise<ManufacturerReportResponse> {
    return this.request<ManufacturerReportResponse>(
      `/lookup/manufacturer/${encodeURIComponent(identifier)}?type=${encodeURIComponent(type)}`
    )
  }

  async generateLookupSummary(
    entityType: string,
    identifier: string,
    reportData: DeviceReportResponse | ManufacturerReportResponse
  ): Promise<SummaryResponse> {
    return this.request<SummaryResponse>('/lookup/summary', {
      method: 'POST',
      body: JSON.stringify({
        entity_type: entityType,
        identifier,
        report_data: reportData,
      }),
    })
  }

  async answerFollowup(
    entityType: string,
    identifier: string,
    reportSummary: string,
    question: string
  ): Promise<FollowupResponse> {
    return this.request<FollowupResponse>('/lookup/followup', {
      method: 'POST',
      body: JSON.stringify({
        entity_type: entityType,
        identifier,
        report_summary: reportSummary,
        question,
      }),
    })
  }
}

export interface UsageStats {
  ip_address: string
  request_count: number
  request_limit: number
  requests_remaining: number
  total_input_tokens: number
  total_output_tokens: number
  first_request: string | null
  last_request: string | null
}

// Device Report types
export interface ClassificationSection {
  device_class?: string
  device_name?: string
  regulation_number?: string
  submission_type?: string
  definition?: string
  medical_specialty?: string
}

export interface EventTypeCounts {
  death: number
  injury: number
  malfunction: number
  other: number
}

export interface EventsSection {
  total_count: number
  event_type_counts: EventTypeCounts
  top_manufacturers: Array<{ name: string; count: number }>
  recent_events: Array<{
    report_number?: string
    event_date?: string
    event_type?: string
    device_name?: string
    manufacturer?: string
    description?: string
  }>
}

export interface RecallClassCounts {
  class_i: number
  class_ii: number
  class_iii: number
}

export interface RecallsSection {
  total_count: number
  class_counts: RecallClassCounts
  status_counts: Record<string, number>
  recent_recalls: Array<{
    recall_number?: string
    date?: string
    class?: string
    status?: string
    reason?: string
    product?: string
  }>
}

export interface ClearancesSection {
  total_count: number
  top_applicants: Array<{ name: string; count: number }>
  recent_clearances: Array<{
    k_number?: string
    date?: string
    device_name?: string
    applicant?: string
    decision?: string
  }>
}

export interface MRISafetyCounts {
  mr_safe: number
  mr_conditional: number
  mr_unsafe: number
  not_specified: number
}

export interface UDISection {
  total_count: number
  mri_safety: MRISafetyCounts
  sterile_count: number
  single_use_count: number
  sample_devices: Array<{
    brand_name?: string
    company_name?: string
    device_description?: string
  }>
}

export interface ManufacturerSummary {
  name: string
  device_count: number
}

export interface DeviceReportResponse {
  identifier: string
  identifier_type: IdentifierType
  product_code?: string
  product_code_name?: string
  classification?: ClassificationSection
  events?: EventsSection
  recalls?: RecallsSection
  clearances?: ClearancesSection
  udi?: UDISection
  top_manufacturers: ManufacturerSummary[]
}

// Manufacturer Report types
export interface CompanyInfoSection {
  name: string
  name_variations: string[]
  total_device_count: number
}

export interface LocationRecord {
  name: string
  city?: string
  state?: string
  country: string
  address?: string
}

export interface LocationsSection {
  total_count: number
  countries: Record<string, number>
  us_states: Record<string, number>
  locations: LocationRecord[]
}

export interface ProductCodeSummary {
  code: string
  name: string
  device_count: number
}

export interface PortfolioSection {
  total_product_codes: number
  product_codes: ProductCodeSummary[]
}

export interface RegulatorySection {
  total_510k: number
  total_pma: number
  recent_510k: Array<{
    k_number?: string
    date?: string
    device_name?: string
    decision?: string
  }>
  recent_pma: Array<{
    pma_number?: string
    date?: string
    trade_name?: string
    decision?: string
  }>
}

export interface ManufacturerReportResponse {
  identifier: string
  identifier_type: IdentifierType
  company_info?: CompanyInfoSection
  locations?: LocationsSection
  portfolio?: PortfolioSection
  events?: EventsSection
  recalls?: RecallsSection
  regulatory?: RegulatorySection
}

export interface SummaryResponse {
  summary: string
}

export interface FollowupResponse {
  answer: string
}

export interface UsageLimitError {
  error: 'usage_limit_exceeded'
  request_count: number
  request_limit: number
  message: string
  contact: string
}

export function isUsageLimitError(error: unknown): error is UsageLimitError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'error' in error &&
    (error as UsageLimitError).error === 'usage_limit_exceeded'
  )
}

export const apiClient = new APIClient()
