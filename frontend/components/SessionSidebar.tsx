'use client';

import { useState, useRef, useEffect } from 'react';
import {
  Box,
  Button,
  Divider,
  HStack,
  IconButton,
  Input,
  Link,
  Text,
  Tooltip,
  VStack,
  useColorModeValue,
} from '@chakra-ui/react';
import { AddIcon, DeleteIcon, EditIcon, ExternalLinkIcon } from '@chakra-ui/icons';
import { useSession } from '@/lib/session-context';
import type { Session } from '@/lib/storage';

function groupSessionsByDate(sessions: Session[]): Record<string, Session[]> {
  const groups: Record<string, Session[]> = {
    'Today': [],
    'Yesterday': [],
    'This Week': [],
    'Older': [],
  };

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  for (const session of sessions) {
    const sessionDate = new Date(session.updatedAt);
    const sessionDay = new Date(sessionDate.getFullYear(), sessionDate.getMonth(), sessionDate.getDate());

    if (sessionDay.getTime() >= today.getTime()) {
      groups['Today'].push(session);
    } else if (sessionDay.getTime() >= yesterday.getTime()) {
      groups['Yesterday'].push(session);
    } else if (sessionDay.getTime() >= weekAgo.getTime()) {
      groups['This Week'].push(session);
    } else {
      groups['Older'].push(session);
    }
  }

  return groups;
}

export function SessionSidebar() {
  const { sessions, currentSession, createSession, loadSession, deleteSession, updateSessionTitle } = useSession();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const hoverBg = useColorModeValue('gray.100', 'gray.700');
  const activeBg = useColorModeValue('brand.50', 'brand.900');
  const activeBorder = useColorModeValue('brand.400', 'brand.500');
  const headingColor = useColorModeValue('gray.500', 'gray.400');
  const mutedColor = useColorModeValue('gray.500', 'gray.500');
  const linkColor = useColorModeValue('brand.600', 'brand.300');

  const groupedSessions = groupSessionsByDate(sessions);

  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingId]);

  const handleStartEdit = (session: Session) => {
    setEditingId(session.id);
    setEditTitle(session.title);
  };

  const handleSaveEdit = async () => {
    if (editingId && editTitle.trim()) {
      await updateSessionTitle(editingId, editTitle.trim());
    }
    setEditingId(null);
    setEditTitle('');
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditTitle('');
  };

  const handleNewChat = () => {
    createSession();
  };

  return (
    <VStack h="100%" p={4} spacing={4} align="stretch" overflow="hidden">
      <Button
        leftIcon={<AddIcon />}
        colorScheme="brand"
        onClick={handleNewChat}
        size="sm"
        w="100%"
      >
        New Chat
      </Button>

      <VStack flex="1" spacing={1} align="stretch" overflowY="auto" overflowX="hidden">
        {Object.entries(groupedSessions).map(([group, groupSessions]) => {
          if (groupSessions.length === 0) return null;
          return (
            <Box key={group} mb={2}>
              <Text fontSize="xs" fontWeight="600" color={headingColor} textTransform="uppercase" mb={1} px={2}>
                {group}
              </Text>
              <VStack spacing={1} align="stretch">
                {groupSessions.map((session) => (
                  <SessionItem
                    key={session.id}
                    session={session}
                    isActive={currentSession?.id === session.id}
                    isEditing={editingId === session.id}
                    editTitle={editTitle}
                    onSelect={() => loadSession(session.id)}
                    onDelete={() => deleteSession(session.id)}
                    onStartEdit={() => handleStartEdit(session)}
                    onSaveEdit={handleSaveEdit}
                    onCancelEdit={handleCancelEdit}
                    onEditTitleChange={setEditTitle}
                    inputRef={inputRef}
                    hoverBg={hoverBg}
                    activeBg={activeBg}
                    activeBorder={activeBorder}
                  />
                ))}
              </VStack>
            </Box>
          );
        })}
      </VStack>

      <Box flexShrink={0}>
        <Divider mb={3} />
        <VStack spacing={2} align="stretch" px={1}>
          <Text fontSize="xs" color={mutedColor} lineHeight="tall">
            AI-powered FDA medical device research tool.
            Built by{' '}
            <Link
              href="https://www.linkedin.com/in/siddnambiar/"
              isExternal
              color={linkColor}
              fontWeight="500"
            >
              Dr. Sidd Nambiar
            </Link>
            {' '}with the assistance of Claude Code, lots of coffee, and patience.
          </Text>
          <HStack spacing={3} flexWrap="wrap">
            <Link
              href="https://open.fda.gov/"
              isExternal
              fontSize="xs"
              color={linkColor}
            >
              OpenFDA <ExternalLinkIcon mx="1px" boxSize={2} />
            </Link>
            <Link
              href="https://accessgudid.nlm.nih.gov/"
              isExternal
              fontSize="xs"
              color={linkColor}
            >
              AccessGUDID <ExternalLinkIcon mx="1px" boxSize={2} />
            </Link>
          </HStack>
        </VStack>
      </Box>
    </VStack>
  );
}

interface SessionItemProps {
  session: Session;
  isActive: boolean;
  isEditing: boolean;
  editTitle: string;
  onSelect: () => void;
  onDelete: () => void;
  onStartEdit: () => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
  onEditTitleChange: (value: string) => void;
  inputRef: React.RefObject<HTMLInputElement>;
  hoverBg: string;
  activeBg: string;
  activeBorder: string;
}

function SessionItem({
  session,
  isActive,
  isEditing,
  editTitle,
  onSelect,
  onDelete,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onEditTitleChange,
  inputRef,
  hoverBg,
  activeBg,
  activeBorder,
}: SessionItemProps) {
  if (isEditing) {
    return (
      <HStack px={2} py={1}>
        <Input
          ref={inputRef}
          size="sm"
          value={editTitle}
          onChange={(e) => onEditTitleChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') onSaveEdit();
            if (e.key === 'Escape') onCancelEdit();
          }}
          onBlur={onSaveEdit}
        />
      </HStack>
    );
  }

  return (
    <HStack
      px={2}
      py={2}
      borderRadius="md"
      cursor="pointer"
      bg={isActive ? activeBg : 'transparent'}
      borderLeftWidth={isActive ? '3px' : '0'}
      borderColor={activeBorder}
      _hover={{ bg: isActive ? activeBg : hoverBg }}
      onClick={onSelect}
      role="group"
    >
      <Box flex="1" overflow="hidden">
        <Tooltip label={session.title} placement="right" hasArrow openDelay={500}>
          <Text fontSize="sm" fontWeight={isActive ? '600' : '400'} isTruncated>
            {session.title}
          </Text>
        </Tooltip>
        <Text fontSize="xs" color="gray.500">
          {session.messageCount} messages
        </Text>
      </Box>
      <HStack spacing={0} opacity={0} _groupHover={{ opacity: 1 }} transition="opacity 0.15s">
        <IconButton
          aria-label="Rename"
          icon={<EditIcon />}
          size="xs"
          variant="ghost"
          onClick={(e) => {
            e.stopPropagation();
            onStartEdit();
          }}
        />
        <IconButton
          aria-label="Delete"
          icon={<DeleteIcon />}
          size="xs"
          variant="ghost"
          colorScheme="red"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        />
      </HStack>
    </HStack>
  );
}
