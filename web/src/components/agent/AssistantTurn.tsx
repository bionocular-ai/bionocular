'use client';

import { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Check, Copy, ThumbsDown, ThumbsUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { FeedbackRating } from '@/lib/api';
import { remarkNctLinks } from '@/lib/agent/remark-nct-links';
import { toTurnTable } from '@/lib/agent/turn-table';
import { efficacyLinkFor } from '@/lib/agent/efficacy-link';
import { createMarkdownComponents } from './markdown-components';
import { ToolStep, type ToolState } from './ToolStep';
import { TurnTable } from './TurnTable';

/**
 * One assistant turn, rendered as a single document hung off an evidence rail.
 *
 * The parts of a turn used to render as separate cards, so one answer arrived
 * as three floating boxes with tool results wedged between them. Reasoning,
 * queries, and answer belong to the same trace and now read as one.
 */

export interface TurnTextPart {
  type: 'text';
  text: string;
}

export interface TurnToolPart {
  type: string;
  toolCallId: string;
  state: ToolState;
  input?: unknown;
  output?: unknown;
  errorText?: string;
}

export type TurnPart = TurnTextPart | TurnToolPart;

export interface AssistantTurnProps {
  parts: TurnPart[];
  /** Dashboard category slug, used to scope NCT links to the right trial page. */
  cancerType: string;
  /** True while this turn is still being streamed. */
  isStreaming: boolean;
  /** Rating this user already gave this answer, if any. */
  rating?: FeedbackRating;
  /** Passing the rating already showing withdraws it. */
  onRate?: (rating: FeedbackRating) => void;
}

function isToolPart(part: TurnPart): part is TurnToolPart {
  return part.type.startsWith('tool-');
}

export function AssistantTurn({ parts, cancerType, isStreaming, rating, onRate }: AssistantTurnProps) {
  const [copied, setCopied] = useState(false);

  const remarkPlugins = useMemo(() => [remarkGfm, remarkNctLinks(cancerType)], [cancerType]);
  const components = useMemo(() => createMarkdownComponents(), []);

  useEffect(() => {
    if (!copied) return;
    const id = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(id);
  }, [copied]);

  const answer = parts
    .filter((part): part is TurnTextPart => part.type === 'text')
    .map((part) => part.text)
    .join('\n\n')
    .trim();

  const toolParts = useMemo(() => parts.filter(isToolPart), [parts]);

  const turnTable = useMemo(
    () => toTurnTable(toolParts.map((part) => part.output)),
    [toolParts]
  );

  // Built from the tool inputs rather than the rows: the filters are what the
  // hub needs, and a capped result cannot say what was asked for.
  const efficacyLink = useMemo(
    () => efficacyLinkFor(toolParts, cancerType),
    [toolParts, cancerType]
  );

  const handleCopy = async () => {
    await navigator.clipboard.writeText(answer);
    setCopied(true);
  };

  return (
    <div
      className={cn(
        'group/turn relative pb-2 pl-[26px]',
        'before:absolute before:top-[7px] before:bottom-3 before:left-1 before:w-px',
        'before:bg-(--brand-border)'
      )}
    >
      {parts.map((part, i) => {
        if (isToolPart(part)) {
          return (
            <ToolStep
              key={`${part.toolCallId}-${i}`}
              toolName={part.type.replace(/^tool-/, '')}
              state={part.state}
              input={part.input}
              output={part.output}
              errorText={part.errorText}
            />
          );
        }
        if (part.type !== 'text' || !part.text) return null;
        return (
          <div key={`text-${i}`} className="relative mb-1.5">
            <span
              aria-hidden
              className={cn(
                'absolute top-[9px] -left-[25px] h-[7px] w-[7px] rounded-full',
                'border border-(--brand-border) bg-(--brand-bg)'
              )}
            />
            <div className="text-[14.5px] leading-[1.66] text-(--brand-text)">
              <ReactMarkdown remarkPlugins={remarkPlugins} components={components}>
                {part.text}
              </ReactMarkdown>
            </div>
          </div>
        );
      })}

      {turnTable ? (
        <TurnTable table={turnTable} cancerType={cancerType} efficacyLink={efficacyLink} />
      ) : null}

      {isStreaming && parts.length === 0 ? (
        <div className="relative mb-1.5">
          <span
            aria-hidden
            className={cn(
              'absolute top-[7px] -left-[26px] h-[9px] w-[9px] rounded-full',
              'bg-(--brand-primary) shadow-[0_0_0_3px_var(--brand-bg)] motion-safe:animate-pulse'
            )}
          />
          <p className="py-0.5 font-mono text-[11px] tracking-[0.06em] text-(--brand-text-muted)">
            Thinking…
          </p>
        </div>
      ) : null}

      {!isStreaming && answer ? (
        <div className="flex gap-1 pt-2">
          <button type="button" onClick={handleCopy} className={ACTION_CLASSES}>
            {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            {copied ? 'Copied' : 'Copy answer'}
          </button>

          {onRate ? (
            <>
              <RateButton
                icon={ThumbsUp}
                label="Helpful"
                active={rating === 'up'}
                onClick={() => onRate('up')}
              />
              <RateButton
                icon={ThumbsDown}
                label="Not helpful"
                active={rating === 'down'}
                onClick={() => onRate('down')}
              />
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/**
 * Actions under a finished turn stay out of the way until the turn is hovered,
 * so a long transcript is not a column of buttons.
 */
const ACTION_CLASSES = cn(
  'inline-flex items-center gap-1.5 rounded-[3px] border border-transparent px-2 py-1',
  'font-mono text-[10px] tracking-[0.05em] text-(--brand-text-muted) transition',
  'opacity-0 group-hover/turn:opacity-100 focus-visible:opacity-100',
  'hover:border-(--brand-border) hover:bg-(--brand-surface) hover:text-(--brand-primary)'
);

function RateButton({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: typeof ThumbsUp;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      // A rating the user gave stays visible after the pointer leaves - it is
      // the state of the answer now, not an action still on offer.
      className={cn(
        ACTION_CLASSES,
        active && 'border-(--brand-border) bg-(--brand-surface) text-(--brand-primary) opacity-100'
      )}
    >
      <Icon className="h-3 w-3" />
      {label}
    </button>
  );
}
