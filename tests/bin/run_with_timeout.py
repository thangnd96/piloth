#!/usr/bin/env python3
"""Run a command with process-group timeout and file logging.

No stdout/stderr pipe is captured by the parent. On timeout, kill the whole
process group so grandchildren cannot survive and keep workspaces/pipes alive.
Exit code: child exit code, or 124 on timeout.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 4 or sys.argv[1] in {"-h", "--help"}:
        print("usage: run_with_timeout.py <seconds> <log-file> <cmd> [args...]", file=sys.stderr)
        return 2
    seconds = float(sys.argv[1])
    log_path = Path(sys.argv[2])
    cmd = sys.argv[3:]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab", buffering=0) as log:
        proc = subprocess.Popen(
            cmd,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
        try:
            return proc.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
            return 124


if __name__ == "__main__":
    raise SystemExit(main())
