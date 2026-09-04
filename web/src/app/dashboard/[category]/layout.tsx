import { Suspense } from 'react';
import { DashboardSidebar } from '@/components/nav/DashboardSidebar';
import { DashboardTopNav } from '@/components/nav/DashboardTopNav';

export default function CategoryLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-(--brand-bg)">
      <DashboardTopNav />
      <div className="flex min-w-0 flex-1">
        <Suspense fallback={<div className="hidden w-64 shrink-0 md:block" />}>
          <DashboardSidebar />
        </Suspense>
        <main className="min-w-0 flex-1 pt-12 md:pt-0">{children}</main>
      </div>
    </div>
  );
}
