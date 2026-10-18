#!/usr/bin/env python3
"""Small serial host-only gate. Invoke only after obtaining the compile slot.

Uses synthetic expanded Q6 rows and the inherited production head, argmax,
and native controller. Never opens a model or a device. Native parity and the
packet49 oracle remain coordinator gates.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

P = Path(__file__).resolve().parent
ROOT = P.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    """Fail closed if the retained gate, tested source or executable changed."""
    report = json.loads((P / "p56-cpu-gates.json").read_text())
    assert report["schema"] == "packet56.cpu-gates.v1" and report["passed"]
    assert not report["device_executed"] and not report["model_weights_read"]
    assert report["sealed_n"] == json.loads((P / "calibration/selection.json").read_text())["draft_vocab_rows"]
    for name, digest in report["sources_sha256"].items():
        assert sha(ROOT / name) == digest, "CPU gate source changed: " + name
    assert sha(P / "build/p56-cpu/p56-cpu-gate") == report["binary_sha256"], "CPU gate binary changed"
    assert len(report["runs"]) == 2 and all(row["result"]["passed"] for row in report["runs"])
    assert report["runs"][0]["result"] == report["runs"][1]["result"]
    for row in report["runs"]:
        gate = row["result"]
        assert gate["synthetic_full_rows"] == 248320 and gate["synthetic_q6_width"] == 2560
        assert gate["full_geometry_prefix_rows_compared"] == report["sealed_n"]
        assert gate["full_geometry_prefix_bytes_compared"] == 2 * report["sealed_n"]
    return dict(passed=True, device_executed=False, receipt_sha256=sha(P / "p56-cpu-gates.json"),
                sealed_n=report["sealed_n"], fresh_processes=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="serially compile the host-only gate")
    parser.add_argument("--output", type=Path, default=P / "p56-cpu-gates.json")
    args = parser.parse_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19, "run with nice -n 19"
    assert set(os.sched_getaffinity(0)) <= set(range(4, 16)) | set(range(20, 32)), "CPU reservation"
    assert os.environ.get("OMP_NUM_THREADS") == "2", "set OMP_NUM_THREADS=2"
    available_kib = int(next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemAvailable:")))
    assert available_kib > 4 * 1024**2, "full synthetic head requires at least 4GiB available host RAM"
    selected = json.loads((P / "calibration/selection.json").read_text())
    # The compile-time constant is authoritative; the selector is hash-bound
    # below and its selected count must agree, independent of metadata layout.
    config = (P / "p56_config.hpp").read_text()
    import re
    match = re.search(r"prefix_rows\s*=\s*(\d+)", config)
    assert match, "missing sealed prefix constant"
    n = int(match.group(1))
    assert n == selected["draft_vocab_rows"], "selection/config mismatch"
    build = P / "build/p56-cpu"
    build.mkdir(parents=True, exist_ok=True)
    binary = build / "p56-cpu-gate"
    deps = build / "p56-cpu-gate.d"
    compile_command = [
        "/usr/bin/g++", "-std=c++20", "-O2", "-g0", "-fno-fast-math", "-ffp-contract=off",
        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections", "-fopenmp", "-pthread",
        "-DOWN_RT_HOST_ONLY", "-DNDEBUG", "-I" + str(P),
        "-I" + str(P.parent.parent / "stage1/packet3-prep/src"),
        "-I" + str(P.parent / "packet2/kernels"),
        "-I" + str(P.parent / "packet2/loader"),
        "-MMD", "-MF", str(deps), str(P / "p56_cpu_gate.cpp"), "-o", str(binary),
    ]
    if args.build:
        with (build / "compile.log").open("w") as log:
            subprocess.run(compile_command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=300)
    assert binary.is_file() and deps.is_file(), "build the CPU gate first"
    dep_paths = [Path(word) for word in deps.read_text().replace("\\\n", " ").split(":", 1)[1].split()]
    dep_paths += [P / name for name in (
        "p56_cpu_gate.py", "calibration/selection.json", "dispatch-speed6.json",
        "mtp.hpp", "main.cpp", "native_controller.hpp",
    )]
    sources = {str(path.resolve().relative_to(ROOT)): sha(path) for path in sorted(set(dep_paths))}
    stamp = build / "build-binding.json"
    if args.build:
        stamp.write_text(json.dumps({"sources_sha256": sources, "binary_sha256": sha(binary)}, indent=2) + "\n")
    binding = json.loads(stamp.read_text())
    assert binding == {"sources_sha256": sources, "binary_sha256": sha(binary)}, "stale gate binary"
    dispatch = json.loads((P / "dispatch-speed6.json").read_text())
    assert dispatch["gemv"]["logits"] == "p33.dense.segment" and dispatch["classes"]["argmax"] == "round2"
    runs = []
    for repeat in range(2):
        command = [str(binary), str(n)]
        start = time.monotonic()
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=120)
        receipt = json.loads(result.stdout)
        assert receipt["passed"] and not receipt["device_executed"] and not receipt["model_weights_read"]
        runs.append({"repeat": repeat, "elapsed_seconds": time.monotonic() - start, "result": receipt})
    assert runs[0]["result"] == runs[1]["result"], "fresh-process gate differs"
    report = {
        "schema": "packet56.cpu-gates.v1", "passed": True, "device_executed": False,
        "model_weights_read": False, "compile_command": compile_command, "sources_sha256": sources,
        "binary_sha256": sha(binary), "sealed_n": n, "runs": runs,
        "scope": "Production p33 dense full248320-row versus sealed-prefix91392-row byte comparison at width2560 using one synthetic expanded Q6 allocation; round2 argmax and actual native controller with mock rank state. No full-model output certification.",
        "real_model_oracle_gate": "pending coordinator chain against unchanged packet49 oracle",
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": True, "sealed_n": n, "fresh_processes": 2, "output": str(args.output)}))


if __name__ == "__main__":
    main()
