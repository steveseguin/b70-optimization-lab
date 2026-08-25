#!/usr/bin/env python3
"""Fail-closed b2dd/1e90 TP1 exact-depth lifecycle and bench adapter.

The public lifecycle interface is inert by default.  ``--execute`` requires an
exact acknowledgement and a clean pushed ``main``.  The same file is supplied
to the frozen strict runner as its benchmark helper; that private adapter runs
all six nonzero exact-depth requests in one already-qualified server.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
SELF = Path(__file__).resolve()
MANIFEST = LANE / "data/2026-08-25-qwen38-b2dd9ce73d-tp1-exact-depth-r1.json"
NOTE = LANE / "notes/2026-08-25-qwen38-b2dd9ce73d-tp1-exact-depth-preregistration.md"
BUILD_RECORD = (
    LANE / "data/2026-08-24-qwen38-b2dd9ce73d-absolute-current-main-build.json"
)
BUILD_NOTE = LANE / "notes/2026-08-24-qwen38-b2dd9ce73d-absolute-current-main-build.md"
COMMON_PATH = LANE / "scripts/run-20260825-qwen38-tp1-parent-sentinel-stage.py"
RUNNER = LANE / "scripts/run-20260823-qwen38-rolling-nightly-strict-smoke.sh"
DEPTH_HELPER = REPO / "scripts/bench-openai-token-depth-suite.py"
FIXTURE = REPO / "data/qwen27-exact-depth/qwen38-bce40ca-exact-depth-v1.json"
MODEL_MANIFEST = REPO / "repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
MODEL_VERIFIER = (
    REPO / "repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
)
QUALITY_HELPER = REPO / "scripts/qwen38-text-quality-suite.py"
PROTECTED_MANIFEST = LANE / "data/2026-08-23-qwen38-current-main-overlay-manifest.json"
BASELINE = Path(
    "/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/"
    "nightly-strict-20260823/"
    "tp1-mtp0-f16-graph-seed0-natural-eos-replay-a-baseline-quality/quality.json"
)

CAMPAIGN_ID = "qwen38-b2dd9ce73d-tp1-exact-depth-20260825-r1"
STAGE_ID = "d1-exact-depths"
ROOT_R1 = Path(
    "/home/steve/qwen38-current-main-runs/"
    "tp1-exact-depth-b2dd9ce73d-20260825-r1/01-exact-depths"
)
CACHE_R1 = Path(
    "/home/steve/qwen38-current-main-runs/"
    "tp1-exact-depth-cache-b2dd9ce73d-20260825-r1/01-exact-depths"
)
PORT_R1 = 20858
DEPTHS = (2048, 4096, 8192, 16384, 24576, 32768)
MAX_MODEL_LEN = 32896
MODEL = "/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan"
MODEL_REVISION = "bce40cacab0a4535b92fb3d57615c2bea9adf3d1"
IMAGE_TAG = "neural-download/vllm-openai-xpu:vllm-b2dd9ce73d-kernel-1e90ffa672-official"
IMAGE_ID = "sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296"
SOURCE_IDENTITY_SHA256 = (
    "2a0ee74968dd68ba15b31eeef3e404807d125e6e52a0e96d25e8b955bd4ae0a0"
)
VLLM_HEAD = "b2dd9ce73dce2ad09007d1db5c171454118981d7"
KERNEL_HEAD = "1e90ffa672ba02f17a909da11838a4c55b199783"
FIXTURE_SHA256 = "ebe507b725af6ec0713de4084d0bf52fbbab48b151511e0019c1bac2c5051bd9"
PROTECTED_VALUES_SHA256 = (
    "e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f"
)


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


COMMON = _load_module("qwen38_exact_depth_common_lifecycle", COMMON_PATH)
DEPTH = _load_module("qwen38_exact_depth_bench", DEPTH_HELPER)
CampaignError = COMMON.CampaignError


DEPENDENCIES = {
    MANIFEST: "85a35f0d33156cfa4c95a43c22291f99bf39576f7c6d95f5d3f0bc9867281aee",
    NOTE: "08eb65b9cb1d236d103cf654a3d18861ac4bbcd69966569539c11c3e792fdd43",
    BUILD_RECORD: "d56dc84c1137d741042b2e295c6b1f6a40bf28a3c56e0c52761dd725e3a5caa0",
    BUILD_NOTE: "64318ac00b4a98f01217ecf0e4ad248da96e3f018738c1fc56368b9ad4a28845",
    COMMON_PATH: "daffc2782871f9499fd09133ee4fa6eb5cd6e626a19204ea1c6361471c6ab351",
    RUNNER: "cb2bfd95e7ad9956dae5bc22ccfa575c8742847c963143291a21505533598202",
    DEPTH_HELPER: "8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067",
    FIXTURE: FIXTURE_SHA256,
    MODEL_MANIFEST: "731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8",
    MODEL_VERIFIER: "5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9",
    QUALITY_HELPER: "67e65fc342393e5ae6903a332c929b3a2693e1f943c8a819b8447284fe835f6d",
    BASELINE: "738b8ed03746ed976c157bf9c392a2637de7c477b719c55f2d533b398adbef18",
    PROTECTED_MANIFEST: "4eb3eeb81e40099a64ba0444743074e6b044295ff566c1abc11d864902abb454",
}

GRAPH_VARIABLES = {
    "XPU_GRAPH",
    "VLLM_XPU_ENABLE_XPU_GRAPH",
    "VLLM_XPU_FORCE_GRAPH_WITH_COMM",
    "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE",
    "COMPILATION_CONFIG",
}


@dataclasses.dataclass(frozen=True)
class Layout:
    output: Path
    cache: Path
    port: int


def sha256_file(path: Path) -> str:
    return COMMON.sha256_file(path)


def load_json(path: Path) -> dict[str, Any]:
    value = COMMON.load_json(path)
    if value is None:
        raise CampaignError(f"invalid or missing JSON: {path}")
    return value


def layout(attempt: int) -> Layout:
    if attempt < 1 or attempt > 99:
        raise CampaignError("attempt must be between 1 and 99")
    suffix = f"r{attempt}"
    output = Path(re.sub(r"r1(?=/)", suffix, str(ROOT_R1), count=1))
    cache = Path(re.sub(r"r1(?=/)", suffix, str(CACHE_R1), count=1))
    port = PORT_R1 + (attempt - 1) * 10
    if port > 65535:
        raise CampaignError("retry port exceeds TCP range")
    return Layout(output, cache, port)


def _require_hash(path: Path, expected: str) -> str:
    if not path.is_file():
        raise CampaignError(f"missing frozen dependency: {path}")
    observed = sha256_file(path)
    if observed != expected:
        raise CampaignError(f"frozen dependency changed: {path} ({observed})")
    return observed


def verify_dependencies() -> dict[str, str]:
    observed = {
        str(path): _require_hash(path, digest) for path, digest in DEPENDENCIES.items()
    }
    manifest = load_json(MANIFEST)
    run = manifest.get("run_identity") or {}
    contract = manifest.get("exact_depth_contract") or {}
    availability = manifest.get("availability") or {}
    if not (
        manifest.get("state") == "preregistered-not-launched"
        and manifest.get("campaign_id") == CAMPAIGN_ID
        and availability.get("execution_state") == "ready-exact-b2dd-image-loaded"
        and run.get("image_tag") == IMAGE_TAG
        and run.get("image_id") == IMAGE_ID
        and run.get("source_identity_sha256") == SOURCE_IDENTITY_SHA256
        and run.get("vllm_head") == VLLM_HEAD
        and run.get("xpu_kernel_head") == KERNEL_HEAD
        and run.get("model_revision") == MODEL_REVISION
        and run.get("tensor_parallel_size") == 1
        and run.get("gpu_affinity") == "0"
        and run.get("mtp_depth") == 0
        and run.get("kv_cache_dtype") == "float16"
        and run.get("graph_mode") == "FULL_AND_PIECEWISE"
        and run.get("max_model_len") == MAX_MODEL_LEN
        and contract.get("fixture_sha256") == FIXTURE_SHA256
        and tuple(contract.get("measured_depths") or ()) == DEPTHS
        and ((contract.get("depth_zero") or {}).get("state_after_campaign"))
        == "missing"
    ):
        raise CampaignError("campaign manifest invariant failed")
    build = load_json(BUILD_RECORD)
    both = (build.get("images") or {}).get("both_current_zero_overlay") or {}
    if not (
        (build.get("vllm") or {}).get("head") == VLLM_HEAD
        and (build.get("kernel") or {}).get("head") == KERNEL_HEAD
        and both.get("tag") == IMAGE_TAG
        and both.get("image_id") == IMAGE_ID
        and both.get("static_preflight_passed") is True
    ):
        raise CampaignError("b2dd both-current build record identity changed")
    model = load_json(MODEL_MANIFEST)
    if not (
        model.get("repository") == "devan-carlin/Qwen3.8-27B-int4-AutoRound"
        and model.get("revision") == MODEL_REVISION
        and ((model.get("identity") or {}).get("quantization"))
        == "AutoRound INT4 W4A16"
    ):
        raise CampaignError("model manifest identity changed")
    protected = load_json(PROTECTED_MANIFEST)
    canonical = (
        json.dumps(
            protected.get("protected_target_only_decode_tok_s"),
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    if hashlib.sha256(canonical.encode()).hexdigest() != PROTECTED_VALUES_SHA256:
        raise CampaignError("protected historical speed ledger changed")
    return observed


def stage_environment() -> dict[str, str]:
    env = os.environ.copy()
    for variable in GRAPH_VARIABLES | {
        "EXTRA_VLLM_ARGS",
        "EXTRA_VLLM_ARGS_JSON",
        "QUALITY_BASELINE_JSON",
        "QUALITY_HELPER_PATH",
        "QUALITY_REQUIRE_BASELINE",
        "BENCH_HELPER_PATH",
        "PROMPT_IDS",
        "CACHE_POLICY",
        "EXPECTED_CACHE_MANIFEST_SHA256",
    }:
        env.pop(variable, None)
    extra = [
        "--pipeline-parallel-size",
        "1",
        "--data-parallel-size",
        "1",
        "--enable-chunked-prefill",
        "--async-scheduling",
        "--compilation-config",
        '{"cudagraph_mode":"FULL_AND_PIECEWISE","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2}',
    ]
    env.update(
        {
            "SOURCE_IMAGE_REPOSITORY": "neural-download/vllm-openai-xpu",
            "SOURCE_IMAGE_TAG": IMAGE_TAG,
            "PULL_SOURCE_IMAGE": "0",
            "EXPECTED_RESOLVED_IMAGE_DIGEST": IMAGE_ID,
            "EXPECTED_IMAGE_ID": IMAGE_ID,
            "SOURCE_IDENTITY_PATH": "/opt/neural-download/source-identity.json",
            "EXPECTED_SOURCE_IDENTITY_SHA256": SOURCE_IDENTITY_SHA256,
            "GPU_MEM_UTIL": "0.90",
            "PYTHONHASHSEED": "0",
            "VLLM_XPU_GRAPH": "1",
            "REQUIRE_GRAPH_CAPTURE": "1",
            "RETURN_TOKEN_IDS": "1",
            "CANARY": "1",
            "CACHE_POLICY": "fresh",
            "MAX_TOKENS": "128",
            "BENCH": "1",
            "NATURAL_EOS": "0",
            "BENCH_HELPER_PATH": str(SELF),
            "QUALITY": "1",
            "QUALITY_HELPER_PATH": str(QUALITY_HELPER),
            "QUALITY_REQUIRE_BASELINE": "1",
            "QUALITY_BASELINE_JSON": str(BASELINE),
            "EXTRA_VLLM_ARGS_JSON": json.dumps(extra, separators=(",", ":")),
            "SUDO_PASS_FILE": os.environ.get(
                "SUDO_PASS_FILE", "/home/steve/SUDOPASSWORD.txt"
            ),
        }
    )
    return env


def ensure_idle(run: Layout) -> None:
    if run.output.exists() or run.cache.exists():
        raise CampaignError(
            f"fresh output/cache already exists: {run.output} or {run.cache}"
        )
    for label, parent in (("output", run.output.parent), ("cache", run.cache.parent)):
        existing = COMMON.nearest_existing(parent)
        fstype = COMMON.require_ok(
            COMMON.command(["findmnt", "-n", "-o", "FSTYPE", "-T", str(existing)]),
            f"{label} filesystem",
        )
        if fstype != "ext4":
            raise CampaignError(f"{label} root must be on ext4, got {fstype}")
    containers = COMMON.require_ok(COMMON.docker_command(["ps", "-q"]), "Docker scan")
    if containers:
        raise CampaignError("a Docker container is already running")
    listener = COMMON.command(["ss", "-ltnH", "sport", "=", f":{run.port}"])
    if listener.returncode != 0 or listener.stdout.strip():
        raise CampaignError(f"port {run.port} scan failed or is occupied")
    processes = COMMON.command(
        ["pgrep", "-af", r"[E]ngineCore|[v]llm serve|[l]lama-server"]
    )
    if processes.returncode not in (0, 1):
        raise CampaignError("model-process scan failed")
    if processes.returncode == 0 and processes.stdout.strip():
        raise CampaignError("a model server process is already running")
    if COMMON.render_users():
        raise CampaignError("a process already owns a render node")


def verify_local_image_available() -> None:
    """Fail before creating a run root unless the exact b2dd image is loaded."""
    result = COMMON.docker_command(
        ["image", "inspect", "--format", "{{.Id}}", IMAGE_TAG]
    )
    if result.returncode != 0:
        raise CampaignError(
            "exact b2dd both-current image is unavailable; restore its pinned "
            "bundle/tag before using this packet"
        )
    observed = result.stdout.strip()
    if observed != IMAGE_ID:
        raise CampaignError(
            f"b2dd image tag resolves to the wrong image ID: {observed or 'empty'}"
        )


def _identity_env(output: Path) -> dict[str, str]:
    path = output / "identity.env"
    if not path.is_file():
        raise CampaignError("run identity.env is missing")
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def verify_exact_run_identity(
    output: Path, *, launch_head: str, expected_cache: Path
) -> dict[str, Any]:
    identity = _identity_env(output)
    expected_extra = json.dumps(
        [
            "--pipeline-parallel-size",
            "1",
            "--data-parallel-size",
            "1",
            "--enable-chunked-prefill",
            "--async-scheduling",
            "--compilation-config",
            '{"cudagraph_mode":"FULL_AND_PIECEWISE","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2}',
        ],
        separators=(",", ":"),
    )
    expected = {
        "lab_git_head": launch_head,
        "tp": "1",
        "gpus": "0",
        "mtp": "0",
        "kv": "f16",
        "max_model_len": str(MAX_MODEL_LEN),
        "gpu_memory_utilization": "0.90",
        "cache_policy": "fresh",
        "cache_dir": str(expected_cache),
        "pull_source_image": "0",
        "source_image_tag": IMAGE_TAG,
        "source_image_repository": "neural-download/vllm-openai-xpu",
        "expected_image_id": IMAGE_ID,
        "tag_image_id": IMAGE_ID,
        "resolved_image_id": IMAGE_ID,
        "registry_digest": IMAGE_ID,
        "source_identity_path": "/opt/neural-download/source-identity.json",
        "expected_source_identity_sha256": SOURCE_IDENTITY_SHA256,
        "vllm_xpu_graph": "1",
        "require_graph_capture": "1",
        "pythonhashseed": "0",
        "natural_eos": "0",
        "return_token_ids": "1",
        "quality": "1",
        "quality_require_baseline": "1",
        "quality_baseline_json": str(BASELINE),
        "quality_baseline_sha256": DEPENDENCIES[BASELINE],
        "prompt_ids": "all",
        "extra_vllm_args_json": expected_extra,
    }
    mismatches = {
        key: {"expected": value, "observed": identity.get(key)}
        for key, value in expected.items()
        if identity.get(key) != value
    }
    if mismatches:
        raise CampaignError(f"exact run identity mismatch: {mismatches}")
    if (output / "image-id.txt").read_text(encoding="utf-8").strip() != IMAGE_ID:
        raise CampaignError("run image ID mismatch")
    source_path = output / "source-identity.json"
    if sha256_file(source_path) != SOURCE_IDENTITY_SHA256:
        raise CampaignError("embedded source identity hash mismatch")
    source = load_json(source_path)
    if (source.get("vllm") or {}).get("head") != VLLM_HEAD:
        raise CampaignError("embedded vLLM source head mismatch")
    if (source.get("kernel") or {}).get("head") != KERNEL_HEAD:
        raise CampaignError("embedded XPU-kernel source head mismatch")
    args = (output / "server-args.txt").read_text(encoding="utf-8").splitlines()
    expected_args = [
        MODEL,
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--trust-remote-code",
        "--served-model-name",
        "qwen38-rolling-nightly-strict",
        "--tensor-parallel-size",
        "1",
        "--max-model-len",
        str(MAX_MODEL_LEN),
        "--max-num-seqs",
        "1",
        "--max-num-batched-tokens",
        "1024",
        "--gpu-memory-utilization",
        "0.90",
        "--dtype",
        "float16",
        "--reasoning-parser",
        "qwen3",
        "--default-chat-template-kwargs",
        '{"enable_thinking": false}',
        "--enable-prompt-tokens-details",
        "--no-enable-prefix-caching",
        "--pipeline-parallel-size",
        "1",
        "--data-parallel-size",
        "1",
        "--enable-chunked-prefill",
        "--async-scheduling",
        "--compilation-config",
        '{"cudagraph_mode":"FULL_AND_PIECEWISE","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2}',
    ]
    if args != expected_args:
        raise CampaignError("server argument vector differs from preregistration")
    recorded: dict[str, str] = {}
    for line in (
        (output / "input-files.sha256").read_text(encoding="utf-8").splitlines()
    ):
        digest, separator, path = line.partition("  ")
        if not separator:
            raise CampaignError("invalid run input hash line")
        recorded[path] = digest
    expected_inputs = {
        str(MODEL_MANIFEST): DEPENDENCIES[MODEL_MANIFEST],
        str(FIXTURE): FIXTURE_SHA256,
        str(SELF): sha256_file(SELF),
        str(QUALITY_HELPER): DEPENDENCIES[QUALITY_HELPER],
        str(MODEL_VERIFIER): DEPENDENCIES[MODEL_VERIFIER],
        str(RUNNER): DEPENDENCIES[RUNNER],
    }
    if recorded != expected_inputs:
        raise CampaignError("strict runner input manifest differs from frozen inputs")
    return {
        "passed": True,
        "image_id": IMAGE_ID,
        "vllm_head": VLLM_HEAD,
        "xpu_kernel_head": KERNEL_HEAD,
        "model_revision": MODEL_REVISION,
        "tp": 1,
        "gpu": 0,
        "mtp_depth": 0,
        "kv_cache_dtype": "float16",
        "graph_mode": "FULL_AND_PIECEWISE",
        "max_model_len": MAX_MODEL_LEN,
    }


def graph_capture_gate(output: Path) -> dict[str, Any]:
    path = output / "server-startup.log"
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    markers = {
        "quantization_inc": "quantization=inc",
        "engine_not_eager": "enforce_eager=False",
        "piecewise_capture": "Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)",
        "full_decode_capture": "Capturing CUDA graphs (decode, FULL)",
        "capture_finished": "Graph capturing finished",
    }
    checks = {key: value in text for key, value in markers.items()}
    return {"passed": all(checks.values()), "checks": checks}


def exact_depth_gate(output: Path) -> dict[str, Any]:
    aggregate = load_json(output / "bench.json")
    rows = aggregate.get("depth_receipts")
    if not isinstance(rows, list):
        return {"passed": False, "reason": "aggregate depth receipts missing"}
    by_depth = {row.get("depth"): row for row in rows if isinstance(row, dict)}
    passed_depths = [
        depth
        for depth in DEPTHS
        if (by_depth.get(depth) or {}).get("gate_passed") is True
    ]
    passed = (
        aggregate.get("schema") == "neural.download.qwen38-exact-depth-battery.v1"
        and aggregate.get("fixture_sha256") == FIXTURE_SHA256
        and aggregate.get("configured_context_capacity") == MAX_MODEL_LEN
        and aggregate.get("one_server") is True
        and aggregate.get("depth_zero_state") == "missing"
        and tuple(by_depth) == DEPTHS
        and passed_depths == list(DEPTHS)
        and aggregate.get("status") == "passed"
    )
    return {
        "passed": passed,
        "expected_depths": list(DEPTHS),
        "passed_depths": passed_depths,
        "depth_zero_state": aggregate.get("depth_zero_state"),
        "rows": rows,
    }


def evidence_hashes(output: Path) -> dict[str, str]:
    names = [
        "bench.json",
        "canary.json",
        "quality.json",
        "metrics.before.prom",
        "metrics.after.prom",
        "server-startup.log",
        "final.status",
        "input-files.sha256",
        "cache-manifest.post.sha256",
    ]
    return {
        name: sha256_file(output / name) for name in names if (output / name).is_file()
    }


def evaluate(
    output: Path,
    runner_rc: int,
    *,
    launch_head: str,
    expected_cache: Path,
) -> tuple[str, dict[str, Any]]:
    gates: dict[str, Any] = {
        "runner_return_code": runner_rc,
        "speed_gate_applied": False,
        "historical_speed_replacement_allowed": False,
    }
    canary = COMMON.load_json(output / "canary.json")
    gates["canary"] = bool(
        canary and canary.get("content") == "14" and canary.get("cached_tokens") == 0
    )
    gates["runner_final_pass"] = bool(
        (output / "final.status").is_file()
        and (output / "final.status").read_text(encoding="utf-8").strip() == "pass"
    )
    try:
        gates["exact_run_identity"] = verify_exact_run_identity(
            output, launch_head=launch_head, expected_cache=expected_cache
        )
    except (CampaignError, OSError, json.JSONDecodeError) as exc:
        gates["exact_run_identity"] = {"passed": False, "error": str(exc)}
    try:
        gates["exact_depth_battery"] = exact_depth_gate(output)
    except (CampaignError, OSError, json.JSONDecodeError) as exc:
        gates["exact_depth_battery"] = {"passed": False, "error": str(exc)}
    quality_passed, quality = COMMON.full_quality_passes(
        COMMON.load_json(output / "quality.json")
    )
    gates["quality"] = quality | {"passed": quality_passed}
    gates["graph_capture"] = graph_capture_gate(output)
    passed = (
        gates["runner_return_code"] == 0
        and gates["runner_final_pass"]
        and gates["canary"]
        and gates["exact_run_identity"].get("passed") is True
        and gates["exact_depth_battery"].get("passed") is True
        and gates["quality"].get("passed") is True
        and gates["graph_capture"].get("passed") is True
    )
    return ("passed" if passed else "quarantined"), gates


def atomic_receipt(output: Path, receipt: dict[str, Any]) -> Path:
    destination = output / "stage-receipt.json"
    if destination.exists():
        raise CampaignError(f"refusing to overwrite receipt: {destination}")
    temporary = output / f".stage-receipt.{os.getpid()}.tmp"
    temporary.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(destination)
    return destination


def execute(attempt: int, acknowledgement: str) -> int:
    expected_ack = f"RUN {CAMPAIGN_ID} {STAGE_ID} r{attempt}"
    if acknowledgement != expected_ack:
        raise CampaignError(f"exact acknowledgement required: {expected_ack}")
    dependencies = verify_dependencies()
    run = layout(attempt)
    env = stage_environment()
    args = [
        str(RUNNER),
        "0",
        "f16",
        str(MAX_MODEL_LEN),
        "0",
        str(run.port),
        str(run.output),
        str(FIXTURE),
        str(run.cache),
    ]
    runner_rc = 125
    cleanup_passed = False
    with COMMON.campaign_locks():
        launch_head = COMMON.git_clean_pushed_main()
        verify_local_image_available()
        ensure_idle(run)
        runner_rc = subprocess.run(args, cwd=REPO, env=env, check=False).returncode
        try:
            COMMON.ensure_post_cleanup(run.port)
            cleanup_passed = True
        except CampaignError:
            cleanup_passed = False
    if not run.output.is_dir():
        raise CampaignError(f"strict runner did not create output: {run.output}")
    state, gates = evaluate(
        run.output,
        runner_rc,
        launch_head=launch_head,
        expected_cache=run.cache,
    )
    gates["post_cleanup_passed"] = cleanup_passed
    if not cleanup_passed:
        state = "quarantined"
    try:
        git_state = COMMON.git_post_run_snapshot(launch_head)
    except CampaignError as exc:
        git_state = {
            "launch_head": launch_head,
            "local_lab_unchanged": False,
            "post_run_check_error": str(exc),
            "remote_movement_is_non_gating_after_launch": True,
        }
    gates["local_lab_unchanged"] = git_state.get("local_lab_unchanged") is True
    gates["live_origin_advanced_during_stage"] = git_state.get(
        "live_origin_advanced_during_stage"
    )
    if not gates["local_lab_unchanged"]:
        state = "quarantined"
    receipt = {
        "schema": "neural.download.qwen38-tp1-exact-depth-stage-receipt.v1",
        "campaign_id": CAMPAIGN_ID,
        "stage_id": STAGE_ID,
        "attempt": attempt,
        "state": state,
        "terminal": True,
        "receipt_complete": True,
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "output": str(run.output),
        "cache": str(run.cache),
        "port": run.port,
        "lab_git_head": launch_head,
        "git_state": git_state,
        "gates": gates,
        "evidence_sha256": evidence_hashes(run.output),
        "frozen_dependency_sha256": dependencies,
        "launcher_sha256_at_launch": sha256_file(SELF),
        "context_semantics": {
            "measured_nonzero_depths": (
                gates.get("exact_depth_battery", {}).get("passed_depths") or []
            ),
            "depth_zero_state": "missing",
            "configured_capacity_is_not_active_context": True,
            "quality_workloads_fill_no_exact_context_cell": True,
        },
        "protected_speed_evidence": {
            "manifest_sha256": DEPENDENCIES[PROTECTED_MANIFEST],
            "canonical_values_sha256": PROTECTED_VALUES_SHA256,
            "historical_b2dd_values_are_immutable": True,
            "speed_floor": None,
            "speed_was_not_a_correctness_gate": True,
            "this_profile_replaces_no_historical_result": True,
        },
        "next_action": (
            "Publish six measured b2dd-profile exact-context cells; depth zero remains missing"
            if state == "passed"
            else "Preserve this terminal attempt; publish only individually passed depth receipts and use a fresh rN for any retry"
        ),
    }
    destination = atomic_receipt(run.output, receipt)
    print(
        json.dumps(
            {
                "campaign_id": CAMPAIGN_ID,
                "stage": STAGE_ID,
                "attempt": attempt,
                "state": state,
                "terminal": True,
                "receipt": str(destination),
            },
            sort_keys=True,
        )
    )
    return 0 if state == "passed" else 20


def plan_payload(attempt: int) -> dict[str, Any]:
    run = layout(attempt)
    return {
        "campaign_id": CAMPAIGN_ID,
        "stage_id": STAGE_ID,
        "attempt": attempt,
        "state": "preregistered-not-launched",
        "runtime_availability": "ready-exact-b2dd-image-loaded",
        "static_check_does_not_prove_runtime_readiness": True,
        "default_is_inert": True,
        "server_count": 1,
        "depths": list(DEPTHS),
        "depth_zero_state": "missing",
        "output": str(run.output),
        "cache": str(run.cache),
        "port": run.port,
        "ack": f"RUN {CAMPAIGN_ID} {STAGE_ID} r{attempt}",
        "speed_floor": None,
        "historical_b2dd_values_are_immutable": True,
    }


def lifecycle_main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="validate only")
    actions.add_argument("--plan", action="store_true", help="render an inert plan")
    actions.add_argument("--execute", action="store_true", help="run the GPU stage")
    parser.add_argument("--stage", choices=(STAGE_ID,))
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--ack", default="")
    args = parser.parse_args(argv)
    if not (args.check or args.plan or args.execute):
        parser.print_help()
        return 0
    if args.check:
        dependencies = verify_dependencies()
        print(
            json.dumps(
                {
                    "campaign_id": CAMPAIGN_ID,
                    "status": "PASS",
                    "launch_performed": False,
                    "dependencies": dependencies,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.plan:
        print(json.dumps(plan_payload(args.attempt), indent=2, sort_keys=True))
        return 0
    if args.stage != STAGE_ID:
        parser.error(f"--execute requires --stage {STAGE_ID}")
    return execute(args.attempt, args.ack)


def _helper_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-mode", required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, required=True)
    parser.add_argument("--metric-tokens", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--timeout", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--return-token-ids", action="store_true")
    parser.add_argument("--request-extra-json", required=True)
    parser.add_argument("--prompt-id", action="append", default=[])
    return parser


def validate_helper_args(args: argparse.Namespace) -> None:
    expected_extra = {
        "chat_template_kwargs": {"enable_thinking": False},
        "ignore_eos": True,
    }
    try:
        extra = json.loads(args.request_extra_json)
    except json.JSONDecodeError as exc:
        raise CampaignError("benchmark request-extra JSON is invalid") from exc
    if not (
        args.api_mode == "chat"
        and args.suite.resolve() == FIXTURE
        and sha256_file(args.suite) == FIXTURE_SHA256
        and args.max_tokens == 128
        and args.metric_tokens == 100
        and args.seed == 1
        and args.return_token_ids is True
        and not args.prompt_id
        and extra == expected_extra
    ):
        raise CampaignError(
            "strict runner invoked exact-depth adapter with wrong identity"
        )


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise CampaignError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def bench_helper_main(argv: list[str]) -> int:
    args = _helper_parser().parse_args(argv)
    validate_helper_args(args)
    if args.out.exists():
        raise CampaignError(f"refusing to overwrite aggregate: {args.out}")
    detail_dir = args.out.parent / "exact-depth"
    if detail_dir.exists():
        raise CampaignError(
            f"refusing existing exact-depth detail directory: {detail_dir}"
        )
    detail_dir.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    for depth in DEPTHS:
        row: dict[str, Any] = {
            "depth": depth,
            "case_id": f"depth-{depth}",
            "gate_passed": False,
        }
        destination = detail_dir / f"depth-{depth}.json"
        try:
            fixture = DEPTH.load_fixture(FIXTURE, depth, f"depth-{depth}")
            payload = DEPTH.request_payload(
                model=args.model,
                prompt_token_ids=fixture.selected.prompt_token_ids,
                adapter="vllm",
            )
            response = DEPTH.post_stream(
                base_url=args.base_url,
                payload=payload,
                timeout=args.timeout,
                requested_adapter="vllm",
                request_id=f"{CAMPAIGN_ID}-depth-{depth}",
            )
            receipt_args = SimpleNamespace(
                base_url=args.base_url,
                model=args.model,
                response_adapter="vllm",
                context_capacity=MAX_MODEL_LEN,
            )
            receipt = DEPTH.build_receipt(
                args=receipt_args,
                fixture=fixture,
                payload=payload,
                row=response,
            )
            _atomic_json(destination, receipt)
            row.update(
                {
                    "gate_passed": (receipt.get("gate") or {}).get("passed") is True,
                    "receipt": str(destination),
                    "receipt_sha256": sha256_file(destination),
                    "fixture_case_sha256": (receipt.get("fixture") or {}).get(
                        "selected_case_sha256"
                    ),
                    "prompt_token_ids_sha256": (receipt.get("fixture") or {}).get(
                        "prompt_token_ids_sha256"
                    ),
                    "metric_window": receipt.get("metric_window"),
                    "response": receipt.get("response"),
                }
            )
        except (OSError, ValueError, RuntimeError, CampaignError) as exc:
            failure = {
                "schema": "neural.download.qwen38-exact-depth-failure.v1",
                "depth": depth,
                "status": "failed",
                "error": str(exc),
            }
            _atomic_json(destination, failure)
            row.update(
                {
                    "error": str(exc),
                    "receipt": str(destination),
                    "receipt_sha256": sha256_file(destination),
                }
            )
        rows.append(row)
    passed_depths = [row["depth"] for row in rows if row["gate_passed"]]
    aggregate = {
        "schema": "neural.download.qwen38-exact-depth-battery.v1",
        "campaign_id": CAMPAIGN_ID,
        "stage_id": STAGE_ID,
        "status": "passed" if passed_depths == list(DEPTHS) else "failed",
        "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "one_server": True,
        "server_base_url": args.base_url,
        "model_alias": args.model,
        "fixture": str(FIXTURE),
        "fixture_sha256": FIXTURE_SHA256,
        "configured_context_capacity": MAX_MODEL_LEN,
        "expected_depths": list(DEPTHS),
        "passed_depths": passed_depths,
        "depth_zero_state": "missing",
        "depth_zero_reason": "empty fixture input is outside the OpenAI-compatible measurement contract",
        "output_tokens_per_depth": 128,
        "metric_events": 100,
        "metric_intervals": 99,
        "speed_floor": None,
        "depth_receipts": rows,
    }
    _atomic_json(args.out, aggregate)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 0 if aggregate["status"] == "passed" else 2


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    # The frozen strict runner invokes this file with its benchmark-helper
    # shape. That path is private to an already executing lifecycle stage.
    if "--suite" in values and "--base-url" in values and "--out" in values:
        return bench_helper_main(values)
    return lifecycle_main(values)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CampaignError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
