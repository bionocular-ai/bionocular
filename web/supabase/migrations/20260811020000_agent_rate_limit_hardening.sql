-- Two fixes to the agent rate limiter.

-- 1. PRIMARY KEY (user_id, ts) made the timestamp part of the key, so two
--    requests from one user landing in the same microsecond collided on insert.
--    A unique violation inside the function surfaces as a 500 to the caller —
--    the one case where the user should have seen a clean 429. A surrogate key
--    lets every request be recorded; idx_agent_rate_limit_user_ts already
--    covers the lookups the function does.
ALTER TABLE agent_rate_limit DROP CONSTRAINT agent_rate_limit_pkey;

ALTER TABLE agent_rate_limit
  ADD COLUMN id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY;

-- 2. A SECURITY DEFINER function without an explicit search_path resolves
--    unqualified names against the caller's, so a same-named table earlier on
--    the path would be used instead of the intended one. Body is otherwise
--    unchanged from 20260426114757_agent.sql.
CREATE OR REPLACE FUNCTION check_agent_rate_limit(
  p_user_id        UUID,
  p_max            INT DEFAULT 20,
  p_window_seconds INT DEFAULT 60
) RETURNS BOOLEAN AS $$
DECLARE
  current_count INT;
BEGIN
  DELETE FROM agent_rate_limit
    WHERE user_id = p_user_id
      AND ts < now() - (p_window_seconds || ' seconds')::interval;

  SELECT COUNT(*) INTO current_count
    FROM agent_rate_limit
    WHERE user_id = p_user_id
      AND ts > now() - (p_window_seconds || ' seconds')::interval;

  IF current_count >= p_max THEN
    RETURN FALSE;
  END IF;

  INSERT INTO agent_rate_limit(user_id) VALUES (p_user_id);
  RETURN TRUE;
END;
$$ LANGUAGE plpgsql
   SECURITY DEFINER
   SET search_path = public, pg_temp;
