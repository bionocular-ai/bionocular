import { createServiceClient } from '@/lib/supabase/service';

/**
 * Postgres-backed sliding-window rate limit. 20 requests per 60s per user
 * (defaults baked into the SQL function). Returns true if the request is
 * allowed and was recorded.
 *
 * Multi-instance safe — counter lives in Supabase Postgres, not memory.
 */
export async function checkAgentRateLimit(userId: string): Promise<boolean> {
  const supabase = createServiceClient();
  const { data, error } = await supabase.rpc('check_agent_rate_limit', {
    p_user_id: userId,
  });
  if (error) throw new Error(`Rate limit check failed: ${error.message}`);
  return data === true;
}
