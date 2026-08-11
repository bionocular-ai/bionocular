-- Trace ID of the most recent request against this session. Every tool call
-- logs the same ID, so a saved conversation can be tied back to the queries
-- that produced its last answer.
ALTER TABLE chat_sessions
  ADD COLUMN last_trace_id TEXT;
