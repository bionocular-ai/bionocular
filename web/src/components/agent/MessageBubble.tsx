'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';

export interface MessageBubbleProps {
  role: 'user' | 'assistant' | 'system';
  text: string;
}

export function MessageBubble({ role, text }: MessageBubbleProps) {
  const isUser = role === 'user';

  return (
    <div
      className={cn(
        'rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm',
        isUser
          ? 'bg-[var(--primary)] text-white max-w-[85%] self-end'
          : 'bg-white border border-slate-200 text-slate-800 max-w-[90%] self-start'
      )}
    >
      {isUser ? (
        <p className="whitespace-pre-wrap">{text}</p>
      ) : (
        <div
          className={cn(
            'prose prose-sm max-w-none',
            'prose-p:my-2 prose-headings:my-3 prose-ul:my-2 prose-ol:my-2',
            'prose-code:px-1 prose-code:py-0.5 prose-code:bg-slate-100 prose-code:rounded prose-code:before:content-none prose-code:after:content-none'
          )}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
