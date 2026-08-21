'use client';

import {
  Children,
  cloneElement,
  createContext,
  isValidElement,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
} from 'react';
import Link from 'next/link';
import { Check, Copy } from 'lucide-react';
import type { Components } from 'react-markdown';
import { cn } from '@/lib/utils';

/**
 * How the agent's markdown is rendered.
 *
 * This replaces a set of `prose-*` classes that never did anything: the
 * Tailwind typography plugin is not installed, so every one of them was an
 * inert string and tables rendered at browser defaults. Overriding the
 * elements directly is also the only seam that can linkify identifiers and
 * give one element its own scroll container.
 */

/** Rows shown before the expander takes over. */
const VISIBLE_ROWS = 8;

/**
 * ClinicalTrials.gov status tokens, rewritten for reading. Anything not listed
 * passes through untouched - the renderer must never quietly reword a value
 * the model reported.
 */
const STATUS_LABELS: Record<string, string> = {
  RECRUITING: 'Recruiting',
  NOT_YET_RECRUITING: 'Not yet recruiting',
  ACTIVE_NOT_RECRUITING: 'Active, not recruiting',
  ENROLLING_BY_INVITATION: 'Enrolling by invitation',
  COMPLETED: 'Completed',
  SUSPENDED: 'Suspended',
  TERMINATED: 'Terminated',
  WITHDRAWN: 'Withdrawn',
  UNKNOWN: 'Unknown status',
};

/** Statuses that mean the trial is still running, and get the accent treatment. */
const OPEN_STATUSES = new Set(['RECRUITING', 'NOT_YET_RECRUITING', 'ENROLLING_BY_INVITATION']);

interface TableState {
  /** Rows to render, or null once expanded. */
  visibleRows: number | null;
  onRowCount: (count: number) => void;
}

const TableContext = createContext<TableState>({ visibleRows: null, onRowCount: () => {} });

function toCsv(table: HTMLTableElement): string {
  return Array.from(table.rows)
    .map((row) =>
      Array.from(row.cells)
        .map((cell) => `"${(cell.textContent ?? '').trim().replace(/"/g, '""')}"`)
        .join(',')
    )
    .join('\n');
}

function MarkdownTable({ children }: { children?: ReactNode }) {
  const tableRef = useRef<HTMLTableElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [rowCount, setRowCount] = useState(0);
  const [copied, setCopied] = useState(false);

  const context = useMemo<TableState>(
    () => ({ visibleRows: expanded ? null : VISIBLE_ROWS, onRowCount: setRowCount }),
    [expanded]
  );

  // Reset the button after a moment, without leaving a timer behind on unmount.
  useEffect(() => {
    if (!copied) return;
    const id = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(id);
  }, [copied]);

  const hiddenRows = expanded ? 0 : Math.max(0, rowCount - VISIBLE_ROWS);

  const handleCopy = async () => {
    if (!tableRef.current) return;
    await navigator.clipboard.writeText(toCsv(tableRef.current));
    setCopied(true);
  };

  return (
    <TableContext.Provider value={context}>
      <div className="group/table relative my-3">
        <div className="overflow-x-auto rounded-[3px] border border-(--brand-border) bg-(--brand-surface)">
          <table ref={tableRef} className="w-full border-separate border-spacing-0 text-[13px]">
            {children}
          </table>
          {hiddenRows > 0 ? (
            <button
              type="button"
              onClick={() => setExpanded(true)}
              className={cn(
                'block w-full border-t border-(--brand-border) bg-(--brand-bg) px-3.5 py-2',
                'text-left font-mono text-[10.5px] tracking-[0.05em] text-(--brand-primary)',
                'hover:bg-(--brand-accent-light) focus-visible:outline-2 focus-visible:-outline-offset-2',
                'focus-visible:outline-(--brand-primary)'
              )}
            >
              Show {hiddenRows} more {hiddenRows === 1 ? 'row' : 'rows'}
            </button>
          ) : null}
        </div>

        <button
          type="button"
          onClick={handleCopy}
          className={cn(
            'absolute -top-2.5 right-2 inline-flex items-center gap-1.5 rounded-[3px] border',
            'border-(--brand-border) bg-(--brand-surface) px-2 py-1',
            'font-mono text-[10px] tracking-[0.05em] text-(--brand-text-muted)',
            'opacity-0 transition group-hover/table:opacity-100 focus-visible:opacity-100',
            'hover:text-(--brand-primary)'
          )}
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? 'Copied' : 'CSV'}
        </button>
      </div>
    </TableContext.Provider>
  );
}

