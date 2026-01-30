'use client'

import React, { useMemo, useState } from 'react'
import {
  Box,
  Button,
  Collapse,
  HStack,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  Tag,
  VStack,
  useColorModeValue,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
} from '@chakra-ui/react'
import { ChevronDownIcon, ChevronUpIcon, ChevronRightIcon } from '@chakra-ui/icons'
import type { DataArtifact, ColumnConfig, DisplayHints, NestedTableConfig } from '@/lib/artifacts'

interface ArtifactRendererProps {
  artifact: DataArtifact
}

function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  return path.split('.').reduce((acc, part) => {
    if (acc && typeof acc === 'object') {
      return (acc as Record<string, unknown>)[part]
    }
    return undefined
  }, obj as unknown)
}

function formatValue(
  value: unknown,
  formatter?: string,
  tagColorMap?: Record<string, string>
): React.ReactNode {
  if (value == null) return 'N/A'

  const strValue = String(value)

  switch (formatter) {
    case 'date':
      if (strValue.length === 8 && /^\d{8}$/.test(strValue)) {
        return `${strValue.slice(0, 4)}-${strValue.slice(4, 6)}-${strValue.slice(6, 8)}`
      }
      return strValue
    case 'number':
      const num = Number(value)
      return isNaN(num) ? strValue : num.toLocaleString()
    case 'tag':
      const colorScheme = tagColorMap?.[strValue] || 'gray'
      return (
        <Tag size="sm" colorScheme={colorScheme}>
          {strValue}
        </Tag>
      )
    default:
      return strValue
  }
}

