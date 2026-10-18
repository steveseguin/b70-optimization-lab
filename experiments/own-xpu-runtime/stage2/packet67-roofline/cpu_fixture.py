#!/usr/bin/env python3
"""Compile/run the actual host kernels twice without linking a GPU backend."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shlex
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compiler", default="g++")
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
    os.nice(max(0, 19 - os.getpriority(os.PRIO_PROCESS, 0)))
    os.sched_setaffinity(0, set(range(8, 16)) | set(range(24, 32)))
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    binary = out / "p67_cpu"
    owner = HERE.parent.parent / "stage1/packet3-prep/src"
    packet2 = HERE.parent / "packet2"
    command = [args.compiler, "-std=c++20", "-O2", "-fno-fast-math", "-ffp-contract=off",
               "-DOWN_RT_HOST_ONLY", "-Werror=return-type", "-I", str(HERE), "-I", str(owner),
               "-I", str(packet2 / "kernels"), "-I", str(packet2 / "loader"),
               "-MMD", "-MF", str(out / "dependencies.d"), str(HERE / "p67_cpu.cpp"), "-o", str(binary)]
    receipt = {"schema": "packet67.cpu-fixture.v1", "passed": False,
               "device_executed": False, "memory_limit_bytes": 8 * 1024**3,
               "compile_command": command, "runs": []}
    try:
        frozen = HERE.parent / "packet64-record-bundle"
        receipt["frozen_production_sources"] = {}
        for name in ("p60_math.hpp", "p49d_recurrence.hpp", "p49c_kernel.hpp", "p49d_small.hpp"):
            local_hash, frozen_hash = digest(HERE / name), digest(frozen / name)
            if local_hash != frozen_hash:
                raise RuntimeError(f"production control differs from frozen packet64: {name}")
            receipt["frozen_production_sources"][name] = frozen_hash
        with (out / "compile.log").open("w") as log:
            subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
        deps = shlex.split((out / "dependencies.d").read_text().replace("\\\n", " ").split(":", 1)[1])
        receipt["sources"] = {str(Path(p).resolve().relative_to(ROOT)): digest(Path(p)) for p in deps}
        receipt["fixture_driver_sha256"] = digest(Path(__file__))
        receipt["binary_sha256"] = digest(binary)
        receipt["compiler_version"] = subprocess.check_output([args.compiler, "--version"], stdin=subprocess.DEVNULL, text=True).splitlines()[0]
        for repeat in (1, 2):
            run = out / f"repeat-{repeat}"
            run.mkdir(exist_ok=True)
            with (run / "run.log").open("w") as log:
                subprocess.run([str(binary), str(run)], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
            native = json.loads((run / "native.json").read_text())
            expected, actual = digest(run / "expected.bin"), digest(run / "candidate.bin")
            assert native["passed"] and native["cases"] == 60 and expected == actual
            receipt["runs"].append({"repeat": repeat, "native": native, "expected_sha256": expected,
                                    "candidate_sha256": actual, "cases_sha256": digest(run / "cases.jsonl")})
        assert receipt["runs"][0]["candidate_sha256"] == receipt["runs"][1]["candidate_sha256"]
        for source, sha256 in receipt["sources"].items():
            if digest(ROOT / source) != sha256:
                raise RuntimeError(f"source changed during CPU gate: {source}")
        receipt["passed"] = True
    finally:
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": receipt["passed"], "receipt": str(out / "receipt.json")}, sort_keys=True))

if __name__ == "__main__":
    main()
