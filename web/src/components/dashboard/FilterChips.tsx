'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

export interface FilterChipsOption<T extends string> {
  value: T;
  label: string;
}

export interface FilterChipsProps<T extends string> {
  /** Leading category label — e.g. "POPULATION". */
  label?: string;
  options: FilterChipsOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
  size?: 'sm' | 'md';
}

// Generic function components don't compose with forwardRef without erasing the
// type parameter, so this is a plain generic component (matching the project's
// SegmentedControl primitive, which is also ref-less).
export function FilterChips<T extends string>({
  label,
  options,
  value,
  onChange,
  className,
  size = 'md',
}: FilterChipsProps<T>) {
  const sizeClasses = {
    track: size === 'sm' ? 'p-0.5 gap-0.5' : 'p-1 gap-1',
    pill: size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-sm',
    label: size === 'sm' ? 'pl-2.5 pr-1 text-[10px]' : 'pl-3 pr-1.5 text-[11px]',
  };

  return (
    <div
      className={cn(
        'inline-flex items-center rounded-full border border-(--brand-border) bg-(--brand-surface)',
        sizeClasses.track,
        className
      )}
      role="group"
      aria-label={label}
    >
      {label ? (
        <span
          className={cn(
            'select-none font-medium uppercase tracking-[0.12em] text-(--brand-text-muted)',
            sizeClasses.label
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {label}
        </span>
      ) : null}

      {options.map((option) => {
        const active = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={cn(
              'rounded-full font-medium transition-all duration-150 ease-out',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-1 focus-visible:ring-offset-(--brand-surface)',
              sizeClasses.pill,
              active
                ? 'bg-(--brand-accent-light) text-(--brand-primary) shadow-[0_1px_2px_rgba(27,79,101,0.12)]'
                : 'text-(--brand-text-muted) hover:text-(--brand-primary)'
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
