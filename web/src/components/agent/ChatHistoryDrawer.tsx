'use client';

import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PanelLeftClose, PanelLeftOpen, Plus, MessageSquare } from 'lucide-react';
import { chatSessionsApi } from '@/lib/api';
import { formatDate } from '@/lib/utils/trial-utils';
import { cn } from '@/lib/utils';

export interface ChatHistoryDrawerProps {
  /** Dashboard category slug. The list is scoped to it, as the chats were. */
  cancerType: string;
  /** Session currently open in the chat panel, highlighted in the list. */
  activeSessionId: string;
  onSelect: (sessionId: string) => void;
  onNewChat: () => void;
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
}

export function ChatHistoryDrawer({
  cancerType,
  activeSessionId,
  onSelect,
  onNewChat,
  collapsed,
  onCollapsedChange,
}: ChatHistoryDrawerProps) {
  const { data: sessions = [], isLoading } = useQuery({
    queryKey: ['chat-sessions', cancerType],
    queryFn: () => chatSessionsApi.list(cancerType),
  });

  // Cmd/Ctrl+B, so a wide data table can be given the whole width without
  // reaching for the mouse.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === 'b' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onCollapsedChange(!collapsed);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [collapsed, onCollapsedChange]);

  const ToggleIcon = collapsed ? PanelLeftOpen : PanelLeftClose;

  return (
    <aside
      aria-label="Chat history"
      className={cn(
        'hidden shrink-0 flex-col bg-(--brand-bg) transition-[width] duration-200 md:flex',
        // Collapsed the rail is a single icon, so the border would be a line
        // down an otherwise empty column.
        collapsed ? 'w-12' : 'w-64 border-r border-(--brand-border)'
      )}
    >
      <div
        className={cn(
          'flex h-12 shrink-0 items-center px-1.5',
          collapsed ? 'justify-center' : 'justify-between pl-3'
        )}
      >
        {!collapsed && (
          <span className="font-mono text-[10px] tracking-[0.12em] text-(--brand-text-muted) uppercase">
            History
          </span>
        )}
        <button
          type="button"
          onClick={() => onCollapsedChange(!collapsed)}
          title={`${collapsed ? 'Show' : 'Hide'} chat history (⌘B)`}
          aria-label={`${collapsed ? 'Show' : 'Hide'} chat history`}
          aria-expanded={!collapsed}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-(--brand-text-muted) transition hover:bg-(--brand-accent-light) hover:text-(--brand-primary) focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:outline-none"
        >
          <ToggleIcon className="h-4 w-4" aria-hidden />
        </button>
      </div>

      {!collapsed && (
        <div className="shrink-0 px-2 pt-2 pb-1.5">
          <button
            type="button"
            onClick={onNewChat}
            title="New chat"
            aria-label="New chat"
            className={cn(
              'flex h-9 w-full items-center gap-2 rounded-lg border border-(--brand-border) bg-(--brand-surface)',
              'px-3 text-sm font-medium text-(--brand-primary) transition',
              'hover:border-(--brand-primary) hover:bg-(--brand-accent-light)',
              'focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:outline-none'
            )}
          >
            <Plus className="h-4 w-4 shrink-0" aria-hidden />
            New chat
          </button>
        </div>
      )}

      {!collapsed && (
        <nav className="min-h-0 flex-1 overflow-y-auto px-2 pt-1 pb-3">
          {isLoading ? (
            <p className="px-3 py-2 text-[13px] text-(--brand-text-muted)">Loading…</p>
          ) : sessions.length === 0 ? (
            <p className="px-3 py-2 text-[13px] leading-relaxed text-(--brand-text-muted)">
              Chats you have here are saved automatically.
            </p>
          ) : (
            <ul className="flex flex-col gap-0.5">
              {sessions.map((session) => {
                const active = session.id === activeSessionId;
                return (
                  <li key={session.id}>
                    <button
                      type="button"
                      onClick={() => onSelect(session.id)}
                      aria-current={active ? 'true' : undefined}
                      className={cn(
                        'flex w-full items-start gap-2 rounded-lg px-2.5 py-2 text-left transition',
                        'focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:outline-none',
                        active
                          ? 'bg-(--brand-accent-light) text-(--brand-primary)'
                          : 'text-(--brand-text) hover:bg-(--brand-accent-light)/50'
                      )}
                    >
                      <MessageSquare
                        className="mt-0.5 h-3.5 w-3.5 shrink-0 text-(--brand-text-muted)"
                        aria-hidden
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[13px] leading-snug">
                          {session.title || 'Untitled chat'}
                        </span>
                        <span className="mt-0.5 block font-mono text-[10px] text-(--brand-text-muted)">
                          {formatDate(session.updated_at)}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </nav>
      )}
    </aside>
  );
}
