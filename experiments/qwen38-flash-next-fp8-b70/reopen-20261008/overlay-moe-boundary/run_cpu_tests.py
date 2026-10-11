#!/usr/bin/env python3
"""CPU-only suite: no device opens, subprocess launches or network connections."""
import json
import os
from pathlib import Path
import sys
import unittest


def guard(event, args):
    if event == "open" and isinstance(args[0], (str, bytes)):
        p = os.path.realpath(os.fsdecode(args[0]))
        if p == "/dev/dri" or p.startswith("/dev/dri/"):
            raise RuntimeError("CPU test forbids render device open")
    if event in ("socket.connect",):
        raise RuntimeError("CPU test forbids network connection")
    if event == "subprocess.Popen":
        executable = os.path.basename(str(args[0]))
        if executable not in ("git",):
            raise RuntimeError("CPU test forbids subprocess: " + executable)


sys.addaudithook(guard)
HERE = Path(__file__).resolve().parent
# Explicitly block all public accelerator entry points; CPU Torch only.
import torch
for name in ("init", "is_available", "device_count", "current_device", "set_device", "synchronize", "empty_cache"):
    if hasattr(torch.xpu, name):
        def forbidden(*args, **kwargs):
            raise RuntimeError("CPU test forbids XPU call")
        setattr(torch.xpu, name, forbidden)

suite = unittest.defaultTestLoader.discover(str(HERE), pattern="test_*.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
receipt = dict(discovered=result.testsRun, passed=result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
               failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
               torch=torch.__version__, device="cpu", gpu_executed=False)
if len(sys.argv) == 2:
    Path(sys.argv[1]).write_text(json.dumps(receipt, indent=2)+"\n")
raise SystemExit(not result.wasSuccessful())
