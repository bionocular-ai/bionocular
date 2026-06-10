import { redirect } from 'next/navigation';
import { dashboardRoute } from '@/lib/constants';

/**
 * The cancer-category landing route has no standalone view — it opens directly
 * on the first dashboard section (Trial Updates), per the sidebar redesign.
 */
export default async function CategoryIndexPage({
  params,
}: {
  params: Promise<{ category: string }>;
}) {
  const { category } = await params;
  redirect(dashboardRoute(category, 'trial-updates'));
}
