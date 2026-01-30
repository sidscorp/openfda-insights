'use client'

import { useState, useCallback } from 'react'
import {
  Box,
  Container,
  VStack,
  HStack,
  Heading,
  Text,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  useColorModeValue,
  IconButton,
  Tooltip,
  Link,
} from '@chakra-ui/react'
import { MoonIcon, SunIcon, ExternalLinkIcon } from '@chakra-ui/icons'
import { useColorMode } from '@chakra-ui/react'
import {
  apiClient,
  LookupCandidate,
  IdentifyResponse,
  DeviceReportResponse,
  ManufacturerReportResponse,
} from '../../lib/api'
import { LookupSearchBox } from '../../components/lookup/LookupSearchBox'
import { DisambiguationView } from '../../components/DisambiguationView'
import { DeviceReportView } from '../../components/lookup/DeviceReportView'
import { ManufacturerReportView } from '../../components/lookup/ManufacturerReportView'

type ViewState =
  | { type: 'idle' }
  | { type: 'loading'; query: string }
  | { type: 'disambiguation'; query: string; candidates: LookupCandidate[] }
  | { type: 'device-report'; report: DeviceReportResponse; query: string }
  | { type: 'manufacturer-report'; report: ManufacturerReportResponse; query: string }
  | { type: 'error'; message: string; query: string }

interface HistoryEntry {
  type: 'search' | 'device' | 'manufacturer'
  query: string
  identifier?: string
  identifierType?: string
}

