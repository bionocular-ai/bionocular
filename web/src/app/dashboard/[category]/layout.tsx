import { Suspense } from 'react';
import { DashboardSidebar } from '@/components/nav/DashboardSidebar';
import { DashboardTopNav } from '@/components/nav/DashboardTopNav';

export default function CategoryLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-(--brand-bg)">
      <Suspense fallback={<aside className="w-24 shrink-0" />}>
        <DashboardSidebar />
      </Suspense>
      <div className="flex min-w-0 flex-1 flex-col">
        <DashboardTopNav />
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
