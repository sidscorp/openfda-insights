'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import {
  Session,
  StoredMessage,
  saveSession,
  getSession,
  listSessions,
  deleteSession as deleteSessionFromDB,
  saveMessage,
  getMessages,
} from './storage';

interface SessionContextType {
  sessions: Session[];
  currentSession: Session | null;
  currentMessages: StoredMessage[];
  isLoading: boolean;
  createSession: () => string;
  loadSession: (id: string) => Promise<void>;
  deleteSession: (id: string) => Promise<void>;
  updateSessionTitle: (id: string, title: string) => Promise<void>;
  addMessage: (message: Omit<StoredMessage, 'id' | 'sessionId' | 'timestamp'>, existingId?: string) => Promise<StoredMessage>;
  refreshSessions: () => Promise<void>;
}

const SessionContext = createContext<SessionContextType | null>(null);

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

interface SessionProviderProps {
  children: ReactNode;
}

export function SessionProvider({ children }: SessionProviderProps) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [currentMessages, setCurrentMessages] = useState<StoredMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const refreshSessions = useCallback(async () => {
    try {
      const allSessions = await listSessions();
      setSessions(allSessions);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      try {
        await refreshSessions();
      } finally {
        setIsLoading(false);
      }
    };
    init();
  }, [refreshSessions]);

  const createSession = useCallback((): string => {
    const id = generateId();
    const now = new Date().toISOString();
    const session: Session = {
      id,
      title: 'New Chat',
      createdAt: now,
      updatedAt: now,
      messageCount: 0,
    };

    setCurrentSession(session);
    setCurrentMessages([]);

    return id;
  }, []);

  const loadSession = useCallback(async (id: string) => {
    setIsLoading(true);
    try {
      const session = await getSession(id);
      if (session) {
        setCurrentSession(session);
        const messages = await getMessages(id);
        setCurrentMessages(messages);
      }
    } catch (error) {
      console.error('Failed to load session:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const deleteSession = useCallback(async (id: string) => {
    try {
      await deleteSessionFromDB(id);
      setSessions(prev => prev.filter(s => s.id !== id));
      if (currentSession?.id === id) {
        setCurrentSession(null);
        setCurrentMessages([]);
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  }, [currentSession]);

  const updateSessionTitle = useCallback(async (id: string, title: string) => {
    try {
      const session = await getSession(id);
      if (session) {
        const updated = { ...session, title, updatedAt: new Date().toISOString() };
        await saveSession(updated);
        setSessions(prev => prev.map(s => s.id === id ? updated : s));
        if (currentSession?.id === id) {
          setCurrentSession(updated);
        }
      }
    } catch (error) {
      console.error('Failed to update session title:', error);
    }
  }, [currentSession]);

  const addMessage = useCallback(async (
    messageData: Omit<StoredMessage, 'id' | 'sessionId' | 'timestamp'>,
    existingId?: string
  ): Promise<StoredMessage> => {
    if (!currentSession) {
      throw new Error('No current session');
    }

    const message: StoredMessage = {
      ...messageData,
      id: existingId || generateId(),
      sessionId: currentSession.id,
      timestamp: new Date().toISOString(),
    };

    await saveMessage(message);
    setCurrentMessages(prev => [...prev, message]);

    const updatedSession = {
      ...currentSession,
      messageCount: currentSession.messageCount + 1,
      updatedAt: new Date().toISOString(),
    };
    await saveSession(updatedSession);
    setCurrentSession(updatedSession);

    setSessions(prev => {
      const filtered = prev.filter(s => s.id !== updatedSession.id);
      return [updatedSession, ...filtered];
    });

    return message;
  }, [currentSession]);

  const value: SessionContextType = {
    sessions,
    currentSession,
    currentMessages,
    isLoading,
    createSession,
    loadSession,
    deleteSession,
    updateSessionTitle,
    addMessage,
    refreshSessions,
  };

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
}
