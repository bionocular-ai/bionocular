-- Thumbs up/down on an individual assistant answer.
--
-- Separate from agent_findings, which records things a user chose to save.
-- This records whether an answer was any good, which is the signal for judging
-- the agent's quality over time - the transcript alone never says that.
CREATE TABLE agent_feedback (
  id         UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id    UUID REFERENCES auth.users(id) NOT NULL,
  session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE NOT NULL,
  -- The assistant message the rating is about, as the client knows it.
  message_id TEXT NOT NULL,
  rating     TEXT NOT NULL CHECK (rating IN ('up', 'down')),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  -- One rating per answer per user: changing your mind replaces it rather than
  -- stacking a second row, so counts stay a headcount and not a click count.
  UNIQUE (user_id, message_id)
);

CREATE INDEX idx_agent_feedback_session ON agent_feedback(session_id);

ALTER TABLE agent_feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own_feedback" ON agent_feedback FOR ALL USING (auth.uid() = user_id);
