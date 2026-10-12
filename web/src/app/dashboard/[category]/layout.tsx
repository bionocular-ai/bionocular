import { Suspense } from 'react';
import { notFound } from 'next/navigation';
import { DashboardSidebar } from '@/components/nav/DashboardSidebar';
import { DashboardTopNav } from '@/components/nav/DashboardTopNav';
import { CATEGORY_SLUG_MAP } from '@/lib/dashboard-constants';

export default async function CategoryLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ category: string }>;
}) {
  // An unknown slug would otherwise render as an empty, made-up category.
  const { category } = await params;
  if (!Object.hasOwn(CATEGORY_SLUG_MAP, category)) notFound();

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
