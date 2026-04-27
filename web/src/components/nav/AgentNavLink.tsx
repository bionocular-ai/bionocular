'use client';

import Link from 'next/link';
import { Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';

export interface AgentNavLinkProps {
  className?: string;
}

export function AgentNavLink({ className }: AgentNavLinkProps) {
  return (
    <Link
      href={ROUTES.AGENT}
      aria-label="Open AI agent"
      className={cn(
        'inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium',
        'border-[var(--primary)] bg-white text-[var(--primary)]',
        'transition-all duration-200 ease-out',
        'hover:bg-[var(--brand-accent-light)] hover:shadow-md',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)] focus-visible:ring-offset-2 focus-visible:ring-offset-white',
        'min-h-[36px] sm:min-h-[38px]',
        'active:scale-[0.98]',
        className
      )}
    >
      <Sparkles className="h-4 w-4 shrink-0 sm:h-[18px] sm:w-[18px]" aria-hidden />
      <span>AI Agent</span>
    </Link>
  );
}
