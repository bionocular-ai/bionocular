'use client';

import { useParams } from 'next/navigation';
import { Info } from 'lucide-react';
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
          title="Bionocular Agent"
          description="Answers are drawn only from Bionocular's own data."
          right={
            <div className="flex flex-wrap items-center gap-2">
              <span
                className="rounded-full border border-(--brand-accent) bg-(--brand-accent-light) px-2.5 py-1 text-[11px] font-medium tracking-[0.06em] text-(--brand-primary) uppercase"
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {categoryName}
              </span>
              <span
                title="The agent has no access to live registries or literature. It answers from Bionocular's own database only."
                className="inline-flex cursor-help items-center gap-1 rounded-full border border-(--brand-border) bg-(--brand-surface) px-2.5 py-1 text-[11px] font-medium tracking-[0.06em] text-(--brand-text-muted) uppercase"
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                Internal data only
                <Info className="h-3 w-3" aria-hidden />
              </span>
            </div>
          }
        />
      </div>

      <div className="min-h-0 flex-1">
        <ChatPanel cancerType={categorySlug} />
      </div>
    </div>
  );
}
