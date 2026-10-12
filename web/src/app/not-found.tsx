import Link from 'next/link';
import { Logo } from '@/components/Logo';
import { ROUTES } from '@/lib/constants';

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-(--brand-bg) px-4 text-center">
      <Logo className="text-[26px]" />
      <div>
        <h1 className="text-2xl font-semibold text-(--brand-text)">Page not found</h1>
        <p className="mt-2 text-sm text-(--brand-text-muted)">
          This page doesn&apos;t exist or has been retired.
        </p>
      </div>
      <Link
        href={ROUTES.DASHBOARD}
        className="inline-flex min-h-[40px] items-center rounded-full bg-(--brand-primary) px-5 text-sm font-medium text-white transition-colors hover:bg-(--brand-primary-hover) focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--brand-primary) focus-visible:ring-offset-2"
      >
        Back to the dashboard
      </Link>
    </main>
  );
}
