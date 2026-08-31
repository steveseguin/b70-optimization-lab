#!/home/steve/.venvs/vllm-xpu/bin/python
"""Exact-shape one-B70 Qwen3.8 Flash-Next GDN history replay gate.

This is a bounded raw-operator reliability diagnostic.  It never initializes
vLLM, loads model weights, starts a server, or launches a collective.  It calls
the exact staged 23-argument ``_xpu_C::gdn_attention`` operator used by A24 and
A25 with the Flash-Next TP4-local shape and dtype contract:

* BF16 projected QKVZ/BA, convolution weights/cache, Z, and core output;
* FP32 recurrent state and A_log, BF16 dt_bias;
* global K/V heads 16/48, local K/V heads 4/12, head dimensions 128/128;
* 64 fixed synthetic tokens per call for 64 sequential calls (4096 tokens);
* one stable cache slot, no initial state on chunk zero, and initial state on
  chunks 1..63, exactly matching chunked-prefill state consumption.

Every trajectory begins from a complete fixed cache reset.  The gate compares
the entering cache, core/Z outputs, and outgoing convolution/recurrent state at
every chunk against trajectory zero, while checking complete output overwrite,
finite values, immutable inputs/metadata, and non-selected cache rows.  On the
first mismatch it restores trajectory zero's exact entering state and repeats
that one chunk, distinguishing instability with identical input/state from a
divergence inherited at an earlier chunk boundary.

Important interpretation boundary: inputs and weights are deterministic
synthetic fixtures, not captured model values.  A pass is a bounded negative
for the exact native shape/history contract, not an end-to-end reliability or
performance result.  It does not test input projections, RMSNormGated, output
projection, TP reduction, PLE, QSA, MoE, scheduling, or cross-stream work.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path("/home/steve/llm-optimizations")
SCRIPT_PATH = Path(__file__).resolve()
STAGE = Path("/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70")
STAGE_PACKAGE = STAGE / "vllm_xpu_kernels"
STAGE_MANIFEST = (
    REPO
    / "experiments/qwen38-flash-next-fp8-b70/data/"
    "runtime-stage-padding-guard-loadable.sha256"
)
MODEL_CONFIG = Path("/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8/config.json")
KERNEL_REPO = Path("/home/steve/src/vllm-xpu-kernels")
A24_IDENTITY = Path(
    "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/"
    "qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt24/"
    "identity.txt"
)
A25_IDENTITY = Path(
    "/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/"
    "qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt25/"
    "identity.txt"
)

EXPECTED = {
    "stage_manifest_sha256":
        "9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b",
    "native_extension_sha256":
        "8f11e716910289c9e53b770fab14231c040ac5b08ea7830947390ac0fb674496",
    "gdn_library_sha256":
        "e7b9757a317157bb4a63159cc38ad3fc302135ca72954807d189420bbcf1595e",
    "model_config_sha256":
        "99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d",
    "runtime_build_commit": "2f829747503c77d4814834dffd0840fb1dd9f75a",
    "gdn_source_sha256":
        "6ac157e3ef5539a3157504ffcc991c35ab8b78ee34c194639918df0583548a88",
    "a24_identity_sha256":
        "412a525029759d0a3a38f264597b607d1af36c07e27d6d658f7ac5fb488f8a4a",
    "a25_identity_sha256":
        "af1ef31a467bbdf0fef03a450817e786a403b77fcedbee864afce1873d99ce29",
    "python_prefix": "/home/steve/.venvs/vllm-xpu",
}

TP_SIZE = 4
NUM_K_HEADS = 16
NUM_V_HEADS = 48
HEAD_K_DIM = 128
HEAD_V_DIM = 128
CONV_WIDTH = 4
LOCAL_K_HEADS = NUM_K_HEADS // TP_SIZE
LOCAL_V_HEADS = NUM_V_HEADS // TP_SIZE
QKVZ_COLS = LOCAL_K_HEADS * (
    2 * HEAD_K_DIM + 2 * (NUM_V_HEADS // NUM_K_HEADS) * HEAD_V_DIM
)
BA_COLS = 2 * LOCAL_V_HEADS
CONV_COLS = LOCAL_K_HEADS * (
    2 * HEAD_K_DIM + (NUM_V_HEADS // NUM_K_HEADS) * HEAD_V_DIM
)
CONV_HISTORY = CONV_WIDTH - 1
TOKENS_PER_CHUNK = 64
CHUNKS = 64
TOTAL_TOKENS = TOKENS_PER_CHUNK * CHUNKS
CACHE_ROWS = 2
ACTIVE_ROW = 1
BASE_SEED = 20260830
OUTPUT_SENTINELS = (31744.0, -31744.0)
REPLAY_REPEATS = 16
TRAJECTORIES = {"smoke": 2, "qualification": 100}
SCHEMA_VERSION = 1
MANIFEST_RE = re.compile(r"^([0-9a-f]{64})  (.+)$")
EXPECTED_OPERATOR_ARGUMENTS = (
    "core_attn_out", "z", "projected_states_qkvz", "projected_states_ba",
    "num_k_heads", "num_v_heads", "head_k_dim", "head_v_dim",
    "conv_state", "ssm_state", "conv_weights", "conv_bias", "activation",
    "A_log", "dt_bias", "num_prefills", "num_decodes",
    "has_initial_state", "non_spec_query_start_loc",
    "non_spec_state_indices_tensor", "num_actual_tokens", "tp_size",
    "reorder_input",
)


class ContractError(RuntimeError):
    """A fail-closed identity, execution, or evidence contract violation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file_sha(path: Path, expected: str, label: str) -> str:
    if not path.is_file() or path.is_symlink():
        raise ContractError(f"{label} is not a regular file: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise ContractError(
            f"{label} SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return actual


def parse_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text().splitlines(), 1):
        match = MANIFEST_RE.fullmatch(raw_line)
        if match is None:
            raise ContractError(
                f"malformed stage manifest line {line_number}: {raw_line!r}"
            )
        expected_sha, relative_text = match.groups()
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise ContractError(f"unsafe stage manifest path: {relative_text!r}")
        normalized = relative.as_posix()
        if normalized in entries:
            raise ContractError(f"duplicate stage manifest path: {normalized}")
        entries[normalized] = expected_sha
    if not entries:
        raise ContractError("stage manifest is empty")
    return entries


