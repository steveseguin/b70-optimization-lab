#!/usr/bin/env python3
"""Offline capability audit, NOT native ABI qualification. Never load a binary."""
import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE2 = HERE.parent
P29 = STAGE2 / "packet29-merged"
P22 = STAGE2 / "packet22-replay"
CURRENT = [P29 / item for item in (
    "p28/submit.cpp", "p28/submit.hpp", "specialised_submit.cpp",
    "round2_submit.cpp", "adapter.cpp", "native.cpp", "runtime_kernels.cpp",
    "kernel_guard.hpp", "backend.hpp", "KERNELS.md")]
CURRENT += [STAGE2 / "packet10-kopt5/kernels.cpp"]
BRIDGE = [P22 / item for item in (
    "raw_typed.hpp", "raw_abi_gate.py", "recording_native.hpp",
    "recording_native.cpp", "backend-notes.md")]
DISPATCH = P29 / "build/k2-r29/run/dispatch-measured.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def admit_raw(receipt):
    # Packet22 receipts or asserted `passed` fields cannot supply missing
    # packet29 functor exports. No raw implementation is present in packet34.
    raise ValueError("raw unavailable: current packet29 exports and final ABI qualification missing")


def audit():
    dispatch = json.loads(DISPATCH.read_text())
    assert dispatch["gemv"]["expsgate"] == "p28.paired.wg32"
    assert dispatch["gemv"]["expsdown"] == "r5"
    assert dispatch["classes"]["gdn.recurrence"] == "round2"
    sources = [p for p in CURRENT if p.suffix == ".cpp"]
    rows = []
    for path in sources:
        text = path.read_text()
        hooks = re.findall(r"\b(?:raw_append|append_typed|RawAbi)\b", text)
        exports = re.findall(r"\b(?:parallel_for|single_task)\s*<", text)
        assert not hooks, "raw hooks now exist: audit must be revised: " + str(path)
        assert not exports, "named exports now exist: audit must be revised: " + str(path)
        rows.append({"path": str(path.relative_to(STAGE2)),
                     "raw_hooks": 0, "named_kernel_exports": 0})
    checks = []
    for name, receipt in (
        ("old_packet22_receipt_rejected", {"passed": True, "kernel_classes": 8,
                                          "binary_sha256": "76f54d63419f364211fff878213cfec1b89196eee248b2e91b1dfeb65ebc07c1"}),
        ("empty_receipt_rejected", {}),
        ("asserted_current_receipt_rejected", {"passed": True, "qualified": True,
                                              "dispatch_sha256": sha(DISPATCH)}),
    ):
        try:
            admit_raw(receipt)
        except ValueError as error:
            checks.append({"name": name, "passed": True, "reason": str(error)})
        else:
            raise AssertionError("raw receipt unexpectedly admitted")
    checks.append({"name": "current_entries_have_no_raw_exports", "passed": True})
    dependencies = CURRENT + BRIDGE + [DISPATCH, Path(__file__).resolve()]
    return {"schema": "own-runtime.packet34.raw-capability-audit.v1",
            "passed": True, "passed_meaning": "fail_closed_capability_tests_only",
            "raw_available": False, "qualified": False, "device_executed": False,
            "native_abi_gate_passed": False,
            "reason": "unchanged current submissions lack typed functor exports and current final ELF/SPIR-V manifests",
            "source_sha256": {str(p.relative_to(STAGE2)): sha(p) for p in dependencies},
            "selected_dispatch": dispatch, "entry_source_audit": rows,
            "checks": checks, "gate_count": len(checks),
            "native_cli_rejection_test": "pending independent source/parser gate; native binary must not be run on CPU"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "raw-abi-gate.json")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if not output.is_relative_to(HERE):
        parser.error("output must remain under packet34")
    row = audit()
    output.write_text(json.dumps(row, indent=2) + "\n")
    print(json.dumps({key: row[key] for key in
                     ("passed", "raw_available", "qualified", "gate_count", "device_executed")}))


if __name__ == "__main__":
    main()
