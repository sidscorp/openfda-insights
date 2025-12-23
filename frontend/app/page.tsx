'use client'

import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
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
  useColorMode,
  useColorModeValue,
  useToast,
  VStack,
} from '@chakra-ui/react'
import { AddIcon, CheckIcon, CloseIcon, MoonIcon, SunIcon, WarningIcon } from '@chakra-ui/icons'
import { apiClient, type AgentStreamEvent } from '@/lib/api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { StructuredDataTable } from '@/components/StructuredDataTable'

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
}

const starterPrompts = [
  'Summarize recent adverse events for pacemakers',
  'Any recalls for insulin pumps mentioning battery issues?',
  'Compare MAUDE signals for endoscopy towers vs laparoscopic cameras',
]

const TOKEN_WARNING_THRESHOLD = 50000
const TOKEN_LIMIT = 100000

export default function Home() {
  const { colorMode, toggleColorMode } = useColorMode()
  const subtitleColor = useColorModeValue('gray.600', 'gray.200')
  const sectionLabelColor = useColorModeValue('gray.600', 'gray.300')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'system',
      role: 'system',
      content:
        'I analyze FDA device data (MAUDE, recalls, 510(k), PMA). Ask about devices, manufacturers, risks, or trends.',
    },
  ])
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
  const [sessionId] = useState(() => crypto.randomUUID())
  const [sessionTokens, setSessionTokens] = useState(0)
  const eventSourceRef = useRef<EventSource | null>(null)
  const hasDeltaRef = useRef(false)
  const streamCompletedRef = useRef(false)
  const toast = useToast()

  const endOfChatRef = useRef<HTMLDivElement | null>(null)
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

  const handleNewChat = () => {
    window.location.reload()
  }

  const handleSend = (prompt?: string) => {
    const text = prompt ?? input.trim()
    if (!text || isStreaming) return

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

    const es = apiClient.openAgentStream(text, {
      onEvent: (event: AgentStreamEvent) => {
        if (event.type === 'clear') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMessage.id ? { ...m, content: '' } : m
            )
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
        } else if (event.type === 'tool_result') {
          setCurrentTool(null)
          setToolCallsDone((prev) => prev + 1)
        } else if (event.type === 'complete') {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantMessage.id) return m
              return {
                ...m,
                content: hasDeltaRef.current ? m.content : event.answer,
                streaming: false,
                meta: {
                  model: event.model,
                  tokens: event.tokens,
                  inputTokens: event.input_tokens,
                  outputTokens: event.output_tokens,
                  cost: event.cost,
                },
                structuredData: event.structured_data || undefined,
              }
            })
          )
          setCurrentTool(null)
          setStreamStatus({ phase: 'final', message: '' })
        } else if (event.type === 'error') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMessage.id ? { ...m, content: `Error: ${event.message}`, streaming: false } : m
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
        // Don't show error popup if the stream completed successfully
        if (streamCompletedRef.current) {
          return
        }
        
        setIsStreaming(false)
        setCurrentTool(null)
        setErrorMessage(err || 'Connection lost')
        setStreamStatus({ phase: 'error', message: err || 'Connection lost' })
        setActiveUserMessageId(null)
        setMessages((prev) =>
          prev.map((m) => (m.streaming ? { ...m, streaming: false, content: `${m.content}\n${err}` } : m))
        )
        toast({
          title: 'Connection lost',
          description: err || 'Check the API URL and server status.',
          status: 'error',
          duration: 4000,
          isClosable: true,
        })
      },
    }, sessionId)

    eventSourceRef.current = es
  }

  const handleStop = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setIsStreaming(false)
    setStreamCompleted(true) // Mark as completed to prevent error popup
    setStreamStatus(null)
    setToolHistory([])
    setCurrentTool(null)
    setErrorMessage(null)
    setToolCallsTotal(0)
    setToolCallsDone(0)
    setActiveUserMessageId(null)
    setMessages((prev) => prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)))
  }

  const guidance = useMemo(
    () => ({
      api: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api',
    }),
    []
  )

  return (
    <Container maxW="5xl" py={{ base: 6, md: 10 }}>
      <Stack spacing={6}>
        <Card borderColor="blackAlpha.100">
          <CardBody>
            <Stack spacing={3} direction={{ base: 'column', md: 'row' }} justify="space-between" align="start">
              <Box>
                <Heading size="lg">FDA Explorer</Heading>
                <Text color={subtitleColor}>Ask questions about device events, recalls, and approvals.</Text>
              </Box>
              <HStack spacing={3}>
                <Tag colorScheme={isStreaming ? 'green' : 'gray'} variant="subtle">
                  API: {guidance.api}
                </Tag>
                {sessionTokens > 0 && (
                  <Tag size="sm" variant="subtle" colorScheme={sessionTokens > TOKEN_WARNING_THRESHOLD ? 'orange' : 'gray'}>
                    {Math.round(sessionTokens / 1000)}k tokens
                  </Tag>
                )}
                <Tooltip label="Start new conversation">
                  <IconButton
                    aria-label="New chat"
                    icon={<AddIcon />}
                    onClick={handleNewChat}
                    variant="ghost"
                    size="sm"
                  />
                </Tooltip>
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

        <Card>
          <CardHeader pb={2}>
            <HStack justify="space-between">
              <Text fontWeight="600" color={sectionLabelColor}>
                Chat
              </Text>
              {isStreaming && (
                <Tooltip label="Stop streaming">
                  <IconButton aria-label="Stop" icon={<CloseIcon boxSize={3} />} size="sm" onClick={handleStop} />
                </Tooltip>
              )}
            </HStack>
          </CardHeader>
          <CardBody pt={0}>
            <Stack spacing={4}>
              <VStack align="stretch" spacing={4} maxH="60vh" overflowY="auto" pr={1}>
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
                <div ref={endOfChatRef} />
              </VStack>

              {sessionTokens > TOKEN_LIMIT && (
                <Alert status="error" borderRadius="md">
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
                <Alert status="warning" borderRadius="md">
                  <AlertIcon />
                  <Box flex="1">
                    <Text fontSize="sm">
                      Conversation is getting long ({Math.round(sessionTokens / 1000)}k tokens).
                      Consider starting a new chat soon.
                    </Text>
                  </Box>
                  <Button size="sm" variant="outline" onClick={handleNewChat}>
                    New Chat
                  </Button>
                </Alert>
              )}

              <Stack direction={{ base: 'column', md: 'row' }} spacing={3}>
                <Textarea
                  placeholder={sessionTokens > TOKEN_LIMIT ? 'Token limit reached - start new chat' : 'Ask about a device, manufacturer, or risk signal...'}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  isDisabled={isStreaming || sessionTokens > TOKEN_LIMIT}
                  rows={3}
                />
                <Button
                  colorScheme="brand"
                  onClick={() => handleSend()}
                  isDisabled={!canSend}
                  minW={{ md: '120px' }}
                >
                  {isStreaming ? 'Streaming...' : 'Send'}
                </Button>
              </Stack>

              <HStack spacing={2} wrap="wrap">
                {starterPrompts.map((p) => (
                  <Button key={p} size="sm" variant="outline" onClick={() => handleSend(p)} isDisabled={isStreaming}>
                    {p}
                  </Button>
                ))}
              </HStack>
            </Stack>
          </CardBody>
        </Card>
      </Stack>
    </Container>
  )
}