def verify_stage() -> dict[str, Any]:
    manifest_sha = require_file_sha(
        STAGE_MANIFEST, EXPECTED["stage_manifest_sha256"], "stage manifest"
    )
    if not STAGE_PACKAGE.is_dir() or STAGE_PACKAGE.is_symlink():
        raise ContractError(f"stage package is not a directory: {STAGE_PACKAGE}")
    entries = parse_manifest(STAGE_MANIFEST)
    all_files = {
        path.relative_to(STAGE_PACKAGE).as_posix()
        for path in STAGE_PACKAGE.rglob("*")
        if path.is_file()
    }
    ignored_transient = sorted(
        relative for relative in all_files
        if Path(relative).name == ".gitkeep" or "__pycache__" in Path(relative).parts
    )
    actual_files = all_files - set(ignored_transient)
    if actual_files != set(entries):
        raise ContractError(
            "stage file set mismatch: "
            f"missing={sorted(set(entries) - actual_files)}, "
            f"extra={sorted(actual_files - set(entries))}"
        )
    for relative, expected_sha in entries.items():
        candidate = STAGE_PACKAGE / relative
        require_file_sha(candidate, expected_sha, f"stage entry {relative}")
    native = STAGE_PACKAGE / "_xpu_C.abi3.so"
    gdn = STAGE_PACKAGE / "libgdn_attn_kernels_xe_2.so"
    return {
        "root": str(STAGE),
        "package": str(STAGE_PACKAGE),
        "manifest": str(STAGE_MANIFEST),
        "manifest_sha256": manifest_sha,
        "entry_count": len(entries),
        "ignored_transient_files": ignored_transient,
        "native_extension_sha256": require_file_sha(
            native, EXPECTED["native_extension_sha256"], "native extension"
        ),
        "gdn_library_sha256": require_file_sha(
            gdn, EXPECTED["gdn_library_sha256"], "GDN library"
        ),
    }


def validate_model() -> dict[str, Any]:
    config_sha = require_file_sha(
        MODEL_CONFIG, EXPECTED["model_config_sha256"], "model config"
    )
    config = json.loads(MODEL_CONFIG.read_text())
    text = config.get("text_config")
    if not isinstance(text, dict):
        raise ContractError("model config has no text_config object")
    required = {
        "model_type": "qwen4_exp_text",
        "hidden_size": 2560,
        "num_hidden_layers": 48,
        "linear_num_key_heads": NUM_K_HEADS,
        "linear_num_value_heads": NUM_V_HEADS,
        "linear_key_head_dim": HEAD_K_DIM,
        "linear_value_head_dim": HEAD_V_DIM,
        "linear_conv_kernel_dim": CONV_WIDTH,
        "mamba_ssm_dtype": "float32",
        "hidden_act": "silu",
    }
    observed = {key: text.get(key) for key in required}
    if observed != required:
        raise ContractError(
            f"model shape contract mismatch: expected {required}, got {observed}"
        )
    if config.get("model_type") != "qwen4_exp":
        raise ContractError("top-level model_type is not qwen4_exp")
    return {
        "path": str(MODEL_CONFIG),
        "sha256": config_sha,
        "fields": observed,
        "weights_loaded": False,
    }


