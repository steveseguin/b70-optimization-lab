#!/home/steve/.venvs/vllm-xpu/bin/python3
"""Validate the exact additive operator ABI of grouped serving stage A2."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parent
BASE_PATH = TOOLS / "inspect-q38-grouped-serving-stage-a2.py"
EXPECTED_BASE_SHA256 = (
    "b37a2e15d61826d1deca3b3dab03028e18b6e7f1a77776bd52b09a6d6d6d40d4"
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if file_sha256(BASE_PATH) != EXPECTED_BASE_SHA256:
    raise RuntimeError(f"A2 inspector dependency drifted: {BASE_PATH}")
SPEC = importlib.util.spec_from_file_location(
    "q38_grouped_stage_a2_inspector", BASE_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {BASE_PATH}")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

GDN_OPERATOR = "_xpu_C::gdn_attention"
GROUPED_OPERATOR = "_xpu_C::cutlass_grouped_gemm_interface"
EXPECTED_ADDED_SCHEMAS = {
    "_xpu_C::cutlass_grouped_gemm_interface(Tensor ptr_A, Tensor ptr_B, Tensor? ptr_scales, Tensor? ptr_bias, Tensor ptr_D, Tensor rows_per_expert, int N, int K, int num_experts, bool is_B_int4, bool is_B_mxfp4) -> Tensor",
    "_xpu_C::cutlass_grouped_gemm_w8a8_int8_active_offsets_interface(Tensor ptr_A, Tensor ptr_A_scales, Tensor ptr_B, Tensor ptr_B_scales, Tensor? ptr_bias, Tensor ptr_D, Tensor expert_first_token_offset, Tensor active_expert_ids, int N, int K, int num_experts, int num_active_experts) -> Tensor",
    "_xpu_C::cutlass_grouped_gemm_w8a8_int8_interface(Tensor ptr_A, Tensor ptr_A_scales, Tensor ptr_B, Tensor ptr_B_scales, Tensor? ptr_bias, Tensor ptr_D, Tensor rows_per_expert, int N, int K, int num_experts) -> Tensor",
    "_xpu_C::cutlass_grouped_gemm_w8a8_int8_offsets_interface(Tensor ptr_A, Tensor ptr_A_scales, Tensor ptr_B, Tensor ptr_B_scales, Tensor? ptr_bias, Tensor ptr_D, Tensor expert_first_token_offset, int N, int K, int num_experts) -> Tensor",
    "_xpu_C::cutlass_grouped_gemm_w8a8_int8_topk8_gemm1_interface(Tensor ptr_A, Tensor ptr_A_scales, Tensor ptr_B, Tensor ptr_B_scales, Tensor? ptr_bias, Tensor ptr_D, Tensor topk_ids, Tensor unpermuted_row_to_permuted_row, int N, int K, int num_experts) -> Tensor",
    "_xpu_C::fp8_gemm_out(Tensor(a!) out, Tensor A, Tensor B, ScalarType? out_dtype, Tensor? A_scale_, Tensor? B_scale_, Tensor? bias_) -> Tensor",
    "_xpu_C::is_xe2_arch(int device_index=-1) -> bool",
    "_xpu_C::is_xe3_arch(int device_index=-1) -> bool",
    "_xpu_C::qwen36_moe_onednn_sidecar_probe(Tensor hidden_states, Tensor topk_weights, Tensor topk_ids, Tensor w13, Tensor w13_scales, Tensor w2, Tensor w2_scales, Tensor output, Tensor remapped_hidden_states, Tensor rows_per_expert, Tensor unpermuted_row_to_permuted_row, Tensor gemm1_a, Tensor gemm1_a_scales, Tensor gemm1_output, Tensor act_output, Tensor gemm2_a, Tensor gemm2_a_scales, Tensor gemm2_output, Tensor? onednn_grouped_offsets, int layer_index, bool dry_create_descriptors, int execute_mode) -> Tensor",
    "_xpu_C::qwen36_moe_w8a8_full_layerlet(Tensor hidden_states, Tensor topk_ids, Tensor topk_weights, Tensor workspace, Tensor remapped_hidden_states, Tensor unpermuted_row_to_permuted_row, Tensor expert_first_token_offset, Tensor gemm1_a, Tensor gemm1_a_scales, Tensor w13, Tensor w13_scales, Tensor? w13_bias, Tensor gemm1_output, Tensor gemm2_a, Tensor gemm2_a_scales, Tensor w2, Tensor w2_scales, Tensor? w2_bias, Tensor gemm2_output, Tensor output, int hidden_size, int inter_size, int num_experts) -> Tensor",
    "_xpu_C::qwen36_moe_w8a8_middle_layerlet(Tensor gemm1_a, Tensor gemm1_a_scales, Tensor w13, Tensor w13_scales, Tensor? w13_bias, Tensor gemm1_output, Tensor gemm2_a, Tensor gemm2_a_scales, Tensor w2, Tensor w2_scales, Tensor? w2_bias, Tensor gemm2_output, Tensor expert_first_token_offset, int gemm1_n, int gemm1_k, int gemm2_n, int gemm2_k, int num_experts) -> Tensor",
    "_xpu_C::qwen36_rows_per_expert_offsets_int64_out(Tensor rows_per_expert, Tensor($0! -> ) offsets) -> Tensor",
    "_xpu_C::qwen36_shared_expert_w8a8_out(Tensor hidden_states, Tensor($0! -> ) hidden_q, Tensor($1! -> ) hidden_scales, Tensor gate_up_w, Tensor gate_up_w_scales, Tensor($2! -> ) gate_up_out, Tensor($3! -> ) act_q, Tensor($4! -> ) act_scales, Tensor down_w, Tensor down_w_scales, Tensor($5! -> ) down_out, Tensor expert_gate_w, Tensor($6! -> ) output) -> Tensor",
    "_xpu_C::qwen36_topk_ids_to_active_expert_ids_int32_out(Tensor topk_ids, Tensor($0! -> ) active_expert_ids, int topk) -> Tensor",
}


def mapped_paths(name: str) -> set[Path]:
    paths: set[Path] = set()
    for line in Path("/proc/self/maps").read_text(encoding="utf-8").splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6 or not fields[5].startswith("/"):
            continue
        raw = fields[5]
        if raw.endswith(" (deleted)") and Path(raw[:-10]).name == name:
            raise BASE.ContractError(f"mapped library was deleted: {raw}")
        path = Path(raw.removesuffix(" (deleted)"))
        if path.name == name:
            paths.add(path.resolve())
    return paths


def one_mapped(name: str) -> Path:
    paths = mapped_paths(name)
    if len(paths) != 1:
        raise BASE.ContractError(
            f"expected one mapped {name}, got {sorted(map(str, paths))}"
        )
    return paths.pop()


def dump(label: str, output: Path) -> None:
    package, entries = BASE.verify_stage(label)
    loader = [item for item in os.environ.get("LD_LIBRARY_PATH", "").split(":") if item]
    if not loader or Path(loader[0]).resolve() != package:
        raise BASE.ContractError(f"LD_LIBRARY_PATH does not begin with {package}")
    if any(
        name == "vllm_xpu_kernels" or name.startswith("vllm_xpu_kernels.")
        for name in sys.modules
    ):
        raise BASE.ContractError("vllm_xpu_kernels was imported before validation")
    sys.path.insert(0, str(package.parent))
    importlib.invalidate_caches()
    package_module = importlib.import_module("vllm_xpu_kernels")
    native_module = importlib.import_module("vllm_xpu_kernels._xpu_C")
    if Path(package_module.__file__).resolve() != (package / "__init__.py").resolve():
        raise BASE.ContractError("package resolved outside the requested stage")
    if Path(native_module.__file__).resolve() != (package / "_xpu_C.abi3.so").resolve():
        raise BASE.ContractError(
            "native extension resolved outside the requested stage"
        )

    import torch

    schemas = sorted(
        (
            schema
            for schema in torch._C._jit_get_all_schemas()
            if schema.name.startswith("_xpu_C::")
        ),
        key=str,
    )
    names = {schema.name for schema in schemas}
    required = {GDN_OPERATOR}
    if label == "candidate":
        required.add(GROUPED_OPERATOR)
    if not required.issubset(names):
        raise BASE.ContractError(
            f"required operators absent: {sorted(required - names)}"
        )
    gdn = next(schema for schema in schemas if schema.name == GDN_OPERATOR)
    gdn_arguments = tuple(argument.name for argument in gdn.arguments)
    if gdn_arguments != BASE.EXPECTED_GDN_ARGUMENTS:
        raise BASE.ContractError(f"GDN ABI drifted: {gdn_arguments}")

    mapped = {
        "gdn": one_mapped("libgdn_attn_kernels_xe_2.so"),
        "sycl": one_mapped("libsycl.so.8"),
    }
    grouped_paths = mapped_paths("libgrouped_gemm_xe_2.so")
    if label == "candidate":
        if grouped_paths != {(package / "libgrouped_gemm_xe_2.so").resolve()}:
            raise BASE.ContractError(
                f"candidate grouped library mismatch: {grouped_paths}"
            )
        mapped["grouped"] = grouped_paths.pop()
    elif grouped_paths:
        raise BASE.ContractError(
            f"accepted stage unexpectedly mapped grouped library: {grouped_paths}"
        )
    expected_mapped = {
        "gdn": package / "libgdn_attn_kernels_xe_2.so",
        "sycl": BASE.SYCL,
    }
    for name, expected in expected_mapped.items():
        if mapped[name] != expected.resolve():
            raise BASE.ContractError(
                f"{name} resolved to {mapped[name]}, expected {expected}"
            )
    if BASE.sha256(BASE.SYCL) != BASE.EXPECTED_SYCL_SHA256:
        raise BASE.ContractError("mapped SYCL runtime drifted")
    BASE.atomic_json(
        output,
        {
            "schema_version": 2,
            "status": "passed",
            "label": label,
            "package": str(package),
            "manifest": str(Path(BASE.STAGES[label]["manifest"]).resolve()),
            "manifest_sha256": BASE.STAGES[label]["manifest_sha256"],
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
        raise BASE.ContractError("schema input did not pass")
    accepted_schemas = set(accepted.get("schemas", []))
    candidate_schemas = set(candidate.get("schemas", []))
    removed = accepted_schemas - candidate_schemas
    added = candidate_schemas - accepted_schemas
    if removed:
        raise BASE.ContractError(
            f"candidate removed accepted schemas: {sorted(removed)}"
        )
    if added != EXPECTED_ADDED_SCHEMAS:
        raise BASE.ContractError(
            f"candidate additive schema set drifted: {sorted(added)}"
        )
    if accepted.get("gdn_argument_names") != list(BASE.EXPECTED_GDN_ARGUMENTS):
        raise BASE.ContractError("accepted GDN ABI differs")
    if candidate.get("gdn_argument_names") != list(BASE.EXPECTED_GDN_ARGUMENTS):
        raise BASE.ContractError("candidate GDN ABI differs")
    BASE.atomic_json(
        output,
        {
            "schema_version": 2,
            "status": "passed",
            "classification": "accepted_schema_preserved_exact_additive_candidate",
            "accepted": str(accepted_path.resolve()),
            "candidate": str(candidate_path.resolve()),
            "accepted_schema_count": len(accepted_schemas),
            "candidate_schema_count": len(candidate_schemas),
            "removed_schemas": [],
            "added_schemas": sorted(added),
            "exact_expected_additive_set": True,
            "gdn_argument_count": len(BASE.EXPECTED_GDN_ARGUMENTS),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    dump_parser = subparsers.add_parser("dump")
    dump_parser.add_argument("--label", choices=tuple(BASE.STAGES), required=True)
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
