import { redirect } from 'next/navigation';

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
  redirect(`/dashboard/${category}/trial-updates`);
}
