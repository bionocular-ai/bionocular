// Build km_curves rows from survival-twin data folders in web/data/survival-twin/.
//
// Per folder (e.g. "Batch-I_31_Overall"):
//   source_name = ^Batch-[IVX]+_\d+   (e.g. Batch-I_31)   cohort = the rest (Overall)
//   - twin curve  ← KM step computed in JS from outputs/ipd_<arm>.csv
//   - twin median ← outputs/validation_report.md
//   - published median/rate/follow-up + publication_id(citation)/cancer_type/nct_id
//                 ← trial_outcomes (matched by source_name, then arm_name)
//   - id = `<folder>_<arm_name>`  e.g. Batch-I_31_Overall_Relatlimab-Nivolumab
//
// Usage (from web/):
//   node scripts/load-km-curves.mjs            # dry run → writes supabase/seed/km_curves_generated.sql
//   node scripts/load-km-curves.mjs --apply    # also upserts directly via SUPABASE_SECRET_KEY

import { readFileSync, readdirSync, writeFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createClient } from '@supabase/supabase-js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = join(__dirname, '..');
const DATA_DIR = join(WEB_ROOT, 'data', 'survival-twin');
const OUT_SQL = join(WEB_ROOT, 'supabase', 'seed', 'km_curves_generated.sql');
const APPLY = process.argv.includes('--apply');

// ---- env (.env.local, hand-parsed; no dotenv dep) -------------------------
function loadEnv() {
  const env = {};
  const text = readFileSync(join(WEB_ROOT, '.env.local'), 'utf8');
  for (const line of text.split('\n')) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m) env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
  return env;
}
const env = loadEnv();
const supabase = createClient(
  env.NEXT_PUBLIC_SUPABASE_URL,
  env.SUPABASE_SECRET_KEY,
  { auth: { persistSession: false } }
);

// ---- tiny parsers ----------------------------------------------------------
function parseCsv(path) {
  const [head, ...rows] = readFileSync(path, 'utf8').trim().split('\n');
  const cols = head.split(',').map((c) => c.replace(/^"|"$/g, ''));
  return rows.map((r) => {
    const vals = r.split(',').map((v) => v.replace(/^"|"$/g, ''));
    return Object.fromEntries(cols.map((c, i) => [c, vals[i]]));
  });
}

// meta.yaml is a fixed, shallow shape — parse it directly rather than add a dep.
function parseMeta(path) {
  const text = readFileSync(path, 'utf8');
  const meta = { arms: [] };
  let arm = null;
  for (const raw of text.split('\n')) {
    if (!raw.trim()) continue;
    const top = raw.match(/^(\w+):\s*(.*)$/);
    if (top && !raw.startsWith(' ')) {
      if (top[1] === 'arms') continue;
      meta[top[1]] = top[2];
      continue;
    }
    const item = raw.match(/^-\s*name:\s*(.*)$/);
    if (item) {
      arm = { name: item[1].trim() };
      meta.arms.push(arm);
      continue;
    }
    const kv = raw.match(/^\s+(\w+):\s*(.*)$/);
    if (kv && arm) arm[kv[1]] = kv[2].trim();
  }
  return meta;
}

// Reconstructed-median + status per arm from the validation report table.
function parseValidation(path) {
  if (!existsSync(path)) return {};
  const out = {};
  for (const line of readFileSync(path, 'utf8').split('\n')) {
    if (!line.startsWith('|')) continue;
    const cells = line.split('|').map((c) => c.trim()).filter(Boolean);
    // | arm | published | reconstructed | S(t_med)% | 95% CI | % diff | flag | pass |
    if (cells.length < 6 || cells[0] === 'arm' || cells[1] === 'published') continue;
    const reconstructed = parseFloat(cells[2]);
    const diff = parseFloat((cells[5] || '').replace('%', ''));
    if (!Number.isNaN(reconstructed)) {
      out[cells[0]] = {
        twin_median: reconstructed,
        match_pct: Number.isNaN(diff) ? null : Math.round((100 - Math.abs(diff)) * 10) / 10,
      };
    }
  }
  return out;
}

// ---- Kaplan-Meier step from reconstructed IPD ------------------------------
function kmSteps(ipdRows) {
  const rows = ipdRows
    .map((r) => ({ time: parseFloat(r.time), status: parseInt(r.status, 10) }))
    .filter((r) => !Number.isNaN(r.time))
    .sort((a, b) => a.time - b.time);
  const n = rows.length;
  const eventTimes = [...new Set(rows.filter((r) => r.status === 1).map((r) => r.time))].sort((a, b) => a - b);

  const coords = [{ time: 0, surv: 100 }];
  let surv = 1;
  for (const t of eventTimes) {
    const atRisk = rows.filter((r) => r.time >= t).length;
    const events = rows.filter((r) => r.time === t && r.status === 1).length;
    if (atRisk > 0) surv *= 1 - events / atRisk;
    coords.push({ time: Math.round(t * 1000) / 1000, surv: Math.round(surv * 1000) / 10 });
  }
  // Hold the last survival value flat out to the maximum observed follow-up
  // (last censored time) so the curve doesn't stop at the final event.
  const maxTime = n ? rows[n - 1].time : 0;
  const last = coords[coords.length - 1];
  if (maxTime > last.time) coords.push({ time: Math.round(maxTime * 1000) / 1000, surv: last.surv });
  return { coords, n };
}

function survAt(coords, t) {
  let s = 100;
  for (const p of coords) {
    if (p.time <= t) s = p.surv;
    else break;
  }
  return Math.round(s * 10) / 10;
}

// ---- arm-name matching (meta ↔ trial_outcomes) -----------------------------
const norm = (s) => (s || '').toLowerCase().replace(/[\s/+_-]/g, '');

