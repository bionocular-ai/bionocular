import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { PGlite } from '@electric-sql/pglite';
import { beforeEach, describe, expect, it } from 'vitest';

// Runs supabase/migrations/20261127000000_outcome_values.sql in an in-process
// Postgres (pglite). The migration itself is never edited for pglite; what
// Supabase provides and pglite lacks is stubbed here instead:
// - the API roles anon, authenticated and service_role (service_role bypasses
//   RLS, as on Supabase);
// - trial_outcomes and clinical_trials, which predate the migrations folder,
//   cut down to the columns the migration reads, with the grants the API
//   roles hold on them live.
const MIGRATION = readFileSync(
  fileURLToPath(
    new URL('../../../../supabase/migrations/20261127000000_outcome_values.sql', import.meta.url),
  ),
  'utf8',
);

const SUPABASE_STUBS = `
  create role anon nologin;
  create role authenticated nologin;
  create role service_role nologin bypassrls;
  grant usage on schema public to anon, authenticated, service_role;

  create table clinical_trials (nct_id text primary key);
  create table trial_outcomes (
    id text primary key, source_type text, source_name text, abstract_id text,
    source_url text, nct_id text, arm_id text, arm_name text, cancer_type text[],
    generic_name text, num_patients int, line_of_treatment text,
    expert_review text, expert_reviewed_at timestamptz
  );
  grant select on clinical_trials, trial_outcomes to authenticated;
  grant all on clinical_trials, trial_outcomes to service_role;
`;

const ASH = 'extraction_results_ASH_2025';
const AML = ['Acute Myeloid Leukemia'];

type Row = Record<string, unknown>;

function arm(abstract: number, armId: string, drug: string): Row {
  return {
    id: `abstract_ASH_2025_${abstract}_${armId}`,
    source_type: 'abstract',
    source_name: ASH,
    abstract_id: `ASH_2025_${abstract}`,
    source_url: `https://doi.org/10.1182/blood-2025-${abstract}`,
    nct_id: abstract === 3 ? null : 'NCT00000001',
    arm_id: armId,
    arm_name: `Arm ${armId}`,
    cancer_type: AML,
    generic_name: drug,
    num_patients: 40,
  };
}

/** One outcome_values row; keys equal the table's columns, minus `id`. */
function val(abstract: number, armId: string | null, field: string, value: string, extra: Row = {}): Row {
  return {
    trial_outcome_id: armId ? `abstract_ASH_2025_${abstract}_${armId}` : null,
    source_type: 'abstract',
    source_id: `ASH_2025_${abstract}`,
    source_url: `https://doi.org/10.1182/blood-2025-${abstract}`,
    nct_id: abstract === 3 ? null : 'NCT00000001',
    cancer_type: AML,
    field_key: field,
    context: '',
    value_text: value,
    value_num: Number(value),
    qualifier: null,
    n: null,
    detail: '',
    derived: false,
    origin: 'abstract',
    caveat: null,
    ...extra,
  };
}

// Abstract 1: two arms, a duplicated value, a pooled value and trial criteria.
// Abstract 2: one arm but only a pooled value (the 31 pooled-only abstracts).
// Abstract 3: one arm, no NCT id, no pooled value.
// Abstract 4: no arm rows at all, only abstract-level values (e.g. abstract 1075).
const ABSTRACTS: Record<number, { arms: Row[]; vals: Row[] }> = {
  1: {
    arms: [arm(1, 'a', 'Venetoclax'), arm(1, 'b', 'Azacitidine')],
    vals: [
      val(1, 'a', 'orr_rate', '73', { n: 41 }),
      val(1, 'b', 'orr_rate', '50'),
      val(1, 'b', 'orr_rate', '52'),
      val(1, null, 'orr_rate', '61', { derived: true }),
      val(1, null, 'response_criteria', 'ELN 2022', { value_num: null, origin: 'registry' }),
    ],
  },
  2: {
    arms: [arm(2, 'a', 'Gilteritinib')],
    vals: [val(2, null, 'orr_rate', '55', { context: 'patients with FLT3-ITD', caveat: 'needs a person' })],
  },
  3: {
    arms: [arm(3, 'a', 'Ivosidenib')],
    vals: [val(3, 'a', 'orr_rate', '30')],
  },
  4: {
    arms: [],
    vals: [
      val(4, null, 'generic_name', 'Ziftomenib', { value_num: null }),
      val(4, null, 'orr_rate', '35'),
    ],
  },
};

