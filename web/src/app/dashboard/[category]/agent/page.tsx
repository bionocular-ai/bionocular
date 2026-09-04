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
        {/* Same measure and gutters as the thread and composer below, so the
            header, the messages and the input all share one left edge. */}
        <div className="shrink-0 px-4 pt-6 pb-4 sm:px-8">
          <PageHeader
            className="mx-auto w-full max-w-3xl"
            category={categoryName}
            title="Bionocular Agent"
            description="Bionocular's own data only - no live registries or literature."
          />
        </div>

        <div className="min-h-0 flex-1">
          <ChatPanel
            key={chat.id}
            cancerType={categorySlug}
            sessionId={chat.id}
            initialMessages={chat.messages}
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
