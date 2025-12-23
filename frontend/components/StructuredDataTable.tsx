'use client'

import { useState } from 'react'
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
} from '@chakra-ui/react'
import { ChevronDownIcon, ChevronUpIcon } from '@chakra-ui/icons'

interface RecallRecord {
  recall_number: string
  recalling_firm: string
  product_description: string
  reason_for_recall: string
  classification: string
  status: string
  recall_initiation_date: string
}

interface DeviceRecord {
  brand_name: string
  company_name: string
  device_description?: string
  product_codes: string[]
}

interface ProductCodeInfo {
  code: string
  name: string
  device_count: number
}

interface ManufacturerInfo {
  name: string
  device_count: number
}

interface StructuredData {
  recalls?: {
    query: string
    total_found: number
    records: RecallRecord[]
    class_counts?: Record<string, number>
    status_counts?: Record<string, number>
  }
  devices?: {
    query: string
    total_devices_matched: number
    product_codes: ProductCodeInfo[]
    manufacturers?: ManufacturerInfo[]
    devices?: DeviceRecord[]
  }
  events?: {
    query: string
    total_found: number
    records: Array<{
      event_type: string
      date_received: string
      brand_name?: string
      manufacturer_name?: string
    }>
  }
}

interface StructuredDataTableProps {
  data: StructuredData
}

