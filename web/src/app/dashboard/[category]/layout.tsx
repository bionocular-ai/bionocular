import { Suspense } from 'react';
import { DashboardSidebar } from '@/components/nav/DashboardSidebar';

export default function CategoryLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-(--brand-bg)">
      <Suspense fallback={<aside className="w-24 shrink-0" />}>
        <DashboardSidebar />
      </Suspense>
      <main className="flex-1 min-w-0">{children}</main>
    </div>
  );
}
