/**
 * State shared by every tool call within one agent turn.
 *
 * Three things have to be known across calls rather than per call: how much
 * of the turn's result budget is left, which identifiers the turn has put in
 * front of the model, and what each call did. All live here, built once per
 * request by `agentTools` and closed over by each tool.
 */

import { NCT_ID_SOURCE } from '../groundedness';

/**
 * Total tool-result characters one turn may send the model, across every
 * call. The per-call cap (`MAX_RESULT_CHARS`, 130k) bounds one result; without
 * this, seven calls at the cap were admissible, and each later step re-sends
 * all of them. Two full results' worth: enough for a filter sweep plus the
 * enrichment pass that follows it, which is the widest turn the product asks
 * for.
 */
export const MAX_TURN_RESULT_CHARS = 260_000;

/**
 * Below this many characters left, a call returns its counts but no rows: a
 * one-row sample of a 500-row match would mislead more than it informs.
 */
export const MIN_RESULT_CHARS = 2_000;

/** Columns whose values are the identifiers an answer may cite. */
const IDENTIFIER_COLUMNS = new Set(['nct_id', 'nct_ids', 'abstract_id', 'publication_id', 'url', 'id']);

/**
 * Every identifier a set of rows carries. Identifier columns are taken
 * whole; every other string is scanned for NCT numbers, since a title or a
 * news headline can name a trial too.
 */
export function collectIdentifiers(value: unknown, into = new Set<string>(), column?: string): Set<string> {
  if (typeof value === 'string') {
    if (column !== undefined && IDENTIFIER_COLUMNS.has(column)) into.add(value);
    for (const id of value.match(new RegExp(NCT_ID_SOURCE, 'g')) ?? []) into.add(id);
  } else if (Array.isArray(value)) {
    for (const entry of value) collectIdentifiers(entry, into, column);
  } else if (value && typeof value === 'object') {
    for (const [key, entry] of Object.entries(value)) collectIdentifiers(entry, into, key);
  }
  return into;
}

/** One tool call, as the run record reports it. */
export interface ToolCallRecord {
  tool: string;
  /** How the call ended, in the tools' own vocabulary (`ok`, `no_rows`, ...). */
  outcome: string;
  ms: number;
  /** Characters of result sent to the model. */
  chars: number;
  rows?: number;
  matched?: number;
  truncatedBy?: string;
}

export interface TurnState {
  /** Characters of tool result still allowed this turn. */
  remainingChars(): number;
  /** Charge a result that was sent to the model. */
  spend(chars: number): void;
  /** Characters spent so far. */
  spentChars(): number;
  readonly limitChars: number;
  /**
   * Every identifier a tool result has carried this turn, plus any the
   * caller retained from earlier turns. `store_finding` checks citations
   * against it, and the route's grounding check reads it.
   */
  readonly evidence: Set<string>;
  /** Record the identifiers in a result's rows. */
  recordEvidence(rows: readonly unknown[]): void;
  /** Skills the model loaded this turn, for the run record. */
  readonly skillsLoaded: Set<string>;
  /** Every tool call this turn, in order. */
  readonly toolCalls: ToolCallRecord[];
  /** `tool:args` keys already executed this turn, so an exact repeat is refused. */
  readonly seenCalls: Set<string>;
}

export interface TurnStateOptions {
  limitChars?: number;
  /** Identifiers from earlier turns the model may still cite. */
  retainedEvidence?: Iterable<string>;
}

export function createTurnState({
  limitChars = MAX_TURN_RESULT_CHARS,
  retainedEvidence = [],
}: TurnStateOptions = {}): TurnState {
  let spent = 0;
  const evidence = new Set<string>(retainedEvidence);

  return {
    limitChars,
    remainingChars: () => Math.max(0, limitChars - spent),
    spentChars: () => spent,
    spend: (chars) => {
      spent += chars;
    },
    evidence,
    recordEvidence: (rows) => {
      collectIdentifiers(rows, evidence);
    },
    skillsLoaded: new Set(),
    toolCalls: [],
    seenCalls: new Set(),
  };
}
