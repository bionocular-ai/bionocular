"""One bulk Vertex AI workload per project on this machine.

The pipelines here and the web app's golden evals (``web/src/lib/agent/evals``)
draw on the same project's shared-pool standing. Two of them at once is how a
run gets refused for reasons that have nothing to do with it, so each takes
this lock for its whole process and a second one refuses to start.

The lock is a file holding the owner's pid. A file whose pid is no longer
running was left by a crash and is taken over. The web side reads and writes
the same file (``vertex-lock.ts``), so keep the format in step with it.
"""

from __future__ import annotations

import atexit
import json
import os
from datetime import datetime, timezone
from pathlib import Path

LOCK_DIR = Path.home() / ".bionocular"


class VertexWorkloadBusyError(RuntimeError):
    """Another bulk workload holds this project's lock."""


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def hold_vertex_lock(project: str, workload: str, lock_dir: Path = LOCK_DIR) -> Path:
    """Take the project's lock until this process exits, or raise if it is held."""
    lock_dir.mkdir(parents=True, exist_ok=True)
    path = lock_dir / f"vertex-{project}.lock"
    owner = json.dumps(
        {
            "pid": os.getpid(),
            "workload": workload,
            "startedAt": datetime.now(timezone.utc).isoformat(),
        }
    )
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            try:
                holder = json.loads(path.read_text())
            except (OSError, ValueError):
                holder = {}
            pid = holder.get("pid")
            if pid == os.getpid():
                return path
            if isinstance(pid, int) and _alive(pid):
                raise VertexWorkloadBusyError(
                    f"{holder.get('workload', 'another workload')} (pid {pid}, since "
                    f"{holder.get('startedAt', '?')}) is already using Vertex project "
                    f"{project}. Wait for it to finish; if that process is gone, "
                    f"delete {path}."
                ) from None
            path.unlink(missing_ok=True)
            continue
        with os.fdopen(fd, "w") as f:
            f.write(owner)
        atexit.register(_release, path)
        return path
    raise VertexWorkloadBusyError(
        f"Could not take {path}; another process raced for it."
    )


def _release(path: Path) -> None:
    try:
        if json.loads(path.read_text()).get("pid") == os.getpid():
            path.unlink()
    except (OSError, ValueError):
        pass
