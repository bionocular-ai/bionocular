import { spawn, spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { holdVertexLock } from './vertex-lock';

const dir = () => mkdtempSync(path.join(tmpdir(), 'vertex-lock-'));

describe('holdVertexLock', () => {
  it('refuses while a live process holds it, naming the holder', () => {
    const d = dir();
    const holder = spawn(process.execPath, ['-e', 'setTimeout(() => {}, 30000)']);
    try {
      writeFileSync(path.join(d, 'vertex-p.lock'), JSON.stringify({ pid: holder.pid, workload: 'run_abstract_pipeline.py' }));
      expect(() => holdVertexLock('p', 'web golden evals', d)).toThrow(/run_abstract_pipeline\.py/);
    } finally {
      holder.kill();
    }
  });

  it('takes over from a crashed holder and releases on request', () => {
    const d = dir();
    const gone = spawnSync(process.execPath, ['-e', '0']).pid;
    const file = path.join(d, 'vertex-p.lock');
    writeFileSync(file, JSON.stringify({ pid: gone, workload: 'x' }));

    const release = holdVertexLock('p', 'web golden evals', d);
    expect(JSON.parse(readFileSync(file, 'utf8')).pid).toBe(process.pid);

    release();
    expect(existsSync(file)).toBe(false);
  });
});
