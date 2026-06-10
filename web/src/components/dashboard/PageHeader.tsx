import * as React from 'react';
import { cn } from '@/lib/utils';

export interface PageHeaderProps {
  /** Eyebrow / breadcrumb — e.g. the cancer category name. */
  category: string;
  /** Large serif section title — e.g. "Trial Updates". */
  title: string;
  /** Optional muted one-line description. */
  description?: string;
  /** Optional right-aligned slot for actions / links. */
  right?: React.ReactNode;
  className?: string;
}

const PageHeader = React.forwardRef<HTMLDivElement, PageHeaderProps>(
  ({ category, title, description, right, className }, ref) => {
    return (
      <header ref={ref} className={cn('flex flex-col gap-2', className)}>
        <p
          className="text-[11px] font-medium uppercase tracking-[0.14em] text-(--brand-text-muted)"
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {category}
        </p>

        <div
          className={cn(
            'flex gap-4',
            right ? 'items-start justify-between' : 'flex-col'
          )}
        >
          <h1
            className="font-semibold leading-[1.1] tracking-[-0.01em] text-(--brand-text)"
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 'clamp(24px, 3.4vw, 34px)',
            }}
          >
            {title}
          </h1>

          {right ? <div className="shrink-0">{right}</div> : null}
        </div>

        {description ? (
          <p className="max-w-[60ch] text-sm leading-relaxed text-(--brand-text-muted)">
            {description}
          </p>
        ) : null}
      </header>
    );
  }
);
PageHeader.displayName = 'PageHeader';

export { PageHeader };
