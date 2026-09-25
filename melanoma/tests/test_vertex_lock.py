"""The per-project lock that keeps two bulk Vertex workloads apart."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.infrastructure.vertex_lock import VertexWorkloadBusyError, hold_vertex_lock


def test_a_live_holder_refuses_a_second_workload(tmp_path: Path) -> None:
    holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        (tmp_path / "vertex-p.lock").write_text(
            json.dumps(
                {"pid": holder.pid, "workload": "golden evals", "startedAt": "t"}
            )
        )
        with pytest.raises(VertexWorkloadBusyError, match="golden evals"):
            hold_vertex_lock("p", "run_abstract_pipeline.py", lock_dir=tmp_path)
    finally:
        holder.kill()
        holder.wait()


def test_a_crashed_holder_is_taken_over(tmp_path: Path) -> None:
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    (tmp_path / "vertex-p.lock").write_text(
        json.dumps({"pid": gone.pid, "workload": "x"})
    )

    path = hold_vertex_lock("p", "run_abstract_pipeline.py", lock_dir=tmp_path)

    assert json.loads(path.read_text())["pid"] == os.getpid()


def test_the_same_process_may_take_it_twice(tmp_path: Path) -> None:
    first = hold_vertex_lock("p", "a", lock_dir=tmp_path)
    assert hold_vertex_lock("p", "a", lock_dir=tmp_path) == first
