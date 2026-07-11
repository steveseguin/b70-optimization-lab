#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the standalone SYCL extension")
    parser.add_argument("--clean", action="store_true", help="remove this experiment's build directory first")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()

    compiler = subprocess.run(
        ["icpx", "--version"], text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=True,
    ).stdout.splitlines()[0]
    if "2025.3" not in compiler:
        raise SystemExit(
            "oneAPI compiler 2025.3 is required by the torch 2.11 XPU runtime; "
            "source /opt/intel/oneapi/compiler/2025.3/env/vars.sh first\n"
            f"selected compiler: {compiler}"
        )

    build_dir = ROOT / "build"
    if args.clean and build_dir.exists():
        import shutil

        shutil.rmtree(build_dir)

    env = os.environ.copy()
    env["MAX_JOBS"] = str(args.jobs)
    # ESIMD templates require the DPC++ frontend for both host and device passes.
    # torch's generic extension helper otherwise selects /usr/bin/c++ as the
    # explicit SYCL host compiler on this machine.
    env["CC"] = str(Path(os.environ.get("CMPLR_ROOT", "/opt/intel/oneapi/compiler/2025.3")) / "bin" / "icx")
    env["CXX"] = str(Path(os.environ.get("CMPLR_ROOT", "/opt/intel/oneapi/compiler/2025.3")) / "bin" / "icpx")
    subprocess.run(
        [sys.executable, "setup.py", "build_ext", "--inplace"],
        cwd=ROOT,
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()
