'use client'

import { Fragment, useEffect, useMemo, useRef, useState, useCallback } from 'react'
import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Card,
  CardBody,
  Container,
  HStack,
  Heading,
  IconButton,
  Spinner,
  Stack,
  Tag,
  Text,
  Textarea,
  Tooltip,
  Collapse,
  useColorMode,
  useColorModeValue,
  useDisclosure,
  useToast,
  VStack,
} from '@chakra-ui/react'
import { CheckIcon, ChevronDownIcon, ChevronUpIcon, CloseIcon, MoonIcon, SunIcon, WarningIcon, SearchIcon } from '@chakra-ui/icons'
import NextLink from 'next/link'
import { apiClient, type AgentStreamEvent, type QueryDetail, type LookupCandidate } from '@/lib/api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { StructuredDataTable } from '@/components/StructuredDataTable'
import { DisambiguationView } from '@/components/DisambiguationView'
import { WorkspaceLayout } from '@/components/WorkspaceLayout'
import { useSession } from '@/lib/session-context'
import type { StoredMessage } from '@/lib/storage'
import { getDataSourceInfo, parseResultSummary } from '@/lib/tool-mappings'

type Role = 'user' | 'assistant' | 'system'
type StreamPhase = 'thinking' | 'tool' | 'error' | 'final'

interface ResponseMeta {
  model?: string
  tokens?: number
  inputTokens?: number
  outputTokens?: number
  cost?: number
}

interface ChatMessage {
  id: string
  role: Role
  content: string
  streaming?: boolean
  meta?: ResponseMeta
  structuredData?: Record<string, unknown>
  queryDetails?: QueryDetail[]
}

const allStarterPrompts = [
  'Show me recent Class I recalls for infusion pumps',
  'What adverse events have been reported for hip implants?',
  'Which companies make pacemakers?',
  'What product codes cover cardiac monitors?',
  'Find surgical mask recalls from the past year',
  'Show me adverse events for cochlear implants',
  'Who manufactures glucose monitors?',
  'What PMA approvals exist for heart valves?',
  'Find recalls for ventilators in 2024',
  'Show me defibrillator manufacturers by country',
]

function getRandomPrompts(count: number): string[] {
  const shuffled = [...allStarterPrompts].sort(() => Math.random() - 0.5)
  return shuffled.slice(0, count)
}

const TOKEN_WARNING_THRESHOLD = 50000
const TOKEN_LIMIT = 100000

export default function Home() {
  return (
    <WorkspaceLayout>
      <ChatArea />
    </WorkspaceLayout>
  )
}

