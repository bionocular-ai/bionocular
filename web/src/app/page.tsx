import { redirect } from 'next/navigation';
import { ROUTES } from '@/lib/constants';

// The marketing page lives at bionocular.ai (landing/); the app's root goes
// straight to the dashboard, and proxy.ts sends signed-out visitors to login.
export default function Home() {
  redirect(ROUTES.DASHBOARD);
}
