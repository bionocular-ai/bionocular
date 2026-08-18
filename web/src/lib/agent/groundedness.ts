/**
 * Does every identifier in an answer trace back to a tool result from the same
 * turn?
 *
 * This is deliberately written over tool results, not over the database. The
 * question is never "does NCT01234567 exist" - it is "did anything this turn
 * actually return NCT01234567". That keeps the check honest if a non-database
 * source is added later, and it catches the failure that matters: an answer
 * that names a trial or a paper nothing looked up.
 */

/**
 * Identifier shapes worth policing. PMIDs and DOIs are here even though nothing
 * currently returns them: with the literature tools gone, an answer citing one
 * is fabricating it, which is exactly what this should catch.
 */
/**
 * Shared with the markdown renderer, which linkifies NCT numbers in answers.
 * Exported as a source string so each caller builds its own regex - a global
 * one carries `lastIndex` state that does not survive being passed around.
 */
export const NCT_ID_SOURCE = String.raw`\bNCT\d{8}\b`;

const IDENTIFIER_PATTERNS: readonly RegExp[] = [
  new RegExp(NCT_ID_SOURCE, 'g'),
  /\bPMID:?\s*(\d{6,9})\b/gi,
  /\b10\.\d{4,9}\/[^\s)"']+/g,
];

export interface GroundednessResult {
  grounded: boolean;
  /** Identifiers found in the answer that no tool result contains. */
  ungrounded: string[];
  /** Every identifier found in the answer, in order of appearance. */
  cited: string[];
}

/** Every string anywhere in the tool results, however deeply nested. */
function collectStrings(value: unknown, into: string[] = []): string[] {
  if (typeof value === 'string') {
    into.push(value);
  } else if (Array.isArray(value)) {
    for (const item of value) collectStrings(item, into);
  } else if (value && typeof value === 'object') {
    for (const item of Object.values(value)) collectStrings(item, into);
  }
  return into;
}

export function extractIdentifiers(answer: string): string[] {
  const found: string[] = [];
  for (const pattern of IDENTIFIER_PATTERNS) {
    // Patterns are module-level and global, so reset before reuse.
    pattern.lastIndex = 0;
    for (const match of answer.matchAll(pattern)) {
      // PMIDs are matched with their prefix but compared as the bare number.
      const identifier = match[1] ?? match[0];
      if (!found.includes(identifier)) found.push(identifier);
    }
  }
  return found;
}

export function checkGroundedness(answer: string, toolResults: unknown[]): GroundednessResult {
  const cited = extractIdentifiers(answer);
  const haystack = collectStrings(toolResults);
  const ungrounded = cited.filter(
    (identifier) => !haystack.some((text) => text.includes(identifier)),
  );
  return { grounded: ungrounded.length === 0, ungrounded, cited };
}
