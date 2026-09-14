#!/usr/bin/env python3
"""Explicit, bounded native qualification of two saved NA implementations.

No model loading, runtime patching, compilation or performance measurement.
--check-only never imports torch. An existing fault latch rejects either mode.
"""

import argparse
import ast
import datetime
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import sys


LANE = Path(__file__).resolve().parents[1]
PACKET = LANE / "data/na-mask-extent-01"
FAULT = Path("/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json")
FUNCTIONS = ("_window_bounds", "_pick_tiles", "_group_mask", "na3d")
CONSTANTS = ("NA_SCORE_BUDGET", "NA_KV_STACK_BUDGET")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check_fault():
    if FAULT.exists():
        raise FaultHalt("Existing fault latch prohibits native requests")


class FaultHalt(RuntimeError):
    pass


def source_module(source):
    tree = ast.parse(source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in FUNCTIONS}
    if set(functions) != set(FUNCTIONS):
        raise ValueError("Expected exact four source functions")
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in CONSTANTS:
                # Only the pinned integer exponent expressions are permitted.
                if not (isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Pow)
                        and isinstance(node.value.left, ast.Constant) and isinstance(node.value.right, ast.Constant)
                        and type(node.value.left.value) is int and type(node.value.right.value) is int):
                    raise ValueError("Unexpected budget constant")
                constants[name] = node.value.left.value ** node.value.right.value
    if constants != {"NA_SCORE_BUDGET": 2 ** 25, "NA_KV_STACK_BUDGET": 2 ** 28}:
        raise ValueError("Budget constants differ from pinned source")
    nodes = []
    for name in FUNCTIONS:
        node = functions[name]
        node.decorator_list = []
        nodes.append(node)
    return ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), constants