function RecallsTable({ recalls }: { recalls: NonNullable<StructuredData['recalls']> }) {
  const borderColor = useColorModeValue('gray.200', 'gray.600')
  const headerBg = useColorModeValue('gray.50', 'gray.700')

  const getClassColor = (cls: string) => {
    if (cls.includes('I') && !cls.includes('II')) return 'red'
    if (cls.includes('II') && !cls.includes('III')) return 'orange'
    if (cls.includes('III')) return 'yellow'
    return 'gray'
  }

  const getStatusColor = (status: string) => {
    if (status.toLowerCase().includes('ongoing')) return 'red'
    if (status.toLowerCase().includes('terminated')) return 'green'
    return 'gray'
  }

  return (
    <Box overflowX="auto">
      <Table size="sm" variant="simple">
        <Thead bg={headerBg}>
          <Tr>
            <Th borderColor={borderColor}>Date</Th>
            <Th borderColor={borderColor}>Class</Th>
            <Th borderColor={borderColor}>Status</Th>
            <Th borderColor={borderColor}>Firm</Th>
            <Th borderColor={borderColor}>Product</Th>
            <Th borderColor={borderColor}>Reason</Th>
          </Tr>
        </Thead>
        <Tbody>
          {recalls.records.map((record, idx) => (
            <Tr key={record.recall_number || idx}>
              <Td borderColor={borderColor} whiteSpace="nowrap">
                {record.recall_initiation_date || 'N/A'}
              </Td>
              <Td borderColor={borderColor}>
                <Tag size="sm" colorScheme={getClassColor(record.classification)}>
                  {record.classification || 'N/A'}
                </Tag>
              </Td>
              <Td borderColor={borderColor}>
                <Tag size="sm" colorScheme={getStatusColor(record.status)}>
                  {record.status}
                </Tag>
              </Td>
              <Td borderColor={borderColor} maxW="200px" isTruncated title={record.recalling_firm}>
                {record.recalling_firm}
              </Td>
              <Td borderColor={borderColor} maxW="250px" isTruncated title={record.product_description}>
                {record.product_description}
              </Td>
              <Td borderColor={borderColor} maxW="300px" isTruncated title={record.reason_for_recall}>
                {record.reason_for_recall}
              </Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  )
}

function DevicesTable({ devices }: { devices: NonNullable<StructuredData['devices']> }) {
  const borderColor = useColorModeValue('gray.200', 'gray.600')
  const headerBg = useColorModeValue('gray.50', 'gray.700')

  const hasProductCodes = devices.product_codes && devices.product_codes.length > 0
  const hasManufacturers = devices.manufacturers && devices.manufacturers.length > 0

  return (
    <VStack spacing={4} align="stretch">
      {hasProductCodes && (
        <Box overflowX="auto">
          <Text fontWeight="semibold" fontSize="xs" color="gray.500" mb={1}>Product Codes</Text>
          <Table size="sm" variant="simple">
            <Thead bg={headerBg}>
              <Tr>
                <Th borderColor={borderColor}>Code</Th>
                <Th borderColor={borderColor}>Name</Th>
                <Th borderColor={borderColor} isNumeric>Device Count</Th>
              </Tr>
            </Thead>
            <Tbody>
              {devices.product_codes.map((pc, idx) => (
                <Tr key={pc.code || idx}>
                  <Td borderColor={borderColor}>
                    <Tag size="sm" colorScheme="blue">{pc.code}</Tag>
                  </Td>
                  <Td borderColor={borderColor}>{pc.name}</Td>
                  <Td borderColor={borderColor} isNumeric>{pc.device_count.toLocaleString()}</Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>
      )}
      {hasManufacturers && (
        <Box overflowX="auto">
          <Text fontWeight="semibold" fontSize="xs" color="gray.500" mb={1}>Top Manufacturers</Text>
          <Table size="sm" variant="simple">
            <Thead bg={headerBg}>
              <Tr>
                <Th borderColor={borderColor}>Manufacturer</Th>
                <Th borderColor={borderColor} isNumeric>Device Count</Th>
              </Tr>
            </Thead>
            <Tbody>
              {devices.manufacturers?.map((mfr, idx) => (
                <Tr key={mfr.name || idx}>
                  <Td borderColor={borderColor}>{mfr.name}</Td>
                  <Td borderColor={borderColor} isNumeric>{mfr.device_count.toLocaleString()}</Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>
      )}
    </VStack>
  )
}

function EventsTable({ events }: { events: NonNullable<StructuredData['events']> }) {
  const borderColor = useColorModeValue('gray.200', 'gray.600')
  const headerBg = useColorModeValue('gray.50', 'gray.700')

  const getEventColor = (eventType: string) => {
    if (eventType.toLowerCase().includes('death')) return 'red'
    if (eventType.toLowerCase().includes('injury')) return 'orange'
    if (eventType.toLowerCase().includes('malfunction')) return 'yellow'
    return 'gray'
  }

  return (
    <Box overflowX="auto">
      <Table size="sm" variant="simple">
        <Thead bg={headerBg}>
          <Tr>
            <Th borderColor={borderColor}>Date</Th>
            <Th borderColor={borderColor}>Type</Th>
            <Th borderColor={borderColor}>Brand</Th>
            <Th borderColor={borderColor}>Manufacturer</Th>
          </Tr>
        </Thead>
        <Tbody>
          {events.records.map((record, idx) => (
            <Tr key={idx}>
              <Td borderColor={borderColor} whiteSpace="nowrap">
                {record.date_received}
              </Td>
              <Td borderColor={borderColor}>
                <Tag size="sm" colorScheme={getEventColor(record.event_type)}>
                  {record.event_type}
                </Tag>
              </Td>
              <Td borderColor={borderColor} maxW="200px" isTruncated>
                {record.brand_name || 'N/A'}
              </Td>
              <Td borderColor={borderColor} maxW="200px" isTruncated>
                {record.manufacturer_name || 'N/A'}
              </Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  )
}

export function StructuredDataTable({ data }: StructuredDataTableProps) {
  const [isOpen, setIsOpen] = useState(false)
  const bgColor = useColorModeValue('gray.50', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.600')

  const hasRecalls = data.recalls && data.recalls.records.length > 0
  const hasDevices = data.devices && (
    (data.devices.product_codes && data.devices.product_codes.length > 0) ||
    (data.devices.manufacturers && data.devices.manufacturers.length > 0)
  )
  const hasEvents = data.events && data.events.records.length > 0

  if (!hasRecalls && !hasDevices && !hasEvents) {
    return null
  }

  const getSummary = () => {
    const parts: string[] = []
    if (hasRecalls) {
      parts.push(`${data.recalls!.total_found} recalls`)
    }
    if (hasDevices) {
      const deviceParts: string[] = []
      if (data.devices!.product_codes?.length) {
        deviceParts.push(`${data.devices!.product_codes.length} codes`)
      }
      if (data.devices!.manufacturers?.length) {
        deviceParts.push(`${data.devices!.manufacturers.length} manufacturers`)
      }
      parts.push(deviceParts.join(', '))
    }
    if (hasEvents) {
      parts.push(`${data.events!.total_found} events`)
    }
    return parts.join(' | ')
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
          <Text fontWeight="medium" fontSize="sm">Data Table</Text>
          <Text fontSize="sm" color="gray.500">({getSummary()})</Text>
        </HStack>
      </Button>
      <Collapse in={isOpen} animateOpacity>
        <Box p={4} maxH="400px" overflowY="auto">
          <VStack spacing={4} align="stretch">
            {hasRecalls && (
              <Box>
                <Text fontWeight="bold" mb={2} fontSize="sm">
                  Recalls ({data.recalls!.total_found} total, showing {data.recalls!.records.length})
                </Text>
                <RecallsTable recalls={data.recalls!} />
              </Box>
            )}
            {hasDevices && (
              <Box>
                <Text fontWeight="bold" mb={2} fontSize="sm">
                  Device Information ({data.devices!.total_devices_matched.toLocaleString()} devices)
                </Text>
                <DevicesTable devices={data.devices!} />
              </Box>
            )}
            {hasEvents && (
              <Box>
                <Text fontWeight="bold" mb={2} fontSize="sm">
                  Adverse Events ({data.events!.total_found} total, showing {data.events!.records.length})
                </Text>
                <EventsTable events={data.events!} />
              </Box>
            )}
          </VStack>
        </Box>
      </Collapse>
    </Box>
  )
}