let db: PGlite;

async function replace(abstract: number, arms: Row[], vals: Row[]) {
  await asRole('service_role', () =>
    db.query('select replace_ash_abstract($1, $2, $3)', [
      `ASH_2025_${abstract}`,
      JSON.stringify(arms),
      JSON.stringify(vals),
    ]),
  );
}

/** Runs `fn` as an API role, the way PostgREST does, then returns to the superuser. */
async function asRole<T>(role: string, fn: () => Promise<T>): Promise<T> {
  await db.exec(`set role ${role}`);
  try {
    return await fn();
  } finally {
    await db.exec('reset role');
  }
}

async function view(where = 'true'): Promise<Row[]> {
  const { rows } = await asRole('authenticated', () =>
    db.query<Row>(`select * from arm_outcomes where ${where} order by id`),
  );
  return rows;
}

beforeEach(async () => {
  db = await PGlite.create();
  await db.exec(SUPABASE_STUBS);
  await db.exec(MIGRATION);
  await db.exec(`
    insert into clinical_trials values ('NCT00000001');
    insert into outcome_fields (key, label, family, scope, value_type, definition, sort_order) values
      ('orr_rate', 'ORR', 'response_rates', 'arm', 'percent', 'Overall response rate.', 1),
      ('response_criteria', 'Response criteria', 'trial_design', 'trial', 'text', 'Criteria used.', 1);
    insert into outcome_fields (key, label, family, scope, value_type, definition, wide_column, sort_order)
      values ('generic_name', 'Generic name', 'regimen_drug', 'arm', 'text', 'Drug.', 'generic_name', 1);
    -- A melanoma row: it must never show up in the view.
    insert into trial_outcomes (id, source_type, source_name, abstract_id, generic_name)
      values ('abstract_ASCO_1_a', 'abstract', 'extraction_results_ASCO_2025', 'ASCO_1', 'Nivolumab');
  `);
  for (const [abstract, { arms, vals }] of Object.entries(ABSTRACTS)) {
    await replace(Number(abstract), arms, vals);
  }
});

