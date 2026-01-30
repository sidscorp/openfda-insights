'use client'

import { useState, useEffect } from 'react'
import {
  Box,
  VStack,
  HStack,
  Text,
  Badge,
  SimpleGrid,
  Card,
  CardHeader,
  CardBody,
  Heading,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Button,
  Progress,
  Wrap,
  WrapItem,
  Tag,
  Link,
} from '@chakra-ui/react'
import { ExternalLinkIcon } from '@chakra-ui/icons'
import { ArrowBackIcon } from '@chakra-ui/icons'
import { ManufacturerReportResponse, apiClient } from '../../lib/api'
import { AISummaryPanel } from './AISummaryPanel'

interface ManufacturerReportViewProps {
  report: ManufacturerReportResponse
  onBack: () => void
  onDeviceClick: (productCode: string) => void
}

function formatNumber(n?: number): string {
  if (n === undefined || n === null) return '0'
  return n.toLocaleString()
}

export function ManufacturerReportView({
  report,
  onBack,
  onDeviceClick,
}: ManufacturerReportViewProps) {
  const [summary, setSummary] = useState<string | null>(null)
  const [isLoadingSummary, setIsLoadingSummary] = useState(false)
  const [summaryRequested, setSummaryRequested] = useState(false)
  const [showAllProducts, setShowAllProducts] = useState(false)
  const [showAll510k, setShowAll510k] = useState(false)
  const [showAllPMA, setShowAllPMA] = useState(false)

  const handleGenerateSummary = async () => {
    if (summaryRequested) return
    setSummaryRequested(true)
    setIsLoadingSummary(true)
    try {
      const result = await apiClient.generateLookupSummary('manufacturer', report.identifier, report)
      setSummary(result.summary)
    } catch (error) {
      console.error('Failed to generate summary:', error)
      setSummary(null)
    } finally {
      setIsLoadingSummary(false)
    }
  }

  const handleFollowup = async (question: string): Promise<string> => {
    const result = await apiClient.answerFollowup(
      'manufacturer',
      report.identifier,
      summary || '',
      question
    )
    return result.answer
  }

  const companyInfo = report.company_info
  const locations = report.locations
  const portfolio = report.portfolio
  const events = report.events
  const recalls = report.recalls
  const regulatory = report.regulatory

  const totalEvents = events?.total_count || 0
  const eventCounts = events?.event_type_counts || { death: 0, injury: 0, malfunction: 0, other: 0 }

  return (
    <VStack align="stretch" spacing={6} w="100%">
      {/* Header */}
      <HStack justify="space-between" align="start" wrap="wrap" gap={4}>
        <HStack spacing={4}>
          <Button
            leftIcon={<ArrowBackIcon />}
            variant="ghost"
            size="sm"
            onClick={onBack}
          >
            Back
          </Button>
          <VStack align="start" spacing={1}>
            <Text fontSize="2xl" fontWeight="bold" color="brand.700" _dark={{ color: 'brand.200' }}>
              {companyInfo?.name || report.identifier}
            </Text>
            {companyInfo?.name_variations && companyInfo.name_variations.length > 0 && (
              <Text color="gray.500" fontSize="sm">
                Also: {companyInfo.name_variations.slice(0, 3).join(', ')}
                {companyInfo.name_variations.length > 3 && ` +${companyInfo.name_variations.length - 3} more`}
              </Text>
            )}
          </VStack>
        </HStack>
      </HStack>

      {/* AI Summary */}
      <AISummaryPanel
        summary={summary}
        isLoadingSummary={isLoadingSummary}
        onAskFollowup={handleFollowup}
        onGenerateSummary={handleGenerateSummary}
        summaryRequested={summaryRequested}
        entityType="manufacturer"
        identifier={report.identifier}
      />

      {/* Quick Stats */}
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
        <Card>
          <CardBody>
            <Stat>
              <StatLabel>Total Devices</StatLabel>
              <StatNumber>{formatNumber(companyInfo?.total_device_count)}</StatNumber>
              <StatHelpText>In UDI database</StatHelpText>
            </Stat>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <Stat>
              <StatLabel>Product Codes</StatLabel>
              <StatNumber>{formatNumber(portfolio?.total_product_codes)}</StatNumber>
              <StatHelpText>Device types</StatHelpText>
            </Stat>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <Stat>
              <StatLabel>Adverse Events</StatLabel>
              <StatNumber color={totalEvents > 1000 ? 'red.500' : 'gray.700'}>
                {formatNumber(totalEvents)}
              </StatNumber>
              <StatHelpText>Total reported</StatHelpText>
            </Stat>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <Stat>
              <StatLabel>Registrations</StatLabel>
              <StatNumber>{formatNumber(locations?.total_count)}</StatNumber>
              <StatHelpText>
                {locations?.countries ? Object.keys(locations.countries).length : 0} countries
              </StatHelpText>
            </Stat>
          </CardBody>
        </Card>
      </SimpleGrid>

      {/* Locations */}
      {locations && locations.total_count > 0 && (
        <Card>
          <CardHeader>
            <VStack align="start" spacing={1}>
              <HStack justify="space-between" w="100%">
                <Heading size="md">Establishment Registrations</Heading>
                <Badge colorScheme="blue" fontSize="sm">
                  {locations.total_count} registrations
                </Badge>
              </HStack>
              <Text fontSize="xs" color="gray.500">
                FDA establishment registrations where owner/operator name contains "{report.identifier}"
              </Text>
            </VStack>
          </CardHeader>
          <CardBody>
            <VStack align="stretch" spacing={4}>
              {/* Country Breakdown */}
              {locations.countries && Object.keys(locations.countries).length > 0 && (
                <Box>
                  <Text fontSize="sm" fontWeight="medium" color="gray.600" mb={2}>
                    By Country
                  </Text>
                  <Wrap spacing={2}>
                    {Object.entries(locations.countries)
                      .sort(([, a], [, b]) => b - a)
                      .slice(0, 10)
                      .map(([country, count]) => (
                        <WrapItem key={country}>
                          <Tag size="md" colorScheme="blue" variant="subtle">
                            {country}: {count}
                          </Tag>
                        </WrapItem>
                      ))}
                  </Wrap>
                </Box>
              )}

              {/* US States */}
              {locations.us_states && Object.keys(locations.us_states).length > 0 && (
                <Box>
                  <Text fontSize="sm" fontWeight="medium" color="gray.600" mb={2}>
                    US States
                  </Text>
                  <Wrap spacing={2}>
                    {Object.entries(locations.us_states)
                      .sort(([, a], [, b]) => b - a)
                      .slice(0, 10)
                      .map(([state, count]) => (
                        <WrapItem key={state}>
                          <Tag size="sm" colorScheme="gray" variant="subtle">
                            {state}: {count}
                          </Tag>
                        </WrapItem>
                      ))}
                  </Wrap>
                </Box>
              )}

              {/* Facility List */}
              {locations.locations && locations.locations.length > 0 && (
                <Box>
                  <Text fontSize="sm" fontWeight="medium" color="gray.600" mb={2}>
                    Facilities
                  </Text>
                  <Box overflowX="auto">
                    <Table size="sm" variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Name</Th>
                          <Th>City</Th>
                          <Th>State</Th>
                          <Th>Country</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {locations.locations.slice(0, 5).map((loc, idx) => (
                          <Tr key={idx}>
                            <Td>{loc.name}</Td>
                            <Td>{loc.city || 'N/A'}</Td>
                            <Td>{loc.state || 'N/A'}</Td>
                            <Td>{loc.country}</Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </Box>
                </Box>
              )}
            </VStack>
          </CardBody>
        </Card>
      )}

      {/* Product Portfolio */}
      {portfolio && portfolio.product_codes && portfolio.product_codes.length > 0 && (
        <Card>
          <CardHeader>
            <HStack justify="space-between">
              <Heading size="md">Product Portfolio</Heading>
              <Badge colorScheme="purple" fontSize="sm">
                {portfolio.total_product_codes} product codes
              </Badge>
            </HStack>
          </CardHeader>
          <CardBody>
            <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={3}>
              {(showAllProducts ? portfolio.product_codes : portfolio.product_codes.slice(0, 12)).map((pc, idx) => (
                <HStack
                  key={idx}
                  p={3}
                  bg="gray.50"
                  _dark={{ bg: 'gray.700' }}
                  borderRadius="md"
                  justify="space-between"
                  cursor="pointer"
                  _hover={{ bg: 'brand.50', _dark: { bg: 'brand.900' } }}
                  onClick={() => onDeviceClick(pc.code)}
                >
                  <VStack align="start" spacing={0}>
                    <HStack spacing={2}>
                      <Text fontWeight="bold" color="brand.600" _dark={{ color: 'brand.300' }}>
                        {pc.code}
                      </Text>
                      <Badge size="sm" colorScheme="gray">{pc.device_count} devices</Badge>
                    </HStack>
                    <Text fontSize="sm" color="gray.600" noOfLines={1}>
                      {pc.name}
                    </Text>
                  </VStack>
                </HStack>
              ))}
            </SimpleGrid>
            {portfolio.product_codes.length > 12 && (
              <Button
                mt={3}
                size="sm"
                variant="ghost"
                colorScheme="brand"
                onClick={() => setShowAllProducts(!showAllProducts)}
                w="100%"
              >
                {showAllProducts
                  ? 'Show less'
                  : `Show all ${portfolio.product_codes.length} product codes`}
              </Button>
            )}
          </CardBody>
        </Card>
      )}

      {/* Adverse Events */}
      {events && totalEvents > 0 && (
        <Card>
          <CardHeader>
            <HStack justify="space-between">
              <Heading size="md">Adverse Events</Heading>
              <Badge colorScheme="red" fontSize="sm">
                {formatNumber(totalEvents)} total
              </Badge>
            </HStack>
          </CardHeader>
          <CardBody>
            <VStack align="stretch" spacing={4}>
              {/* Event Type Breakdown */}
              <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
                <Box>
                  <HStack justify="space-between">
                    <Text fontSize="sm" color="gray.500">Deaths</Text>
                    <Text fontWeight="bold" color="red.600">{formatNumber(eventCounts.death)}</Text>
                  </HStack>
                  <Progress
                    value={totalEvents ? (eventCounts.death / totalEvents) * 100 : 0}
                    colorScheme="red"
                    size="sm"
                    mt={1}
                  />
                </Box>
                <Box>
                  <HStack justify="space-between">
                    <Text fontSize="sm" color="gray.500">Injuries</Text>
                    <Text fontWeight="bold" color="orange.500">{formatNumber(eventCounts.injury)}</Text>
                  </HStack>
                  <Progress
                    value={totalEvents ? (eventCounts.injury / totalEvents) * 100 : 0}
                    colorScheme="orange"
                    size="sm"
                    mt={1}
                  />
                </Box>
                <Box>
                  <HStack justify="space-between">
                    <Text fontSize="sm" color="gray.500">Malfunctions</Text>
                    <Text fontWeight="bold" color="yellow.600">{formatNumber(eventCounts.malfunction)}</Text>
                  </HStack>
                  <Progress
                    value={totalEvents ? (eventCounts.malfunction / totalEvents) * 100 : 0}
                    colorScheme="yellow"
                    size="sm"
                    mt={1}
                  />
                </Box>
                <Box>
                  <HStack justify="space-between">
                    <Text fontSize="sm" color="gray.500">Other</Text>
                    <Text fontWeight="bold" color="gray.600">{formatNumber(eventCounts.other)}</Text>
                  </HStack>
                  <Progress
                    value={totalEvents ? (eventCounts.other / totalEvents) * 100 : 0}
                    colorScheme="gray"
                    size="sm"
                    mt={1}
                  />
                </Box>
              </SimpleGrid>

              {/* Recent Events Table */}
              {events.recent_events && events.recent_events.length > 0 && (
                <Box>
                  <Text fontSize="sm" fontWeight="medium" color="gray.600" mb={2}>
                    Recent Events
                  </Text>
                  <Box overflowX="auto">
                    <Table size="sm" variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Date</Th>
                          <Th>Type</Th>
                          <Th>Device</Th>
                          <Th>Report #</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {events.recent_events.slice(0, 5).map((event, idx) => (
                          <Tr key={idx}>
                            <Td>{event.event_date || 'N/A'}</Td>
                            <Td>
                              <Badge
                                colorScheme={
                                  event.event_type === 'Death'
                                    ? 'red'
                                    : event.event_type === 'Injury'
                                    ? 'orange'
                                    : 'yellow'
                                }
                                size="sm"
                              >
                                {event.event_type || 'Unknown'}
                              </Badge>
                            </Td>
                            <Td maxW="200px" isTruncated>{event.device_name || 'N/A'}</Td>
                            <Td fontSize="xs" color="gray.500">{event.report_number || 'N/A'}</Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </Box>
                </Box>
              )}
            </VStack>
          </CardBody>
        </Card>
      )}

      {/* Recalls */}
      {recalls && recalls.total_count > 0 && (
        <Card>
          <CardHeader>
            <HStack justify="space-between">
              <Heading size="md">Recalls</Heading>
              <Badge colorScheme="orange" fontSize="sm">
                {formatNumber(recalls.total_count)} total
              </Badge>
            </HStack>
          </CardHeader>
          <CardBody>
            <VStack align="stretch" spacing={4}>
              {/* Class Breakdown */}
              <SimpleGrid columns={3} spacing={4}>
                <Box textAlign="center" p={3} bg="red.50" _dark={{ bg: 'red.900' }} borderRadius="md">
                  <Text fontSize="2xl" fontWeight="bold" color="red.600">
                    {recalls.class_counts.class_i}
                  </Text>
                  <Text fontSize="sm" color="gray.600">Class I</Text>
                </Box>
                <Box textAlign="center" p={3} bg="orange.50" _dark={{ bg: 'orange.900' }} borderRadius="md">
                  <Text fontSize="2xl" fontWeight="bold" color="orange.600">
                    {recalls.class_counts.class_ii}
                  </Text>
                  <Text fontSize="sm" color="gray.600">Class II</Text>
                </Box>
                <Box textAlign="center" p={3} bg="yellow.50" _dark={{ bg: 'yellow.900' }} borderRadius="md">
                  <Text fontSize="2xl" fontWeight="bold" color="yellow.600">
                    {recalls.class_counts.class_iii}
                  </Text>
                  <Text fontSize="sm" color="gray.600">Class III</Text>
                </Box>
              </SimpleGrid>

              {/* Recent Recalls */}
              {recalls.recent_recalls && recalls.recent_recalls.length > 0 && (
                <Box>
                  <Text fontSize="sm" fontWeight="medium" color="gray.600" mb={2}>
                    Recent Recalls
                  </Text>
                  <Box overflowX="auto">
                    <Table size="sm" variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Date</Th>
                          <Th>Class</Th>
                          <Th>Status</Th>
                          <Th>Reason</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {recalls.recent_recalls.slice(0, 5).map((recall, idx) => (
                          <Tr key={idx}>
                            <Td>{recall.date || 'N/A'}</Td>
                            <Td>
                              <Badge
                                colorScheme={
                                  recall.class === 'I' ? 'red' : recall.class === 'II' ? 'orange' : 'yellow'
                                }
                              >
                                {recall.class || '?'}
                              </Badge>
                            </Td>
                            <Td>{recall.status || 'N/A'}</Td>
                            <Td fontSize="sm" maxW="300px" isTruncated>
                              {recall.reason || 'N/A'}
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </Box>
                </Box>
              )}
            </VStack>
          </CardBody>
        </Card>
      )}

      {/* Regulatory History */}
      {regulatory && (regulatory.total_510k > 0 || regulatory.total_pma > 0) && (
        <Card>
          <CardHeader>
            <Heading size="md">Regulatory History</Heading>
          </CardHeader>
          <CardBody>
            <VStack align="stretch" spacing={4}>
              <SimpleGrid columns={2} spacing={4}>
                <Box textAlign="center" p={4} bg="green.50" _dark={{ bg: 'green.900' }} borderRadius="md">
                  <Text fontSize="3xl" fontWeight="bold" color="green.600">
                    {regulatory.total_510k}
                  </Text>
                  <Text fontSize="sm" color="gray.600">510(k) Clearances</Text>
                </Box>
                <Box textAlign="center" p={4} bg="purple.50" _dark={{ bg: 'purple.900' }} borderRadius="md">
                  <Text fontSize="3xl" fontWeight="bold" color="purple.600">
                    {regulatory.total_pma}
                  </Text>
                  <Text fontSize="sm" color="gray.600">PMA Approvals</Text>
                </Box>
              </SimpleGrid>

              {/* Recent 510(k) */}
              {regulatory.recent_510k && regulatory.recent_510k.length > 0 && (
                <Box>
                  <HStack justify="space-between" mb={2}>
                    <Text fontSize="sm" fontWeight="medium" color="gray.600">
                      {showAll510k ? 'All' : 'Recent'} 510(k) Clearances
                    </Text>
                    {regulatory.total_510k > 5 && (
                      <Button
                        size="xs"
                        variant="ghost"
                        colorScheme="green"
                        onClick={() => setShowAll510k(!showAll510k)}
                      >
                        {showAll510k ? 'Show less' : `View all ${regulatory.total_510k}`}
                      </Button>
                    )}
                  </HStack>
                  <Box overflowX="auto" maxH={showAll510k ? '400px' : 'auto'} overflowY={showAll510k ? 'auto' : 'visible'}>
                    <Table size="sm" variant="simple">
                      <Thead>
                        <Tr>
                          <Th>K Number</Th>
                          <Th>Date</Th>
                          <Th>Device</Th>
                          <Th>Decision</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {(showAll510k ? regulatory.recent_510k : regulatory.recent_510k.slice(0, 5)).map((k, idx) => (
                          <Tr key={idx}>
                            <Td fontFamily="mono" fontSize="sm">
                              {k.k_number ? (
                                <Link
                                  href={`https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=${k.k_number}`}
                                  isExternal
                                  color="green.600"
                                  _hover={{ textDecoration: 'underline' }}
                                >
                                  {k.k_number} <ExternalLinkIcon mx="2px" boxSize={3} />
                                </Link>
                              ) : 'N/A'}
                            </Td>
                            <Td>{k.date || 'N/A'}</Td>
                            <Td maxW="200px" isTruncated>{k.device_name || 'N/A'}</Td>
                            <Td>
                              <Badge colorScheme="green">{k.decision || 'N/A'}</Badge>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </Box>
                  {showAll510k && regulatory.total_510k > regulatory.recent_510k.length && (
                    <Text fontSize="xs" color="gray.500" mt={2} textAlign="center">
                      Showing {regulatory.recent_510k.length} of {regulatory.total_510k} clearances (API returns limited results)
                    </Text>
                  )}
                </Box>
              )}

              {/* Recent PMA */}
              {regulatory.recent_pma && regulatory.recent_pma.length > 0 && (
                <Box>
                  <HStack justify="space-between" mb={2}>
                    <Text fontSize="sm" fontWeight="medium" color="gray.600">
                      {showAllPMA ? 'All' : 'Recent'} PMA Approvals
                    </Text>
                    {regulatory.total_pma > 5 && (
                      <Button
                        size="xs"
                        variant="ghost"
                        colorScheme="purple"
                        onClick={() => setShowAllPMA(!showAllPMA)}
                      >
                        {showAllPMA ? 'Show less' : `View all ${regulatory.total_pma}`}
                      </Button>
                    )}
                  </HStack>
                  <Box overflowX="auto" maxH={showAllPMA ? '400px' : 'auto'} overflowY={showAllPMA ? 'auto' : 'visible'}>
                    <Table size="sm" variant="simple">
                      <Thead>
                        <Tr>
                          <Th>PMA Number</Th>
                          <Th>Date</Th>
                          <Th>Trade Name</Th>
                          <Th>Decision</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {(showAllPMA ? regulatory.recent_pma : regulatory.recent_pma.slice(0, 5)).map((pma, idx) => (
                          <Tr key={idx}>
                            <Td fontFamily="mono" fontSize="sm">
                              {pma.pma_number ? (
                                <Link
                                  href={`https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?id=${pma.pma_number}`}
                                  isExternal
                                  color="purple.600"
                                  _hover={{ textDecoration: 'underline' }}
                                >
                                  {pma.pma_number} <ExternalLinkIcon mx="2px" boxSize={3} />
                                </Link>
                              ) : 'N/A'}
                            </Td>
                            <Td>{pma.date || 'N/A'}</Td>
                            <Td maxW="200px" isTruncated>{pma.trade_name || 'N/A'}</Td>
                            <Td>
                              <Badge colorScheme="purple">{pma.decision || 'N/A'}</Badge>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </Box>
                  {showAllPMA && regulatory.total_pma > regulatory.recent_pma.length && (
                    <Text fontSize="xs" color="gray.500" mt={2} textAlign="center">
                      Showing {regulatory.recent_pma.length} of {regulatory.total_pma} approvals (API returns limited results)
                    </Text>
                  )}
                </Box>
              )}
            </VStack>
          </CardBody>
        </Card>
      )}
    </VStack>
  )
}
