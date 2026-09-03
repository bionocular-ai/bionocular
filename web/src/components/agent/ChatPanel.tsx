'use client';

import { useState, useEffect, useRef } from 'react';
import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';
import { Send, Square, RotateCcw, FlaskConical, Hash, Activity } from 'lucide-react';
import { cn } from '@/lib/utils';
import { UserBubble } from './UserBubble';
import { AssistantTurn, type TurnPart, type TurnTextPart } from './AssistantTurn';

const COLD_START_DELAY_MS = 5000;
/** How close to the bottom still counts as "following the stream". */
const BOTTOM_THRESHOLD_PX = 80;
/** Roughly six lines, after which the composer scrolls instead of growing. */
const MAX_COMPOSER_HEIGHT_PX = 160;

export interface ChatPanelProps {
  /** Dashboard category slug. Every tool query is restricted to it server-side. */
  cancerType: string;
}

export function ChatPanel({ cancerType }: ChatPanelProps) {
  // One ID for the life of this chat, so the server upserts a single row
  // instead of inserting one per turn.
  const [sessionId] = useState(() => crypto.randomUUID());

  const { messages, sendMessage, status, error, stop, regenerate } = useChat({
    transport: new DefaultChatTransport({
      api: '/api/agent/chat',
      body: { cancerType, sessionId },
    }),
  });

  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // Follow the stream only while the reader is already at the bottom. Without
  // this, every token re-pins the view and scrolling up mid-answer is impossible.
  const pinnedToBottom = useRef(true);

  // Cold-start hint: track elapsed-since-request-start in state so render is pure.
  // setElapsed only fires inside callbacks (setInterval, cleanup), never in the
  // synchronous effect body — required by react-hooks/purity + set-state-in-effect.
  const [elapsed, setElapsed] = useState(0);
  const isBusy = status === 'submitted' || status === 'streaming';

  useEffect(() => {
    if (!isBusy) return;
    const start = Date.now();
    const id = setInterval(() => setElapsed(Date.now() - start), 500);
    return () => {
      clearInterval(id);
      setElapsed(0);
    };
  }, [isBusy]);

  const lastMsg = messages[messages.length - 1];
  const hasAssistantText =
    lastMsg?.role === 'assistant' &&
    lastMsg.parts.some((p) => p.type === 'text' && (p as TurnTextPart).text.length > 0);
  const showColdStartHint = isBusy && !hasAssistantText && elapsed > COLD_START_DELAY_MS;

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

  const resizeComposer = (el: HTMLTextAreaElement) => {
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_COMPOSER_HEIGHT_PX)}px`;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isBusy) return;
    pinnedToBottom.current = true;
    sendMessage({ text: trimmed });
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  return (
    <div className="flex h-full flex-col bg-(--brand-bg)">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex flex-1 flex-col overflow-y-auto px-4 py-6 sm:px-8"
      >
        <div
          className={cn(
            'mx-auto flex w-full max-w-3xl flex-col gap-6',
            // With nothing said yet the thread is three short cards in a tall
            // box. Centring them strands them between two empty bands, so they
            // sit against the composer instead - the input is what they feed.
            messages.length === 0 && 'mt-auto'
          )}
        >
          {messages.length === 0 ? (
            <EmptyState
              onPick={(q) => {
                setInput(q);
                textareaRef.current?.focus();
              }}
            />
          ) : (
            messages.map((message, index) => {
              if (message.role === 'user') {
                const text = (message.parts as TurnPart[])
                  .filter((p): p is TurnTextPart => p.type === 'text')
                  .map((p) => p.text)
                  .join('');
                return <UserBubble key={message.id} text={text} />;
              }
              return (
                <AssistantTurn
                  key={message.id}
                  parts={message.parts as TurnPart[]}
                  cancerType={cancerType}
                  isStreaming={isBusy && index === messages.length - 1}
                />
              );
            })
          )}

          {/* A turn that has not started streaming yet has no message to hang the rail off. */}
          {isBusy && lastMsg?.role === 'user' ? (
            <AssistantTurn parts={[]} cancerType={cancerType} isStreaming />
          ) : null}

          {showColdStartHint && (
            <p className="max-w-[62ch] pl-[26px] text-[12px] text-(--brand-text-muted)">
              Waking the server (free tier sleeps after idle). First request after a long pause can
              take up to a minute.
            </p>
          )}

          {error && (
            <div className="max-w-[60ch] border-l-2 border-red-700 bg-red-50 px-4 py-3 text-[13px] text-red-700">
              {error.message || 'Something went wrong. Please try again.'}
              <button
                type="button"
                onClick={() => regenerate()}
                className={cn(
                  'mt-2 flex items-center gap-1.5 rounded-[3px] border border-red-200 bg-white',
                  'px-2 py-1 font-mono text-[10px] tracking-[0.06em] hover:bg-red-50'
                )}
              >
                <RotateCcw className="h-3 w-3" />
                Retry
              </button>
            </div>
          )}
        </div>
      </div>

      <form
        onSubmit={handleSubmit}
        className="border-t border-(--brand-border) bg-(--brand-surface) px-4 py-3 sm:px-8"
      >
        <div className="mx-auto max-w-3xl">
          <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              resizeComposer(e.target);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e as unknown as React.FormEvent);
              }
            }}
            placeholder="Ask about a trial, drug, or target…"
            rows={1}
            className={cn(
              'flex-1 resize-none rounded-xl border border-(--brand-border) bg-(--brand-surface)',
              'px-3.5 py-2.5 text-sm text-(--brand-text) placeholder:text-(--brand-text-muted)',
              'focus:border-(--brand-primary) focus:ring-3 focus:ring-(--brand-primary)/12 focus:outline-none'
            )}
          />
          {isBusy ? (
            <button
              type="button"
              onClick={stop}
              className={cn(
                'inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl',
                'border border-(--brand-border) bg-(--brand-surface) text-(--brand-primary)',
                'hover:bg-(--brand-accent-light)'
              )}
              aria-label="Stop generating"
            >
              <Square className="h-3.5 w-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className={cn(
                'inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl',
                'bg-(--brand-primary) text-white transition hover:bg-(--brand-primary-hover)',
                'disabled:cursor-not-allowed disabled:opacity-50'
              )}
              aria-label="Send"
            >
              <Send className="h-4 w-4" />
            </button>
          )}
          </div>
          <p className="mt-2 max-w-3xl font-mono text-[10px] tracking-[0.06em] text-(--brand-text-muted) uppercase">
            Enter to send · Shift+Enter for a new line
          </p>
        </div>
      </form>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  // Every example has to be answerable from the database, for whichever cancer
  // type the dashboard is on - naming another one would ask the agent for
  // something it is scoped out of. The label names the kind of question, so the
  // three together show the breadth rather than just seeding one query.
  const examples = [
    {
      label: 'Trial phase',
      icon: FlaskConical,
      question: 'What phase 3 trials do we have for BRAF-mutant disease?',
    },
    {
      label: 'NCT registry',
      icon: Hash,
      question: 'Tell me about NCT00006368.',
    },
    {
      label: 'Survival metrics',
      icon: Activity,
      question: 'Which treatments have reported overall survival data?',
    },
  ];
  // The page header already names and scopes the agent, so this only has to
  // get the first question asked.
  return (
    <div className="flex flex-col gap-3">
      <p className="font-mono text-[10px] tracking-[0.12em] text-(--brand-text-muted) uppercase">
        Start with
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        {examples.map(({ label, icon: Icon, question }) => (
          <button
            key={question}
            type="button"
            onClick={() => onPick(question)}
            className={cn(
              'group flex flex-col gap-2 rounded-xl border border-(--brand-border)',
              'bg-(--brand-surface) px-3.5 py-3 text-left transition',
              'hover:border-(--brand-primary) hover:bg-(--brand-accent-light)',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)'
            )}
          >
            <span className="flex items-center gap-1.5 font-mono text-[10px] tracking-[0.12em] text-(--brand-text-muted) uppercase group-hover:text-(--brand-primary)">
              <Icon className="h-3.5 w-3.5 text-(--brand-accent)" aria-hidden />
              {label}
            </span>
            <span className="text-sm leading-snug text-(--brand-text)">{question}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
