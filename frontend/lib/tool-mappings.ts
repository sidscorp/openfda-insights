export interface DataSourceInfo {
  name: string
  endpoint: string
  icon: string
}

export const TOOL_DATA_SOURCES: Record<string, DataSourceInfo> = {
  resolve_device: {
    name: 'GUDID Device Database',
    endpoint: 'GUDID/AccessGUDID',
    icon: '🔍',
  },
  resolve_manufacturer: {
    name: 'GUDID Manufacturer Database',
    endpoint: 'GUDID/AccessGUDID',
    icon: '🏭',
  },
  search_events: {
    name: 'OpenFDA Adverse Events (MAUDE)',
    endpoint: 'device/event.json',
    icon: '⚠️',
  },
  search_recalls: {
    name: 'OpenFDA Device Recalls',
    endpoint: 'device/enforcement.json',
    icon: '🔄',
  },
  search_510k: {
    name: 'OpenFDA 510(k) Clearances',
    endpoint: 'device/510k.json',
    icon: '✅',
  },
  search_pma: {
    name: 'OpenFDA PMA Approvals',
    endpoint: 'device/pma.json',
    icon: '🏥',
  },
  search_classifications: {
    name: 'OpenFDA Device Classifications',
    endpoint: 'device/classification.json',
    icon: '📋',
  },
  search_udi: {
    name: 'OpenFDA UDI Database',
    endpoint: 'device/udi.json',
    icon: '🏷️',
  },
  search_registrations: {
    name: 'OpenFDA Registration/Listing',
    endpoint: 'device/registrationlisting.json',
    icon: '📝',
  },
  resolve_location: {
    name: 'Location Resolver',
    endpoint: 'device/registrationlisting.json',
    icon: '📍',
  },
  aggregate_registrations: {
    name: 'Registration Aggregations',
    endpoint: 'device/registrationlisting.json',
    icon: '📊',
  },
}

export function getDataSourceInfo(toolName: string): DataSourceInfo {
  return (
    TOOL_DATA_SOURCES[toolName] || {
      name: toolName.replace(/_/g, ' '),
      endpoint: 'unknown',
      icon: '🔧',
    }
  )
}

export function formatArgs(args: Record<string, unknown>): string {
  const relevantArgs: string[] = []

  if (args.query) relevantArgs.push(`query: "${args.query}"`)
  if (args.product_codes && Array.isArray(args.product_codes)) {
    relevantArgs.push(`codes: [${args.product_codes.join(', ')}]`)
  }
  if (args.country) relevantArgs.push(`country: ${args.country}`)
  if (args.date_from || args.date_to) {
    const dateRange = [args.date_from, args.date_to].filter(Boolean).join(' - ')
    relevantArgs.push(`date: ${dateRange}`)
  }
  if (args.limit) relevantArgs.push(`limit: ${args.limit}`)
  if (args.manufacturer) relevantArgs.push(`manufacturer: "${args.manufacturer}"`)
  if (args.applicant) relevantArgs.push(`applicant: "${args.applicant}"`)

  return relevantArgs.join(', ') || 'No parameters'
}

export function parseResultSummary(toolName: string, content: string): string {
  const foundMatch = content.match(/Found (\d+)/i)
  if (foundMatch) {
    return `${foundMatch[1]} records found`
  }

  const totalMatch = content.match(/Total:?\s*(\d+)/i)
  if (totalMatch) {
    return `${totalMatch[1]} records found`
  }

  const countMatch = content.match(/(\d+)\s+(?:results?|records?|events?|recalls?|clearances?)/i)
  if (countMatch) {
    return `${countMatch[1]} records found`
  }

  if (content.includes('No ') && content.includes('found')) {
    return '0 records found'
  }

  if (content.includes('resolved') || content.includes('Resolved')) {
    const codeMatch = content.match(/(\d+)\s+product\s+codes?/i)
    if (codeMatch) {
      return `${codeMatch[1]} codes resolved`
    }
    return 'Query resolved'
  }

  return 'Query complete'
}
