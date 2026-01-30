'use client'

import { useState, useMemo } from 'react'
import {
  Box,
  Grid,
  GridItem,
  Heading,
  Input,
  InputGroup,
  InputLeftElement,
  Text,
  VStack,
  HStack,
  Badge,
  Icon,
  Collapse,
  useColorModeValue,
  Button,
  Divider,
} from '@chakra-ui/react'
import { SearchIcon, ChevronDownIcon, ChevronRightIcon } from '@chakra-ui/icons'
import type { LookupCandidate, EntityType } from '@/lib/api'

interface DisambiguationViewProps {
  query: string
  candidates: LookupCandidate[]
  onSelect: (candidate: LookupCandidate) => void
}

interface GroupedItems {
  [key: string]: LookupCandidate[]
}

const DEVICE_CLASS_LABELS: Record<string, { name: string; color: string; description: string }> = {
  '1': { name: 'Class I', color: 'green', description: 'General Controls (Low Risk)' },
  '2': { name: 'Class II', color: 'yellow', description: 'Special Controls (Moderate Risk)' },
  '3': { name: 'Class III', color: 'red', description: 'Premarket Approval (High Risk)' },
  'unknown': { name: 'Unclassified', color: 'gray', description: '' },
}

function GroupHeader({
  label,
  count,
  isOpen,
  onToggle,
  colorScheme,
}: {
  label: string
  count: number
  isOpen: boolean
  onToggle: () => void
  colorScheme: string
}) {
  const headerBg = useColorModeValue('gray.50', 'gray.700')
  const headerHoverBg = useColorModeValue('gray.100', 'gray.600')

  return (
    <HStack
      px={4}
      py={3}
      bg={headerBg}
      cursor="pointer"
      onClick={onToggle}
      _hover={{ bg: headerHoverBg }}
      transition="background 0.2s"
      borderBottomWidth="1px"
    >
      <Icon
        as={isOpen ? ChevronDownIcon : ChevronRightIcon}
        transition="transform 0.2s"
      />
      <Text fontWeight="600" flex="1">
        {label}
      </Text>
      <Badge colorScheme={colorScheme} borderRadius="full">
        {count}
      </Badge>
    </HStack>
  )
}

function CandidateItem({
  candidate,
  onSelect,
}: {
  candidate: LookupCandidate
  onSelect: (candidate: LookupCandidate) => void
}) {
  const hoverBg = useColorModeValue('brand.50', 'brand.900')
  const borderColor = useColorModeValue('gray.100', 'gray.600')

  return (
    <Box
      px={4}
      py={3}
      cursor="pointer"
      onClick={() => onSelect(candidate)}
      _hover={{ bg: hoverBg }}
      transition="background 0.2s"
      borderBottomWidth="1px"
      borderColor={borderColor}
    >
      <Text fontWeight="500" fontSize="sm" noOfLines={1}>
        {candidate.display_name}
      </Text>
      {candidate.description && candidate.description !== candidate.display_name.split(': ')[1] && (
        <Text fontSize="xs" color="gray.500" noOfLines={1} mt={1}>
          {candidate.description}
        </Text>
      )}
      {candidate.device_count && (
        <Text fontSize="xs" color="gray.400" mt={1}>
          {candidate.device_count.toLocaleString()} registered devices
        </Text>
      )}
    </Box>
  )
}

