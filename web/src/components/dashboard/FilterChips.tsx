'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

export interface FilterChipsOption<T extends string> {
  value: T;
  label: string;
  /** Shown after the label as a quieter figure, so "New 33" reads as a name and its size. */
  count?: number;
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
    count: size === 'sm' ? 'text-[11px]' : 'text-xs',
  };

  // One thumb marks the selection and slides from the old choice to the new one,
  // measured from the selected button so options of any width line up.
  const buttons = React.useRef(new Map<T, HTMLButtonElement>());
  const [thumb, setThumb] = React.useState<{ x: number; w: number; moved: boolean } | null>(null);
  const trackRef = React.useRef<HTMLDivElement>(null);
  React.useLayoutEffect(() => {
    const measure = () => {
      const el = buttons.current.get(value);
      if (!el) return setThumb(null);
      // The first placement lands without motion; later ones slide.
      setThumb((prev) => ({ x: el.offsetLeft, w: el.offsetWidth, moved: prev !== null }));
    };
    measure();
    // Font loading and count changes resize the buttons after the first paint.
    const observer = new ResizeObserver(measure);
    if (trackRef.current) observer.observe(trackRef.current);
    return () => observer.disconnect();
  }, [value, options]);

  return (
    <div
      ref={trackRef}
      className={cn(
        'relative inline-flex items-center rounded-full border border-(--brand-border) bg-(--brand-surface)',
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

      {thumb && (
        <span
          aria-hidden
          className={cn(
            'pointer-events-none absolute inset-y-1 left-0 rounded-full bg-(--brand-accent-light) shadow-[0_1px_2px_rgba(27,79,101,0.12)]',
            size === 'sm' && 'inset-y-0.5',
            // Critically damped: it settles on the choice without overshooting.
            thumb.moved && 'transition-[transform,width] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] motion-reduce:transition-none'
          )}
          style={{ transform: `translateX(${thumb.x}px)`, width: thumb.w }}
        />
      )}

      {options.map((option) => {
        const active = value === option.value;
        return (
          <button
            key={option.value}
            ref={(el) => {
              if (el) buttons.current.set(option.value, el);
              else buttons.current.delete(option.value);
            }}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={cn(
              'relative inline-flex items-baseline gap-1.5 rounded-full font-medium transition-[color,scale] duration-100 ease-out',
              // Feedback on press, before the click lands.
              'active:scale-[0.97] motion-reduce:active:scale-100',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-1 focus-visible:ring-offset-(--brand-surface)',
              sizeClasses.pill,
              // Before the thumb is measured, the selected pill carries its own fill.
              active && !thumb && 'bg-(--brand-accent-light)',
              active ? 'text-(--brand-primary)' : 'text-(--brand-text-muted) hover:text-(--brand-primary)'
            )}
          >
            {option.label}
            {/* The space keeps the accessible name "New 33", not "New33". */}
            {option.count != null && ' '}
            {option.count != null && (
              <span
                className={cn(
                  'tabular-nums font-normal',
                  sizeClasses.count,
                  active ? 'text-(--brand-primary)/70' : 'text-(--brand-text-muted)/80'
                )}
              >
                {option.count.toLocaleString()}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
