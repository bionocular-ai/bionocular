-- Agent findings: things the assistant saved on behalf of a user.
CREATE TABLE agent_findings (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id     UUID REFERENCES auth.users(id) NOT NULL,
  finding_type TEXT NOT NULL,
  title       TEXT NOT NULL,
  summary     TEXT NOT NULL,
  source_tool TEXT NOT NULL,
  citations   JSONB DEFAULT '[]',
  metadata    JSONB DEFAULT '{}',
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- Persisted chat history.
CREATE TABLE chat_sessions (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id     UUID REFERENCES auth.users(id) NOT NULL,
  title       TEXT,
  messages    JSONB NOT NULL DEFAULT '[]',
  token_usage JSONB,
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chat_sessions_user_updated   ON chat_sessions(user_id, updated_at DESC);
CREATE INDEX idx_agent_findings_user_created  ON agent_findings(user_id, created_at DESC);

ALTER TABLE agent_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions  ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own_findings" ON agent_findings FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_sessions" ON chat_sessions  FOR ALL USING (auth.uid() = user_id);

-- Per-user sliding-window rate limiter. Accessed only via the SECURITY DEFINER
-- RPC below (which bypasses RLS) using the secret key. RLS is enabled with no
-- policies as defense-in-depth so anon/authenticated keys can't reach it via
-- PostgREST even if the table is accidentally exposed.
CREATE TABLE agent_rate_limit (
  user_id UUID NOT NULL,
  ts      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, ts)
);

CREATE INDEX idx_agent_rate_limit_user_ts ON agent_rate_limit(user_id, ts DESC);

ALTER TABLE agent_rate_limit ENABLE ROW LEVEL SECURITY;

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
$$ LANGUAGE plpgsql SECURITY DEFINER;
