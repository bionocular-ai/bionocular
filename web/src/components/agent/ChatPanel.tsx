'use client';

import { useState, useEffect, useRef } from 'react';
import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport, type UIMessage } from 'ai';
import { Send, Square, RotateCcw, FlaskConical, Activity, Layers, Newspaper } from 'lucide-react';
import { cn } from '@/lib/utils';
import { agentFeedbackApi, type FeedbackRating } from '@/lib/api';
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
  /**
   * The conversation to write to. Owned by the page so the history drawer and
   * the panel agree on which chat is open; the server upserts a single row on
   * it rather than inserting one per turn.
   */
  sessionId: string;
  /** Transcript of a reopened conversation. Empty for a new one. */
  initialMessages?: UIMessage[];
  /** Fires when a turn finishes, so a new chat appears in the history list. */
  onTurnFinished?: () => void;
}

export function ChatPanel({
  cancerType,
  sessionId,
  initialMessages,
  onTurnFinished,
}: ChatPanelProps) {
  // `id` and `messages` seed the chat on mount only, so the page remounts this
  // component (keyed on sessionId) when another conversation is opened.
  const { messages, sendMessage, status, error, stop, regenerate } = useChat({
    id: sessionId,
    messages: initialMessages,
    transport: new DefaultChatTransport({
      api: '/api/agent/chat',
      body: { cancerType, sessionId },
    }),
    onFinish: () => onTurnFinished?.(),
  });

  const [input, setInput] = useState('');
  // Ratings this user has already given, by assistant message id. Seeded from
  // the database so a reopened conversation shows the thumbs it was given.
  const [ratings, setRatings] = useState<Record<string, FeedbackRating>>({});
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
    if (!initialMessages?.length) return;
    let cancelled = false;
    agentFeedbackApi.listForSession(sessionId).then((saved) => {
      if (!cancelled) setRatings(saved);
    });
    return () => {
      cancelled = true;
    };
  }, [sessionId, initialMessages?.length]);

  const rate = (messageId: string, rating: FeedbackRating) => {
    const withdrawing = ratings[messageId] === rating;
    // Optimistic: a thumb that lags behind the click reads as a dropped one.
    setRatings((prev) => {
      const next = { ...prev };
      if (withdrawing) delete next[messageId];
      else next[messageId] = rating;
      return next;
    });
    if (withdrawing) agentFeedbackApi.clear(messageId);
    else agentFeedbackApi.rate(sessionId, messageId, rating);
  };

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

  // Before the first question the thread and the composer sit together in the
  // middle of the page, the way every other chat product opens; once there is a
  // transcript the thread takes the height and the composer pins to the bottom.
  const isEmpty = messages.length === 0;

  return (
    <div className={cn('flex h-full flex-col bg-(--brand-bg)', isEmpty && 'justify-center')}>
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className={cn(
          'flex flex-col overflow-y-auto px-4 py-6 sm:px-8',
          isEmpty ? 'shrink-0' : 'flex-1'
        )}
      >
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
          {isEmpty ? (
            <h2 className="text-center text-2xl font-medium text-balance text-(--brand-text)">
              What do you want to know?
            </h2>
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
                  rating={ratings[message.id]}
                  onRate={(rating) => rate(message.id, rating)}
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
        className="px-4 py-3 sm:px-8"
      >
        <div className="mx-auto max-w-3xl">
          {/* The box is the bordered control; the textarea inside it is bare,
              so the send button reads as part of the same field. */}
          <div
            className={cn(
              'flex items-end gap-2 rounded-xl border border-(--brand-border) bg-(--brand-surface)',
              'py-1.5 pr-1.5 pl-3.5',
              'focus-within:border-(--brand-primary) focus-within:ring-3 focus-within:ring-(--brand-primary)/12'
            )}
          >
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
                'flex-1 resize-none border-0 bg-transparent py-2 text-sm',
                'text-(--brand-text) placeholder:text-(--brand-text-muted) focus:outline-none'
              )}
            />
            {isBusy ? (
              <button
                type="button"
                onClick={stop}
                className={cn(
                  'inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
                  'bg-(--brand-primary) text-white transition hover:bg-(--brand-primary-hover)'
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
                  'inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
                  'bg-(--brand-primary) text-white transition hover:bg-(--brand-primary-hover)',
                  'disabled:cursor-not-allowed disabled:opacity-50'
                )}
                aria-label="Send"
              >
                <Send className="h-4 w-4" />
              </button>
            )}
          </div>
          {isEmpty && (
            <Suggestions
              onPick={(q) => {
                setInput(q);
                textareaRef.current?.focus();
              }}
            />
          )}
        </div>
      </form>
    </div>
  );
}

function Suggestions({ onPick }: { onPick: (q: string) => void }) {
  // One per table the agent can reach - registry, outcomes, landscape, news -
  // so the four together show what it holds rather than seeding one query. None
  // of them names a drug, a biomarker or an NCT number: the same chips are
  // shown on every cancer-type dashboard, and the agent is scoped to that type,
  // so anything specific would be a question it cannot answer half the time.
  const examples = [
    {
      label: 'Recruiting phase 3',
      icon: FlaskConical,
      question: 'Which phase 3 trials are currently recruiting?',
    },
    {
      label: 'Survival reported',
      icon: Activity,
      question: 'Which treatments have reported a median overall survival?',
    },
    {
      label: 'First-line treatments',
      icon: Layers,
      question: 'What treatment modalities show up most in first-line trials?',
    },
    {
      label: 'Latest news',
      icon: Newspaper,
      question: 'What is the most recent news coverage we have?',
    },
  ];
  return (
    <div className="mt-3 flex flex-wrap justify-center gap-2">
      {examples.map(({ label, icon: Icon, question }) => (
        <button
          key={question}
          type="button"
          onClick={() => onPick(question)}
          className={cn(
            'flex items-center gap-1.5 rounded-full border border-(--brand-border)',
            'px-3 py-1.5 text-[13px] text-(--brand-text-muted) transition',
            'hover:border-(--brand-primary) hover:bg-(--brand-accent-light) hover:text-(--brand-primary)',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)'
          )}
        >
          <Icon className="h-3.5 w-3.5 text-(--brand-accent)" aria-hidden />
          {label}
        </button>
      ))}
    </div>
  );
}