// Endpoint → trial_outcomes column groups.
const PUBLISHED = {
  PFS: { median: 'median_pfs', followup: 'pfs_followup_months', rates: [['pfs_rate_24m', 24], ['pfs_rate_12m', 12], ['pfs_rate_6m', 6]] },
  OS: { median: 'median_os', followup: 'os_followup_months', rates: [['os_rate_24m', 24], ['os_rate_12m', 12], ['os_rate_6m', 6]] },
};

const num = (v) => (v == null || v === '' ? null : Number(v));
const sqlStr = (v) => (v == null ? 'NULL' : `'${String(v).replace(/'/g, "''")}'`);
const sqlNum = (v) => (v == null || Number.isNaN(v) ? 'NULL' : String(v));

async function buildFolder(folder) {
  const m = folder.match(/^(Batch-[IVX]+_\d+)(?:_(.+))?$/);
  if (!m) { console.warn(`skip ${folder}: name not Batch-*_N[_cohort]`); return []; }
  const source_name = m[1];
  const cohort = m[2] || null;

  const inDir = join(DATA_DIR, folder, 'inputs');
  const outDir = join(DATA_DIR, folder, 'outputs');
  const meta = parseMeta(join(inDir, 'meta.yaml'));
  const endpoint = (meta.endpoint || 'PFS').toUpperCase();
  const pub = PUBLISHED[endpoint] || PUBLISHED.PFS;
  const validation = parseValidation(join(outDir, 'validation_report.md'));

  const { data: outcomes, error } = await supabase
    .from('trial_outcomes')
    .select('*')
    .eq('source_name', source_name);
  if (error) throw error;
  const meta0 = outcomes?.[0] || {};
  const publication_id = meta0.publication_id ?? null;        // citation string
  const cancer_type = Array.isArray(meta0.cancer_type) ? meta0.cancer_type[0] : meta0.cancer_type ?? null;
  const nct_id = meta0.nct_id ?? null;

  if (!outcomes?.length) console.warn(`! ${folder}: no trial_outcomes row for source_name=${source_name}`);

  const rows = [];
  for (const arm of meta.arms) {
    const safe = arm.name.replace(/\//g, '-');
    const ipdPath = join(outDir, `ipd_${safe}.csv`);
    if (!existsSync(ipdPath)) { console.warn(`  skip arm ${arm.name}: ${ipdPath} missing`); continue; }

    const { coords, n } = kmSteps(parseCsv(ipdPath));
    const oc = outcomes?.find((o) => norm(o.arm_name) === norm(arm.name)) || {};

    const rate = pub.rates.map(([col, t]) => [num(oc[col]), t]).find(([v]) => v != null) || [null, null];
    const v = validation[arm.name] || {};

    rows.push({
      id: `${folder}_${arm.name}`,
      publication_id,
      nct_id,
      cancer_type,
      comparison_label: cohort,
      arm_name: arm.name,
      endpoint,
      twin_coords: coords,
      published_median: num(oc[pub.median]) ?? num(arm.published_median),
      twin_median: v.twin_median ?? null,
      rate_timepoint: rate[1],
      published_rate: rate[0],
      twin_rate: rate[1] != null ? survAt(coords, rate[1]) : null,
      median_follow_up: num(oc[pub.followup]),
      match_pct: v.match_pct ?? null,
      n_points: n,
      reference: publication_id,
    });
  }
  return rows;
}

function toSql(rows) {
  const cols = ['id', 'publication_id', 'nct_id', 'cancer_type', 'comparison_label', 'arm_name', 'endpoint',
    'twin_coords', 'published_median', 'twin_median', 'rate_timepoint', 'published_rate', 'twin_rate',
    'median_follow_up', 'match_pct', 'n_points', 'reference'];
  const values = rows.map((r) => `  (${[
    sqlStr(r.id), sqlStr(r.publication_id), sqlStr(r.nct_id), sqlStr(r.cancer_type), sqlStr(r.comparison_label),
    sqlStr(r.arm_name), sqlStr(r.endpoint), `${sqlStr(JSON.stringify(r.twin_coords))}::jsonb`,
    sqlNum(r.published_median), sqlNum(r.twin_median), sqlNum(r.rate_timepoint), sqlNum(r.published_rate),
    sqlNum(r.twin_rate), sqlNum(r.median_follow_up), sqlNum(r.match_pct), sqlNum(r.n_points), sqlStr(r.reference),
  ].join(', ')})`).join(',\n');
  const updates = cols.filter((c) => c !== 'id').map((c) => `${c} = EXCLUDED.${c}`).join(', ');
  return `-- Generated by scripts/load-km-curves.mjs. Do not edit by hand.\n` +
    `INSERT INTO km_curves (${cols.join(', ')})\nVALUES\n${values}\nON CONFLICT (id) DO UPDATE SET ${updates};\n`;
}

async function main() {
  const folders = readdirSync(DATA_DIR, { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name);
  let all = [];
  for (const f of folders) all = all.concat(await buildFolder(f));
  console.log(`Built ${all.length} km_curves rows from ${folders.length} folders.`);

  const sql = toSql(all);
  writeFileSync(OUT_SQL, sql);
  console.log(`Wrote SQL → ${OUT_SQL}`);

  if (APPLY) {
    const { error } = await supabase.from('km_curves').upsert(all.map((r) => ({
      ...r, twin_coords: r.twin_coords,
    })), { onConflict: 'id' });
    if (error) throw error;
    console.log(`Applied: upserted ${all.length} rows into km_curves.`);
  } else {
    console.log('Dry run. Re-run with --apply to upsert, or run the SQL in Supabase.');
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