def dependencies():
    versions = {}
    for name in ("torch", "comfy-kitchen", "numpy"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def run(args, receipt):
    check_fault()  # Must precede dependency/native imports, even in check-only.
    checks_bytes = (PACKET / "source-checks.json").read_bytes()
    checks = json.loads(checks_bytes)
    receipt["source_checks_sha256"] = sha(checks_bytes)
    modules = []
    receipt["sources"] = {}
    for label in ("original", "candidate"):
        source = (PACKET / f"{label}-na.py").read_bytes()
        digest = sha(source)
        if digest != checks[f"{label}_sha256"]:
            raise ValueError(f"{label} source hash mismatch")
        receipt["sources"][label] = digest
        modules.append(source_module(source.decode()))
    receipt["dependency_versions"] = dependencies()
    receipt["source_checks_passed"] = True
    check_fault()
    if args.check_only:
        receipt["status"] = "source-check-only-native-unqualified"
        return 0

    # Deliberately below the gate. This is the only native import location.
    import torch
    receipt["torch_imported"] = True
    check_fault()
    torch.use_deterministic_algorithms(True, warn_only=False)
    device = torch.device(args.device)
    if device.type == "xpu":
        if not torch.xpu.is_available() or torch.xpu.device_count() <= 3:
            raise RuntimeError("Explicit xpu:3 device unavailable")
        receipt["device_name"] = torch.xpu.get_device_name(device)
    receipt["strict_determinism"] = {
        "enabled": torch.are_deterministic_algorithms_enabled(),
        "warn_only": torch.is_deterministic_algorithms_warn_only_enabled(),
        "float32_matmul_precision": torch.get_float32_matmul_precision(),
    }
    if not receipt["strict_determinism"]["enabled"] or receipt["strict_determinism"]["warn_only"]:
        raise RuntimeError("Strict determinism not enabled")
    receipt["torch_identity"] = {"version": str(torch.__version__),
                                 "git_version": getattr(torch.version, "git_version", None),
                                 "module_path": str(torch.__file__)}
    implementations = []
    for label, (module, constants) in zip(("original", "candidate"), modules, strict=True):
        namespace = {"torch": torch, "functional": torch.nn.functional, "math": math, **constants}
        exec(compile(module, f"saved-{label}-na.py", "exec"), namespace)
        implementations.append(namespace)
    original, candidate = implementations

    def snapshot(tensor):
        check_fault()
        contiguous = tensor.detach().contiguous().to("cpu")
        raw = contiguous.view(torch.uint8).numpy().tobytes()
        return {"shape": list(contiguous.shape), "dtype": str(contiguous.dtype),
                "sha256": sha(raw), "finite": bool(torch.isfinite(contiguous).all().item())}, raw

    def compare_calls(kind, identity, calls):
        row = {"kind": kind, **identity, "outputs": []}
        receipt["cases"].append(row)
        raw_outputs = []
        for name, call in calls:
            check_fault()
            tensor = call()
            summary, raw = snapshot(tensor)
            row["outputs"].append({"implementation": name, **summary})
            raw_outputs.append(raw)
            del tensor
        row["exact"] = (raw_outputs[0] == raw_outputs[1] == raw_outputs[2]
                        and all(o["finite"] for o in row["outputs"])
                        and all((o["shape"], o["dtype"]) ==
                                (row["outputs"][0]["shape"], row["outputs"][0]["dtype"])
                                for o in row["outputs"]))
        if not row["exact"]:
            raise RuntimeError(f"Native exact comparison failed: {kind} {identity}")

    # Explicit small boundary geometries; no model-sized masks are allocated.
    geometries = [
        ((1, 1, 1), (1, 1, 1), (False, False, False), ((0, 1),) * 3),
        ((3, 4, 5), (3, 3, 3), (False, False, False), ((0, 2), (1, 4), (3, 5))),
        ((3, 4, 5), (7, 7, 7), (False, False, False), ((1, 3), (0, 2), (2, 5))),
        ((3, 4, 5), (2, 3, 4), (True, True, True), ((0, 3), (1, 4), (2, 5))),
        ((3, 4, 5), (3, 2, 3), (True, False, True), ((1, 3), (2, 4), (0, 3))),
    ]
    with torch.inference_mode():
        for dtype in (torch.bfloat16, torch.float32):
            for case_id, (dims, kernels, causal, ranges) in enumerate(geometries):
                check_fault()
                rel = []
                for d, k, c, (lo, hi) in zip(dims, kernels, causal, ranges, strict=True):
                    starts, ends = original["_window_bounds"](d, k, c)
                    origin = starts[lo]
                    rel.append((tuple(v - origin for v in starts[lo:hi]),
                                tuple(v - origin for v in ends[lo:hi])))
                calls = [(label, lambda impl=impl: impl["_group_mask"](rel, dtype, device))
                         for label, impl in (("original", original), ("candidate", candidate), ("candidate-repeat", candidate))]
                compare_calls("mask", {"case_id": case_id, "dtype": str(dtype), "relative_bounds": rel}, calls)

            for case_id, (dims, kernels, causal, scale) in enumerate([
                ((1, 1, 1), (1, 1, 1), (False, False, False), 1.0),
                ((2, 3, 4), (3, 3, 3), (False, False, False), None),
                ((3, 4, 5), (2, 3, 4), (True, False, True), 1.0),
            ]):
                check_fault()
                shape = (1, *dims, 2, 8)
                values = torch.arange(math.prod(shape), dtype=torch.float32).reshape(shape)
                q = ((values % 17 - 8) / 16).to(device=device, dtype=dtype)
                k = ((values % 13 - 6) / 16).to(device=device, dtype=dtype)
                v = ((values % 11 - 5) / 16).to(device=device, dtype=dtype)
                calls = [(label, lambda impl=impl: impl["na3d"](q, k, v, list(kernels), list(causal), scale))
                         for label, impl in (("original", original), ("candidate", candidate), ("candidate-repeat", candidate))]
                compare_calls("attention", {"case_id": case_id, "dtype": str(dtype), "shape": shape,
                                           "kernels": kernels, "causal": causal, "scale": scale}, calls)
                del q, k, v, values
    check_fault()
    receipt["status"] = "small-native-mask-attention-parity-passed"
    receipt["passed"] = True
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, choices=("cpu", "xpu:3"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    receipt = {"schema": "ltx25.na-mask-extent-native-qualification.v1",
               "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "script_sha256": sha(Path(__file__).read_bytes()), "python": sys.version,
               "platform": platform.platform(), "device": args.device, "check_only": args.check_only,
               "torch_imported": False, "passed": False, "cases": [],
               "full_clip_parity_tested": False, "timing_measured": False,
               "limitations": ["Small bounded native cases only; no full-clip parity or speed claim",
                               "Tiny attention cases use unchanged production budgets and do not force tiling"]}
    # Exclusive creation prevents replacing an earlier qualification receipt.
    with args.output.open("x") as output:
        try:
            code = run(args, receipt)
        except FaultHalt as exc:
            status = ("halted-fault-before-torch-import" if not receipt["torch_imported"]
                      else "halted-fault-during-native-qualification")
            receipt.update(status=status, error=str(exc), fault_path=str(FAULT))
            if FAULT.exists():
                receipt["fault_sha256"] = sha(FAULT.read_bytes())
            code = 2
        except Exception as exc:
            receipt.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            code = 1
        receipt["torch_present_in_sys_modules"] = "torch" in sys.modules
        json.dump(receipt, output, indent=2)
        output.write("\n")
    print(json.dumps({"status": receipt["status"], "output": str(args.output),
                      "torch_imported": receipt["torch_imported"], "passed": receipt["passed"]}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
