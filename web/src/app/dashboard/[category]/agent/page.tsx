'use client';

import { useCallback, useState } from 'react';
import { useParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import type { UIMessage } from 'ai';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { ChatPanel } from '@/components/agent/ChatPanel';
import { ChatHistoryDrawer } from '@/components/agent/ChatHistoryDrawer';
import { chatSessionsApi } from '@/lib/api';
import { slugToCategory } from '@/lib/dashboard-constants';

/** A chat the panel has not written yet, so nothing is loaded into it. */
function newChat() {
  return { id: crypto.randomUUID(), messages: [] as UIMessage[] };
}

export default function AgentPage() {
  const params = useParams();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);
  const queryClient = useQueryClient();

  // The open conversation lives here rather than in ChatPanel so the drawer can
  // switch it. ChatPanel is keyed on the id, so a switch remounts it with the
  // transcript already in hand - useChat seeds from its props only on mount.
  const [chat, setChat] = useState(newChat);
  const [collapsed, setCollapsed] = useState(false);

  const openSession = useCallback(async (sessionId: string) => {
    const messages = await chatSessionsApi.getMessages(sessionId);
    setChat({ id: sessionId, messages });
  }, []);

  return (
    <div className="flex h-[calc(100dvh-6.5rem)] md:h-[calc(100dvh-3.5rem)]">
      <ChatHistoryDrawer
        cancerType={categorySlug}
        activeSessionId={chat.id}
        onSelect={openSession}
        onNewChat={() => setChat(newChat())}
        collapsed={collapsed}
        onCollapsedChange={setCollapsed}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1">
          <ChatPanel
            key={chat.id}
            cancerType={categorySlug}
            sessionId={chat.id}
            initialMessages={chat.messages}
            // Inside the thread rather than above it, so it scrolls away with
            // the conversation like every other dashboard page's header.
            header={<PageHeader className="pt-6 pb-4" category={categoryName} title="AI Agent" />}
            // A first turn creates the row the drawer lists, and later turns
            // move it up the list, so both have to invalidate.
            onTurnFinished={() =>
              queryClient.invalidateQueries({ queryKey: ['chat-sessions', categorySlug] })
            }
          />
        </div>
      </div>
    </div>
  );
}
