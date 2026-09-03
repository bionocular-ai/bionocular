'use client';

import { useParams } from 'next/navigation';
import { PageHeader } from '@/components/dashboard/PageHeader';
import { ChatPanel } from '@/components/agent/ChatPanel';
import { slugToCategory } from '@/lib/dashboard-constants';

export default function AgentPage() {
  const params = useParams();
  const categorySlug = params?.category as string;
  const categoryName = slugToCategory(categorySlug);

  // The chat scrolls internally, so the page itself must be exactly as tall as
  // the viewport minus the top nav (3.5rem), plus the mobile bar the dashboard
  // layout leaves room for (3rem).
  return (
    <div className="flex h-[calc(100dvh-6.5rem)] flex-col md:h-[calc(100dvh-3.5rem)]">
      {/* Same measure and gutters as the thread and composer below, so the
          header, the messages and the input all share one left edge. */}
      <div className="shrink-0 px-4 pt-6 pb-4 sm:px-8">
        <PageHeader
          className="mx-auto w-full max-w-3xl"
          category={categoryName}
          title="Bionocular Agent"
          description="Bionocular's own data only - no live registries or literature."
        />
      </div>

      <div className="min-h-0 flex-1">
        <ChatPanel cancerType={categorySlug} />
      </div>
    </div>
  );
}