def parse_identity(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ContractError(f"malformed identity line {line_number} in {path}")
        key, value = line.split("=", 1)
        if not key or key in result:
            raise ContractError(f"duplicate/empty identity key on line {line_number}")
        result[key] = value
    return result


def validate_reference_identities() -> dict[str, Any]:
    expected_common = {
        "model": str(MODEL_CONFIG.parent),
        "kernels_head": "ad25aa9f69a2171612b9c6b83dfa82c69559f9e4",
        "runtime_stage_build_head": EXPECTED["runtime_build_commit"],
        "stage": str(STAGE),
        "kv_cache_memory_bytes": "134217728",
        "kv_cache_layout": "BLHNC",
    }
    output: dict[str, Any] = {}
    for label, path, expected_sha in (
        ("a24", A24_IDENTITY, EXPECTED["a24_identity_sha256"]),
        ("a25", A25_IDENTITY, EXPECTED["a25_identity_sha256"]),
    ):
        identity_sha = require_file_sha(path, expected_sha, f"{label} identity")
        fields = parse_identity(path)
        observed = {key: fields.get(key) for key in expected_common}
        if observed != expected_common:
            raise ContractError(
                f"{label} reference identity mismatch: expected "
                f"{expected_common}, got {observed}"
            )
        if fields.get("tp") != "4 ep=4 all2all=allgather_reducescatter":
            raise ContractError(f"{label} TP/EP contract is not exact: {fields.get('tp')}")
        run_contract = fields.get("moe_backend", "")
        required_fragments = (
            "triton", "eager=1", "mtp=0", "max_model_len=4352",
            "max_num_batched_tokens=64",
        )
        if any(fragment not in run_contract for fragment in required_fragments):
            raise ContractError(f"{label} run contract is not exact: {run_contract}")
        output[label] = {
            "path": str(path),
            "sha256": identity_sha,
            "vllm_head": fields.get("vllm_head"),
            "fields": observed,
            "run_contract": run_contract,
        }
    return output


def git_output(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(KERNEL_REPO), *args],
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def validate_source() -> dict[str, Any]:
    commit = EXPECTED["runtime_build_commit"]
    git_output("cat-file", "-e", f"{commit}^{{commit}}")
    source = subprocess.run(
        [
            "git", "-C", str(KERNEL_REPO), "show",
            f"{commit}:csrc/xpu/gdn_attn/gdn_attn_interface.cpp",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    source_sha = hashlib.sha256(source).hexdigest()
    if source_sha != EXPECTED["gdn_source_sha256"]:
        raise ContractError(
            "runtime-build GDN source mismatch: "
            f"expected {EXPECTED['gdn_source_sha256']}, got {source_sha}"
        )
    return {
        "repo": str(KERNEL_REPO),
        "runtime_build_commit": commit,
        "runtime_gdn_source_sha256": source_sha,
        "current_head": git_output("rev-parse", "HEAD"),
        "current_tree_is_not_execution_authority": True,
    }


def find_live_model_processes() -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    self_pid = os.getpid()
    needles = ("vllm serve", "vllm.entrypoints", "EngineCore", "Worker_TP")
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == self_pid:
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", errors="replace"
            ).strip()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if command and any(needle in command for needle in needles):
            matches.append({"pid": int(entry.name), "command": command})
    return sorted(matches, key=lambda item: item["pid"])


def validate_process(physical_gpu: int) -> dict[str, Any]:
    if physical_gpu not in range(4):
        raise ContractError("physical GPU must be 0, 1, 2, or 3")
    if Path(sys.prefix).resolve() != Path(EXPECTED["python_prefix"]).resolve():
        raise ContractError(
            f"wrong Python prefix: expected {EXPECTED['python_prefix']}, got {sys.prefix}"
        )
    if os.environ.get("ZE_AFFINITY_MASK") != str(physical_gpu):
        raise ContractError(
            f"ZE_AFFINITY_MASK must be exactly {physical_gpu}, got "
            f"{os.environ.get('ZE_AFFINITY_MASK')!r}"
        )
    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise ContractError("PYTHONDONTWRITEBYTECODE must be exactly 1")
    components = [
        item for item in os.environ.get("LD_LIBRARY_PATH", "").split(":") if item
    ]
    if not components or components[0] != str(STAGE_PACKAGE):
        raise ContractError(
            f"LD_LIBRARY_PATH must begin with {STAGE_PACKAGE}; got {components}"
        )
    live = find_live_model_processes()
    if live:
        raise ContractError(f"refusing to overlap live model processes: {live}")
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    marker_path = Path("/run/qwen38-flash-next-full-load.boot-id")
    marker = marker_path.read_text().strip() if marker_path.is_file() else None
    return {
        "hostname": socket.gethostname(),
        "python": sys.executable,
        "python_prefix": sys.prefix,
        "physical_gpu": physical_gpu,
        "logical_device": "xpu:0",
        "ze_affinity_mask": os.environ["ZE_AFFINITY_MASK"],
        "python_dont_write_bytecode": os.environ["PYTHONDONTWRITEBYTECODE"],
        "stage_library_path_first": True,
        "live_model_processes": [],
        "boot_id": boot_id,
        "full_load_marker": marker,
        "consumed_boot_is_allowed_for_raw_component_gate": marker == boot_id,
    }


def shape_contract() -> dict[str, Any]:
    return {
        "tp_size": TP_SIZE,
        "num_k_heads_global": NUM_K_HEADS,
        "num_v_heads_global": NUM_V_HEADS,
        "num_k_heads_local": LOCAL_K_HEADS,
        "num_v_heads_local": LOCAL_V_HEADS,
        "head_k_dim": HEAD_K_DIM,
        "head_v_dim": HEAD_V_DIM,
        "qkvz_shape_per_chunk": [TOKENS_PER_CHUNK, QKVZ_COLS],
        "ba_shape_per_chunk": [TOKENS_PER_CHUNK, BA_COLS],
        "core_z_shape_per_chunk": [TOKENS_PER_CHUNK, LOCAL_V_HEADS, HEAD_V_DIM],
        "conv_state_shape": [CACHE_ROWS, CONV_HISTORY, CONV_COLS],
        "ssm_state_shape": [CACHE_ROWS, LOCAL_V_HEADS, HEAD_V_DIM, HEAD_K_DIM],
        "activation_dtype": "torch.bfloat16",
        "conv_state_dtype": "torch.bfloat16",
        "ssm_state_dtype": "torch.float32",
        "A_log_dtype": "torch.float32",
        "dt_bias_dtype": "torch.bfloat16",
        "tokens_per_chunk": TOKENS_PER_CHUNK,
        "chunks_per_trajectory": CHUNKS,
        "tokens_per_trajectory": TOTAL_TOKENS,
        "active_cache_row": ACTIVE_ROW,
        "cache_reset_each_trajectory": True,
        "has_initial_state_by_chunk": [False] + [True] * (CHUNKS - 1),
        "num_prefills": 1,
        "num_decodes": 0,
        "reorder_input": True,
        "synthetic_fixed_inputs": True,
        "model_weights_loaded": False,
    }


def preflight(physical_gpu: int) -> dict[str, Any]:
    if (LOCAL_K_HEADS, LOCAL_V_HEADS, QKVZ_COLS, BA_COLS, CONV_COLS) != (
        4, 12, 4096, 24, 2560
    ):
        raise ContractError("internal TP4-local shape derivation changed")
    return {
        "process": validate_process(physical_gpu),
        "model": validate_model(),
        "references": validate_reference_identities(),
        "source": validate_source(),
        "stage": verify_stage(),
        "shape": shape_contract(),
        "script": str(SCRIPT_PATH),
        "script_sha256": sha256_file(SCRIPT_PATH),
    }


def tensor_digest(torch: Any, tensor: Any) -> dict[str, Any]:
    cpu = tensor.detach().contiguous().cpu()
    raw = cpu.view(torch.uint8).numpy().tobytes()
    return {
        "shape": list(cpu.shape),
        "dtype": str(cpu.dtype),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def digest_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return left == right


def make_cpu_fixture(torch: Any) -> dict[str, Any]:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(BASE_SEED)

    def randn(
        shape: tuple[int, ...], *, scale: float, dtype: Any = torch.bfloat16
    ) -> Any:
        return (
            torch.randn(shape, generator=generator, dtype=torch.float32) * scale
        ).to(dtype)

    return {
        "qkvz": randn((CHUNKS, TOKENS_PER_CHUNK, QKVZ_COLS), scale=0.125),
        "ba": randn((CHUNKS, TOKENS_PER_CHUNK, BA_COLS), scale=0.125),
        "conv_weights": randn((CONV_COLS, CONV_WIDTH), scale=0.03125),
        "conv_state": randn(
            (CACHE_ROWS, CONV_HISTORY, CONV_COLS), scale=0.015625
        ),
        "ssm_state": randn(
            (CACHE_ROWS, LOCAL_V_HEADS, HEAD_V_DIM, HEAD_K_DIM),
            scale=0.015625,
            dtype=torch.float32,
        ),
        "A_log": randn((LOCAL_V_HEADS,), scale=0.03125, dtype=torch.float32),
        "dt_bias": randn((LOCAL_V_HEADS,), scale=0.03125),
    }


def mapped_gdn_library() -> dict[str, str]:
    expected = (STAGE_PACKAGE / "libgdn_attn_kernels_xe_2.so").resolve()
    mapped: set[Path] = set()
    for line in Path("/proc/self/maps").read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6 or not fields[5].startswith("/"):
            continue
        if fields[5].endswith(" (deleted)"):
            raw = fields[5].removesuffix(" (deleted)")
            if Path(raw).name == expected.name:
                raise ContractError(f"mapped GDN library was deleted: {fields[5]}")
            continue
        candidate = Path(fields[5])
        if candidate.name == expected.name:
            mapped.add(candidate.resolve())
    if mapped != {expected}:
        raise ContractError(
            f"mapped GDN library mismatch: expected {expected}, got {sorted(map(str, mapped))}"
        )
    return {
        "path": str(expected),
        "sha256": require_file_sha(
            expected, EXPECTED["gdn_library_sha256"], "mapped GDN library"
        ),
    }


def import_native(torch: Any) -> dict[str, Any]:
    if any(
        name == "vllm_xpu_kernels" or name.startswith("vllm_xpu_kernels.")
        for name in sys.modules
    ):
        raise ContractError("vllm_xpu_kernels imported before identity checks")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(STAGE))
    importlib.invalidate_caches()
    package = importlib.import_module("vllm_xpu_kernels")
    native = importlib.import_module("vllm_xpu_kernels._xpu_C")
    package_path = Path(package.__file__).resolve()
    native_path = Path(native.__file__).resolve()
    if package_path != (STAGE_PACKAGE / "__init__.py").resolve():
        raise ContractError(f"loaded package path mismatch: {package_path}")
    if native_path != (STAGE_PACKAGE / "_xpu_C.abi3.so").resolve():
        raise ContractError(f"loaded native extension path mismatch: {native_path}")
    if not hasattr(torch.ops._xpu_C, "gdn_attention"):
        raise ContractError("staged extension did not register gdn_attention")
    schema = torch.ops._xpu_C.gdn_attention.default._schema
    names = tuple(argument.name for argument in schema.arguments)
    if names != EXPECTED_OPERATOR_ARGUMENTS:
        raise ContractError(
            f"operator ABI mismatch: expected {EXPECTED_OPERATOR_ARGUMENTS}, got {names}"
        )
    return {
        "package_path": str(package_path),
        "native_path": str(native_path),
        "native_sha256": sha256_file(native_path),
        "operator": "_xpu_C::gdn_attention",
        "operator_schema": str(schema),
        "operator_argument_count": len(names),
        "operator_argument_names": list(names),
        "mapped_gdn_library": mapped_gdn_library(),
        "direct_raw_op": True,
    }


def check_tensor(torch: Any, tensor: Any, *, sentinel: float | None = None) -> dict[str, Any]:
    finite = bool(torch.isfinite(tensor).all().item())
    sentinel_count = (
        int(torch.eq(tensor, sentinel).sum().item()) if sentinel is not None else None
    )
    return {
        "digest": tensor_digest(torch, tensor),
        "finite": finite,
        "sentinel_count": sentinel_count,
        "passed": finite and (sentinel_count in (None, 0)),
    }


def call_native(
    torch: Any,
    *,
    qkvz: Any,
    ba: Any,
    conv_state: Any,
    ssm_state: Any,
    fixture: dict[str, Any],
    has_initial: Any,
    query_start: Any,
    state_index: Any,
    core: Any,
    z: Any,
) -> None:
    torch.ops._xpu_C.gdn_attention(
        core,
        z,
        qkvz,
        ba,
        NUM_K_HEADS,
        NUM_V_HEADS,
        HEAD_K_DIM,
        HEAD_V_DIM,
        conv_state=conv_state,
        ssm_state=ssm_state,
        conv_weights=fixture["conv_weights"],
        conv_bias=None,
        activation="silu",
        A_log=fixture["A_log"],
        dt_bias=fixture["dt_bias"],
        num_prefills=1,
        num_decodes=0,
        has_initial_state=has_initial,
        non_spec_query_start_loc=query_start,
        non_spec_state_indices_tensor=state_index,
        num_actual_tokens=TOKENS_PER_CHUNK,
        tp_size=TP_SIZE,
        reorder_input=True,
    )


def classify_mismatch(fields: list[str]) -> str:
    if any(name.startswith("pre_") for name in fields):
        return "entering-cache-state-diverged"
    if any(name in {"qkvz", "ba", "metadata"} for name in fields):
        return "immutable-input-or-metadata-mutated"
    if any(name in {"core", "z", "post_conv", "post_ssm"} for name in fields):
        return "native-op-diverged-from-identical-trajectory"
    if any(name.startswith("nonselected") for name in fields):
        return "out-of-scope-cache-row-mutated"
    return "unclassified"


def snapshot_replay(
    torch: Any,
    *,
    chunk: int,
    fixture: dict[str, Any],
    canonical_pre_conv: Any,
    canonical_pre_ssm: Any,
    canonical: dict[str, Any],
    query_start: Any,
    state_index: Any,
    has_initial_false: Any,
    has_initial_true: Any,
) -> tuple[dict[str, Any], int]:
    device = torch.device("xpu:0")
    conv_work = fixture["conv_state"].clone()
    ssm_work = fixture["ssm_state"].clone()
    qkvz_work = torch.empty_like(fixture["qkvz"][chunk])
    ba_work = torch.empty_like(fixture["ba"][chunk])
    core = torch.empty(
        (TOKENS_PER_CHUNK, LOCAL_V_HEADS, HEAD_V_DIM),
        dtype=torch.bfloat16,
        device=device,
    )
    z = torch.empty_like(core)
    expected = {
        name: canonical[name]
        for name in ("core", "z", "post_conv", "post_ssm")
    }
    observations: list[dict[str, Any]] = []
    for repeat in range(REPLAY_REPEATS):
        conv_work.copy_(fixture["conv_state"])
        ssm_work.copy_(fixture["ssm_state"])
        conv_work[ACTIVE_ROW].copy_(canonical_pre_conv)
        ssm_work[ACTIVE_ROW].copy_(canonical_pre_ssm)
        qkvz_work.copy_(fixture["qkvz"][chunk])
        ba_work.copy_(fixture["ba"][chunk])
        poison = OUTPUT_SENTINELS[repeat % len(OUTPUT_SENTINELS)]
        core.fill_(poison)
        z.fill_(poison)
        call_native(
            torch,
            qkvz=qkvz_work,
            ba=ba_work,
            conv_state=conv_work,
            ssm_state=ssm_work,
            fixture=fixture,
            has_initial=has_initial_false if chunk == 0 else has_initial_true,
            query_start=query_start,
            state_index=state_index,
            core=core,
            z=z,
        )
        torch.xpu.synchronize()
        observed = {
            "core": tensor_digest(torch, core),
            "z": tensor_digest(torch, z),
            "post_conv": tensor_digest(torch, conv_work[ACTIVE_ROW]),
            "post_ssm": tensor_digest(torch, ssm_work[ACTIVE_ROW]),
        }
        fields = [name for name in expected if observed[name] != expected[name]]
        observations.append({
            "repeat": repeat,
            "passed": not fields,
            "mismatched_fields": fields,
            "digests": observed,
        })
    passed = all(item["passed"] for item in observations)
    return ({
        "chunk": chunk,
        "repeats": REPLAY_REPEATS,
        "restores_canonical_entering_state_each_repeat": True,
        "passed": passed,
        "interpretation": (
            "original divergence was inherited before this chunk"
            if passed
            else "native op diverged with identical input and restored entering state"
        ),
        "observations": observations,
    }, REPLAY_REPEATS)


def execute_run(args: argparse.Namespace) -> int:
    if args.json_out.exists() or args.json_out.with_suffix(args.json_out.suffix + ".tmp").exists():
        raise ContractError(f"refusing to overwrite output or temporary: {args.json_out}")
    trajectories = TRAJECTORIES[args.mode]
    identity = preflight(args.physical_gpu)
    import torch

    if not torch.xpu.is_available() or int(torch.xpu.device_count()) != 1:
        raise ContractError(
            f"affinity-isolated process must see exactly one XPU; got {torch.xpu.device_count()}"
        )
    torch.xpu.set_device(0)
    engagement = import_native(torch)
    cpu_fixture = make_cpu_fixture(torch)
    fixture_digests = {
        name: tensor_digest(torch, value) for name, value in cpu_fixture.items()
    }
    qkvz_chunk_digests = [
        tensor_digest(torch, cpu_fixture["qkvz"][chunk]) for chunk in range(CHUNKS)
    ]
    ba_chunk_digests = [
        tensor_digest(torch, cpu_fixture["ba"][chunk]) for chunk in range(CHUNKS)
    ]
    device = torch.device("xpu:0")
    fixture = {name: value.to(device) for name, value in cpu_fixture.items()}
    qkvz_work = torch.empty_like(fixture["qkvz"][0])
    ba_work = torch.empty_like(fixture["ba"][0])
    conv_work = torch.empty_like(fixture["conv_state"])
    ssm_work = torch.empty_like(fixture["ssm_state"])
    core = torch.empty(
        (TOKENS_PER_CHUNK, LOCAL_V_HEADS, HEAD_V_DIM),
        dtype=torch.bfloat16,
        device=device,
    )
    z = torch.empty_like(core)
    query_start = torch.tensor(
        [0, TOKENS_PER_CHUNK], dtype=torch.int32, device=device
    )
    state_index = torch.tensor([ACTIVE_ROW], dtype=torch.int32, device=device)
    has_initial_false = torch.tensor([False], dtype=torch.bool, device=device)
    has_initial_true = torch.tensor([True], dtype=torch.bool, device=device)
    metadata_before = {
        "query_start": tensor_digest(torch, query_start),
        "state_index": tensor_digest(torch, state_index),
        "has_initial_false": tensor_digest(torch, has_initial_false),
        "has_initial_true": tensor_digest(torch, has_initial_true),
    }
    nonselected_reference = {
        "conv": tensor_digest(torch, fixture["conv_state"][0]),
        "ssm": tensor_digest(torch, fixture["ssm_state"][0]),
    }

    canonical: list[dict[str, Any]] = []
    canonical_pre_states: list[tuple[Any, Any]] = []
    trajectory_results: list[dict[str, Any]] = []
    first_mismatch: dict[str, Any] | None = None
    native_calls = 0

    for trajectory in range(trajectories):
        conv_work.copy_(fixture["conv_state"])
        ssm_work.copy_(fixture["ssm_state"])
        trajectory_digests: list[dict[str, Any]] = []
        chunks_executed = 0
        for chunk in range(CHUNKS):
            qkvz_work.copy_(fixture["qkvz"][chunk])
            ba_work.copy_(fixture["ba"][chunk])
            pre = {
                "pre_conv": tensor_digest(torch, conv_work[ACTIVE_ROW]),
                "pre_ssm": tensor_digest(torch, ssm_work[ACTIVE_ROW]),
            }
            if trajectory == 0:
                canonical_pre_states.append((
                    conv_work[ACTIVE_ROW].clone(), ssm_work[ACTIVE_ROW].clone()
                ))
            poison = OUTPUT_SENTINELS[(trajectory + chunk) % len(OUTPUT_SENTINELS)]
            core.fill_(poison)
            z.fill_(poison)
            call_native(
                torch,
                qkvz=qkvz_work,
                ba=ba_work,
                conv_state=conv_work,
                ssm_state=ssm_work,
                fixture=fixture,
                has_initial=has_initial_false if chunk == 0 else has_initial_true,
                query_start=query_start,
                state_index=state_index,
                core=core,
                z=z,
            )
            native_calls += 1
            torch.xpu.synchronize()
            core_check = check_tensor(torch, core, sentinel=poison)
            z_check = check_tensor(torch, z, sentinel=poison)
            observed = {
                **pre,
                "core": core_check["digest"],
                "z": z_check["digest"],
                "post_conv": tensor_digest(torch, conv_work[ACTIVE_ROW]),
                "post_ssm": tensor_digest(torch, ssm_work[ACTIVE_ROW]),
                "qkvz": tensor_digest(torch, qkvz_work),
                "ba": tensor_digest(torch, ba_work),
                "nonselected_conv": tensor_digest(torch, conv_work[0]),
                "nonselected_ssm": tensor_digest(torch, ssm_work[0]),
            }
            invariant_failures: list[str] = []
            if not core_check["passed"]:
                invariant_failures.append("core")
            if not z_check["passed"]:
                invariant_failures.append("z")
            if observed["qkvz"] != qkvz_chunk_digests[chunk]:
                invariant_failures.append("qkvz")
            if observed["ba"] != ba_chunk_digests[chunk]:
                invariant_failures.append("ba")
            if observed["nonselected_conv"] != nonselected_reference["conv"]:
                invariant_failures.append("nonselected_conv")
            if observed["nonselected_ssm"] != nonselected_reference["ssm"]:
                invariant_failures.append("nonselected_ssm")
            metadata_after = {
                "query_start": tensor_digest(torch, query_start),
                "state_index": tensor_digest(torch, state_index),
                "has_initial_false": tensor_digest(torch, has_initial_false),
                "has_initial_true": tensor_digest(torch, has_initial_true),
            }
            if metadata_after != metadata_before:
                invariant_failures.append("metadata")

            comparison_fields = (
                "pre_conv", "pre_ssm", "core", "z", "post_conv", "post_ssm"
            )
            if trajectory == 0:
                canonical.append({
                    "chunk": chunk,
                    "has_initial_state": chunk != 0,
                    **{name: observed[name] for name in comparison_fields},
                })
                mismatched = list(invariant_failures)
            else:
                mismatched = [
                    name for name in comparison_fields
                    if observed[name] != canonical[chunk][name]
                ] + invariant_failures
                mismatched = list(dict.fromkeys(mismatched))
            trajectory_digests.append({
                name: observed[name] for name in comparison_fields
            })
            chunks_executed += 1
            if mismatched:
                first_mismatch = {
                    "trajectory": trajectory,
                    "chunk": chunk,
                    "token_range": [
                        chunk * TOKENS_PER_CHUNK,
                        (chunk + 1) * TOKENS_PER_CHUNK - 1,
                    ],
                    "mismatched_fields": mismatched,
                    "classification": classify_mismatch(mismatched),
                    "has_initial_state": chunk != 0,
                    "observed": observed,
                    "reference": (
                        canonical[chunk] if trajectory != 0 else None
                    ),
                }
                break
        serialized = json.dumps(
            trajectory_digests, sort_keys=True, separators=(",", ":")
        ).encode()
        trajectory_results.append({
            "trajectory": trajectory,
            "chunks_executed": chunks_executed,
            "passed": first_mismatch is None,
            "trajectory_digest": hashlib.sha256(serialized).hexdigest(),
        })
        if first_mismatch is not None:
            break

    replay = None
    if first_mismatch is not None and canonical:
        mismatch_chunk = first_mismatch["chunk"]
        if mismatch_chunk < len(canonical_pre_states):
            replay, replay_calls = snapshot_replay(
                torch,
                chunk=mismatch_chunk,
                fixture=fixture,
                canonical_pre_conv=canonical_pre_states[mismatch_chunk][0],
                canonical_pre_ssm=canonical_pre_states[mismatch_chunk][1],
                canonical=canonical[mismatch_chunk],
                query_start=query_start,
                state_index=state_index,
                has_initial_false=has_initial_false,
                has_initial_true=has_initial_true,
            )
            native_calls += replay_calls

    source_after = {
        name: tensor_digest(torch, tensor) for name, tensor in fixture.items()
    }
    source_immutable = source_after == fixture_digests
    metadata_after = {
        "query_start": tensor_digest(torch, query_start),
        "state_index": tensor_digest(torch, state_index),
        "has_initial_false": tensor_digest(torch, has_initial_false),
        "has_initial_true": tensor_digest(torch, has_initial_true),
    }
    metadata_immutable = metadata_after == metadata_before
    passed = (
        first_mismatch is None
        and len(trajectory_results) == trajectories
        and all(item["passed"] for item in trajectory_results)
        and source_immutable
        and metadata_immutable
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic": "qwen38-flash-next-exact-shape-gdn-history-replay",
        "status": "pass" if passed else "fail",
        "valid": True,
        "scientific_classification": "bounded-negative" if passed else "positive",
        "mode": args.mode,
        "identity": identity,
        "engagement": engagement,
        "assumptions": {
            "production_shape_and_dtype_exact": True,
            "production_chunk_state_lifecycle_exact": True,
            "production_values_exact": False,
            "synthetic_fixture": True,
            "one_affinity_isolated_B70": True,
            "no_model_load": True,
            "no_server": True,
            "no_collectives": True,
            "no_runtime_source_edit": True,
        },
        "execution": {
            "trajectories_requested": trajectories,
            "trajectories_executed": len(trajectory_results),
            "chunks_per_trajectory": CHUNKS,
            "native_calls": native_calls,
            "complete_cache_reset_each_trajectory": True,
            "synchronize_after_each_chunk": True,
            "base_seed": BASE_SEED,
            "output_sentinels": list(OUTPUT_SENTINELS),
        },
        "fixture_digests": fixture_digests,
        "qkvz_chunk_digests": qkvz_chunk_digests,
        "ba_chunk_digests": ba_chunk_digests,
        "metadata_before": metadata_before,
        "metadata_after": metadata_after,
        "metadata_immutable": metadata_immutable,
        "source_after": source_after,
        "source_immutable": source_immutable,
        "canonical_chunks": canonical,
        "trajectory_results": trajectory_results,
        "first_mismatch": first_mismatch,
        "snapshot_replay": replay,
        "summary": {
            "pass_all": passed,
            "all_chunks_exact": first_mismatch is None,
            "source_immutable": source_immutable,
            "metadata_immutable": metadata_immutable,
            "first_mismatch": first_mismatch,
        },
        "interpretation_boundary": (
            "A pass clears only this exact synthetic one-card native shape/history "
            "contract. A production-value fixture or focused model trace remains "
            "required before attributing the endpoint divergence."
        ),
        "postflight_mapped_gdn_library": mapped_gdn_library(),
    }
    atomic_write_json(args.json_out, payload)
    print(json.dumps({
        "json": str(args.json_out),
        "status": payload["status"],
        "mode": args.mode,
        "native_calls": native_calls,
        "first_mismatch": first_mismatch,
    }, sort_keys=True))
    return 0 if passed else 1


def load_result(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ContractError(f"result is not a regular file: {path}")
    payload = json.loads(path.read_text())
    if payload.get("diagnostic") != "qwen38-flash-next-exact-shape-gdn-history-replay":
        raise ContractError(f"not a GDN history replay result: {path}")
    if payload.get("valid") is not True or payload.get("status") != "pass":
        raise ContractError(f"result is not a valid pass: {path}")
    return payload


def execute_compare(args: argparse.Namespace) -> int:
    if len(args.json) < 2:
        raise ContractError("compare requires at least two fresh-process results")
    loaded = [(path.resolve(), load_result(path.resolve())) for path in args.json]
    reference = loaded[0][1]
    binding_fields = (
        "mode", "assumptions", "fixture_digests", "metadata_before",
        "canonical_chunks",
    )
    comparisons = []
    for path, payload in loaded:
        equal = {
            field: payload.get(field) == reference.get(field)
            for field in binding_fields
        }
        identity_equal = (
            payload["identity"]["model"] == reference["identity"]["model"]
            and payload["identity"]["references"]
            == reference["identity"]["references"]
            and payload["identity"]["stage"] == reference["identity"]["stage"]
            and payload["identity"]["shape"] == reference["identity"]["shape"]
            and payload["engagement"] == reference["engagement"]
        )
        comparisons.append({
            "path": str(path),
            "sha256": sha256_file(path),
            "binding_equal": equal,
            "identity_equal": identity_equal,
            "passed": identity_equal and all(equal.values()),
        })
    passed = all(item["passed"] for item in comparisons)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic": "qwen38-flash-next-gdn-history-fresh-process-comparison",
        "status": "pass" if passed else "fail",
        "valid": True,
        "result_count": len(loaded),
        "comparisons": comparisons,
        "summary": {
            "pass_all": passed,
            "all_canonical_chunk_digests_equal": all(
                item["binding_equal"]["canonical_chunks"] for item in comparisons
            ),
        },
    }
    atomic_write_json(args.json_out, payload)
    print(json.dumps({"json": str(args.json_out), "status": payload["status"]}))
    return 0 if passed else 1


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise ContractError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        raise ContractError(f"refusing existing temporary output: {temporary}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight_parser = subparsers.add_parser(
        "preflight", help="validate the complete contract without importing torch"
    )
    preflight_parser.add_argument(
        "--physical-gpu", type=int, choices=range(4), required=True
    )
    run_parser = subparsers.add_parser(
        "run", help="run one affinity-isolated exact-shape raw-op gate"
    )
    run_parser.add_argument(
        "--physical-gpu", type=int, choices=range(4), required=True
    )
    run_parser.add_argument(
        "--mode", choices=tuple(TRAJECTORIES), required=True,
        help="smoke=2 trajectories; qualification=100 trajectories",
    )
    run_parser.add_argument("--json-out", type=Path, required=True)
    compare_parser = subparsers.add_parser(
        "compare", help="compare two or more successful fresh-process results"
    )
    compare_parser.add_argument("--json", type=Path, nargs="+", required=True)
    compare_parser.add_argument("--json-out", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "preflight":
            identity = preflight(args.physical_gpu)
            print(json.dumps({
                "status": "pass",
                "physical_gpu": args.physical_gpu,
                "identity": identity,
            }, sort_keys=True))
            return 0
        if args.command == "run":
            return execute_run(args)
        if args.command == "compare":
            return execute_compare(args)
        raise AssertionError(f"unhandled command: {args.command}")
    except (
        ContractError, OSError, ValueError, KeyError, RuntimeError,
        subprocess.SubprocessError,
    ) as exc:
        print(json.dumps({
            "status": "invalid",
            "valid": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
