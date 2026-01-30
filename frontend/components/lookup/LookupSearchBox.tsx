'use client'

import { useState, useEffect, useRef, KeyboardEvent } from 'react'
import {
  Box,
  Input,
  InputGroup,
  InputLeftElement,
  InputRightElement,
  Spinner,
  Text,
  HStack,
  Tag,
  TagLabel,
  TagCloseButton,
  Wrap,
  WrapItem,
  IconButton,
} from '@chakra-ui/react'
import { SearchIcon, CloseIcon } from '@chakra-ui/icons'

const STORAGE_KEY = 'fda-lookup-recent-searches'
const MAX_RECENT = 5

interface LookupSearchBoxProps {
  onSearch: (query: string) => void
  isLoading: boolean
  placeholder?: string
}

export function LookupSearchBox({
  onSearch,
  isLoading,
  placeholder = 'Search devices, manufacturers, product codes...',
}: LookupSearchBoxProps) {
  const [query, setQuery] = useState('')
  const [recentSearches, setRecentSearches] = useState<string[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      try {
        setRecentSearches(JSON.parse(stored))
      } catch {}
    }
  }, [])

  const saveRecentSearch = (search: string) => {
    const updated = [search, ...recentSearches.filter((s) => s !== search)].slice(0, MAX_RECENT)
    setRecentSearches(updated)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
  }

  const removeRecentSearch = (search: string) => {
    const updated = recentSearches.filter((s) => s !== search)
    setRecentSearches(updated)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
  }

  const handleSubmit = () => {
    const trimmed = query.trim()
    if (trimmed && !isLoading) {
      saveRecentSearch(trimmed)
      onSearch(trimmed)
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSubmit()
    }
  }

  const handleRecentClick = (search: string) => {
    setQuery(search)
    saveRecentSearch(search)
    onSearch(search)
  }

  return (
    <Box w="100%">
      <InputGroup size="lg">
        <InputLeftElement pointerEvents="none" h="100%">
          {isLoading ? (
            <Spinner size="sm" color="brand.500" />
          ) : (
            <SearchIcon color="gray.400" />
          )}
        </InputLeftElement>
        <Input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          borderRadius="xl"
          bg="white"
          _dark={{ bg: 'gray.800' }}
          border="2px solid"
          borderColor="gray.200"
          _hover={{ borderColor: 'brand.300' }}
          _focus={{
            borderColor: 'brand.500',
            boxShadow: '0 0 0 1px var(--chakra-colors-brand-500)',
          }}
          fontSize="md"
          py={6}
          disabled={isLoading}
        />
        {query && (
          <InputRightElement h="100%">
            <IconButton
              aria-label="Clear search"
              icon={<CloseIcon boxSize={3} />}
              size="sm"
              variant="ghost"
              onClick={() => setQuery('')}
              isDisabled={isLoading}
            />
          </InputRightElement>
        )}
      </InputGroup>

      {recentSearches.length > 0 && !query && (
        <Box mt={4}>
          <Text fontSize="sm" color="gray.500" mb={2}>
            Recent searches
          </Text>
          <Wrap spacing={2}>
            {recentSearches.map((search) => (
              <WrapItem key={search}>
                <Tag
                  size="md"
                  variant="subtle"
                  colorScheme="brand"
                  cursor="pointer"
                  onClick={() => handleRecentClick(search)}
                  _hover={{ bg: 'brand.100' }}
                >
                  <TagLabel>{search}</TagLabel>
                  <TagCloseButton
                    onClick={(e) => {
                      e.stopPropagation()
                      removeRecentSearch(search)
                    }}
                  />
                </Tag>
              </WrapItem>
            ))}
          </Wrap>
        </Box>
      )}
    </Box>
  )
}