function ChatArea() {
  const { colorMode, toggleColorMode } = useColorMode()
  const subtitleColor = useColorModeValue('gray.600', 'gray.200')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamCompleted, setStreamCompleted] = useState(false)
  const [streamStatus, setStreamStatus] = useState<{ phase: StreamPhase; message: string } | null>(null)
  const [streamSeconds, setStreamSeconds] = useState(0)
  const [toolHistory, setToolHistory] = useState<string[]>([])
  const [currentTool, setCurrentTool] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [toolCallsTotal, setToolCallsTotal] = useState(0)
  const [toolCallsDone, setToolCallsDone] = useState(0)
  const [activeUserMessageId, setActiveUserMessageId] = useState<string | null>(null)
  const [sessionTokens, setSessionTokens] = useState(0)
  const [hasGeneratedTitle, setHasGeneratedTitle] = useState(false)
  const [starterPrompts] = useState(() => getRandomPrompts(3))
  const [pendingQueries, setPendingQueries] = useState<Map<string, QueryDetail[]>>(new Map())
  const [disambiguationData, setDisambiguationData] = useState<{
    query: string
    candidates: LookupCandidate[]
  } | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const hasDeltaRef = useRef(false)
  const streamCompletedRef = useRef(false)
  const toast = useToast()

  const {
    currentSession,
    currentMessages,
    createSession,
    addMessage,
    updateSessionTitle,
  } = useSession()

  const endOfChatRef = useRef<HTMLDivElement | null>(null)
  const sessionInitiatedRef = useRef(false)

  useEffect(() => {
    if (!currentSession && !sessionInitiatedRef.current) {
      sessionInitiatedRef.current = true
      createSession()
    }
  }, [currentSession, createSession])

  useEffect(() => {
    // Don't reconstruct messages during streaming - it would lose local state
    if (isStreaming) return

    if (currentMessages.length > 0) {
      const reconstructedMessages: ChatMessage[] = [
        {
          id: 'system',
          role: 'system',
          content: `Welcome to OpenFDA Explorer! I can help you research:\n\n• **Medical device recalls** and safety alerts\n• **Adverse event reports** from the MAUDE database\n• **510(k) clearances** and PMA approvals\n• **Manufacturer** and facility information\n\nTry the examples below, or use [Quick Lookup](/lookup) for instant device and manufacturer reports.`,
        },
        ...currentMessages.map((m) => ({
          id: m.id,
          role: m.role as Role,
          content: m.content,
          meta: m.meta as ResponseMeta,
          structuredData: m.structuredData as Record<string, unknown>,
          queryDetails: m.queryDetails as QueryDetail[],
        })),
      ]
      setMessages(reconstructedMessages)
      setHasGeneratedTitle(true)
    } else {
      setMessages([
        {
          id: 'system',
          role: 'system',
          content: `Welcome to OpenFDA Explorer! I can help you research:\n\n• **Medical device recalls** and safety alerts\n• **Adverse event reports** from the MAUDE database\n• **510(k) clearances** and PMA approvals\n• **Manufacturer** and facility information\n\nTry the examples below, or use [Quick Lookup](/lookup) for instant device and manufacturer reports.`,
        },
      ])
      setHasGeneratedTitle(false)
    }
  }, [currentMessages, isStreaming])

  useEffect(() => {
    endOfChatRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (!isStreaming) {
      setStreamSeconds(0)
      return
    }
    const startedAt = Date.now()
    const interval = window.setInterval(() => {
      setStreamSeconds(Math.floor((Date.now() - startedAt) / 1000))
    }, 1000)
    return () => window.clearInterval(interval)
  }, [isStreaming])

  const canSend = input.trim().length > 0 && !isStreaming && sessionTokens <= TOKEN_LIMIT

  const handleNewChat = useCallback(() => {
    sessionInitiatedRef.current = true
    createSession()
    setSessionTokens(0)
    setHasGeneratedTitle(false)
  }, [createSession])

  const generateTitleIfNeeded = useCallback(
    async (userMessage: string, assistantResponse: string) => {
      if (hasGeneratedTitle || !currentSession) return
      try {
        const { title } = await apiClient.generateSessionTitle(userMessage, assistantResponse)
        if (title && title !== 'New Chat') {
          await updateSessionTitle(currentSession.id, title)
        }
        setHasGeneratedTitle(true)
      } catch (err) {
        console.error('Failed to generate title:', err)
      }
    },
    [hasGeneratedTitle, currentSession, updateSessionTitle]
  )

  const sendToAgent = useCallback(
    (text: string) => {
      if (!text || isStreaming || !currentSession) return

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: text,
      }
      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '',
        streaming: true,
      }

      setMessages((prev) => [...prev, userMessage, assistantMessage])
      setInput('')
      setIsStreaming(true)
      streamCompletedRef.current = false
      setStreamCompleted(false)
      setStreamStatus({ phase: 'thinking', message: '' })
      setToolHistory([])
      setCurrentTool(null)
      setErrorMessage(null)
      setToolCallsTotal(0)
      setToolCallsDone(0)
      setActiveUserMessageId(userMessage.id)
      hasDeltaRef.current = false
      setPendingQueries(new Map())

      addMessage({ role: 'user', content: text }, userMessage.id)

      const es = apiClient.openAgentStream(
        text,
        {
          onEvent: (event: AgentStreamEvent) => {
            if (event.type === 'clear') {
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantMessage.id ? { ...m, content: '' } : m))
              )
            } else if (event.type === 'complete') {
              const newTokens = (event.input_tokens || 0) + (event.output_tokens || 0)
              setSessionTokens((prev) => prev + newTokens)
            }

            if (event.type === 'thinking') {
              setStreamStatus({ phase: 'thinking', message: '' })
            } else if (event.type === 'delta') {
              hasDeltaRef.current = true
              setCurrentTool(null)
              setStreamStatus({ phase: 'final', message: '' })
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMessage.id
                    ? { ...m, content: `${m.content}${event.content}`, streaming: true }
                    : m
                )
              )
            } else if (event.type === 'tool_call') {
              setCurrentTool(event.tool)
              setToolHistory((prev) => [...prev, event.tool])
              setToolCallsTotal((prev) => prev + 1)
              setStreamStatus({ phase: 'tool', message: '' })

              const queryId = `${event.tool}-${Date.now()}`
              const sourceInfo = getDataSourceInfo(event.tool)
              const newQuery: QueryDetail = {
                id: queryId,
                tool: event.tool,
                dataSource: sourceInfo.name,
                args: event.args,
                status: 'pending',
                timestamp: Date.now(),
              }
              setPendingQueries((prev) => {
                const existing = prev.get(assistantMessage.id) || []
                const updated = new Map(prev)
                updated.set(assistantMessage.id, [...existing, newQuery])
                return updated
              })
            } else if (event.type === 'tool_result') {
              setCurrentTool(null)
              setToolCallsDone((prev) => prev + 1)

              setPendingQueries((prev) => {
                const queries = prev.get(assistantMessage.id) || []
                const pendingIdx = queries.findIndex((q) => q.status === 'pending')
                if (pendingIdx >= 0) {
                  const updated = [...queries]
                  updated[pendingIdx] = {
                    ...updated[pendingIdx],
                    status: 'complete',
                    resultSummary: parseResultSummary(updated[pendingIdx].tool, event.content),
                  }
                  const newMap = new Map(prev)
                  newMap.set(assistantMessage.id, updated)
                  return newMap
                }
                return prev
              })
            } else if (event.type === 'complete') {
              const finalContent = hasDeltaRef.current ? undefined : event.answer

              setPendingQueries((prev) => {
                const queries = prev.get(assistantMessage.id) || []

                setMessages((prevMessages) =>
                  prevMessages.map((m) => {
                    if (m.id !== assistantMessage.id) return m
                    return {
                      ...m,
                      content: finalContent ?? m.content,
                      streaming: false,
                      meta: {
                        model: event.model,
                        tokens: event.tokens,
                        inputTokens: event.input_tokens,
                        outputTokens: event.output_tokens,
                        cost: event.cost,
                      },
                      structuredData: event.structured_data || undefined,
                      queryDetails: queries.length > 0 ? queries : undefined,
                    }
                  })
                )

                const assistantContent = event.answer

                addMessage({
                  role: 'assistant',
                  content: assistantContent,
                  meta: {
                    model: event.model,
                    tokens: event.tokens,
                    cost: event.cost,
                  },
                  structuredData: event.structured_data,
                  queryDetails: queries.length > 0 ? queries : undefined,
                }, assistantMessage.id)

                generateTitleIfNeeded(text, assistantContent)

                return prev
              })

              setCurrentTool(null)
              setStreamStatus({ phase: 'final', message: '' })
            } else if (event.type === 'error') {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMessage.id
                    ? { ...m, content: `Error: ${event.message}`, streaming: false }
                    : m
                )
              )
              setCurrentTool(null)
              setErrorMessage(event.message)
              setStreamStatus({ phase: 'error', message: event.message })
            }

            if (event.type === 'complete' || event.type === 'error') {
              setIsStreaming(false)
              streamCompletedRef.current = true
              setStreamCompleted(true)
              setActiveUserMessageId(null)
              setTimeout(() => {
                if (eventSourceRef.current) {
                  eventSourceRef.current.close()
                  eventSourceRef.current = null
                }
              }, 500)
            }
          },
          onError: (err) => {
            if (streamCompletedRef.current) {
              return
            }

            setIsStreaming(false)
            setCurrentTool(null)
            setErrorMessage(err || 'Connection lost')
            setStreamStatus({ phase: 'error', message: err || 'Connection lost' })
            setActiveUserMessageId(null)
            setMessages((prev) =>
              prev.map((m) =>
                m.streaming ? { ...m, streaming: false, content: `${m.content}\n${err}` } : m
              )
            )
            toast({
              title: 'Connection lost',
              description: err || 'Check the API URL and server status.',
              status: 'error',
              duration: 4000,
              isClosable: true,
            })
          },
        },
        currentSession.id
      )

      eventSourceRef.current = es
    },
    [
      isStreaming,
      currentSession,
      addMessage,
      generateTitleIfNeeded,
      toast,
    ]
  )

  const handleSend = useCallback(
    async (prompt?: string) => {
      const text = prompt ?? input.trim()
      if (!text || isStreaming || !currentSession) return

      // Clear input immediately for responsiveness
      setInput('')

      // Check if disambiguation is needed
      try {
        const identifyResult = await apiClient.identify(text)

        if (identifyResult.needs_disambiguation && identifyResult.candidates.length > 1) {
          // Show disambiguation UI
          setDisambiguationData({ query: text, candidates: identifyResult.candidates })
          return
        }

        // No disambiguation needed - proceed to agent
        sendToAgent(text)
      } catch (e) {
        // Fallback to agent on identify error
        console.warn('Identify call failed, falling back to agent:', e)
        sendToAgent(text)
      }
    },
    [
      input,
      isStreaming,
      currentSession,
      sendToAgent,
    ]
  )

  const handleDisambiguationSelect = useCallback(
    (candidate: LookupCandidate) => {
      setDisambiguationData(null)
      // Send refined query to agent with the specific entity
      const refinedQuery = candidate.entity_type === 'device'
        ? `Tell me about product code ${candidate.identifier} (${candidate.display_name})`
        : `Tell me about manufacturer "${candidate.display_name}"`
      sendToAgent(refinedQuery)
    },
    [sendToAgent]
  )

  const handleDisambiguationCancel = useCallback(() => {
    setDisambiguationData(null)
  }, [])

  const handleStop = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setIsStreaming(false)
    setStreamCompleted(true)
    setStreamStatus(null)
    setToolHistory([])
    setCurrentTool(null)
    setErrorMessage(null)
    setToolCallsTotal(0)
    setToolCallsDone(0)
    setActiveUserMessageId(null)
    setMessages((prev) => prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)))
  }

  return (
    <Box h="100%" display="flex" flexDirection="column" overflow="hidden">
      <Card borderRadius={0} borderBottomWidth="1px" flexShrink={0}>
        <CardBody py={3}>
          <Stack spacing={2} direction={{ base: 'column', md: 'row' }} justify="space-between" align="center">
            <Box>
              <Heading size="md">OpenFDA Explorer</Heading>
              <Text fontSize="sm" color={subtitleColor}>
                {currentSession?.title || 'New Chat'}
              </Text>
            </Box>
            <HStack spacing={2}>
              {sessionTokens > 0 && (
                <Tooltip
                  label="Tokens measure conversation length. As tokens increase, the AI must process more context, which can reduce accuracy and increase response time. Start a new chat for fresh, focused responses."
                  hasArrow
                  maxW="280px"
                  placement="bottom"
                >
                  <Tag
                    size="sm"
                    variant="subtle"
                    colorScheme={sessionTokens > TOKEN_WARNING_THRESHOLD ? 'orange' : 'gray'}
                    cursor="help"
                  >
                    {Math.round(sessionTokens / 1000)}k tokens
                  </Tag>
                </Tooltip>
              )}
              <Button
                as={NextLink}
                href="/lookup"
                leftIcon={<SearchIcon />}
                variant="outline"
                size="sm"
                colorScheme="brand"
              >
                Quick Lookup
              </Button>
              <IconButton
                aria-label="Toggle color mode"
                icon={colorMode === 'light' ? <MoonIcon /> : <SunIcon />}
                onClick={toggleColorMode}
                variant="ghost"
                size="sm"
              />
            </HStack>
          </Stack>
        </CardBody>
      </Card>

      <VStack flex="1" align="stretch" spacing={4} p={4} overflowY="auto">
        {disambiguationData ? (
          <Box>
            <DisambiguationView
              query={disambiguationData.query}
              candidates={disambiguationData.candidates}
              onSelect={handleDisambiguationSelect}
            />
            <Button
              mt={4}
              variant="ghost"
              size="sm"
              onClick={handleDisambiguationCancel}
            >
              Cancel and search differently
            </Button>
          </Box>
        ) : (
          <>
            {messages.map((m) => (
              <Box key={m.id}>
                <MessageBubble message={m} />
                {m.id === activeUserMessageId && streamStatus && (
                  <ThinkingPanel
                    isStreaming={isStreaming}
                    streamSeconds={streamSeconds}
                    phase={streamStatus.phase}
                    errorMessage={errorMessage}
                    toolHistory={toolHistory}
                    currentTool={currentTool}
                    toolCallsDone={toolCallsDone}
                    toolCallsTotal={toolCallsTotal}
                  />
                )}
              </Box>
            ))}
          </>
        )}
        <div ref={endOfChatRef} />
      </VStack>

      <Box p={4} borderTopWidth="1px" flexShrink={0}>
        {sessionTokens > TOKEN_LIMIT && (
          <Alert status="error" borderRadius="md" mb={3}>
            <AlertIcon />
            <Box flex="1">
              <Text fontWeight="600">Token limit reached</Text>
              <Text fontSize="sm">Please start a new chat to continue.</Text>
            </Box>
            <Button size="sm" colorScheme="red" onClick={handleNewChat}>
              New Chat
            </Button>
          </Alert>
        )}

        {sessionTokens > TOKEN_WARNING_THRESHOLD && sessionTokens <= TOKEN_LIMIT && (
          <Alert status="warning" borderRadius="md" mb={3}>
            <AlertIcon />
            <Box flex="1">
              <Text fontSize="sm">
                Conversation is getting long ({Math.round(sessionTokens / 1000)}k tokens). Consider starting a new
                chat soon.
              </Text>
            </Box>
            <Button size="sm" variant="outline" onClick={handleNewChat}>
              New Chat
            </Button>
          </Alert>
        )}

        <Stack direction={{ base: 'column', md: 'row' }} spacing={3} align="stretch">
          <Textarea
            placeholder={
              sessionTokens > TOKEN_LIMIT
                ? 'Token limit reached - start new chat'
                : 'Ask about a device, manufacturer, or risk signal...'
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && canSend) {
                e.preventDefault()
                handleSend()
              }
            }}
            isDisabled={isStreaming || sessionTokens > TOKEN_LIMIT}
            rows={2}
            resize="none"
          />
          <Button
            colorScheme="brand"
            onClick={isStreaming ? handleStop : () => handleSend()}
            isDisabled={!canSend && !isStreaming}
            minW={{ md: '100px' }}
          >
            {isStreaming ? (
              <HStack spacing={2}>
                <Spinner size="sm" />
                <Text>Stop</Text>
              </HStack>
            ) : (
              'Send'
            )}
          </Button>
        </Stack>

        {messages.length === 1 && (
          <Box mt={3}>
            <Text fontSize="xs" color="gray.500" mb={2}>
              Try asking:
            </Text>
            <HStack spacing={2} wrap="wrap">
              {starterPrompts.map((p) => (
                <Button key={p} size="xs" variant="outline" onClick={() => handleSend(p)} isDisabled={isStreaming}>
                  {p}
                </Button>
              ))}
            </HStack>
          </Box>
        )}
      </Box>
    </Box>
  )
}

