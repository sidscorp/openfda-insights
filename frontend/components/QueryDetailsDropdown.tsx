'use client'

import { useState } from 'react'
import {
  Box,
  Button,
  Collapse,
  HStack,
  VStack,
  Text,
  Tag,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  useColorModeValue,
  Code,
  Tooltip,
} from '@chakra-ui/react'
import { ChevronDownIcon, ChevronUpIcon } from '@chakra-ui/icons'
import type { QueryDetail } from '@/lib/api'
import { getDataSourceInfo, formatArgs } from '@/lib/tool-mappings'

interface QueryDetailsDropdownProps {
  queries: QueryDetail[]
  isStreaming?: boolean
}

export function QueryDetailsDropdown({ queries, isStreaming }: QueryDetailsDropdownProps) {
  const [isOpen, setIsOpen] = useState(false)

  const bgColor = useColorModeValue('gray.50', 'gray.800')
  const borderColor = useColorModeValue('gray.200', 'gray.600')
  const headerBg = useColorModeValue('gray.100', 'gray.700')
  const textMuted = useColorModeValue('gray.600', 'gray.400')

  if (!queries || queries.length === 0) {
    return null
  }

  const pendingCount = queries.filter((q) => q.status === 'pending').length

  return (
    <Box mt={3} borderWidth="1px" borderColor={borderColor} borderRadius="md" overflow="hidden">
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
        _hover={{ bg: headerBg }}
      >
        <HStack spacing={2}>
          <Text fontSize="sm" fontWeight="medium">
            Data Sources
          </Text>
          <Tag size="sm" colorScheme="blue">
            {queries.length}
          </Tag>
          {isStreaming && pendingCount > 0 && (
            <Tag size="sm" colorScheme="orange" variant="subtle">
              {pendingCount} pending
            </Tag>
          )}
        </HStack>
      </Button>

      <Collapse in={isOpen} animateOpacity>
        <Box p={3} maxH="300px" overflowY="auto">
          <Table size="sm" variant="simple">
            <Thead bg={headerBg}>
              <Tr>
                <Th borderColor={borderColor} width="35%">
                  Data Source
                </Th>
                <Th borderColor={borderColor} width="40%">
                  Parameters
                </Th>
                <Th borderColor={borderColor} width="25%">
                  Result
                </Th>
              </Tr>
            </Thead>
            <Tbody>
              {queries.map((query) => {
                const sourceInfo = getDataSourceInfo(query.tool)
                return (
                  <Tr key={query.id}>
                    <Td borderColor={borderColor}>
                      <VStack align="start" spacing={0}>
                        <HStack spacing={1}>
                          <Text>{sourceInfo.icon}</Text>
                          <Text fontWeight="medium" fontSize="sm">
                            {query.dataSource}
                          </Text>
                        </HStack>
                        <Tooltip label={`OpenFDA endpoint: ${sourceInfo.endpoint}`} hasArrow>
                          <Code fontSize="xs" colorScheme="gray" cursor="help">
                            {sourceInfo.endpoint}
                          </Code>
                        </Tooltip>
                      </VStack>
                    </Td>
                    <Td borderColor={borderColor}>
                      <Text fontSize="xs" color={textMuted} noOfLines={2}>
                        {formatArgs(query.args)}
                      </Text>
                    </Td>
                    <Td borderColor={borderColor}>
                      {query.status === 'pending' ? (
                        <Tag size="sm" colorScheme="orange">
                          Querying...
                        </Tag>
                      ) : query.status === 'error' ? (
                        <Tag size="sm" colorScheme="red">
                          Error
                        </Tag>
                      ) : (
                        <Tag size="sm" colorScheme="green">
                          {query.resultSummary || 'Complete'}
                        </Tag>
                      )}
                    </Td>
                  </Tr>
                )
              })}
            </Tbody>
          </Table>
        </Box>
      </Collapse>
    </Box>
  )
}
