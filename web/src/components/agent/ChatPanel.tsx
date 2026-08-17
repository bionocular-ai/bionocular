'use client';

import { useState, useEffect, useRef } from 'react';
import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';
import { Send, Loader2, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { MessageBubble } from './MessageBubble';
import { ToolCard } from './ToolCard';

const COLD_START_DELAY_MS = 5000;
/** How close to the bottom still counts as "following the stream". */
const BOTTOM_THRESHOLD_PX = 80;

interface MessageTextPart { type: 'text'; text: string }
interface MessageToolPart {
  type: string;
  toolCallId: string;
  state: 'input-streaming' | 'input-available' | 'output-available' | 'output-error';
  input?: unknown;
  output?: unknown;
  errorText?: string;
}
type MessagePart = MessageTextPart | MessageToolPart;

function isToolPart(part: { type: string }): part is MessageToolPart {
  return part.type.startsWith('tool-');
}

export interface ChatPanelProps {
  /** Dashboard category slug. Every tool query is restricted to it server-side. */
  cancerType: string;
}

export function ChatPanel({ cancerType }: ChatPanelProps) {
  // One ID for the life of this chat, so the server upserts a single row
  // instead of inserting one per turn.
  const [sessionId] = useState(() => crypto.randomUUID());

  const { messages, sendMessage, status, error } = useChat({
    transport: new DefaultChatTransport({
      api: '/api/agent/chat',
      body: { cancerType, sessionId },
    }),
  });

  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  // Follow the stream only while the reader is already at the bottom. Without
  // this, every token re-pins the view and scrolling up mid-answer is impossible.
  const pinnedToBottom = useRef(true);

  // Cold-start hint: track elapsed-since-request-start in state so render is pure.
  // setElapsed only fires inside callbacks (setInterval, cleanup), never in the
  // synchronous effect body — required by react-hooks/purity + set-state-in-effect.
  const [elapsed, setElapsed] = useState(0);
  const isBusyForHint = status === 'submitted' || status === 'streaming';

  useEffect(() => {
    if (!isBusyForHint) return;
    const start = Date.now();
    const id = setInterval(() => setElapsed(Date.now() - start), 500);
    return () => {
      clearInterval(id);
      setElapsed(0);
    };
  }, [isBusyForHint]);

  const lastMsg = messages[messages.length - 1];
  const hasAssistantText =
    lastMsg?.role === 'assistant' &&
    lastMsg.parts.some(
      (p) => p.type === 'text' && (p as MessageTextPart).text.length > 0
    );
  const showColdStartHint =
    isBusyForHint && !hasAssistantText && elapsed > COLD_START_DELAY_MS;

  useEffect(() => {
    if (!pinnedToBottom.current) return;
    // Instant, not smooth: a smooth scroll restarted on every token never
    // settles, and while it animates the container swallows wheel input.
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    pinnedToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < BOTTOM_THRESHOLD_PX;
  };

  const isBusy = status === 'submitted' || status === 'streaming';

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isBusy) return;
    pinnedToBottom.current = true;
    sendMessage({ text: trimmed });
    setInput('');
  };

  return (
    <div className="flex h-full flex-col bg-[var(--brand-bg)]">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-6 sm:px-8"
      >
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {messages.length === 0 ? (
            <EmptyState onPick={(q) => setInput(q)} />
          ) : (
            messages.map((message) => (
              <div key={message.id} className="flex flex-col gap-2">
                {(message.parts as MessagePart[]).map((part, i) => {
                  if (part.type === 'text') {
                    return (
                      <MessageBubble
                        key={`${message.id}-${i}`}
                        role={message.role as 'user' | 'assistant'}
                        text={(part as MessageTextPart).text}
                      />
                    );
                  }
                  if (isToolPart(part)) {
                    return (
                      <ToolCard
                        key={`${message.id}-${i}-${part.toolCallId}`}
                        toolName={part.type.replace(/^tool-/, '')}
                        state={part.state}
                        input={part.input}
                        output={part.output}
                        errorText={part.errorText}
                      />
                    );
                  }
                  return null;
                })}
              </div>
            ))
          )}

          {isBusy && (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Thinking…</span>
            </div>
          )}

          {showColdStartHint && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              Waking the server (free tier sleeps after idle). First request after a long pause
              can take up to a minute.
            </div>
          )}

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error.message || 'Something went wrong. Please try again.'}
            </div>
          )}
        </div>
      </div>

      <form
        onSubmit={handleSubmit}
        className="border-t border-slate-200 bg-white px-4 py-3 sm:px-8"
      >
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e as unknown as React.FormEvent);
              }
            }}
            placeholder="Ask about a trial, drug, target, or cancer indication…"
            rows={1}
            className={cn(
              'flex-1 resize-none rounded-xl border border-slate-300 bg-white px-3 py-2',
              'text-sm text-slate-900 placeholder:text-slate-400',
              'focus:outline-none focus:ring-2 focus:ring-[var(--primary)]'
            )}
            disabled={isBusy}
          />
          <button
            type="submit"
            disabled={isBusy || !input.trim()}
            className={cn(
              'inline-flex h-10 w-10 items-center justify-center rounded-xl',
              'bg-[var(--primary)] text-white transition',
              'hover:bg-[var(--accent-dark)]',
              'disabled:cursor-not-allowed disabled:opacity-50'
            )}
            aria-label="Send"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </form>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  // Every example has to be answerable from the database, for whichever cancer
  // type the dashboard is on - naming another one would ask the agent for
  // something it is scoped out of.
  const examples = [
    'What phase 3 trials do we have for BRAF-mutant disease?',
    'Tell me about NCT00006368.',
    'Which treatments have reported overall survival data?',
  ];
  return (
    <div className="flex flex-col items-center gap-6 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--brand-accent-light)]">
        <Sparkles className="h-6 w-6 text-[var(--primary)]" />
      </div>
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Bionocular Research Agent</h2>
        <p className="mt-1 text-sm text-slate-500">
          Ask about the trials, reported outcomes, survival curves, and news Bionocular tracks for
          this cancer type. No live registry or literature lookups.
        </p>
      </div>
      <div className="grid w-full max-w-xl gap-2">
        {examples.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onPick(q)}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-sm text-slate-700 hover:border-[var(--primary)] hover:text-slate-900"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
