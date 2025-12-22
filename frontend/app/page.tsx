'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
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
  useToast,
  VStack,
} from '@chakra-ui/react'
import { CloseIcon, MoonIcon, SunIcon } from '@chakra-ui/icons'
import { apiClient, type AgentStreamEvent } from '@/lib/api'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

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
}

type StepStatus = 'queued' | 'running' | 'done' | 'error'

interface StreamStep {
  id: string
  label: string
  status: StepStatus
  detail?: string
}

const starterPrompts = [
  'Summarize recent adverse events for pacemakers',
  'Any recalls for insulin pumps mentioning battery issues?',
  'Compare MAUDE signals for endoscopy towers vs laparoscopic cameras',
]

export default function Home() {
  const { colorMode, toggleColorMode } = useColorMode()
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
  const [streamSteps, setStreamSteps] = useState<StreamStep[]>([])
  const [showThinking, setShowThinking] = useState(true)
  const [toolCallsTotal, setToolCallsTotal] = useState(0)
  const [toolCallsDone, setToolCallsDone] = useState(0)
  const [activeUserMessageId, setActiveUserMessageId] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const hasDeltaRef = useRef(false)
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

  const canSend = input.trim().length > 0 && !isStreaming

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
    setStreamCompleted(false)
    setStreamStatus({ phase: 'thinking', message: 'Waiting for the model to respond...' })
    setStreamSteps([
      { id: 'queue', label: 'Queueing request', status: 'done' },
      { id: 'thinking', label: 'Interpreting question', status: 'running' },
    ])
    setShowThinking(true)
    setToolCallsTotal(0)
    setToolCallsDone(0)
    setActiveUserMessageId(userMessage.id)
    hasDeltaRef.current = false

    const es = apiClient.openAgentStream(text, {
      onEvent: (event: AgentStreamEvent) => {
        if (event.type === 'thinking') {
          setStreamStatus({ phase: 'thinking', message: event.content })
          setStreamSteps((prev) =>
            prev.map((step) =>
              step.id === 'thinking' ? { ...step, status: 'running' as StepStatus, detail: event.content } : step
            )
          )
        } else if (event.type === 'delta') {
          hasDeltaRef.current = true
          setStreamStatus({ phase: 'final', message: 'Drafting response...' })
          setStreamSteps((prev) => {
            const next = prev.map((step) =>
              step.status === 'running' ? { ...step, status: 'done' as StepStatus } : step
            )
            const hasDraft = next.some((step) => step.id === 'draft')
            if (!hasDraft) {
              next.push({ id: 'draft', label: 'Drafting response', status: 'running' as StepStatus })
            }
            return next
          })
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMessage.id
                ? { ...m, content: `${m.content}${event.content}`, streaming: true }
                : m
            )
          )
        } else if (event.type === 'tool_call') {
          setStreamStatus({ phase: 'tool', message: `Running ${event.tool}...` })
          setToolCallsTotal((prev) => prev + 1)
          setStreamSteps((prev) => {
            const next = prev.map((step) =>
              step.status === 'running' ? { ...step, status: 'done' as StepStatus } : step
            )
            return [
              ...next,
              {
                id: `tool-${event.tool}-${Date.now()}`,
                label: `Querying ${event.tool.replace(/_/g, ' ')}`,
                status: 'running' as StepStatus,
              },
            ]
          })
        } else if (event.type === 'tool_result') {
          setStreamStatus({ phase: 'tool', message: 'Processing tool results...' })
          setToolCallsDone((prev) => prev + 1)
          setStreamSteps((prev) => {
            const next = prev.map((step) =>
              step.status === 'running' ? { ...step, status: 'done' as StepStatus } : step
            )
            next.push({
              id: `synth-${Date.now()}`,
              label: 'Synthesizing findings',
              status: 'running' as StepStatus,
            })
            return next
          })
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
              }
            })
          )
          setStreamStatus({ phase: 'final', message: 'Answer ready.' })
          setStreamSteps((prev) =>
            prev
              .map((step) => (step.status === 'running' ? { ...step, status: 'done' as StepStatus } : step))
              .concat({
                id: 'done',
                label: 'Response delivered',
                status: 'done' as StepStatus,
              })
          )
        } else if (event.type === 'error') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMessage.id ? { ...m, content: `Error: ${event.message}`, streaming: false } : m
            )
          )
          setStreamStatus({ phase: 'error', message: event.message })
          setStreamSteps((prev) =>
            prev
              .map((step) => (step.status === 'running' ? { ...step, status: 'error' as StepStatus } : step))
              .concat({
                id: 'error',
                label: 'Request failed',
                status: 'error' as StepStatus,
                detail: event.message,
              })
          )
        }

        if (event.type === 'complete' || event.type === 'error') {
          setIsStreaming(false)
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
        if (streamCompleted) {
          return
        }
        
        setIsStreaming(false)
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
    })

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
    setStreamSteps([])
    setShowThinking(false)
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
                <Text color="gray.600">Ask questions about device events, recalls, and approvals.</Text>
              </Box>
              <HStack spacing={3}>
                <Tag colorScheme={isStreaming ? 'green' : 'gray'} variant="subtle">
                  API: {guidance.api}
                </Tag>
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
              <Text fontWeight="600" color="gray.600">
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
                        streamStatus={streamStatus}
                        streamSteps={streamSteps}
                        showThinking={showThinking}
                        onToggle={() => setShowThinking((prev) => !prev)}
                        toolCallsDone={toolCallsDone}
                        toolCallsTotal={toolCallsTotal}
                      />
                    )}
                  </Box>
                ))}
                <div ref={endOfChatRef} />
              </VStack>

              <Stack direction={{ base: 'column', md: 'row' }} spacing={3}>
                <Textarea
                  placeholder="Ask about a device, manufacturer, or risk signal..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  isDisabled={isStreaming}
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

