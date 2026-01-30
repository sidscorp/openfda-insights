'use client'

import { useState, useRef, KeyboardEvent } from 'react'
import {
  Box,
  VStack,
  HStack,
  Text,
  Input,
  InputGroup,
  InputRightElement,
  IconButton,
  Spinner,
  Collapse,
  useDisclosure,
  Icon,
  Divider,
  Button,
} from '@chakra-ui/react'
import { ChevronDownIcon, ChevronUpIcon, ArrowForwardIcon } from '@chakra-ui/icons'

interface FollowupQA {
  question: string
  answer: string
}

interface AISummaryPanelProps {
  summary: string | null
  isLoadingSummary: boolean
  onAskFollowup: (question: string) => Promise<string>
  onGenerateSummary: () => void
  summaryRequested: boolean
  entityType: string
  identifier: string
}

export function AISummaryPanel({
  summary,
  isLoadingSummary,
  onAskFollowup,
  onGenerateSummary,
  summaryRequested,
  entityType,
  identifier,
}: AISummaryPanelProps) {
  const { isOpen, onToggle } = useDisclosure({ defaultIsOpen: true })
  const [followupQuestion, setFollowupQuestion] = useState('')
  const [followups, setFollowups] = useState<FollowupQA[]>([])
  const [isAskingFollowup, setIsAskingFollowup] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleAskFollowup = async () => {
    const question = followupQuestion.trim()
    if (!question || isAskingFollowup) return

    setIsAskingFollowup(true)
    setFollowupQuestion('')

    try {
      const answer = await onAskFollowup(question)
      setFollowups((prev) => [...prev, { question, answer }])
    } catch (error) {
      setFollowups((prev) => [
        ...prev,
        { question, answer: 'Sorry, I could not answer that question.' },
      ])
    } finally {
      setIsAskingFollowup(false)
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleAskFollowup()
    }
  }

  return (
    <Box
      bg="brand.50"
      _dark={{ bg: 'gray.700', borderColor: 'gray.600' }}
      borderRadius="xl"
      p={4}
      border="1px solid"
      borderColor="brand.100"
    >
      <HStack
        justify="space-between"
        cursor="pointer"
        onClick={onToggle}
        mb={isOpen ? 3 : 0}
      >
        <HStack spacing={2}>
          <Text fontSize="lg">🤖</Text>
          <Text fontWeight="semibold" color="brand.700" _dark={{ color: 'brand.200' }}>
            AI Summary
          </Text>
        </HStack>
        <Icon
          as={isOpen ? ChevronUpIcon : ChevronDownIcon}
          color="brand.500"
          boxSize={5}
        />
      </HStack>

      <Collapse in={isOpen} animateOpacity>
        <VStack align="stretch" spacing={3}>
          {!summaryRequested ? (
            <Button
              colorScheme="brand"
              variant="outline"
              size="sm"
              onClick={(e) => {
                e.stopPropagation()
                onGenerateSummary()
              }}
              leftIcon={<Text>✨</Text>}
            >
              Generate AI Summary
            </Button>
          ) : isLoadingSummary ? (
            <HStack spacing={3} py={2}>
              <Spinner size="sm" color="brand.500" />
              <Text color="gray.600" _dark={{ color: 'gray.300' }}>
                Generating summary...
              </Text>
            </HStack>
          ) : summary ? (
            <Text color="gray.700" _dark={{ color: 'gray.200' }} lineHeight="tall">
              {summary}
            </Text>
          ) : (
            <Text color="gray.500" fontStyle="italic">
              Could not generate summary
            </Text>
          )}

          {followups.length > 0 && (
            <>
              <Divider borderColor="brand.200" />
              <VStack align="stretch" spacing={3}>
                {followups.map((qa, idx) => (
                  <Box key={idx}>
                    <Text
                      fontSize="sm"
                      fontWeight="medium"
                      color="brand.600"
                      _dark={{ color: 'brand.300' }}
                      mb={1}
                    >
                      Q: {qa.question}
                    </Text>
                    <Text
                      color="gray.700"
                      _dark={{ color: 'gray.200' }}
                      fontSize="sm"
                      pl={3}
                      borderLeft="2px solid"
                      borderColor="brand.300"
                    >
                      {qa.answer}
                    </Text>
                  </Box>
                ))}
              </VStack>
            </>
          )}

          {summaryRequested && summary && (
            <InputGroup size="sm" mt={2}>
              <Input
                ref={inputRef}
                value={followupQuestion}
                onChange={(e) => setFollowupQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a follow-up question..."
                borderRadius="lg"
                bg="white"
                _dark={{ bg: 'gray.800' }}
                disabled={isAskingFollowup || isLoadingSummary}
              />
              <InputRightElement>
                {isAskingFollowup ? (
                  <Spinner size="xs" color="brand.500" />
                ) : (
                  <IconButton
                    aria-label="Ask question"
                    icon={<ArrowForwardIcon />}
                    size="xs"
                    colorScheme="brand"
                    variant="ghost"
                    onClick={handleAskFollowup}
                    isDisabled={!followupQuestion.trim() || isLoadingSummary}
                  />
                )}
              </InputRightElement>
            </InputGroup>
          )}
        </VStack>
      </Collapse>
    </Box>
  )
}