function MarkdownTbody({ children }: { children?: ReactNode }) {
  const { visibleRows, onRowCount } = useContext(TableContext);
  const rows = Children.toArray(children);

  useEffect(() => {
    onRowCount(rows.length);
  }, [rows.length, onRowCount]);

  // Rows past the cut are hidden rather than dropped, so copy-as-CSV still sees
  // the whole table while it is collapsed.
  const rendered =
    visibleRows === null
      ? rows
      : rows.map((row, i) =>
          i < visibleRows || !isValidElement(row)
            ? row
            : cloneElement(row as ReactElement<{ hidden?: boolean }>, { hidden: true })
        );

  return <tbody>{rendered}</tbody>;
}

function StatusPill({ token }: { token: string }) {
  return (
    <span
      className={cn(
        'inline-block whitespace-nowrap rounded-[3px] border px-1.5 py-0.5',
        'font-mono text-[10px] font-medium',
        OPEN_STATUSES.has(token)
          ? 'border-(--brand-accent) bg-(--brand-accent-light) text-(--brand-primary)'
          : 'border-(--brand-border) text-(--brand-text-muted)'
      )}
    >
      {STATUS_LABELS[token]}
    </span>
  );
}

export function createMarkdownComponents(): Components {
  return {
    table: ({ children }) => <MarkdownTable>{children}</MarkdownTable>,

    thead: ({ children }) => <thead>{children}</thead>,

    tbody: ({ children }) => <MarkdownTbody>{children}</MarkdownTbody>,

    th: ({ children }) => (
      <th
        className={cn(
          'whitespace-nowrap border-b border-(--brand-border) bg-(--brand-accent-light)',
          'px-3.5 py-2.5 text-left align-bottom',
          'font-mono text-[9.5px] font-semibold uppercase tracking-[0.09em] text-(--brand-primary)'
        )}
        scope="col"
      >
        {children}
      </th>
    ),

    td: ({ children }) => {
      const token = typeof children === 'string' ? children.trim() : null;
      return (
        <td
          className={cn(
            'border-b border-(--brand-border)/45 px-3.5 py-2.5 align-top leading-[1.45]',
            '[tr:last-child_&]:border-b-0 first:whitespace-nowrap'
          )}
        >
          {token && token in STATUS_LABELS ? <StatusPill token={token} /> : children}
        </td>
      );
    },

    a: ({ href, children }) => {
      if (href && href.startsWith('/')) {
        return (
          <Link
            href={href}
            className={cn(
              'font-mono text-[12px] font-medium text-(--brand-primary)',
              'border-b border-(--brand-border) pb-px no-underline',
              'hover:border-(--brand-primary)'
            )}
          >
            {children}
          </Link>
        );
      }
      return (
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className="text-(--brand-primary) underline underline-offset-2"
        >
          {children}
        </a>
      );
    },

    p: ({ children }) => <p className="mb-3 max-w-[66ch] last:mb-0">{children}</p>,

    ul: ({ children }) => (
      <ul className="mb-3 max-w-[66ch] list-disc pl-5 last:mb-0">{children}</ul>
    ),
    ol: ({ children }) => (
      <ol className="mb-3 max-w-[66ch] list-decimal pl-5 last:mb-0">{children}</ol>
    ),
    li: ({ children }) => <li className="mb-1 last:mb-0">{children}</li>,

    h1: ({ children }) => <h3 className="mt-5 mb-2 text-[15px] font-semibold">{children}</h3>,
    h2: ({ children }) => <h3 className="mt-5 mb-2 text-[14px] font-semibold">{children}</h3>,
    h3: ({ children }) => <h4 className="mt-4 mb-2 text-[13.5px] font-semibold">{children}</h4>,
    h4: ({ children }) => <h5 className="mt-4 mb-1.5 text-[13px] font-semibold">{children}</h5>,

    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,

    hr: () => <hr className="my-4 border-t border-(--brand-border)" />,

    // The agent's "Notes / caveats" blocks land here.
    blockquote: ({ children }) => (
      <blockquote
        className={cn(
          'my-4 max-w-[70ch] border-l-2 border-(--brand-accent) bg-(--brand-surface)',
          'px-4 py-3 text-[12.5px] leading-relaxed text-(--brand-text-muted)'
        )}
      >
        {children}
      </blockquote>
    ),

    code: ({ children }) => (
      <code className="rounded-[3px] bg-(--brand-accent-light) px-1.5 py-0.5 font-mono text-[12px] text-(--brand-primary)">
        {children}
      </code>
    ),

    pre: ({ children }) => (
      <pre className="my-3 overflow-x-auto rounded-[3px] border border-(--brand-border) bg-(--brand-surface) p-3 text-[12px]">
        {children}
      </pre>
    ),
  };
}
