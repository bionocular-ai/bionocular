import { cn } from '@/lib/cn'

const COPY: Record<
  'no-manifest' | 'run-error',
  { icon: 'folder' | 'alert'; title: string; body: string; command?: string }
> = {
  'no-manifest': {
    icon: 'folder',
    title: 'No validation runs found',
    body: 'Publish a run manifest to public/runs.json by running, from tools/validation-explorer:',
    command: 'npm run load-runs',
  },
  'run-error': {
    icon: 'alert',
    title: "Couldn't load this run",
    body: 'Check that validation.json exists under public/runs/<run-id>/ and is valid JSON, then reload.',
  },
}

function FolderIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={cn('h-6 w-6 text-slate-400')}>
      <path
        d="M3.75 6.75A1.5 1.5 0 0 1 5.25 5.25h4.19c.4 0 .78.16 1.06.44l1.31 1.31h7.19a1.5 1.5 0 0 1 1.5 1.5v9.25a1.5 1.5 0 0 1-1.5 1.5H5.25a1.5 1.5 0 0 1-1.5-1.5V6.75Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function AlertIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className={cn('h-6 w-6 text-amber-500')}>
      <path
        d="M10.29 3.86 1.82 18a1.5 1.5 0 0 0 1.29 2.25h17.78A1.5 1.5 0 0 0 22.18 18L13.71 3.86a1.5 1.5 0 0 0-2.42 0Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M12 9v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M12 16.5h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

export function EmptyState({ kind }: { kind: 'no-manifest' | 'run-error' }) {
  const { icon, title, body, command } = COPY[kind]
  return (
    <div
      className={cn(
        'm-8 flex flex-col items-center gap-3 rounded-lg border border-dashed border-slate-300 p-10 text-center',
      )}
    >
      {icon === 'folder' ? <FolderIcon /> : <AlertIcon />}
      <h2 className={cn('text-sm font-semibold text-slate-700')}>{title}</h2>
      <p className={cn('max-w-sm text-sm text-slate-500')}>{body}</p>
      {command && (
        <code
          className={cn(
            'rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 font-mono text-xs text-slate-700',
          )}
        >
          {command}
        </code>
      )}
    </div>
  )
}
