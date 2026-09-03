#!/usr/bin/env python3
"""Write one strict, self-observing XPU-idle snapshot into an existing run."""

from __future__ import annotations

import argparse
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from preflight_laguna_m8_gather_sharded_operational import (
    OperationalPreflightError,
    capture_idle_snapshot,
)


# Originating-host artifact root; REPRO_ARTIFACT_ROOT relocates it.
DEFAULT_ARTIFACT_ROOT = "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1"
RUN_ROOT = Path(os.environ.get("REPRO_ARTIFACT_ROOT", DEFAULT_ARTIFACT_ROOT)) / "runs"


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
        0o600,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise RuntimeError("short idle-snapshot write")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve(strict=False)
    if not RUN_ROOT.is_dir():
        raise SystemExit(
            f"run root is absent: {RUN_ROOT} (set REPRO_ARTIFACT_ROOT to the Laguna artifact root)"
        )
    run_root = RUN_ROOT.resolve(strict=True)
    if (
        not output.is_relative_to(run_root)
        or not output.parent.is_dir()
        or output.parent.is_symlink()
        or stat.S_IMODE(output.parent.stat().st_mode) & 0o077
        or output.exists()
    ):
        raise SystemExit("idle output must be fresh under a private NVMe run directory")
    try:
        report = capture_idle_snapshot()
        status = 0
    except OperationalPreflightError as error:
        report = {
            "format": "laguna-m8-strict-idle-wrapper-v1",
            "status": "failed",
            "observed_utc": datetime.now(timezone.utc).isoformat(),
            "failure": {
                "message": str(error),
                "stage": error.stage,
                "type": type(error).__name__,
            },
        }
        status = 1
    except BaseException as error:
        report = {
            "format": "laguna-m8-strict-idle-wrapper-v1",
            "status": "failed",
            "observed_utc": datetime.now(timezone.utc).isoformat(),
            "failure": {
                "message": str(error),
                "stage": "wrapper",
                "type": type(error).__name__,
            },
        }
        status = 1
    write_exclusive(output, report)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
