/**
 * One log line per tool call, keyed by the request's trace ID.
 *
 * The trace ID is also written to the chat session row, so a line here can be
 * tied back to the conversation that produced it - previously a tool call left
 * no trace at all, and a wrong answer could not be traced to the query behind it.
 */

const MAX_LOGGED_STRING = 80;

/**
 * Arguments are model-authored, so they are logged shortened rather than
 * verbatim. None of the tools take secrets; the truncation is there to keep a
 * long free-text argument from dominating the line.
 */
function redactArgs(args: unknown): unknown {
  if (typeof args === 'string') {
    return args.length > MAX_LOGGED_STRING ? `${args.slice(0, MAX_LOGGED_STRING)}…` : args;
  }
  if (Array.isArray(args)) return args.map(redactArgs);
  if (args && typeof args === 'object') {
    return Object.fromEntries(
      Object.entries(args).map(([key, value]) => [key, redactArgs(value)]),
    );
  }
  return args;
}

/** Rows a result carries, for whichever shape the tool returned. */
function rowCount(result: unknown): number | undefined {
  if (!result || typeof result !== 'object') return undefined;
  const record = result as Record<string, unknown>;
  if (Array.isArray(record.rows)) return record.rows.length;
  if (record.tables && typeof record.tables === 'object') {
    return Object.values(record.tables as Record<string, unknown>).reduce<number>((total, hit) => {
      const rows = (hit as { rows?: unknown[] } | null)?.rows;
      return total + (Array.isArray(rows) ? rows.length : 0);
    }, 0);
  }
  return undefined;
}

/** How the call ended, in the tools' own vocabulary. */
function outcomeOf(result: unknown): string {
  if (!result || typeof result !== 'object') return 'ok';
  const record = result as Record<string, unknown>;
  if (record.ok === false || record.found === false) {
    return String(record.reason ?? 'not_ok');
  }
  return 'ok';
}

export async function runTool<T>(
  name: string,
  traceId: string,
  args: unknown,
  execute: () => Promise<T>,
): Promise<T> {
  const startedAt = Date.now();
  try {
    const result = await execute();
    console.info('agent tool', {
      traceId,
      tool: name,
      args: redactArgs(args),
      outcome: outcomeOf(result),
      rows: rowCount(result),
      ms: Date.now() - startedAt,
    });
    return result;
  } catch (err) {
    // The tools return structured failures rather than throwing, so anything
    // caught here is unexpected and worth the louder level.
    console.error('agent tool threw', {
      traceId,
      tool: name,
      args: redactArgs(args),
      ms: Date.now() - startedAt,
      error: err instanceof Error ? err.message : String(err),
    });
    throw err;
  }
}