function formatToolName(tool: string): string {
  return tool.replace(/_/g, ' ').replace(/^search /, '')
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

  // Completed state - minimal single line
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

  // Error state
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

  // Streaming state - breadcrumb layout
  return (
    <Box
      mt={3}
      px={4}
      py={3}
      bg={streamingBg}
      borderRadius="xl"
      borderWidth="1px"
      borderColor={streamingBorder}
    >
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

      {/* Breadcrumb trail */}
      {(toolHistory.length > 0 || currentTool) && (
        <HStack mt={2} spacing={1} flexWrap="wrap" fontSize="xs">
          {toolHistory.map((tool, i) => (
            <Fragment key={i}>
              <Text color={breadcrumbColor}>{formatToolName(tool)}</Text>
              <Text color="gray.400">→</Text>
            </Fragment>
          ))}
          {currentTool && (
            <Text fontWeight="600" color={currentToolColor}>
              [{formatToolName(currentTool)}...]
            </Text>
          )}
        </HStack>
      )}

      {/* Progress bar */}
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

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  const userBg = useColorModeValue('brand.50', 'brand.900')
  const assistantBg = useColorModeValue('white', 'gray.700')
  const userBorder = useColorModeValue('brand.100', 'brand.700')
  const assistantBorder = useColorModeValue('gray.100', 'gray.600')
  const contentColor = useColorModeValue('gray.800', 'gray.100')
  const strongColor = useColorModeValue('gray.900', 'white')
  const codeBackground = useColorModeValue('orange.50', 'whiteAlpha.200')
  const bg = isUser ? userBg : assistantBg
  const border = isUser ? userBorder : assistantBorder

  return (
    <Box
      alignSelf={isUser ? 'flex-end' : 'flex-start'}
      maxW="90%"
      bg={bg}
      borderColor={border}
      borderWidth="1px"
      borderRadius="xl"
      px={4}
      py={3}
      shadow="sm"
    >
      <HStack justify="space-between" mb={2}>
        <Tag size="sm" colorScheme={isUser ? 'brand' : 'gray'}>
          {isUser ? 'You' : message.role === 'system' ? 'System' : 'FDA Agent'}
        </Tag>
        {message.streaming && <Spinner size="sm" color="brand.500" />}
      </HStack>
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
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {message.content || '...'}
        </ReactMarkdown>
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
      {!isUser && message.role !== 'system' && message.streaming && (
        <Text mt={2} fontSize="sm" color="orange.600">
          Thinking...
        </Text>
      )}
      {!isUser && message.role !== 'system' && !message.streaming && message.structuredData && (
        <StructuredDataTable data={message.structuredData as Parameters<typeof StructuredDataTable>[0]['data']} />
      )}
      {!isUser && message.role !== 'system' && message.meta && (
        <HStack spacing={2} mt={3} wrap="wrap">
          {message.meta.model && (
            <Tag size="sm" variant="subtle">
              Model: {message.meta.model}
            </Tag>
          )}
          {message.meta.tokens !== undefined && (
            <Tag size="sm" variant="subtle">
              Tokens: {message.meta.tokens}
            </Tag>
          )}
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
          <Tag size="sm" variant="subtle">
            Cost: {message.meta.cost != null ? `$${message.meta.cost.toFixed(4)}` : 'n/a'}
          </Tag>
        </HStack>
      )}
    </Box>
  )
}
