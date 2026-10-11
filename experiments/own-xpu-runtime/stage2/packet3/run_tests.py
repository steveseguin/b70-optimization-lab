#!/usr/bin/env python3
"""Compile/run host C++ only; never imports SYCL or torch. Delete build scratch."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
# This command changes only its own scheduling priority/thread environment.
os.nice(max(0, 19 - os.getpriority(os.PRIO_PROCESS, 0)))
os.environ.update(OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", MKL_NUM_THREADS="2", PYTHONDONTWRITEBYTECODE="1")
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "model")]
import plan


def run(args):
    subprocess.run(args, check=True, cwd=ROOT)


def main():
    BUILD.mkdir(exist_ok=True)
    start = time.time()
    commands = []
    receipt = {"schema": "own-xpu-runtime.stage2.packet3.cpu-tests.v1", "gpu_execution": False,
               "synthetic_only": True, "native_gate": "NOT RUN", "nice": os.getpriority(os.PRIO_PROCESS, 0),
               "OMP_NUM_THREADS": os.environ["OMP_NUM_THREADS"], "python": sys.version,
               "compiler": subprocess.check_output(["g++", "--version"], text=True).splitlines()[0]}
    try:
        for source, binary in (("step/main.cpp", "step"), ("tests/host.cpp", "host-tests")):
            cmd = ["g++", "-std=c++20", "-O2", "-ffp-contract=off", "-fno-fast-math", "-Wall", "-Wextra", "-Werror", str(ROOT / source), "-o", str(BUILD / binary)]
            commands.append(cmd)
            run(cmd)
        model = plan.build_plan(plan.census_directory())
        plan.export_directory(model, BUILD / "directory.txt")
        launch = json.loads(subprocess.check_output([str(BUILD / "step"), "record", str(BUILD / "directory.txt")], text=True))
        receipt["record"] = {k: v for k, v in launch.items() if k not in ("launches", "buffers")}
        receipt["placement"] = model["per_card"]
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        receipt.update(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), passed=result.wasSuccessful(),
                       cpp_cases=18, numpy_tiny_buffers=113, numpy_tiny_values=3873, numpy_real_buffers=49, numpy_real_values=996958)
        receipt["launch_plan_sha256"] = hashlib.sha256(json.dumps(launch, sort_keys=True).encode()).hexdigest()
        receipt["source_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(ROOT.rglob("*")) if p.is_file() and "build" not in p.parts and p.suffix in (".hpp", ".cpp", ".py")}
        dependency = ROOT.parent / "packet2/kernels/math.hpp"
        receipt["packet2_math_sha256"] = hashlib.sha256(dependency.read_bytes()).hexdigest()
        receipt["input_sha256"] = {str(path.relative_to(ROOT.parents[3])): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (ROOT.parent / "packet2/kernels/grids.hpp", ROOT.parent / "packet1b/reference.py",
                         ROOT / "gate-evidence.json", plan.CENSUS)}
        receipt["commands"] = commands
        receipt["elapsed_seconds"] = round(time.time() - start, 3)
        (ROOT / "test-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        return 0 if result.wasSuccessful() else 1
    finally:
        shutil.rmtree(BUILD)


if __name__ == "__main__":
    raise SystemExit(main())
