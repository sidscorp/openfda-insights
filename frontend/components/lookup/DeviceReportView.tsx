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
  Icon,
  Divider,
  Progress,
  Tooltip,
} from '@chakra-ui/react'
import { ArrowBackIcon, ExternalLinkIcon } from '@chakra-ui/icons'
import { DeviceReportResponse, apiClient } from '../../lib/api'
import { AISummaryPanel } from './AISummaryPanel'

interface DeviceReportViewProps {
  report: DeviceReportResponse
  onBack: () => void
  onManufacturerClick: (name: string) => void
}

function getClassBadgeColor(deviceClass?: string): string {
  switch (deviceClass) {
    case '1':
      return 'green'
    case '2':
      return 'yellow'
    case '3':
      return 'red'
    default:
      return 'gray'
  }
}

function getClassDescription(deviceClass?: string): string {
  switch (deviceClass) {
    case '1':
      return 'Low Risk'
    case '2':
      return 'Moderate Risk'
    case '3':
      return 'High Risk'
    default:
      return 'Unknown'
  }
}

function formatNumber(n?: number): string {
  if (n === undefined || n === null) return '0'
  return n.toLocaleString()
}

export function DeviceReportView({
  report,
  onBack,
  onManufacturerClick,
}: DeviceReportViewProps) {
  const [summary, setSummary] = useState<string | null>(null)
  const [isLoadingSummary, setIsLoadingSummary] = useState(false)
  const [summaryRequested, setSummaryRequested] = useState(false)

  const handleGenerateSummary = async () => {
    if (summaryRequested) return
    setSummaryRequested(true)
    setIsLoadingSummary(true)
    try {
      const result = await apiClient.generateLookupSummary('device', report.identifier, report)
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
      'device',
      report.identifier,
      summary || '',
      question
    )
    return result.answer
  }

  const deviceClass = report.classification?.device_class
  const events = report.events
  const recalls = report.recalls
  const clearances = report.clearances
  const udi = report.udi

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
            <HStack spacing={3}>
              <Text fontSize="2xl" fontWeight="bold" color="brand.700" _dark={{ color: 'brand.200' }}>
                {report.product_code}
              </Text>
              <Tooltip label={getClassDescription(deviceClass)} placement="top">
                <Badge colorScheme={getClassBadgeColor(deviceClass)} fontSize="md" px={3} py={1}>
                  Class {deviceClass || '?'}
                </Badge>
              </Tooltip>
            </HStack>
            <Text color="gray.600" _dark={{ color: 'gray.300' }} fontSize="lg">
              {report.product_code_name || report.classification?.device_name || 'Medical Device'}
            </Text>
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
        entityType="device"
        identifier={report.identifier}
      />

      {/* Quick Stats */}
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
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
              <StatLabel>Recalls</StatLabel>
              <StatNumber color={recalls?.total_count ? 'orange.500' : 'gray.700'}>
                {formatNumber(recalls?.total_count)}
              </StatNumber>
              <StatHelpText>Total recalls</StatHelpText>
            </Stat>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <Stat>
              <StatLabel>510(k) Clearances</StatLabel>
              <StatNumber>{formatNumber(clearances?.total_count)}</StatNumber>
              <StatHelpText>FDA cleared</StatHelpText>
            </Stat>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <Stat>
              <StatLabel>Registered Devices</StatLabel>
              <StatNumber>{formatNumber(udi?.total_count)}</StatNumber>
              <StatHelpText>In UDI database</StatHelpText>
            </Stat>
          </CardBody>
        </Card>
      </SimpleGrid>

      {/* Classification Details */}
      {report.classification && (
        <Card>
          <CardHeader>
            <Heading size="md">Classification</Heading>
          </CardHeader>
          <CardBody>
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
              {report.classification.regulation_number && (
                <Box>
                  <Text fontSize="sm" color="gray.500">Regulation Number</Text>
                  <Text fontWeight="medium">{report.classification.regulation_number}</Text>
                </Box>
              )}
              {report.classification.medical_specialty && (
                <Box>
                  <Text fontSize="sm" color="gray.500">Medical Specialty</Text>
                  <Text fontWeight="medium">{report.classification.medical_specialty}</Text>
                </Box>
              )}
              {report.classification.submission_type && (
                <Box>
                  <Text fontSize="sm" color="gray.500">Submission Type</Text>
                  <Text fontWeight="medium">{report.classification.submission_type}</Text>
                </Box>
              )}
            </SimpleGrid>
            {report.classification.definition && (
              <Box mt={4}>
                <Text fontSize="sm" color="gray.500">Definition</Text>
                <Text mt={1}>{report.classification.definition}</Text>
              </Box>
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

              {/* Top Manufacturers with Events */}
              {events.top_manufacturers && events.top_manufacturers.length > 0 && (
                <Box>
                  <Text fontSize="sm" fontWeight="medium" color="gray.600" mb={2}>
                    Top Manufacturers by Event Count
                  </Text>
                  <VStack align="stretch" spacing={1}>
                    {events.top_manufacturers.slice(0, 5).map((mfr, idx) => (
                      <HStack key={idx} justify="space-between">
                        <Text
                          fontSize="sm"
                          color="brand.600"
                          cursor="pointer"
                          _hover={{ textDecoration: 'underline' }}
                          onClick={() => onManufacturerClick(mfr.name)}
                        >
                          {mfr.name}
                        </Text>
                        <Text fontSize="sm" color="gray.500">{formatNumber(mfr.count)}</Text>
                      </HStack>
                    ))}
                  </VStack>
                </Box>
              )}

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
                          <Th>Manufacturer</Th>
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
                            <Td>{event.manufacturer || 'N/A'}</Td>
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
                  <Text fontSize="xs" color="gray.500">Most Serious</Text>
                </Box>
                <Box textAlign="center" p={3} bg="orange.50" _dark={{ bg: 'orange.900' }} borderRadius="md">
                  <Text fontSize="2xl" fontWeight="bold" color="orange.600">
                    {recalls.class_counts.class_ii}
                  </Text>
                  <Text fontSize="sm" color="gray.600">Class II</Text>
                  <Text fontSize="xs" color="gray.500">Moderate</Text>
                </Box>
                <Box textAlign="center" p={3} bg="yellow.50" _dark={{ bg: 'yellow.900' }} borderRadius="md">
                  <Text fontSize="2xl" fontWeight="bold" color="yellow.600">
                    {recalls.class_counts.class_iii}
                  </Text>
                  <Text fontSize="sm" color="gray.600">Class III</Text>
                  <Text fontSize="xs" color="gray.500">Minor</Text>
                </Box>
              </SimpleGrid>

              {/* Recent Recalls Table */}
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

      {/* Clearances */}
      {clearances && clearances.total_count > 0 && (
        <Card>
          <CardHeader>
            <HStack justify="space-between">
              <Heading size="md">510(k) Clearances</Heading>
              <Badge colorScheme="green" fontSize="sm">
                {formatNumber(clearances.total_count)} total
              </Badge>
            </HStack>
          </CardHeader>
          <CardBody>
            <VStack align="stretch" spacing={4}>
              {/* Top Applicants */}
              {clearances.top_applicants && clearances.top_applicants.length > 0 && (
                <Box>
                  <Text fontSize="sm" fontWeight="medium" color="gray.600" mb={2}>
                    Top Applicants
                  </Text>
                  <VStack align="stretch" spacing={1}>
                    {clearances.top_applicants.slice(0, 5).map((app, idx) => (
                      <HStack key={idx} justify="space-between">
                        <Text
                          fontSize="sm"
                          color="brand.600"
                          cursor="pointer"
                          _hover={{ textDecoration: 'underline' }}
                          onClick={() => onManufacturerClick(app.name)}
                        >
                          {app.name}
                        </Text>
                        <Text fontSize="sm" color="gray.500">{app.count} clearances</Text>
                      </HStack>
                    ))}
                  </VStack>
                </Box>
              )}

              {/* Recent Clearances */}
              {clearances.recent_clearances && clearances.recent_clearances.length > 0 && (
                <Box>
                  <Text fontSize="sm" fontWeight="medium" color="gray.600" mb={2}>
                    Recent Clearances
                  </Text>
                  <Box overflowX="auto">
                    <Table size="sm" variant="simple">
                      <Thead>
                        <Tr>
                          <Th>K Number</Th>
                          <Th>Date</Th>
                          <Th>Device</Th>
                          <Th>Applicant</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {clearances.recent_clearances.slice(0, 5).map((clr, idx) => (
                          <Tr key={idx}>
                            <Td fontFamily="mono" fontSize="sm">{clr.k_number || 'N/A'}</Td>
                            <Td>{clr.date || 'N/A'}</Td>
                            <Td maxW="200px" isTruncated>{clr.device_name || 'N/A'}</Td>
                            <Td maxW="200px" isTruncated>{clr.applicant || 'N/A'}</Td>
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

      {/* Top Manufacturers */}
      {report.top_manufacturers && report.top_manufacturers.length > 0 && (
        <Card>
          <CardHeader>
            <Heading size="md">Top Manufacturers</Heading>
          </CardHeader>
          <CardBody>
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
              {report.top_manufacturers.map((mfr, idx) => (
                <HStack
                  key={idx}
                  p={3}
                  bg="gray.50"
                  _dark={{ bg: 'gray.700' }}
                  borderRadius="md"
                  justify="space-between"
                  cursor="pointer"
                  _hover={{ bg: 'brand.50', _dark: { bg: 'brand.900' } }}
                  onClick={() => onManufacturerClick(mfr.name)}
                >
                  <Text fontWeight="medium" color="brand.600" _dark={{ color: 'brand.300' }}>
                    {mfr.name}
                  </Text>
                  <Badge colorScheme="brand">{mfr.device_count} devices</Badge>
                </HStack>
              ))}
            </SimpleGrid>
          </CardBody>
        </Card>
      )}
    </VStack>
  )
}
