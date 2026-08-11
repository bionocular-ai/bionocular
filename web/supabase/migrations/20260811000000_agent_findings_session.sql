-- Link a saved finding back to the conversation that produced it. Without this
-- the audit trail stops at the finding: there is no way to see which turn, or
-- which tool results, it came from.
ALTER TABLE agent_findings
  ADD COLUMN session_id UUID REFERENCES chat_sessions(id) ON DELETE SET NULL;

CREATE INDEX idx_agent_findings_session ON agent_findings(session_id);