describe('outcome_values migration', () => {
  it('one view row per arm plus one All arms row per abstract with arm-less values', async () => {
    const rows = await view();
    expect(rows.map((r) => [r.id, r.arm_name])).toEqual([
      ['abstract_ASH_2025_1_a', 'Arm a'],
      ['abstract_ASH_2025_1_all', 'All arms (pooled or trial-level)'],
      ['abstract_ASH_2025_1_b', 'Arm b'],
      ['abstract_ASH_2025_2_a', 'Arm a'],
      ['abstract_ASH_2025_2_all', 'All arms (pooled or trial-level)'],
      ['abstract_ASH_2025_3_a', 'Arm a'],
      ['abstract_ASH_2025_4_all', 'All arms (pooled or trial-level)'],
    ]);
    const all1 = rows.find((r) => r.id === 'abstract_ASH_2025_1_all')!;
    expect(all1).toMatchObject({
      trial_outcome_id: null,
      source_id: 'ASH_2025_1',
      source_url: 'https://doi.org/10.1182/blood-2025-1',
      nct_id: 'NCT00000001',
      cancer_type: AML,
      abstract_drugs: 'Azacitidine; Venetoclax',
      values: { response_rates: [{ field: 'ORR', value: '61', derived: true }] },
    });
    // The arm-less trial value does not make a pooled entry of its own.
    expect(rows.find((r) => r.id === 'abstract_ASH_2025_3_a')).toMatchObject({
      nct_id: null,
      generic_name: 'Ivosidenib',
      num_patients: 40,
      abstract_drugs: 'Ivosidenib',
      values: { response_rates: [{ field: 'ORR', value: '30' }] },
    });
  });

  it('arm-less abstract keeps its DOI link and drug name on the All arms row', async () => {
    expect(await view(`source_id = 'ASH_2025_4'`)).toMatchObject([
      {
        id: 'abstract_ASH_2025_4_all',
        source_url: 'https://doi.org/10.1182/blood-2025-4',
        abstract_drugs: 'Ziftomenib',
        nct_id: 'NCT00000001',
      },
    ]);
  });

  it('pooled_only_abstract_has_all_arms_row', async () => {
    const rows = await view(`source_id = 'ASH_2025_2'`);
    expect(rows.map((r) => r.id)).toEqual(['abstract_ASH_2025_2_a', 'abstract_ASH_2025_2_all']);
    expect(rows[0].values).toBeNull();
    expect(rows[1].values).toEqual({
      response_rates: [
        { field: 'ORR', value: '55', context: 'patients with FLT3-ITD', caveat: 'needs a person' },
      ],
    });
  });

  it('trial values ride on every arm row', async () => {
    const rows = await view(`source_id = 'ASH_2025_1'`);
    expect(rows).toHaveLength(3);
    for (const row of rows) {
      // Registry provenance survives, so the agent can say where the criteria came from.
      expect(row.trial).toEqual({ 'Response criteria': { value: 'ELN 2022', origin: 'registry' } });
      expect(row.values).not.toHaveProperty('trial_design');
    }
    expect((await view(`source_id = 'ASH_2025_3'`))[0].trial).toBeNull();
  });

  it('duplicate field and context are both kept', async () => {
    const [b] = await view(`id = 'abstract_ASH_2025_1_b'`);
    expect(b.values).toEqual({
      response_rates: [
        { field: 'ORR', value: '50' },
        { field: 'ORR', value: '52' },
      ],
    });
  });

  it('reload_removes_cleared_value_keeps_expert_review', async () => {
    await db.exec(`
      update trial_outcomes set expert_review = 'good', expert_reviewed_at = '2026-11-20'
      where id = 'abstract_ASH_2025_1_a'
    `);
    const reloaded = { ...arm(1, 'a', 'Venetoclax'), arm_name: 'Arm a renamed' };
    await replace(1, [reloaded], ABSTRACTS[1].vals.filter((v) => v.trial_outcome_id === 'abstract_ASH_2025_1_a'));

    const { rows: arms } = await db.query<Row>(
      `select id, arm_name, expert_review, expert_reviewed_at from trial_outcomes
       where abstract_id = 'ASH_2025_1'`,
    );
    expect(arms).toEqual([
      {
        id: 'abstract_ASH_2025_1_a',
        arm_name: 'Arm a renamed',
        expert_review: 'good',
        expert_reviewed_at: new Date('2026-11-20T00:00:00Z'),
      },
    ]);
    const { rows: vals } = await db.query<Row>(
      `select trial_outcome_id, value_text from outcome_values where source_id = 'ASH_2025_1'`,
    );
    expect(vals).toEqual([{ trial_outcome_id: 'abstract_ASH_2025_1_a', value_text: '73' }]);
    expect((await view(`source_id = 'ASH_2025_1'`)).map((r) => r.id)).toEqual(['abstract_ASH_2025_1_a']);
  });

  it('delete_ash_abstracts_except removes dropped abstracts', async () => {
    const { rows } = await asRole('service_role', () =>
      db.query<{ removed: number }>(
        `select delete_ash_abstracts_except(array['ASH_2025_1', 'ASH_2025_2', 'ASH_2025_4']) as removed`,
      ),
    );
    expect(rows[0].removed).toBe(1);
    expect((await view()).map((r) => r.source_id)).not.toContain('ASH_2025_3');
    const { rows: left } = await db.query<Row>(
      `select (select count(*)::int from trial_outcomes where abstract_id = 'ASH_2025_3') as arms,
              (select count(*)::int from outcome_values where source_id = 'ASH_2025_3') as vals,
              (select count(*)::int from trial_outcomes where id = 'abstract_ASCO_1_a') as melanoma`,
    );
    expect(left[0]).toEqual({ arms: 0, vals: 0, melanoma: 1 });
  });

  it('delete_ash_abstracts_except refuses an empty or null keep list', async () => {
    for (const keep of ['{}', null]) {
      await expect(
        asRole('service_role', () => db.query('select delete_ash_abstracts_except($1)', [keep])),
      ).rejects.toThrow(/empty keep list/);
    }
    const { rows } = await db.query<Row>(`select count(*)::int as n from trial_outcomes`);
    expect(rows[0].n).toBe(5);
  });

  it('values keyed by family support a json path select', async () => {
    const { rows } = await asRole('authenticated', () =>
      db.query<{ rr: unknown }>(
        `select values->'response_rates' as rr from arm_outcomes where id = 'abstract_ASH_2025_1_a'`,
      ),
    );
    expect(rows).toEqual([{ rr: [{ field: 'ORR', value: '73', n: 41 }] }]);
  });

  it('anon cannot execute the RPCs', async () => {
    for (const role of ['anon', 'authenticated']) {
      await expect(
        asRole(role, () => db.query(`select replace_ash_abstract('ASH_2025_1', '[]', '[]')`)),
      ).rejects.toThrow(/permission denied/);
      await expect(
        asRole(role, () => db.query(`select delete_ash_abstracts_except('{}')`)),
      ).rejects.toThrow(/permission denied/);
    }
    // anon reads nothing at all, matching trial_outcomes.
    await expect(asRole('anon', () => db.query('select * from arm_outcomes'))).rejects.toThrow(
      /permission denied/,
    );
  });

  it('refuses an empty abstract and rows outside its ASH abstract', async () => {
    const refuse = async (abstractId: string, arms: Row[], vals: Row[], error: RegExp) =>
      expect(
        asRole('service_role', () =>
          db.query('select replace_ash_abstract($1, $2, $3)', [
            abstractId,
            JSON.stringify(arms),
            JSON.stringify(vals),
          ]),
        ),
      ).rejects.toThrow(error);
    const melanoma = async () =>
      (await db.query<Row>(`select * from trial_outcomes where id = 'abstract_ASCO_1_a'`)).rows;
    await db.exec(`update trial_outcomes set expert_review = 'good' where id = 'abstract_ASCO_1_a'`);
    const before = await melanoma();

    await refuse('ASH_2025_1', [], [], /nothing to load/);
    await refuse('ASH_2025_2', [arm(1, 'a', 'Venetoclax')], [], /another abstract/);
    // An arm claiming this abstract but carrying a melanoma row's id.
    await refuse('ASH_2025_9', [{ ...arm(9, 'a', 'Venetoclax'), id: 'abstract_ASCO_1_a' }], [], /another abstract/);
    await refuse('ASH_2025_9', [{ ...arm(9, 'a', 'Venetoclax'), source_name: 'extraction_results_ASCO_2025' }], [], /another abstract/);
    await refuse('ASH_2025_9', [], [{ ...val(9, null, 'orr_rate', '1'), source_id: 'ASH_2025_1' }], /another abstract/);
    // A value may only hang off an arm sent in the same payload.
    await refuse('ASH_2025_9', [], [val(9, null, 'orr_rate', '1', { trial_outcome_id: 'abstract_ASCO_1_a' })], /arm not in the payload/);
    await refuse('ASH_2025_1', [arm(1, 'a', 'Venetoclax')], [val(1, 'b', 'orr_rate', '1')], /arm not in the payload/);
    // A non-ASH abstract id would let the arm delete reach melanoma rows.
    await refuse('ASCO_1', [], [{ ...val(9, null, 'orr_rate', '1'), source_id: 'ASCO_1' }], /not an ASH/);

    expect(await melanoma()).toEqual(before);
  });
});
