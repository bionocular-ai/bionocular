import { createClient } from '@supabase/supabase-js';
import { env, getServerEnv } from '@/lib/env';

/**
 * Server-only Supabase client using the secret key. Bypasses RLS.
 *
 * NEVER import from a client component or any file that ships to the browser.
 * Use only inside route handlers, server actions, or server components that
 * need privileged writes (e.g. inserting rate-limit rows, persisting agent
 * findings on behalf of a user).
 */
export function createServiceClient() {
  const { supabaseSecretKey } = getServerEnv();
  return createClient(env.supabase.url, supabaseSecretKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
