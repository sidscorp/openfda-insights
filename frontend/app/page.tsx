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
  Input,
  Spinner,
  Stack,
  Tag,
  Text,
  Textarea,
  Tooltip,
  useToast,
  VStack,
} from '@chakra-ui/react'
import { CloseIcon } from '@chakra-ui/icons'
import { apiClient, type AgentStreamEvent } from '@/lib/api'

type Role = 'user' | 'assistant' | 'system'

interface ChatMessage {
  id: string
  role: Role
  content: string
  streaming?: boolean
}

const starterPrompts = [
  'Summarize recent adverse events for pacemakers',
  'Any recalls for insulin pumps mentioning battery issues?',
  'Compare MAUDE signals for endoscopy towers vs laparoscopic cameras',
]

export default function Home() {
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
  const eventSourceRef = useRef<EventSource | null>(null)
  const toast = useToast()

  const endOfChatRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    endOfChatRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

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

    const es = apiClient.openAgentStream(text, {
      onEvent: (event: AgentStreamEvent) => {
        setMessages((prev) =>
          prev.map((m) => {
            if (m.id !== assistantMessage.id) return m
            switch (event.type) {
              case 'thinking':
              case 'tool_result':
                return { ...m, content: (m.content + '\n' + event.content).trim(), streaming: true }
              case 'complete':
                return { ...m, content: event.answer, streaming: false }
              case 'error':
                return { ...m, content: `Error: ${event.message}`, streaming: false }
              case 'tool_call':
                return {
                  ...m,
                  content: (m.content + `\n[Running ${event.tool}...]`).trim(),
                  streaming: true,
                }
              case 'start':
              default:
                return m
            }
          })
        )

        if (event.type === 'complete' || event.type === 'error') {
          setIsStreaming(false)
          es.close()
          eventSourceRef.current = null
        }
      },
      onError: (err) => {
        setIsStreaming(false)
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
              <Tag colorScheme={isStreaming ? 'green' : 'gray'} variant="subtle">
                API: {guidance.api}
              </Tag>
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
                  <MessageBubble key={m.id} message={m} />
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
      <Text whiteSpace="pre-wrap" color="gray.800">
        {message.content || '...'}
      </Text>
    </Box>
  )
}