function formatToolName(tool: string): string {
  const toolDescriptions: Record<string, string> = {
    resolve_device: 'resolve device',
    search_maude: 'searching adverse events',
    search_recalls: 'searching recalls',
    search_510k: 'searching 510(k)',
    search_pma: 'searching PMA',
    search_registrations: 'searching registrations',
    search_classifications: 'searching classifications',
  }
  return toolDescriptions[tool] || tool.replace(/_/g, ' ').replace(/^search /, '')
}

function ThinkingPanel({
  isStreaming,
  streamSeconds,
  phase,
  errorMessage,
  toolHistory,
  currentTool,
  toolCallsDone,
  toolCallsTotal,
}: {
  isStreaming: boolean
  streamSeconds: number
  phase: StreamPhase
  errorMessage: string | null
  toolHistory: string[]
  currentTool: string | null
  toolCallsDone: number
  toolCallsTotal: number
}) {
  const progressPct = toolCallsTotal > 0 ? Math.round((toolCallsDone / toolCallsTotal) * 100) : 0

  const completeBg = useColorModeValue('green.50', 'green.900')
  const completeBorder = useColorModeValue('green.200', 'green.700')
  const completeText = useColorModeValue('green.700', 'green.200')
  const errorBg = useColorModeValue('red.50', 'red.900')
  const errorBorder = useColorModeValue('red.200', 'red.700')
  const errorText = useColorModeValue('red.700', 'red.200')
  const streamingBg = useColorModeValue('orange.50', 'orange.900')
  const streamingBorder = useColorModeValue('orange.200', 'orange.700')
  const breadcrumbColor = useColorModeValue('gray.600', 'gray.300')
  const currentToolColor = useColorModeValue('orange.600', 'orange.300')
  const progressBarBg = useColorModeValue('orange.100', 'orange.800')

  if (!isStreaming && phase === 'final') {
    return (
      <HStack
        mt={3}
        px={3}
        py={2}
        bg={completeBg}
        borderWidth="1px"
        borderColor={completeBorder}
        borderRadius="lg"
        spacing={2}
      >
        <CheckIcon color="green.500" boxSize={3} />
        <Text fontSize="sm" color={completeText}>
          Complete • {streamSeconds}s{toolHistory.length > 0 && ` • ${toolHistory.length} tools`}
        </Text>
      </HStack>
    )
  }

  if (phase === 'error') {
    return (
      <Box mt={3} px={3} py={2} bg={errorBg} borderWidth="1px" borderColor={errorBorder} borderRadius="lg">
        <HStack spacing={2}>
          <WarningIcon color="red.500" boxSize={3} />
          <Text fontSize="sm" color={errorText}>
            Error • {streamSeconds}s
          </Text>
        </HStack>
        {errorMessage && (
          <Text fontSize="xs" color={errorText} mt={1} opacity={0.8}>
            {errorMessage}
          </Text>
        )}
      </Box>
    )
  }

  return (
    <Box mt={3} px={4} py={3} bg={streamingBg} borderRadius="xl" borderWidth="1px" borderColor={streamingBorder}>
      <HStack justify="space-between">
        <HStack spacing={2}>
          <Spinner size="sm" color="orange.500" />
          <Text fontWeight="600" fontSize="sm">
            {phase === 'thinking' ? 'Thinking' : 'Working'}
          </Text>
        </HStack>
        <Tag size="sm" colorScheme="orange">
          {streamSeconds}s
        </Tag>
      </HStack>

      {(toolHistory.length > 0 || currentTool) && (
        <HStack mt={2} spacing={1} flexWrap="wrap" fontSize="sm">
          {toolHistory.map((tool, i) => (
            <Fragment key={i}>
              <Text color={breadcrumbColor}>{formatToolName(tool)}</Text>
              <Text color="gray.400">→</Text>
            </Fragment>
          ))}
          {currentTool && (
            <Text fontWeight="700" fontSize="md" color={currentToolColor}>
              {formatToolName(currentTool)}
            </Text>
          )}
        </HStack>
      )}

      {toolCallsTotal > 0 && (
        <Box mt={2}>
          <Text fontSize="xs" color={breadcrumbColor} mb={1}>
            {toolCallsDone}/{toolCallsTotal} tools
          </Text>
          <Box height="4px" borderRadius="full" bg={progressBarBg} overflow="hidden">
            <Box height="100%" width={`${progressPct}%`} bg="orange.400" transition="width 0.2s" />
          </Box>
        </Box>
      )}
    </Box>
  )
}