function GroupedList({
  groups,
  groupOrder,
  groupMeta,
  filter,
  onSelect,
  defaultOpenGroups = [],
}: {
  groups: GroupedItems
  groupOrder: string[]
  groupMeta: Record<string, { name: string; color: string; description?: string }>
  filter: string
  onSelect: (candidate: LookupCandidate) => void
  defaultOpenGroups?: string[]
}) {
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set(defaultOpenGroups))

  const toggleGroup = (key: string) => {
    setOpenGroups((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  const filteredGroups = useMemo(() => {
    const lowerFilter = filter.toLowerCase()
    const result: GroupedItems = {}

    for (const [key, items] of Object.entries(groups)) {
      const filtered = items.filter(
        (item) =>
          item.display_name.toLowerCase().includes(lowerFilter) ||
          (item.description && item.description.toLowerCase().includes(lowerFilter))
      )
      if (filtered.length > 0) {
        result[key] = filtered
      }
    }

    return result
  }, [groups, filter])

  const activeGroupOrder = groupOrder.filter((key) => filteredGroups[key]?.length > 0)

  if (activeGroupOrder.length === 0) {
    return (
      <Box p={4} textAlign="center">
        <Text color="gray.500" fontSize="sm">
          No matches found
        </Text>
      </Box>
    )
  }

  return (
    <VStack spacing={0} align="stretch">
      {activeGroupOrder.map((key) => {
        const items = filteredGroups[key]
        const meta = groupMeta[key] || { name: key, color: 'gray' }
        const isOpen = openGroups.has(key)

        return (
          <Box key={key}>
            <GroupHeader
              label={meta.description ? `${meta.name} (${meta.description})` : meta.name}
              count={items.length}
              isOpen={isOpen}
              onToggle={() => toggleGroup(key)}
              colorScheme={meta.color}
            />
            <Collapse in={isOpen} animateOpacity>
              <VStack spacing={0} align="stretch">
                {items.map((item) => (
                  <CandidateItem
                    key={`${item.entity_type}-${item.identifier}`}
                    candidate={item}
                    onSelect={onSelect}
                  />
                ))}
              </VStack>
            </Collapse>
          </Box>
        )
      })}
    </VStack>
  )
}

export function DisambiguationView({ query, candidates, onSelect }: DisambiguationViewProps) {
  const [deviceFilter, setDeviceFilter] = useState('')
  const [manufacturerFilter, setManufacturerFilter] = useState('')

  const cardBg = useColorModeValue('white', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.600')
  const headerBg = useColorModeValue('gray.50', 'gray.700')

  // Separate devices and manufacturers
  const { devices, manufacturers } = useMemo(() => {
    const devices: LookupCandidate[] = []
    const manufacturers: LookupCandidate[] = []

    for (const candidate of candidates) {
      if (candidate.entity_type === 'device') {
        devices.push(candidate)
      } else if (candidate.entity_type === 'manufacturer') {
        manufacturers.push(candidate)
      }
    }

    return { devices, manufacturers }
  }, [candidates])

  // Group devices by class
  const deviceGroups = useMemo(() => {
    const groups: GroupedItems = {
      '1': [],
      '2': [],
      '3': [],
      'unknown': [],
    }

    for (const device of devices) {
      const cls = device.device_class || 'unknown'
      if (groups[cls]) {
        groups[cls].push(device)
      } else {
        groups['unknown'].push(device)
      }
    }

    return groups
  }, [devices])

  // Group manufacturers by first letter
  const { manufacturerGroups, manufacturerGroupOrder } = useMemo(() => {
    const groups: GroupedItems = {}
    const letters = new Set<string>()

    for (const mfr of manufacturers) {
      const letter = mfr.display_name.charAt(0).toUpperCase()
      if (!groups[letter]) {
        groups[letter] = []
      }
      groups[letter].push(mfr)
      letters.add(letter)
    }

    // Sort manufacturers within each group by device count (descending)
    for (const letter of Object.keys(groups)) {
      groups[letter].sort((a, b) => (b.device_count || 0) - (a.device_count || 0))
    }

    const order = Array.from(letters).sort()
    return { manufacturerGroups: groups, manufacturerGroupOrder: order }
  }, [manufacturers])

  // Create meta for manufacturer groups (just the letter with gray color)
  const manufacturerGroupMeta = useMemo(() => {
    const meta: Record<string, { name: string; color: string }> = {}
    for (const letter of manufacturerGroupOrder) {
      meta[letter] = { name: letter, color: 'gray' }
    }
    return meta
  }, [manufacturerGroupOrder])

  const totalDevices = devices.length
  const totalManufacturers = manufacturers.length
  const totalResults = totalDevices + totalManufacturers

  // Determine which groups to open by default (first non-empty group in each column)
  const defaultOpenDeviceGroups = useMemo(() => {
    for (const cls of ['3', '2', '1', 'unknown']) {
      if (deviceGroups[cls]?.length > 0) {
        return [cls]
      }
    }
    return []
  }, [deviceGroups])

  const defaultOpenManufacturerGroups = useMemo(() => {
    if (manufacturerGroupOrder.length > 0) {
      return [manufacturerGroupOrder[0]]
    }
    return []
  }, [manufacturerGroupOrder])

  return (
    <Box>
      <VStack spacing={4} align="stretch" mb={6}>
        <Heading size="md">Results for "{query}"</Heading>
        <Text color="gray.500">
          Found {totalResults} matches in FDA database ({totalDevices} device types, {totalManufacturers} companies)
        </Text>
      </VStack>

      <Grid templateColumns={{ base: '1fr', md: '1fr 1fr' }} gap={5}>
        {/* Devices Column */}
        <GridItem>
          <Box
            bg={cardBg}
            borderWidth="1px"
            borderColor={borderColor}
            borderRadius="lg"
            overflow="hidden"
          >
            <Box px={4} py={3} bg={headerBg} borderBottomWidth="1px">
              <Heading size="sm" mb={3}>
                Medical Devices
              </Heading>
              <InputGroup size="sm">
                <InputLeftElement pointerEvents="none">
                  <SearchIcon color="gray.400" />
                </InputLeftElement>
                <Input
                  placeholder="Search by name or product code..."
                  value={deviceFilter}
                  onChange={(e) => setDeviceFilter(e.target.value)}
                  borderRadius="md"
                />
              </InputGroup>
            </Box>
            <Box maxH="500px" overflowY="auto">
              {totalDevices > 0 ? (
                <GroupedList
                  groups={deviceGroups}
                  groupOrder={['3', '2', '1', 'unknown']}
                  groupMeta={DEVICE_CLASS_LABELS}
                  filter={deviceFilter}
                  onSelect={onSelect}
                  defaultOpenGroups={defaultOpenDeviceGroups}
                />
              ) : (
                <Box p={4} textAlign="center">
                  <Text color="gray.500" fontSize="sm">
                    No device matches
                  </Text>
                </Box>
              )}
            </Box>
          </Box>
        </GridItem>

        {/* Manufacturers Column */}
        <GridItem>
          <Box
            bg={cardBg}
            borderWidth="1px"
            borderColor={borderColor}
            borderRadius="lg"
            overflow="hidden"
          >
            <Box px={4} py={3} bg={headerBg} borderBottomWidth="1px">
              <Heading size="sm" mb={3}>
                Device Manufacturers
              </Heading>
              <InputGroup size="sm">
                <InputLeftElement pointerEvents="none">
                  <SearchIcon color="gray.400" />
                </InputLeftElement>
                <Input
                  placeholder="Search by company name..."
                  value={manufacturerFilter}
                  onChange={(e) => setManufacturerFilter(e.target.value)}
                  borderRadius="md"
                />
              </InputGroup>
            </Box>
            <Box maxH="500px" overflowY="auto">
              {totalManufacturers > 0 ? (
                <GroupedList
                  groups={manufacturerGroups}
                  groupOrder={manufacturerGroupOrder}
                  groupMeta={manufacturerGroupMeta}
                  filter={manufacturerFilter}
                  onSelect={onSelect}
                  defaultOpenGroups={defaultOpenManufacturerGroups}
                />
              ) : (
                <Box p={4} textAlign="center">
                  <Text color="gray.500" fontSize="sm">
                    No manufacturer matches
                  </Text>
                </Box>
              )}
            </Box>
          </Box>
        </GridItem>
      </Grid>
    </Box>
  )
}
