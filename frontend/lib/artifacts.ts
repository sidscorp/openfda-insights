export interface ColumnConfig {
  key: string
  label: string
  width?: string
  truncate?: number
  sortable?: boolean
  formatter?: 'date' | 'number' | 'tag' | 'link'
  tag_color_map?: Record<string, string>
}

export interface NestedTableConfig {
  data_key: string
  columns: ColumnConfig[]
}

export interface DisplayHints {
  render_type: 'table' | 'summary_cards' | 'key_value'
  title?: string
  columns?: ColumnConfig[]
  summary_fields?: string[]
  default_sort?: string
  expandable?: boolean
  max_rows?: number
  nested_table?: NestedTableConfig
}

export interface DataArtifact {
  id: string
  type: ArtifactType
  tool_name: string
  data: Record<string, unknown>
  display_hints?: DisplayHints
  total_count?: number
  records_returned?: number
}

export type ArtifactType =
  | 'resolved_entities'
  | 'device_list'
  | 'manufacturers_list'
  | 'product_codes_list'
  | 'location_context'
  | 'recall_search_result'
  | 'event_search_result'
  | 'clearance_search_result'
  | 'classification_search_result'
  | 'udi_search_result'
  | 'registration_search_result'
  | 'pma_search_result'
  | 'aggregated_registrations'

export interface AggregationCount {
  term: string
  count: number
}

export interface RecallRecord {
  recall_number: string
  recalling_firm: string
  product_description: string
  reason_for_recall: string
  classification: string
  status: string
  recall_initiation_date: string
}

export interface RecallSearchResult {
  query: string
  total_found: number
  records: RecallRecord[]
  aggregations?: Record<string, AggregationCount[]>
}

export interface AdverseEventRecord {
  mdr_report_key?: string
  event_type: string
  date_received: string
  brand_name?: string
  manufacturer_name?: string
  product_code?: string
  event_description?: string
}

export interface EventSearchResult {
  query: string
  total_found: number
  records: AdverseEventRecord[]
  aggregations?: Record<string, AggregationCount[]>
}

export interface ProductCodeInfo {
  code: string
  name: string
  device_count: number
  device_class?: string
}

export interface DeviceListRecord {
  brand_name: string
  company_name: string
  version_model_number?: string
  primary_di?: string
  device_description?: string
  product_codes?: string[]
}

export interface DeviceListResult {
  query: string
  product_code?: string
  product_code_name?: string
  device_class?: string
  total_found: number
  records: DeviceListRecord[]
}

export interface ManufacturerInfo {
  name: string
  device_count: number
  variations?: string[]
  top_product_codes?: ProductCodeInfo[]
}

export interface ResolvedEntities {
  query: string
  total_devices_matched: number
  product_codes: ProductCodeInfo[]
  manufacturers?: ManufacturerInfo[]
}

export interface Clearance510kRecord {
  k_number: string
  device_name: string
  applicant: string
  product_code: string
  decision_date: string
  decision_description: string
}

export interface Clearance510kSearchResult {
  query: string
  total_found: number
  records: Clearance510kRecord[]
  aggregations?: Record<string, AggregationCount[]>
}

export interface PMARecord {
  pma_number: string
  trade_name?: string
  generic_name?: string
  applicant: string
  decision_date: string
  decision_code?: string
  advisory_committee?: string
}

export interface PMASearchResult {
  query: string
  total_found: number
  records: PMARecord[]
  aggregations?: Record<string, AggregationCount[]>
}

export interface ClassificationRecord {
  product_code: string
  device_name: string
  device_class: string
  regulation_number?: string
  medical_specialty?: string
}

export interface ClassificationSearchResult {
  query: string
  total_found: number
  records: ClassificationRecord[]
  aggregations?: Record<string, AggregationCount[]>
}

export interface UDIRecord {
  brand_name?: string
  company_name?: string
  version_model_number?: string
  primary_di?: string
  mri_safety?: string
  device_description?: string
}

export interface UDISearchResult {
  query: string
  total_found: number
  records: UDIRecord[]
  aggregations?: Record<string, AggregationCount[]>
}

export interface RegistrationRecord {
  registration_number?: string
  name: string
  city?: string
  state_code?: string
  country_code: string
  proprietary_names?: string[]
}

export interface RegistrationSearchResult {
  query: string
  total_found: number
  records: RegistrationRecord[]
  aggregations?: Record<string, AggregationCount[]>
}

export interface LocationContext {
  location_type: string
  location_name: string
  country_codes: string[]
  state_code?: string
  total_establishments: number
  top_manufacturers?: string[]
}

export interface StructuredData {
  recalls?: RecallSearchResult
  devices?: ResolvedEntities
  events?: EventSearchResult
  clearances?: Clearance510kSearchResult
  pma_approvals?: PMASearchResult
  classifications?: ClassificationSearchResult
  udi?: UDISearchResult
  registrations?: RegistrationSearchResult
  location?: LocationContext
  manufacturers?: ManufacturerInfo[]
  registration_aggregations?: Record<string, unknown>
  _artifacts?: DataArtifact[]
}
