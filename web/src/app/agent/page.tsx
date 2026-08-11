import { redirect } from 'next/navigation';
import { dashboardRoute } from '@/lib/constants';
import { DEFAULT_CANCER_TYPE_SLUG } from '@/lib/dashboard-constants';

/**
 * The agent used to live here, standalone and with no cancer type in scope.
 * It now runs inside a dashboard category, which is where its scope comes from.
 * Kept as a redirect so existing links and bookmarks still land somewhere real.
 */
export default function AgentRedirectPage() {
  redirect(dashboardRoute(DEFAULT_CANCER_TYPE_SLUG, 'agent'));
}
