/**
 * One bulk Vertex AI workload per project on this machine.
 *
 * The golden evals and the melanoma pipelines draw on the same project's
 * shared-pool standing, so two at once get refused for each other's load.
 * Each takes this lock for its run and a second one refuses to start. The
 * file and its format are shared with `melanoma/src/infrastructure/vertex_lock.py`;
 * keep the two in step.
 */

import { mkdirSync, openSync, readFileSync, rmSync, writeSync, closeSync } from 'node:fs';
import { homedir } from 'node:os';
import path from 'node:path';

export const LOCK_DIR = path.join(homedir(), '.bionocular');

interface Holder {
  pid?: number;
  workload?: string;
  startedAt?: string;
}

function alive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === 'EPERM';
  }
}

function readHolder(file: string): Holder {
  try {
    return JSON.parse(readFileSync(file, 'utf8')) as Holder;
  } catch {
    return {};
  }
}

/** Take the project's lock, or throw naming whoever holds it. Returns the release. */
export function holdVertexLock(project: string, workload: string, dir = LOCK_DIR): () => void {
  mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `vertex-${project}.lock`);
  const owner = JSON.stringify({ pid: process.pid, workload, startedAt: new Date().toISOString() });
  const release = () => {
    if (readHolder(file).pid === process.pid) rmSync(file, { force: true });
  };

  for (let attempt = 0; attempt < 2; attempt++) {
    let fd: number;
    try {
      fd = openSync(file, 'wx');
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error;
      const holder = readHolder(file);
      if (holder.pid === process.pid) return release;
      if (typeof holder.pid === 'number' && alive(holder.pid)) {
        throw new Error(
          `${holder.workload ?? 'another workload'} (pid ${holder.pid}, since ${holder.startedAt ?? '?'}) ` +
            `is already using Vertex project ${project}. Wait for it to finish; if that process is gone, delete ${file}.`,
        );
      }
      rmSync(file, { force: true });
      continue;
    }
    writeSync(fd, owner);
    closeSync(fd);
    return release;
  }
  throw new Error(`Could not take ${file}; another process raced for it.`);
}
