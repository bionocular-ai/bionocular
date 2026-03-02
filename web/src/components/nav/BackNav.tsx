'use client';

import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface BackNavProps {
  /** When set, render as a link (preferred for known destinations). */
  href?: string;
  /** When set, render as a button (e.g. conditional back or router.back()). */
  onClick?: () => void;
  /** Accessible label and visible text. e.g. "Back to trials", "Back to dashboard", "Back" */
  label: string;
  className?: string;
}

const baseStyles = [
  'group inline-flex items-center gap-2 rounded-md py-2 pr-3 pl-2 text-sm font-medium',
  'text-slate-600 hover:text-slate-900 hover:bg-slate-200',
  'transition-all duration-200 ease-out',
  'hover:-translate-x-0.5 active:translate-x-0',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2',
  'min-h-[36px] min-w-[36px]',
].join(' ');

/**
 * Back navigation control. Use as a link when destination is known, or a button when conditional.
 * Placement: top-left of content area or in the same row as the page title (industry standard).
 */
export function BackNav({ href, onClick, label, className }: BackNavProps) {
  if (href != null) {
    return (
      <Link
        href={href}
        aria-label={label}
        className={cn(baseStyles, className)}
      >
        <ArrowLeft className="h-4 w-4 shrink-0 transition-transform duration-200 ease-out group-hover:-translate-x-0.5" aria-hidden />
        <span>{label}</span>
      </Link>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={cn(baseStyles, 'text-left', className)}
    >
      <ArrowLeft className="h-4 w-4 shrink-0 transition-transform duration-200 ease-out group-hover:-translate-x-0.5" aria-hidden />
      <span>{label}</span>
    </button>
  );
}
