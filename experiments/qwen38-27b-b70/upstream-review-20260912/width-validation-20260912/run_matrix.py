#!/usr/bin/env python3
"""Execute preregistered operator cells inside the parent's device guard."""
from pathlib import Path
import argparse
import subprocess
import sys

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--build-suffix", default="-2025-build")
args = parser.parse_args()
for arm in ("stock", "candidate"):
    for dtype in ("float16", "bfloat16"):
        print(f"BEGIN arm={arm} dtype={dtype}", flush=True)
        subprocess.run([
            sys.executable, str(root / "probe_width.py"), "--arm", arm,
            "--dtype", dtype, "--library",
            f"/home/steve/q27-validation-20260912/width-{arm}{args.build_suffix}/width_review.so",
        ], check=True, timeout=120)
        print(f"PASS arm={arm} dtype={dtype}", flush=True)