function DynamicTable({
  data,
  hints,
}: {
  data: Record<string, unknown>
  hints: DisplayHints
}) {
  const borderColor = useColorModeValue('gray.200', 'gray.600')
  const headerBg = useColorModeValue('gray.50', 'gray.700')

  // Handle different data structures: records array, product_codes array, or the data itself as array
  let records: Record<string, unknown>[] = []
  if (Array.isArray(data)) {
    records = data
  } else if (data.records && Array.isArray(data.records)) {
    records = data.records
  } else if (data.product_codes && Array.isArray(data.product_codes)) {
    records = data.product_codes
  }
  const columns = hints.columns || []
  const maxRows = hints.max_rows || 20

  const [showAll, setShowAll] = useState(false)
  const displayRecords = showAll ? records : records.slice(0, maxRows)

  if (records.length === 0) {
    return <Text fontSize="sm" color="gray.500">No records to display</Text>
  }

  return (
    <Box>
      <Box overflowX="auto">
        <Table size="sm" variant="simple">
          <Thead bg={headerBg}>
            <Tr>
              {columns.map((col) => (
                <Th key={col.key} borderColor={borderColor} width={col.width}>
                  {col.label}
                </Th>
              ))}
            </Tr>
          </Thead>
          <Tbody>
            {displayRecords.map((record, idx) => (
              <Tr key={idx}>
                {columns.map((col) => {
                  let value = getNestedValue(record, col.key)
                  const displayValue =
                    col.truncate &&
                    typeof value === 'string' &&
                    value.length > col.truncate
                      ? value.slice(0, col.truncate) + '...'
                      : value
                  return (
                    <Td
                      key={col.key}
                      borderColor={borderColor}
                      maxW={col.width}
                      isTruncated
                      title={typeof value === 'string' ? value : undefined}
                    >
                      {formatValue(displayValue, col.formatter, col.tag_color_map)}
                    </Td>
                  )
                })}
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Box>
      {records.length > maxRows && (
        <Button
          size="sm"
          variant="ghost"
          mt={2}
          onClick={() => setShowAll(!showAll)}
        >
          {showAll ? 'Show less' : `Show all ${records.length} records`}
        </Button>
      )}
    </Box>
  )
}

function NestedProductCodesTable({
  productCodes,
  columns,
  borderColor,
}: {
  productCodes: Record<string, unknown>[]
  columns?: ColumnConfig[]
  borderColor: string
}) {
  const nestedHeaderBg = useColorModeValue('gray.100', 'gray.600')

  if (!productCodes || productCodes.length === 0) {
    return <Text fontSize="xs" color="gray.500" ml={6}>No product codes available</Text>
  }

  const defaultColumns: ColumnConfig[] = [
    { key: 'code', label: 'Code', width: '80px', formatter: 'tag' },
    { key: 'name', label: 'Device Category' },
    { key: 'device_class', label: 'Class', width: '60px', formatter: 'tag', tag_color_map: { '1': 'green', '2': 'yellow', '3': 'red' } },
    { key: 'device_count', label: 'Devices', width: '100px', formatter: 'number' },
  ]

  const cols = columns || defaultColumns

  return (
    <Box ml={6} mr={2} mb={2}>
      <Table size="xs" variant="simple">
        <Thead bg={nestedHeaderBg}>
          <Tr>
            {cols.map((col) => (
              <Th key={col.key} borderColor={borderColor} fontSize="xs" py={1} width={col.width}>
                {col.label}
              </Th>
            ))}
          </Tr>
        </Thead>
        <Tbody>
          {productCodes.map((pc, idx) => (
            <Tr key={idx}>
              {cols.map((col) => {
                const value = getNestedValue(pc, col.key)
                return (
                  <Td key={col.key} borderColor={borderColor} fontSize="xs" py={1}>
                    {formatValue(value, col.formatter, col.tag_color_map)}
                  </Td>
                )
              })}
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  )
}

function ManufacturerTable({
  data,
  hints,
}: {
  data: Record<string, unknown>
  hints: DisplayHints
}) {
  const borderColor = useColorModeValue('gray.200', 'gray.600')
  const headerBg = useColorModeValue('gray.50', 'gray.700')
  const expandedBg = useColorModeValue('gray.50', 'gray.750')

  const items = Array.isArray(data) ? data : []
  const maxRows = hints.max_rows || 20
  const nestedConfig = hints.nested_table

  const [showAll, setShowAll] = useState(false)
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set())
  const displayItems = showAll ? items : items.slice(0, maxRows)

  const toggleRow = (idx: number) => {
    const newExpanded = new Set(expandedRows)
    if (newExpanded.has(idx)) {
      newExpanded.delete(idx)
    } else {
      newExpanded.add(idx)
    }
    setExpandedRows(newExpanded)
  }

  if (items.length === 0) {
    return <Text fontSize="sm" color="gray.500">No manufacturers to display</Text>
  }

  const hasNestedData = nestedConfig && items.some(
    (item) => {
      const mfr = item as Record<string, unknown>
      const nested = mfr[nestedConfig.data_key]
      return Array.isArray(nested) && nested.length > 0
    }
  )

  return (
    <Box>
      <Box overflowX="auto">
        <Table size="sm" variant="simple">
          <Thead bg={headerBg}>
            <Tr>
              {hasNestedData && <Th borderColor={borderColor} width="40px"></Th>}
              <Th borderColor={borderColor}>Manufacturer</Th>
              <Th borderColor={borderColor} isNumeric width="120px">Device Count</Th>
            </Tr>
          </Thead>
          <Tbody>
            {displayItems.map((item, idx) => {
              const mfr = item as Record<string, unknown>
              const isExpanded = expandedRows.has(idx)
              const nestedData = nestedConfig
                ? (mfr[nestedConfig.data_key] as Record<string, unknown>[] | undefined)
                : undefined
              const hasNested = nestedData && nestedData.length > 0

              return (
                <React.Fragment key={idx}>
                  <Tr
                    cursor={hasNested ? 'pointer' : 'default'}
                    onClick={() => hasNested && toggleRow(idx)}
                    _hover={hasNested ? { bg: expandedBg } : undefined}
                  >
                    {hasNestedData && (
                      <Td borderColor={borderColor} py={1}>
                        {hasNested && (
                          <Box
                            as="span"
                            transform={isExpanded ? 'rotate(90deg)' : 'rotate(0deg)'}
                            transition="transform 0.2s"
                            display="inline-block"
                          >
                            <ChevronRightIcon />
                          </Box>
                        )}
                      </Td>
                    )}
                    <Td borderColor={borderColor}>{String(mfr.name || 'Unknown')}</Td>
                    <Td borderColor={borderColor} isNumeric>
                      {Number(mfr.device_count || 0).toLocaleString()}
                    </Td>
                  </Tr>
                  {isExpanded && hasNested && (
                    <Tr>
                      <Td colSpan={hasNestedData ? 3 : 2} borderColor={borderColor} bg={expandedBg} py={2}>
                        <NestedProductCodesTable
                          productCodes={nestedData}
                          columns={nestedConfig?.columns}
                          borderColor={borderColor}
                        />
                      </Td>
                    </Tr>
                  )}
                </React.Fragment>
              )
            })}
          </Tbody>
        </Table>
      </Box>
      {items.length > maxRows && (
        <Button
          size="sm"
          variant="ghost"
          mt={2}
          onClick={() => setShowAll(!showAll)}
        >
          {showAll ? 'Show less' : `Show all ${items.length} manufacturers`}
        </Button>
      )}
    </Box>
  )
}

function SummaryCards({
  data,
  hints,
}: {
  data: Record<string, unknown>
  hints: DisplayHints
}) {
  const fields =
    hints.summary_fields ||
    Object.keys(data).filter((k) => typeof data[k] !== 'object' || data[k] === null)

  const formatLabel = (field: string) =>
    field
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase())

  return (
    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
      {fields.map((field) => {
        const value = data[field]
        const displayValue =
          typeof value === 'number'
            ? value.toLocaleString()
            : Array.isArray(value)
            ? value.slice(0, 3).join(', ') + (value.length > 3 ? '...' : '')
            : String(value ?? 'N/A')
        return (
          <Stat key={field} p={3} borderWidth="1px" borderRadius="md">
            <StatLabel fontSize="xs" color="gray.500">
              {formatLabel(field)}
            </StatLabel>
            <StatNumber fontSize="md">{displayValue}</StatNumber>
          </Stat>
        )
      })}
    </SimpleGrid>
  )
}

function KeyValueDisplay({ data }: { data: Record<string, unknown> }) {
  const borderColor = useColorModeValue('gray.200', 'gray.600')

  const entries = Object.entries(data).filter(
    ([, v]) => v != null && typeof v !== 'object'
  )

  return (
    <VStack align="stretch" spacing={1}>
      {entries.map(([key, value]) => (
        <HStack
          key={key}
          py={1}
          borderBottomWidth="1px"
          borderColor={borderColor}
        >
          <Text fontWeight="semibold" minW="150px" fontSize="sm">
            {key.replace(/_/g, ' ')}:
          </Text>
          <Text fontSize="sm">{String(value)}</Text>
        </HStack>
      ))}
    </VStack>
  )
}

export function ArtifactRenderer({ artifact }: ArtifactRendererProps) {
  const [isOpen, setIsOpen] = useState(false)
  const bgColor = useColorModeValue('gray.50', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.600')

  const hints: DisplayHints = artifact.display_hints || { render_type: 'table' }
  const data = artifact.data as Record<string, unknown>

  const summary = useMemo(() => {
    const parts: string[] = []
    if (artifact.total_count) parts.push(`${artifact.total_count.toLocaleString()} total`)
    if (artifact.records_returned && artifact.records_returned !== artifact.total_count) {
      parts.push(`showing ${artifact.records_returned}`)
    }
    return parts.join(', ') || ''
  }, [artifact])

  const title = hints.title || artifact.type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

  const renderContent = () => {
    if (artifact.type === 'manufacturers_list' && Array.isArray(data)) {
      return <ManufacturerTable data={data} hints={hints} />
    }

    switch (hints.render_type) {
      case 'table':
        return <DynamicTable data={data} hints={hints} />
      case 'summary_cards':
        return <SummaryCards data={data} hints={hints} />
      case 'key_value':
        return <KeyValueDisplay data={data} />
      default:
        return <DynamicTable data={data} hints={hints} />
    }
  }

  return (
    <Box
      mt={3}
      borderWidth="1px"
      borderColor={borderColor}
      borderRadius="md"
      overflow="hidden"
    >
      <Button
        w="100%"
        variant="ghost"
        justifyContent="space-between"
        bg={bgColor}
        borderRadius={0}
        py={2}
        px={4}
        onClick={() => setIsOpen(!isOpen)}
        rightIcon={isOpen ? <ChevronUpIcon /> : <ChevronDownIcon />}
      >
        <HStack spacing={2}>
          <Text fontWeight="medium" fontSize="sm">
            {title}
          </Text>
          {summary && (
            <Text fontSize="sm" color="gray.500">
              ({summary})
            </Text>
          )}
        </HStack>
      </Button>
      <Collapse in={isOpen} animateOpacity>
        <Box p={4} maxH="400px" overflowY="auto">
          {renderContent()}
        </Box>
      </Collapse>
    </Box>
  )
}
