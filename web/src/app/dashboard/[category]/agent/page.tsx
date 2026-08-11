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
      <div className="shrink-0 border-b border-(--brand-border) px-6 py-5 sm:px-8">
        <PageHeader
          category={categoryName}
          title="AI Agent"
          description={`Answers are drawn only from Bionocular's own data for ${categoryName}. The agent has no access to live registries or literature.`}
        />
      </div>

      <div className="min-h-0 flex-1">
        <ChatPanel cancerType={categorySlug} />
      </div>
    </div>
  );
}
