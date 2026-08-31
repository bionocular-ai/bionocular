/**
 * The turn's answer, as a link into the Efficacy Intelligence Hub.
 *
 * The hub charts `trial_outcomes`, which is the table a question about ORR or
 * PFS is answered from - so when a turn queried that table under filters the
 * hub can express, the same population can be opened as charts rather than
 * ending at a table in the chat.
 *
 * Derived from the tool *inputs*, not the rows. The filters are what the hub
 * needs, and re-deriving them from a capped result would be guessing at the
 * question from a sample of its answer.
 */

import { dashboardRoute } from '@/lib/constants';

/** The one table the hub reads. A turn that never touched it has nothing to open. */
const HUB_TABLE = 'trial_outcomes';

/**
 * Filters the hub cannot reproduce, so a turn using either gets no link.
 *
 * The hub's treatment picker is keyed by exact treatment name and cannot
 * express a substring match, and it has no way to be handed an arbitrary set of
 * NCT numbers. A link that quietly opened a different population than the
 * answer would be worse than no link at all.
 *
 * Neither is the common path for the questions this link exists for: phase and
 * status reach `trial_outcomes` through the registry join, so a phase-scoped
 * question filters it directly instead of handing over NCT numbers.
 */
const UNREPRODUCIBLE = ['drug', 'nctIds'] as const;

export interface EfficacyLink {
  href: string;
  /**
   * The agent's own result was capped, so the hub - which applies no size
   * budget - will legitimately show more rows than the answer did.
   */
  showsMore: boolean;
}

interface TurnToolPart {
  input?: unknown;
  output?: unknown;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : null;
}

/** A successful `trial_outcomes` query whose filters the hub can express. */
function usableQuery(part: TurnToolPart): Record<string, unknown> | null {
  const output = asRecord(part.output);
  const input = asRecord(part.input);
  if (!output || !input) return null;
  if (output.ok !== true || output.table !== HUB_TABLE) return null;
  if (!Array.isArray(output.rows) || output.rows.length === 0) return null;
  if (UNREPRODUCIBLE.some((name) => input[name] !== undefined)) return null;
  return input;
}

export function efficacyLinkFor(
  parts: readonly TurnToolPart[],
  cancerSlug: string,
): EfficacyLink | null {
  const part = parts.find((candidate) => usableQuery(candidate) !== null);
  if (!part) return null;
  const input = usableQuery(part)!;

  const query: Record<string, string> = { mode: 'efficacy' };
  // Every hub filter the agent left open is pinned to its `all` value, not left
  // to the hub's default. Funding is the one that bites: the hub defaults to
  // `industry`, and the agent applies no funding filter unless asked - on the
  // Phase 1 cutaneous melanoma set that default alone hides 96 of 189 rows.
  query.funding = typeof input.funding === 'string' ? input.funding : 'all';
  if (typeof input.phase === 'string') query.phase = input.phase;
  if (Array.isArray(input.status) && input.status.length > 0) {
    query.status = input.status.join(',');
  }

  const coverage = asRecord(asRecord(part.output)?.coverage);
  return {
    href: dashboardRoute(cancerSlug, 'analytics', query),
    showsMore: coverage?.complete === false,
  };
}
