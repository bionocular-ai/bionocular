import { redirect } from 'next/navigation';
import Link from 'next/link';
import { createClient } from '@/lib/supabase/server';
import { Logo } from '@/components/Logo';
import { UserMenu } from '@/components/user-menu';
import { HomeNavLink } from '@/components/nav/HomeNavLink';
import { ChatPanel } from '@/components/agent/ChatPanel';
import { ROUTES } from '@/lib/constants';

export const dynamic = 'force-dynamic';

export default async function AgentPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    redirect(`${ROUTES.LOGIN}?callbackUrl=${encodeURIComponent(ROUTES.AGENT)}`);
  }

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-[var(--brand-bg)]">
      <header className="sticky top-0 z-50 shrink-0 border-b border-slate-200 bg-white shadow-sm">
        <div className="w-full px-6 sm:px-10 lg:px-16">
          <div className="flex h-14 items-center justify-between gap-3 sm:h-16">
            <Link href={ROUTES.HOME} className="brand flex-shrink-0 hover:opacity-80 transition-opacity">
              <Logo height={32} />
              <span className="brand-text dashboard-brand-text">
                bi<span className="brand-o">o</span>nocular
              </span>
            </Link>
            <div className="flex items-center gap-3">
              <HomeNavLink />
              <UserMenu />
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-hidden">
        <ChatPanel />
      </main>
    </div>
  );
}