function ThinkingPanel({
  isStreaming,
  streamSeconds,
  streamStatus,
  streamSteps,
  showThinking,
  onToggle,
  toolCallsDone,
  toolCallsTotal,
}: {
  isStreaming: boolean
  streamSeconds: number
  streamStatus: { phase: StreamPhase; message: string }
  streamSteps: StreamStep[]
  showThinking: boolean
  onToggle: () => void
  toolCallsDone: number
  toolCallsTotal: number
}) {
  const progressPct =
    toolCallsTotal > 0 ? Math.min(100, Math.round((toolCallsDone / toolCallsTotal) * 100)) : 0

  return (
    <Box
      mt={3}
      borderRadius="xl"
      borderWidth="1px"
      borderColor={streamStatus.phase === 'error' ? 'red.200' : 'orange.200'}
      bg={streamStatus.phase === 'error' ? 'red.50' : 'orange.50'}
      px={4}
      py={3}
    >
      <HStack justify="space-between" align="start">
        <HStack spacing={3}>
          {isStreaming ? <Spinner size="sm" color="orange.500" /> : <Tag size="sm">Status</Tag>}
          <Text fontWeight="600">
            {streamStatus.phase === 'thinking' && 'Thinking'}
            {streamStatus.phase === 'tool' && 'Working'}
            {streamStatus.phase === 'final' && 'Complete'}
            {streamStatus.phase === 'error' && 'Error'}
          </Text>
        </HStack>
        <HStack spacing={2}>
          {!isStreaming && (
            <Button size="xs" variant="ghost" onClick={onToggle}>
              {showThinking ? 'Hide steps' : 'Show steps'}
            </Button>
          )}
          <Tag size="sm" colorScheme={streamStatus.phase === 'error' ? 'red' : 'orange'}>
            {isStreaming ? `Live • ${streamSeconds}s` : 'Idle'}
          </Tag>
        </HStack>
      </HStack>
      {showThinking && (
        <>
          <Text mt={2} color="gray.700">
            {streamStatus.message}
          </Text>
          {toolCallsTotal > 0 && (
            <Box mt={3}>
              <HStack justify="space-between" mb={1}>
                <Text fontSize="xs" color="gray.600">
                  Tool calls
                </Text>
                <Text fontSize="xs" color="gray.600">
                  {toolCallsDone}/{toolCallsTotal}
                </Text>
              </HStack>
              <Box height="6px" borderRadius="full" bg="orange.100" overflow="hidden">
                <Box height="100%" width={`${progressPct}%`} bg="orange.400" transition="width 0.3s ease" />
              </Box>
            </Box>
          )}
          {streamSteps.length > 0 && (
            <Stack spacing={2} mt={3}>
              {streamSteps.slice(-5).map((step) => (
                <HStack key={step.id} spacing={2} align="start">
                  <Tag
                    size="sm"
                    colorScheme={step.status === 'done' ? 'green' : step.status === 'error' ? 'red' : 'orange'}
                    variant={step.status === 'running' ? 'solid' : 'subtle'}
                  >
                    {step.status === 'done' && 'Done'}
                    {step.status === 'running' && 'Now'}
                    {step.status === 'queued' && 'Next'}
                    {step.status === 'error' && 'Fail'}
                  </Tag>
                  <Box>
                    <Text fontSize="sm" color="gray.800">
                      {step.label}
                    </Text>
                    {step.detail && (
                      <Text fontSize="xs" color="gray.600">
                        {step.detail}
                      </Text>
                    )}
                  </Box>
                </HStack>
              ))}
            </Stack>
          )}
        </>
      )}
    </Box>
  )
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  const bg = isUser ? 'brand.50' : 'white'
  const border = isUser ? 'brand.100' : 'gray.100'

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
        color="gray.800"
        sx={{
          p: { marginTop: 0, marginBottom: 2, whiteSpace: 'pre-wrap' },
          ul: { paddingLeft: 6, marginBottom: 3 },
          ol: { paddingLeft: 6, marginBottom: 3 },
          li: { marginBottom: 1 },
          strong: { color: 'gray.900' },
          code: {
            fontSize: '0.9em',
            background: 'orange.50',
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