export default function LookupPage() {
  const [viewState, setViewState] = useState<ViewState>({ type: 'idle' })
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const { colorMode, toggleColorMode } = useColorMode()

  const bgGradient = useColorModeValue(
    'linear(to-br, gray.50, blue.50, gray.50)',
    'linear(to-br, gray.900, gray.800, gray.900)'
  )

  const pushHistory = useCallback((entry: HistoryEntry) => {
    setHistory((prev) => [...prev, entry])
  }, [])

  const handleSearch = useCallback(async (query: string) => {
    setViewState({ type: 'loading', query })
    pushHistory({ type: 'search', query })

    try {
      const result: IdentifyResponse = await apiClient.identify(query)

      if (result.needs_disambiguation) {
        if (result.candidates.length === 0) {
          setViewState({
            type: 'error',
            message: `No results found for "${query}". Try a different search term.`,
            query,
          })
        } else if (result.candidates.length === 1) {
          const candidate = result.candidates[0]
          await handleCandidateSelect(candidate, query)
        } else {
          setViewState({
            type: 'disambiguation',
            query,
            candidates: result.candidates,
          })
        }
      } else if (result.entity_type && result.identifier && result.identifier_type) {
        if (result.entity_type === 'device') {
          await fetchDeviceReport(result.identifier, result.identifier_type, query)
        } else {
          await fetchManufacturerReport(result.identifier, result.identifier_type, query)
        }
      } else {
        setViewState({
          type: 'error',
          message: 'Unable to identify the search term. Please try a more specific query.',
          query,
        })
      }
    } catch (error) {
      console.error('Search failed:', error)
      setViewState({
        type: 'error',
        message: error instanceof Error ? error.message : 'Search failed. Please try again.',
        query,
      })
    }
  }, [])

  const fetchDeviceReport = useCallback(async (identifier: string, type: string, query: string) => {
    setViewState({ type: 'loading', query })
    try {
      const report = await apiClient.getDeviceReport(identifier, type)
      setViewState({ type: 'device-report', report, query })
    } catch (error) {
      console.error('Failed to fetch device report:', error)
      setViewState({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to load device report.',
        query,
      })
    }
  }, [])

  const fetchManufacturerReport = useCallback(async (identifier: string, type: string, query: string) => {
    setViewState({ type: 'loading', query })
    try {
      const report = await apiClient.getManufacturerReport(identifier, type)
      setViewState({ type: 'manufacturer-report', report, query })
    } catch (error) {
      console.error('Failed to fetch manufacturer report:', error)
      setViewState({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to load manufacturer report.',
        query,
      })
    }
  }, [])

  const handleCandidateSelect = useCallback(async (candidate: LookupCandidate, query: string) => {
    pushHistory({
      type: candidate.entity_type === 'device' ? 'device' : 'manufacturer',
      query,
      identifier: candidate.identifier,
      identifierType: candidate.identifier_type,
    })

    if (candidate.entity_type === 'device') {
      await fetchDeviceReport(candidate.identifier, candidate.identifier_type, query)
    } else {
      await fetchManufacturerReport(candidate.identifier, candidate.identifier_type, query)
    }
  }, [fetchDeviceReport, fetchManufacturerReport, pushHistory])

  const handleManufacturerClick = useCallback(async (name: string) => {
    pushHistory({
      type: 'manufacturer',
      query: name,
      identifier: name,
      identifierType: 'company_name',
    })
    await fetchManufacturerReport(name, 'company_name', name)
  }, [fetchManufacturerReport, pushHistory])

  const handleDeviceClick = useCallback(async (productCode: string) => {
    pushHistory({
      type: 'device',
      query: productCode,
      identifier: productCode,
      identifierType: 'product_code',
    })
    await fetchDeviceReport(productCode, 'product_code', productCode)
  }, [fetchDeviceReport, pushHistory])

  const handleBack = useCallback(() => {
    if (history.length <= 1) {
      setViewState({ type: 'idle' })
      setHistory([])
      return
    }

    const newHistory = [...history]
    newHistory.pop()
    const prev = newHistory[newHistory.length - 1]
    setHistory(newHistory)

    if (!prev) {
      setViewState({ type: 'idle' })
      return
    }

    if (prev.type === 'search') {
      handleSearch(prev.query)
    } else if (prev.type === 'device' && prev.identifier && prev.identifierType) {
      fetchDeviceReport(prev.identifier, prev.identifierType, prev.query)
    } else if (prev.type === 'manufacturer' && prev.identifier && prev.identifierType) {
      fetchManufacturerReport(prev.identifier, prev.identifierType, prev.query)
    }
  }, [history, handleSearch, fetchDeviceReport, fetchManufacturerReport])

  const renderContent = () => {
    switch (viewState.type) {
      case 'idle':
        return (
          <VStack spacing={8} w="100%" maxW="600px" mx="auto" pt={20}>
            <VStack spacing={2} textAlign="center">
              <Heading
                size="2xl"
                bgGradient="linear(to-r, brand.500, brand.700)"
                bgClip="text"
              >
                FDA Lookup
              </Heading>
              <Text color="gray.500" fontSize="lg">
                Search for medical devices and manufacturers
              </Text>
            </VStack>
            <LookupSearchBox
              onSearch={handleSearch}
              isLoading={false}
              placeholder="Enter device name, product code, or manufacturer..."
            />
            <VStack spacing={2} color="gray.400" fontSize="sm">
              <Text>Try: pacemaker, medtronic, DXY, K231234</Text>
            </VStack>
          </VStack>
        )

      case 'loading':
        return (
          <VStack spacing={4} py={20}>
            <Spinner size="xl" color="brand.500" thickness="4px" />
            <Text color="gray.500">Searching for "{viewState.query}"...</Text>
          </VStack>
        )

      case 'disambiguation':
        return (
          <Box w="100%">
            <Box mb={6}>
              <LookupSearchBox
                onSearch={handleSearch}
                isLoading={false}
              />
            </Box>
            <DisambiguationView
              query={viewState.query}
              candidates={viewState.candidates}
              onSelect={(candidate) => handleCandidateSelect(candidate, viewState.query)}
            />
          </Box>
        )

      case 'device-report':
        return (
          <Box w="100%">
            <Box mb={6}>
              <LookupSearchBox
                onSearch={handleSearch}
                isLoading={false}
              />
            </Box>
            <DeviceReportView
              report={viewState.report}
              onBack={handleBack}
              onManufacturerClick={handleManufacturerClick}
            />
          </Box>
        )

      case 'manufacturer-report':
        return (
          <Box w="100%">
            <Box mb={6}>
              <LookupSearchBox
                onSearch={handleSearch}
                isLoading={false}
              />
            </Box>
            <ManufacturerReportView
              report={viewState.report}
              onBack={handleBack}
              onDeviceClick={handleDeviceClick}
            />
          </Box>
        )

      case 'error':
        return (
          <VStack spacing={6} w="100%" maxW="600px" mx="auto" pt={10}>
            <LookupSearchBox
              onSearch={handleSearch}
              isLoading={false}
            />
            <Alert
              status="error"
              variant="subtle"
              flexDirection="column"
              alignItems="center"
              justifyContent="center"
              textAlign="center"
              borderRadius="xl"
              py={6}
            >
              <AlertIcon boxSize="40px" mr={0} />
              <AlertTitle mt={4} mb={1} fontSize="lg">
                Search Error
              </AlertTitle>
              <AlertDescription maxWidth="sm">
                {viewState.message}
              </AlertDescription>
            </Alert>
          </VStack>
        )
    }
  }

  return (
    <Box minH="100vh" bgGradient={bgGradient}>
      <Box
        as="header"
        py={4}
        px={6}
        borderBottomWidth="1px"
        borderColor={useColorModeValue('gray.200', 'gray.700')}
        bg={useColorModeValue('whiteAlpha.800', 'blackAlpha.400')}
        backdropFilter="blur(10px)"
      >
        <HStack justify="space-between" maxW="1400px" mx="auto">
          <HStack
            spacing={3}
            cursor="pointer"
            onClick={() => {
              setViewState({ type: 'idle' })
              setHistory([])
            }}
          >
            <Text fontSize="xl" fontWeight="bold" color="brand.600">
              FDA Lookup
            </Text>
          </HStack>
          <HStack spacing={4}>
            <Tooltip label="Full Agent Chat">
              <Link href="/" isExternal={false}>
                <IconButton
                  aria-label="Go to agent"
                  icon={<ExternalLinkIcon />}
                  variant="ghost"
                  size="sm"
                />
              </Link>
            </Tooltip>
            <Tooltip label={colorMode === 'light' ? 'Dark mode' : 'Light mode'}>
              <IconButton
                aria-label="Toggle color mode"
                icon={colorMode === 'light' ? <MoonIcon /> : <SunIcon />}
                onClick={toggleColorMode}
                variant="ghost"
                size="sm"
              />
            </Tooltip>
          </HStack>
        </HStack>
      </Box>

      <Container maxW="1400px" py={8} px={6}>
        {renderContent()}
      </Container>

      <Box
        as="footer"
        py={4}
        textAlign="center"
        borderTopWidth="1px"
        borderColor={useColorModeValue('gray.200', 'gray.700')}
        mt="auto"
      >
        <Text fontSize="sm" color="gray.500">
          Data from{' '}
          <Link href="https://open.fda.gov" isExternal color="brand.500">
            openFDA
          </Link>{' '}
          &bull;{' '}
          <Link href="/" color="brand.500">
            Full Agent Chat
          </Link>
        </Text>
      </Box>
    </Box>
  )
}
