#!/usr/bin/env node
import { readFileSync, writeFileSync, mkdirSync, existsSync, rmSync, copyFileSync, readdirSync } from 'node:fs'
import { join, dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { buildManifestEntry, runKey } from './load-runs.core.mjs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const APP_ROOT = resolve(__dirname, '..')
const OUTPUT_ROOT = resolve(APP_ROOT, '../../melanoma/data/output')
const PUBLIC_RUNS = join(APP_ROOT, 'public', 'runs')

function findValidationRuns(root) {
  // returns [{ runId, cohortDir, validationPath, resultsPath }]
  const runs = []
  for (const cohortDir of readdirSync(root, { withFileTypes: true })) {
    if (!cohortDir.isDirectory()) continue
    const cohortPath = join(root, cohortDir.name)
    for (const entry of readdirSync(cohortPath, { withFileTypes: true })) {
      if (!entry.isDirectory() || !entry.name.startsWith('validation')) continue
      const validationPath = join(cohortPath, entry.name, 'validation.json')
      if (!existsSync(validationPath)) continue
      runs.push({
        runId: entry.name,
        cohortDir: cohortDir.name,
        validationPath,
        resultsPath: join(cohortPath, 'results.json'),
      })
    }
  }
  return runs
}

function main() {
  if (!existsSync(OUTPUT_ROOT)) {
    console.error(`No melanoma output dir at ${OUTPUT_ROOT}`)
    process.exit(1)
  }
  if (existsSync(PUBLIC_RUNS)) rmSync(PUBLIC_RUNS, { recursive: true, force: true })
  mkdirSync(PUBLIC_RUNS, { recursive: true })

  const manifest = []
  for (const run of findValidationRuns(OUTPUT_ROOT)) {
    const meta = JSON.parse(readFileSync(run.validationPath, 'utf8')).metadata ?? {}
    const destDir = join(PUBLIC_RUNS, runKey(run.cohortDir, run.runId))
    mkdirSync(destDir, { recursive: true })
    copyFileSync(run.validationPath, join(destDir, 'validation.json'))
    if (existsSync(run.resultsPath)) {
      copyFileSync(run.resultsPath, join(destDir, 'results.json'))
    }
    manifest.push(buildManifestEntry(meta, run.runId, run.cohortDir))
  }

  manifest.sort((a, b) => (b.run_date ?? '').localeCompare(a.run_date ?? ''))
  writeFileSync(join(APP_ROOT, 'public', 'runs.json'), JSON.stringify(manifest, null, 2))
  console.log(`Loaded ${manifest.length} run(s):`)
  for (const m of manifest) console.log(`  ${m.id} (${m.cohort}) - ${m.counts.total} trials`)
}

main()
