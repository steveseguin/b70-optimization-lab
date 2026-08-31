#!/home/steve/.venvs/vllm-xpu/bin/python3
"""Hash-bound package, loader, and operator-schema check for serving stage A2."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
from typing import Any


REPO = Path("/home/steve/llm-optimizations")
ACCEPTED_PACKAGE = Path(
    "/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70/vllm_xpu_kernels"
)
ACCEPTED_MANIFEST = (
    REPO / "experiments/qwen38-flash-next-fp8-b70/data/"
    "runtime-stage-padding-guard-loadable.sha256"
)
CANDIDATE_PACKAGE = Path(
    "/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2/vllm_xpu_kernels"
)
CANDIDATE_MANIFEST = Path(
    "/mnt/fast-ai/qwen38-build/"
    "runtime-serving-hcgrouped-eeee7d6-a2-evidence/runtime-stage.sha256"
)
SYCL = Path("/home/steve/.venvs/vllm-xpu/lib/libsycl.so.8")
EXPECTED_SYCL_SHA256 = (
    "0336997fdfed9b2e6385e9f1cea2395eb5e130d3e5e9c943df5b0c10c1b5e57f"
)
STAGES = {
    "accepted": {
        "package": ACCEPTED_PACKAGE,
        "manifest": ACCEPTED_MANIFEST,
        "manifest_sha256": (
            "9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b"
        ),
        "native_sha256": (
            "8f11e716910289c9e53b770fab14231c040ac5b08ea7830947390ac0fb674496"
        ),
        "gdn_sha256": (
            "e7b9757a317157bb4a63159cc38ad3fc302135ca72954807d189420bbcf1595e"
        ),
        "grouped_sha256": (
            "d30e4f776088a58252da3c35f43ef060ee1872d38afd4c6b329b6f51fc50e488"
        ),
    },
    "candidate": {
        "package": CANDIDATE_PACKAGE,
        "manifest": CANDIDATE_MANIFEST,
        "manifest_sha256": (
            "a4e83ec34d91b70a666dc170fcc3bda75562592c58fce198f29cfa4d25755d0d"
        ),
        "native_sha256": (
            "8d6d41a2259b4d4eda53edd9524d113d9190ae1b093a150fd79aa72a5c28dd76"
        ),
        "gdn_sha256": (
            "6c9ba1f12838b3eaa27e91610f0344fbf11671bfee204c6a9a68564fc654c17e"
        ),
        "grouped_sha256": (
            "c8ba41d4978b0095648acee6782b7fd300ebc26403b5d1f2f7bcfb87b3430c42"
        ),
    },
}
REQUIRED_OPERATORS = {
    "_xpu_C::cutlass_grouped_gemm_interface",
    "_xpu_C::gdn_attention",
}
EXPECTED_GDN_ARGUMENTS = (
    "core_attn_out",
    "z",
    "projected_states_qkvz",
    "projected_states_ba",
    "num_k_heads",
    "num_v_heads",
    "head_k_dim",
    "head_v_dim",
    "conv_state",
    "ssm_state",
    "conv_weights",
    "conv_bias",
    "activation",
    "A_log",
    "dt_bias",
    "num_prefills",
    "num_decodes",
    "has_initial_state",
    "non_spec_query_start_loc",
    "non_spec_state_indices_tensor",
    "num_actual_tokens",
    "tp_size",
    "reorder_input",
)


class ContractError(RuntimeError):
    """A stage identity, loader, schema, or evidence contract failed."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.resolve()
    temporary = path.with_name(path.name + ".tmp")
    if path.exists() or temporary.exists():
        raise ContractError(f"refusing to overwrite evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def parse_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fields = line.split(maxsplit=1)
        if len(fields) != 2 or len(fields[0]) != 64:
            raise ContractError(f"malformed manifest line {number}")
        expected, name = fields
        name = name.removeprefix("*")
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or name in entries:
            raise ContractError(f"unsafe or duplicate manifest entry: {name}")
        entries[name] = expected
    if len(entries) != 18:
        raise ContractError(f"stage manifest has {len(entries)} entries, expected 18")
    return entries


def verify_stage(label: str) -> tuple[Path, dict[str, str]]:
    identity = STAGES[label]
    package = Path(identity["package"]).resolve()
    manifest = Path(identity["manifest"]).resolve()
    if sha256(manifest) != identity["manifest_sha256"]:
        raise ContractError(f"{label} manifest digest drifted")
    entries = parse_manifest(manifest)
    actual_files = {
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
        and path.name != ".gitkeep"
        and "__pycache__" not in path.parts
    }
    if actual_files != set(entries):
        raise ContractError(
            f"{label} inventory mismatch: missing={sorted(set(entries) - actual_files)} "
            f"extra={sorted(actual_files - set(entries))}"
        )
    for name, expected in entries.items():
        candidate = package / name
        if candidate.is_symlink() or sha256(candidate) != expected:
            raise ContractError(f"{label} stage entry drifted: {name}")
    required = {
        "_xpu_C.abi3.so": identity["native_sha256"],
        "libgdn_attn_kernels_xe_2.so": identity["gdn_sha256"],
        "libgrouped_gemm_xe_2.so": identity["grouped_sha256"],
    }
    for name, expected in required.items():
        if entries.get(name) != expected:
            raise ContractError(f"{label} required binary drifted: {name}")
    return package, entries


def mapped_library(name: str) -> Path:
    paths: set[Path] = set()
    for line in Path("/proc/self/maps").read_text(encoding="utf-8").splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6 or not fields[5].startswith("/"):
            continue
        raw = fields[5]
        if raw.endswith(" (deleted)") and Path(raw[:-10]).name == name:
            raise ContractError(f"mapped library was deleted: {raw}")
        path = Path(raw.removesuffix(" (deleted)"))
        if path.name == name:
            paths.add(path.resolve())
    if len(paths) != 1:
        raise ContractError(
            f"expected one mapped {name}, got {sorted(map(str, paths))}"
        )
    return paths.pop()


def dump(label: str, output: Path) -> None:
    package, entries = verify_stage(label)
    loader = [item for item in os.environ.get("LD_LIBRARY_PATH", "").split(":") if item]
    if not loader or Path(loader[0]).resolve() != package:
        raise ContractError(f"LD_LIBRARY_PATH does not begin with {package}")
    if any(
        name == "vllm_xpu_kernels" or name.startswith("vllm_xpu_kernels.")
        for name in sys.modules
    ):
        raise ContractError("vllm_xpu_kernels was imported before stage validation")
    stage_root = package.parent
    sys.path.insert(0, str(stage_root))
    importlib.invalidate_caches()
    package_module = importlib.import_module("vllm_xpu_kernels")
    native_module = importlib.import_module("vllm_xpu_kernels._xpu_C")
    if Path(package_module.__file__).resolve() != (package / "__init__.py").resolve():
        raise ContractError("package resolved outside the requested stage")
    if Path(native_module.__file__).resolve() != (package / "_xpu_C.abi3.so").resolve():
        raise ContractError("native extension resolved outside the requested stage")

    import torch

    schemas = sorted(
        (
            schema
            for schema in torch._C._jit_get_all_schemas()
            if schema.name.startswith("_xpu_C::")
        ),
        key=lambda schema: str(schema),
    )
    names = {schema.name for schema in schemas}
    if not REQUIRED_OPERATORS.issubset(names):
        raise ContractError(
            f"required operators absent: {sorted(REQUIRED_OPERATORS - names)}"
        )
    gdn = next(schema for schema in schemas if schema.name == "_xpu_C::gdn_attention")
    gdn_arguments = tuple(argument.name for argument in gdn.arguments)
    if gdn_arguments != EXPECTED_GDN_ARGUMENTS:
        raise ContractError(f"GDN ABI drifted: {gdn_arguments}")

    mapped = {
        "gdn": mapped_library("libgdn_attn_kernels_xe_2.so"),
        "grouped": mapped_library("libgrouped_gemm_xe_2.so"),
        "sycl": mapped_library("libsycl.so.8"),
    }
    expected_mapped = {
        "gdn": package / "libgdn_attn_kernels_xe_2.so",
        "grouped": package / "libgrouped_gemm_xe_2.so",
        "sycl": SYCL,
    }
    for name, expected in expected_mapped.items():
        if mapped[name] != expected.resolve():
            raise ContractError(
                f"{name} resolved to {mapped[name]}, expected {expected}"
            )
    if sha256(SYCL) != EXPECTED_SYCL_SHA256:
        raise ContractError("mapped SYCL runtime drifted")
    atomic_json(
        output,
        {
            "schema_version": 1,
            "status": "passed",
            "label": label,
            "package": str(package),
            "manifest": str(Path(STAGES[label]["manifest"]).resolve()),
            "manifest_sha256": STAGES[label]["manifest_sha256"],
            "entries": entries,
            "package_path": str(Path(package_module.__file__).resolve()),
            "native_path": str(Path(native_module.__file__).resolve()),
            "mapped": {name: str(path) for name, path in mapped.items()},
            "schema_count": len(schemas),
            "schemas": [str(schema) for schema in schemas],
            "schema_names": sorted(names),
            "gdn_argument_names": list(gdn_arguments),
        },
    )


def compare(accepted_path: Path, candidate_path: Path, output: Path) -> None:
    accepted = json.loads(accepted_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    if accepted.get("status") != "passed" or candidate.get("status") != "passed":
        raise ContractError("schema input did not pass")
    accepted_schemas = accepted.get("schemas")
    candidate_schemas = candidate.get("schemas")
    if accepted_schemas != candidate_schemas:
        raise ContractError("candidate operator schema set differs from accepted stage")
    if candidate.get("gdn_argument_names") != list(EXPECTED_GDN_ARGUMENTS):
        raise ContractError("candidate GDN ABI differs")
    atomic_json(
        output,
        {
            "schema_version": 1,
            "status": "passed",
            "classification": "accepted_candidate_operator_schema_parity",
            "accepted": str(accepted_path.resolve()),
            "candidate": str(candidate_path.resolve()),
            "schema_count": len(candidate_schemas),
            "exact_schema_set_parity": True,
            "required_operators": sorted(REQUIRED_OPERATORS),
            "gdn_argument_count": len(EXPECTED_GDN_ARGUMENTS),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    dump_parser = subparsers.add_parser("dump")
    dump_parser.add_argument("--label", choices=tuple(STAGES), required=True)
    dump_parser.add_argument("--output", type=Path, required=True)
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--accepted", type=Path, required=True)
    compare_parser.add_argument("--candidate", type=Path, required=True)
    compare_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "dump":
        dump(args.label, args.output)
    else:
        compare(args.accepted, args.candidate, args.output)


if __name__ == "__main__":
    main()
