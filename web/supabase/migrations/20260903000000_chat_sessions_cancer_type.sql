-- The agent runs inside a dashboard category and every tool query is scoped to
-- it server-side, so a saved conversation only makes sense listed beside others
-- from the same indication. Without this the history drawer would offer a user
-- chats whose answers came from a different data scope.
--
-- Rows written before this column existed keep NULL: the scope they ran under
-- was never recorded and cannot be inferred from the transcript. They drop out
-- of every scoped list, which is the honest outcome.
ALTER TABLE chat_sessions ADD COLUMN cancer_type TEXT;

-- The drawer reads one user's sessions for one indication, newest first.
CREATE INDEX idx_chat_sessions_user_cancer_updated
  ON chat_sessions(user_id, cancer_type, updated_at DESC);