function parseThinkingContent(content: string): { thinking: string | null; main: string } {
  // Match complete <think>...</think> blocks
  const thinkMatch = content.match(/<think>([\s\S]*?)<\/think>/)
  if (thinkMatch) {
    const thinking = thinkMatch[1].trim()
    const main = content.replace(/<think>[\s\S]*?<\/think>\s*/, '').trim()
    return { thinking, main }
  }
  // Match unclosed <think> tags (streaming/truncated)
  const unclosedMatch = content.match(/<think>([\s\S]*)$/)
  if (unclosedMatch) {
    return { thinking: unclosedMatch[1].trim(), main: '' }
  }
  return { thinking: null, main: content }
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'
  const { isOpen: isThinkingOpen, onToggle: onThinkingToggle } = useDisclosure({ defaultIsOpen: false })
  const userBg = useColorModeValue('brand.50', 'brand.900')
  const assistantBg = useColorModeValue('white', 'gray.700')
  const systemBg = useColorModeValue('gray.50', 'gray.750')
  const userBorder = useColorModeValue('brand.100', 'brand.700')
  const assistantBorder = useColorModeValue('gray.100', 'gray.600')
  const systemBorder = useColorModeValue('brand.200', 'brand.600')
  const contentColor = useColorModeValue('gray.800', 'gray.100')
  const strongColor = useColorModeValue('gray.900', 'white')
  const codeBackground = useColorModeValue('orange.50', 'whiteAlpha.200')
  const thinkingBg = useColorModeValue('purple.50', 'purple.900')
  const thinkingBorder = useColorModeValue('purple.200', 'purple.700')
  const thinkingText = useColorModeValue('purple.700', 'purple.200')
  const bg = isUser ? userBg : isSystem ? systemBg : assistantBg
  const border = isUser ? userBorder : isSystem ? systemBorder : assistantBorder

  const { thinking, main } = useMemo(
    () => (message.role === 'assistant' ? parseThinkingContent(message.content) : { thinking: null, main: message.content }),
    [message.content, message.role]
  )

  return (
    <Box
      alignSelf={isUser ? 'flex-end' : 'flex-start'}
      maxW="90%"
      bg={bg}
      borderColor={border}
      borderWidth="1px"
      borderLeftWidth={isSystem ? '3px' : '1px'}
      borderLeftColor={isSystem ? 'brand.400' : border}
      borderRadius="xl"
      px={4}
      py={3}
      shadow="sm"
    >
      <HStack justify="space-between" mb={2}>
        <Tag size="xs" variant="subtle" colorScheme={isUser ? 'brand' : 'gray'}>
          {isUser ? 'You' : isSystem ? 'System' : 'FDA Agent'}
        </Tag>
        {message.streaming && <Spinner size="sm" color="brand.500" />}
      </HStack>

      {thinking && (
        <Box mb={3}>
          <HStack
            spacing={1}
            cursor="pointer"
            onClick={onThinkingToggle}
            color={thinkingText}
            fontSize="sm"
            fontWeight="500"
            _hover={{ opacity: 0.8 }}
          >
            {isThinkingOpen ? <ChevronUpIcon boxSize={4} /> : <ChevronDownIcon boxSize={4} />}
            <Text>💭 Reasoning {message.streaming && !main ? '...' : ''}</Text>
          </HStack>
          <Collapse in={isThinkingOpen} animateOpacity>
            <Box
              mt={2}
              p={3}
              bg={thinkingBg}
              borderWidth="1px"
              borderColor={thinkingBorder}
              borderRadius="md"
              fontSize="sm"
              fontStyle="italic"
              color={thinkingText}
              whiteSpace="pre-wrap"
            >
              {thinking}
            </Box>
          </Collapse>
        </Box>
      )}

      <Box
        color={contentColor}
        sx={{
          p: { marginTop: 0, marginBottom: 2, whiteSpace: 'pre-wrap' },
          ul: { paddingLeft: 6, marginBottom: 3 },
          ol: { paddingLeft: 6, marginBottom: 3 },
          li: { marginBottom: 1 },
          strong: { color: strongColor },
          code: {
            fontSize: '0.9em',
            background: codeBackground,
            paddingX: 1.5,
            paddingY: 0.5,
            borderRadius: 'md',
          },
          h1: { fontSize: '1.1rem', fontWeight: 700, marginBottom: 2 },
          h2: { fontSize: '1.05rem', fontWeight: 700, marginBottom: 2 },
          h3: { fontSize: '1rem', fontWeight: 700, marginBottom: 2 },
        }}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{main || (thinking ? '' : '...')}</ReactMarkdown>
        {!isUser && message.role !== 'system' && message.streaming && (
          <Box
            as="span"
            ml={1}
            display="inline-block"
            width="8px"
            height="16px"
            borderRadius="sm"
            background="orange.400"
            animation="pulse-glow 1.2s ease-in-out infinite"
            aria-hidden="true"
          />
        )}
      </Box>
      {!isUser && message.role !== 'system' && message.streaming && !thinking && (
        <Text mt={2} fontSize="sm" color="orange.600">
          Thinking...
        </Text>
      )}
      {!isUser && message.role !== 'system' && !message.streaming && message.structuredData && (
        <StructuredDataTable data={message.structuredData as Parameters<typeof StructuredDataTable>[0]['data']} />
      )}
      {!isUser && message.role !== 'system' && message.meta && (message.meta.inputTokens !== undefined || message.meta.outputTokens !== undefined) && (
        <HStack spacing={2} mt={3} wrap="wrap">
          {message.meta.inputTokens !== undefined && (
            <Tag size="sm" variant="subtle">
              In: {message.meta.inputTokens}
            </Tag>
          )}
          {message.meta.outputTokens !== undefined && (
            <Tag size="sm" variant="subtle">
              Out: {message.meta.outputTokens}
            </Tag>
          )}
        </HStack>
      )}
    </Box>
  )
}
