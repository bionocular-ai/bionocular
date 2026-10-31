import Image from 'next/image';
import type { LucideIcon } from 'lucide-react';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input, type InputProps } from '@/components/ui/input';
import { cn } from '@/lib/utils';

// Shared chrome for the login, signup, forgot-password and reset-password pages

export const authLinkClass =
  'inline-block -mx-1 px-1 py-1 rounded text-sm text-(--brand-primary) hover:underline hover:opacity-80 transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary)';

export function AuthCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    // Top-anchored rather than centered, so a growing card extends downward instead of shifting the fields
    <div className="min-h-screen flex items-start justify-center px-4 pb-4 pt-[max(1rem,calc(50vh-290px))] relative overflow-hidden" style={{ background: '#0E3547' }}>
      {/* Brand teal mesh gradient background */}
      <div className="absolute inset-0" style={{
        background: `
          radial-gradient(ellipse 130% 90% at 15% 50%, rgba(27,79,101,0.92) 0%, transparent 55%),
          radial-gradient(ellipse 80% 70% at 60% 30%, rgba(122,193,162,0.18) 0%, transparent 50%),
          radial-gradient(ellipse 100% 100% at 80% 80%, rgba(27,79,101,0.5) 0%, transparent 60%),
          #0E3547
        `
      }} />
      {/* Subtle wave pattern overlay */}
      <div className="absolute inset-0 opacity-20">
        <svg className="absolute top-0 left-0 w-full h-full" viewBox="0 0 1200 800" preserveAspectRatio="none">
          <path d="M0,200 Q300,150 600,200 T1200,200 L1200,800 L0,800 Z" fill="url(#wave-gradient)" className="opacity-50" />
          <path d="M0,300 Q400,250 800,300 T1200,300 L1200,800 L0,800 Z" fill="url(#wave-gradient)" className="opacity-30" />
          <defs>
            <linearGradient id="wave-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#7AC1A2" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#1B4F65" stopOpacity="0.1" />
            </linearGradient>
          </defs>
        </svg>
      </div>

      <Card className="w-full max-w-md shadow-2xl border-0 bg-white rounded-2xl relative z-10">
        <CardHeader className="pb-8 pt-10">
          <div className="flex justify-center mb-4">
            <div className="relative w-24 h-24">
              <Image src="/logo.svg" alt="Bionocular Logo" fill sizes="96px" className="object-contain" priority />
            </div>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-center -mt-1 text-(--brand-primary)">
            {title}
          </h1>
        </CardHeader>
        <CardContent className="px-8 pb-8">{children}</CardContent>
      </Card>
    </div>
  );
}

export function AuthField({
  id,
  label,
  icon: Icon,
  hint,
  errorId,
  ...inputProps
}: InputProps & { id: string; label: string; icon: LucideIcon; hint?: string; errorId?: string }) {
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-(--brand-text)">
        {label}
      </label>
      <div className="relative">
        <Icon aria-hidden className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-(--brand-primary)" />
        <Input
          id={id}
          aria-invalid={errorId ? true : undefined}
          aria-describedby={[hintId, errorId].filter(Boolean).join(' ') || undefined}
          className="h-12 pl-11 rounded-lg border-gray-300 focus-visible:border-(--brand-primary) focus-visible:ring-(--brand-primary)"
          {...inputProps}
        />
      </div>
      {hint && (
        <p id={hintId} className="text-xs text-(--brand-text-muted)">
          {hint}
        </p>
      )}
    </div>
  );
}

export function AuthAlert({ id, tone, children }: { id?: string; tone: 'error' | 'success'; children: React.ReactNode }) {
  const Icon = tone === 'error' ? AlertCircle : CheckCircle2;
  return (
    <div
      id={id}
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn(
        'flex items-start gap-2 p-3 text-sm text-left border rounded-lg',
        tone === 'error'
          ? 'text-red-700 bg-red-50 border-red-200'
          : 'text-(--brand-primary) bg-(--brand-accent-light) border-(--brand-accent)'
      )}
    >
      <Icon aria-hidden className="h-4 w-4 mt-0.5 shrink-0" />
      <div>{children}</div>
    </div>
  );
}

export function AuthSubmit({ loading, loadingLabel, children }: { loading: boolean; loadingLabel: string; children: React.ReactNode }) {
  return (
    <Button
      type="submit"
      className="w-full h-12 text-base font-semibold rounded-lg text-white shadow-md bg-(--brand-primary) hover:bg-(--brand-primary-hover) hover:shadow-lg active:scale-[0.98] motion-reduce:active:scale-100 transition-[background-color,box-shadow,transform] duration-100 ease-out focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-2"
      disabled={loading}
    >
      {loading ? (
        <>
          <Loader2 aria-hidden className="h-5 w-5 animate-spin" />
          {loadingLabel}
        </>
      ) : (
        children
      )}
    </Button>
  );
}
