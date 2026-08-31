/**
 * A stand-in for the PostgREST query builder, for tests.
 *
 * It records the query a tool builds - table, projection, and every filter with
 * the operator used - and hands back fixture rows. That is what makes the
 * regression this whole change exists for testable without a database: the bug
 * was never in the rows that came back, it was in `.eq()` being used on a
 * `text[]` column, which is visible only in the query.
 */

export interface RecordedFilter {
  operator: 'eq' | 'neq' | 'in' | 'contains' | 'overlaps' | 'ilike' | 'is';
  column: string;
  value: unknown;
}

export interface RecordedQuery {
  table: string;
  projection: string;
  filters: RecordedFilter[];
  limit?: number;
  head: boolean;
  countRequested: boolean;
}

export interface TableFixture {
  rows?: unknown[];
  count?: number;
  error?: { code: string; message: string };
  /**
   * Count returned to a `head: true` query on this table (the via-join
   * "unlinked rows" check), when it must differ from `count`. Falls back to
   * `count` when absent, since a real head query answers the same predicate
   * space as the row query, just without materialising rows.
   */
  unlinkedCount?: number;
}

export interface RecordedUpsert {
  table: string;
  values: Record<string, unknown>;
  onConflict?: string;
}

export interface FakeSupabase {
  from: (table: string) => FakeQuery;
  /** Every query built during the test, in order. */
  queries: RecordedQuery[];
  /** Every row written during the test, in order. */
  upserts: RecordedUpsert[];
}

interface FakeQuery extends PromiseLike<{ data: unknown[] | null; error: unknown; count: number | null }> {
  select: (projection: string, options?: { count?: string; head?: boolean }) => FakeQuery;
  limit: (n: number) => FakeQuery;
  eq: (column: string, value: unknown) => FakeQuery;
  neq: (column: string, value: unknown) => FakeQuery;
  in: (column: string, values: readonly unknown[]) => FakeQuery;
  contains: (column: string, value: unknown) => FakeQuery;
  overlaps: (column: string, values: readonly unknown[]) => FakeQuery;
  ilike: (column: string, value: string) => FakeQuery;
  is: (column: string, value: null) => FakeQuery;
  /** Resolves the first fixture row rather than the array, as PostgREST does. */
  maybeSingle: () => Promise<{ data: unknown; error: unknown }>;
  upsert: (
    values: Record<string, unknown>,
    options?: { onConflict?: string },
  ) => PromiseLike<{ error: unknown }>;
}

/**
 * @param fixtures rows (or an error) keyed by table name; missing tables
 * resolve to zero rows, which is the realistic default.
 */
export function createFakeSupabase(fixtures: Record<string, TableFixture> = {}): FakeSupabase {
  const queries: RecordedQuery[] = [];
  const upserts: RecordedUpsert[] = [];

  function from(table: string): FakeQuery {
    const record: RecordedQuery = {
      table,
      projection: '',
      filters: [],
      head: false,
      countRequested: false,
    };
    queries.push(record);

    const query: FakeQuery = {
      select(projection, options) {
        record.projection = projection;
        record.countRequested = options?.count === 'exact';
        record.head = options?.head === true;
        return query;
      },
      limit(n) {
        record.limit = n;
        return query;
      },
      eq(column, value) {
        record.filters.push({ operator: 'eq', column, value });
        return query;
      },
      neq(column, value) {
        record.filters.push({ operator: 'neq', column, value });
        return query;
      },
      in(column, values) {
        record.filters.push({ operator: 'in', column, value: values });
        return query;
      },
      contains(column, value) {
        record.filters.push({ operator: 'contains', column, value });
        return query;
      },
      overlaps(column, values) {
        record.filters.push({ operator: 'overlaps', column, value: values });
        return query;
      },
      ilike(column, value) {
        record.filters.push({ operator: 'ilike', column, value });
        return query;
      },
      is(column, value) {
        record.filters.push({ operator: 'is', column, value });
        return query;
      },
      maybeSingle() {
        const fixture = fixtures[table] ?? {};
        return Promise.resolve(
          fixture.error
            ? { data: null, error: fixture.error }
            : { data: fixture.rows?.[0] ?? null, error: null },
        );
      },
      upsert(values, options) {
        upserts.push({ table, values, onConflict: options?.onConflict });
        return Promise.resolve({ error: fixtures[table]?.error ?? null });
      },
      then(onfulfilled) {
        const fixture = fixtures[table] ?? {};
        const rows = fixture.rows ?? [];
        const result = fixture.error
          ? { data: null, error: fixture.error, count: null }
          : record.head
            ? { data: null, error: null, count: fixture.unlinkedCount ?? fixture.count ?? rows.length }
            : { data: rows, error: null, count: fixture.count ?? rows.length };
        return Promise.resolve(result).then(onfulfilled);
      },
    };

    return query;
  }

  return { from, queries, upserts };
}
