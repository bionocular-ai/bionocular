/**
 * What of the conversation history the model is sent.
 *
 * The client posts the whole transcript, tool outputs included, and the UI
 * and `chat_sessions` need them whole. The model does not: a 189-row outcomes
 * result from turn one is re-sent on every step of every later turn otherwise.
 * Before `convertToModelMessages`, every earlier turn's data-tool output is
 * replaced by a stub that keeps what the model still needs - what was queried,
 * the coverage report, and the identifiers the rows carried - and drops the
 * rows. The identifiers are also returned so the turn's evidence set starts
 * with them and a citation of an earlier result still grounds.
 *
 * This is a model-context concern only. Nothing here touches what is
 * persisted or rendered.
 */

import type { UIMessage } from 'ai';
import { collectIdentifiers } from './tools/turn';

/** Tools whose outputs carry rows worth pruning. `load_skill` is kept: it is method, not data. */
const DATA_TOOL_PARTS = new Set(['tool-query_proprietary_data', 'tool-lookup_trial']);

/** Identifiers to keep on a stub; enough to name every trial a sweep found. */
const MAX_STUB_IDS = 200;

export interface PrunedHistory {
  messages: UIMessage[];
  /** Every identifier an earlier turn's results carried. */
  retainedEvidence: string[];
}

interface ToolPartLike {
  type: string;
  state?: string;
  output?: unknown;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

/** The rows an output carries, whichever tool shape it is. */
function rowsOf(output: Record<string, unknown>): unknown[] {
  if (Array.isArray(output.rows)) return output.rows;
  if (isRecord(output.tables)) {
    return Object.values(output.tables).flatMap((hit) =>
      isRecord(hit) && Array.isArray(hit.rows) ? hit.rows : [],
    );
  }
  return [];
}

/**
 * The stub an earlier turn's output becomes. Everything except the rows is
 * kept as-is - `coverage`, `reason`, `hint`, `found`, `nctId` - so a refusal
 * or a miss reads exactly as it did.
 */
export function stubOutput(output: unknown): unknown {
  if (!isRecord(output)) return output;
  const rows = rowsOf(output);
  if (rows.length === 0) return output;
  const ids = [...collectIdentifiers(rows)].slice(0, MAX_STUB_IDS);
  const { rows: _rows, tables, ...rest } = output;
  void _rows;
  const stubbedTables = isRecord(tables)
    ? Object.fromEntries(
        Object.entries(tables).map(([table, hit]) => [
          table,
          isRecord(hit) && Array.isArray(hit.rows) ? { ...hit, rows: undefined, rowCount: hit.rows.length } : hit,
        ]),
      )
    : undefined;
  return {
    ...rest,
    ...(stubbedTables ? { tables: stubbedTables } : {}),
    pruned: true,
    rowCount: rows.length,
    identifiers: ids,
    hint: 'Rows from an earlier turn are no longer in context; re-query if the answer needs them.',
  };
}

export function pruneHistory(messages: UIMessage[]): PrunedHistory {
  const retained = new Set<string>();
  // The current turn is the last user message and anything after it; every
  // assistant message before it is history.
  const lastUser = messages.map((m) => m.role).lastIndexOf('user');

  const pruned = messages.map((message, index) => {
    if (message.role !== 'assistant' || index > lastUser) return message;
    let changed = false;
    const parts = message.parts.map((part) => {
      const toolPart = part as ToolPartLike;
      if (!DATA_TOOL_PARTS.has(toolPart.type) || toolPart.state !== 'output-available') return part;
      if (!isRecord(toolPart.output) || rowsOf(toolPart.output).length === 0) return part;
      for (const id of collectIdentifiers(rowsOf(toolPart.output))) retained.add(id);
      changed = true;
      return { ...part, output: stubOutput(toolPart.output) };
    });
    return changed ? ({ ...message, parts } as UIMessage) : message;
  });

  return { messages: pruned, retainedEvidence: [...retained] };
}
