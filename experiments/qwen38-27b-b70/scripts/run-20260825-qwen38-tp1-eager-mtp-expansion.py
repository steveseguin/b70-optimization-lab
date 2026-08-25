#!/usr/bin/env python3
"""Fail-closed launcher for the two-stage eager-MTP TP1 expansion.

Default invocation is inert.  ``--execute`` requires an exact acknowledgement,
clean pushed local/live main, immutable inputs and parent evidence, a fresh ext4
root/cache/port, and idle GPU/runtime state.  The strict server mechanics remain
delegated to the frozen rolling-image runner.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-25-qwen38-b2dd9ce73d-tp1-eager-mtp-expansion-r1.json"
NOTE = LANE / "notes/2026-08-25-qwen38-b2dd9ce73d-tp1-eager-mtp-expansion-preregistration.md"
PARENT_RESULT = LANE / "data/2026-08-25-qwen38-b2dd9ce73d-tp1-eager-mtp2-parent-r1.json"
PARENT_NOTE = LANE / "notes/2026-08-25-qwen38-b2dd9ce73d-tp1-eager-mtp2-parent-r1.md"
COMMON_PATH = LANE / "scripts/run-20260825-qwen38-tp1-parent-sentinel-stage.py"
RUNNER = LANE / "scripts/run-20260823-qwen38-rolling-nightly-strict-smoke.sh"
SHORT_SUITE = REPO / "patches/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-20260817/validation-suite.json"
BASELINE = Path("/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp1-mtp0-f16-graph-seed0-natural-eos-replay-a-baseline-quality/quality.json")
CONTROL_ROOT = Path("/home/steve/qwen38-current-main-runs/tp1-parent-sentinels-b2dd9ce73d-20260825-r1/02-eager-control/full-short")
P3_ROOT = Path("/home/steve/qwen38-current-main-runs/tp1-parent-sentinels-b2dd9ce73d-20260825-r1/03-eager-mtp2/sensitive-screen")

CAMPAIGN_ID = "qwen38-b2dd9ce73d-tp1-eager-mtp-expansion-20260825-r1"
ROOT_R1 = Path("/home/steve/qwen38-current-main-runs/tp1-eager-mtp-expansion-b2dd9ce73d-20260825-r1")
CACHE_R1 = Path("/home/steve/qwen38-current-main-runs/tp1-eager-mtp-expansion-cache-b2dd9ce73d-20260825-r1")
IMAGE_ID = "sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296"
SOURCE_IDENTITY_SHA256 = "2a0ee74968dd68ba15b31eeef3e404807d125e6e52a0e96d25e8b955bd4ae0a0"
VLLM_HEAD = "b2dd9ce73dce2ad09007d1db5c171454118981d7"
KERNEL_HEAD = "1e90ffa672ba02f17a909da11838a4c55b199783"
MODEL = "/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan"
MANIFEST_SHA256 = "1e219d1a9f560efe6d82a0b9ec419b6098af8d4c9e66e6d2fc54ccdcc45425b9"
PROTECTED_MANIFEST_SHA256 = "4eb3eeb81e40099a64ba0444743074e6b044295ff566c1abc11d864902abb454"
PROTECTED_VALUES_SHA256 = "e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f"


def _load_common() -> Any:
    spec = importlib.util.spec_from_file_location("qwen38_tp1_parent_common", COMMON_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {COMMON_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


COMMON = _load_common()
CampaignError = COMMON.CampaignError


@dataclasses.dataclass(frozen=True)
class ExpansionStage:
    stage_id: str
    rank: int
    mtp: int
    directory: str
    cache_directory: str
    port_r1: int
    required_stage: str | None


STAGES = {
    "e1-mtp2-full": ExpansionStage(
        "e1-mtp2-full", 1, 2, "01-mtp2-full", "01-mtp2-full", 19856, None
    ),
    "e2-mtp4-full-actual": ExpansionStage(
        "e2-mtp4-full-actual",
        2,
        4,
        "02-mtp4-full-actual",
        "02-mtp4-full-actual",
        19857,
        "e1-mtp2-full",
    ),
}


DEPENDENCIES = {
    MANIFEST: MANIFEST_SHA256,
    NOTE: "48e5ff7bd94ec33b932c12665d3e10e85ffafa158ab4cdee953c940d469b1b81",
    PARENT_RESULT: "4df7d2ee53aa9bbb561d8a8465933a6d80c303d688a79494d7f59d5cd8301186",
    PARENT_NOTE: "41418a9b1bdc882e7817beb957097c67155a707beb38f8dd2a57fe928c333aa8",
    COMMON_PATH: "daffc2782871f9499fd09133ee4fa6eb5cd6e626a19204ea1c6361471c6ab351",
    RUNNER: "cb2bfd95e7ad9956dae5bc22ccfa575c8742847c963143291a21505533598202",
    SHORT_SUITE: "292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c",
    BASELINE: "738b8ed03746ed976c157bf9c392a2637de7c477b719c55f2d533b398adbef18",
}

PARENT_EVIDENCE = {
    CONTROL_ROOT / "stage-receipt.json": "e4513a9a76ff8c5673a06099c8f1f00ba7b25b60cd0635c6914c1e397495ba86",
    CONTROL_ROOT / "bench.json": "4509e8b085a69b9e82659816aaf324ba06e170b7a85762e419528874ead582ff",
    CONTROL_ROOT / "quality.json": "e3c9279540056e46e8d7cbfe255e837b09c182f747df5134ff7403dbd0ca884b",
    P3_ROOT / "stage-receipt.json": "f7501bced81beefd52bf8b56a44c16be3d9ea861d7695fe884b4ba3b2cbcc14a",
    P3_ROOT / "bench.json": "bab562a946e194826469ebaa7ab9fd0c046ed7f185860db3772da208d5450658",
    P3_ROOT / "metrics.before.prom": "8c70c8002cfbded324bc99105a8bec2dddc926af39a66732862c0046d4fc2452",
    P3_ROOT / "metrics.after.prom": "0fcf348661bd46d559c9da342bce2cfa2605a3796ae8f17eba4d03532ea2aef1",
}


def sha256_file(path: Path) -> str:
    return COMMON.sha256_file(path)


def layout(stage: ExpansionStage, attempt: int) -> tuple[Path, Path, int]:
    if attempt < 1 or attempt > 99:
        raise CampaignError("attempt must be between 1 and 99")
    suffix = f"r{attempt}"
    root = Path(re.sub(r"r1$", suffix, str(ROOT_R1))) / stage.directory
    cache = Path(re.sub(r"r1$", suffix, str(CACHE_R1))) / stage.cache_directory
    port = stage.port_r1 + (attempt - 1) * 10
    if port > 65535:
        raise CampaignError("retry port exceeds TCP range")
    return root, cache, port


def receipt_path(stage: ExpansionStage, attempt: int) -> Path:
    return layout(stage, attempt)[0] / "stage-receipt.json"


def _require_hash(path: Path, expected: str) -> str:
    if not path.is_file():
        raise CampaignError(f"missing frozen input: {path}")
    observed = sha256_file(path)
    if observed != expected:
        raise CampaignError(f"frozen input changed: {path} ({observed})")
    return observed


def _load_json(path: Path) -> dict[str, Any]:
    value = COMMON.load_json(path)
    if value is None:
        raise CampaignError(f"invalid or missing JSON: {path}")
    return value


def verify_parent_evidence() -> dict[str, str]:
    observed = {str(path): _require_hash(path, digest) for path, digest in PARENT_EVIDENCE.items()}
    control = _load_json(CONTROL_ROOT / "stage-receipt.json")
    p3 = _load_json(P3_ROOT / "stage-receipt.json")
    if not (
        control.get("stage_id") == "p2-eager-control"
        and control.get("state") == "passed"
        and control.get("terminal") is True
        and ((control.get("gates") or {}).get("quality") or {}).get("passed") is True
        and ((control.get("gates") or {}).get("benchmark") or {}).get("row_count") == 25
    ):
        raise CampaignError("qualified eager target-control receipt no longer passes")
    p3_gates = p3.get("gates") or {}
    if not (
        p3.get("stage_id") == "p3-eager-mtp2"
        and p3.get("state") == "passed"
        and p3.get("terminal") is True
        and (p3_gates.get("acceptance") or {}).get("passed") is True
        and (p3_gates.get("target_oracle") or {}).get("passed") is True
        and p3_gates.get("speed_gate_applied") is False
    ):
        raise CampaignError("eager-MTP2 sensitive parent no longer passes")
    result = _load_json(PARENT_RESULT)
    if not (
        result.get("classification") == "passed-sensitive-parent"
        and ((result.get("interpretation") or {}).get("full_mtp2_short_battery_eligible") is True)
        and ((result.get("interpretation") or {}).get("one_eager_mtp4_short_actual_eligible_after_full_mtp2_pass") is True)
    ):
        raise CampaignError("tracked MTP2 parent closeout does not unlock expansion")
    return observed


def verify_dependencies() -> dict[str, str]:
    common = COMMON.verify_dependencies()
    observed: dict[str, str] = {}
    for path, digest in DEPENDENCIES.items():
        observed[str(path)] = _require_hash(path, digest)
    manifest = _load_json(MANIFEST)
    stages = manifest.get("stages") or []
    if not (
        manifest.get("state") == "preregistered-not-launched"
        and manifest.get("campaign_id") == CAMPAIGN_ID
        and len(stages) == 2
        and [stage.get("stage_id") for stage in stages]
        == ["e1-mtp2-full", "e2-mtp4-full-actual"]
        and [stage.get("mtp_depth") for stage in stages] == [2, 4]
        and manifest.get("protected_speed_evidence", {}).get("manifest_sha256")
        == PROTECTED_MANIFEST_SHA256
        and manifest.get("protected_speed_evidence", {}).get("canonical_values_sha256")
        == PROTECTED_VALUES_SHA256
    ):
        raise CampaignError("expansion manifest invariant failed")
    observed.update(verify_parent_evidence())
    observed.update({f"parent-common:{key}": value for key, value in common.items()})
    return observed


def verify_stage_order(stage: ExpansionStage, attempt: int) -> None:
    if stage.required_stage is None:
        verify_parent_evidence()
        return
    predecessor = STAGES[stage.required_stage]
    path = receipt_path(predecessor, attempt)
    receipt = _load_json(path)
    gates = receipt.get("gates") or {}
    identity = gates.get("exact_run_identity") or {}
    if not (
        receipt.get("campaign_id") == CAMPAIGN_ID
        and receipt.get("stage_id") == predecessor.stage_id
        and receipt.get("attempt") == attempt
        and receipt.get("state") == "passed"
        and receipt.get("terminal") is True
        and identity.get("mtp_depth") == 2
        and (gates.get("acceptance") or {}).get("passed") is True
        and (gates.get("target_oracle") or {}).get("passed") is True
        and (gates.get("quality") or {}).get("passed") is True
    ):
        raise CampaignError("MTP4 actual requires the same-attempt MTP2 full receipt to pass")


def ensure_idle(stage: ExpansionStage, attempt: int) -> None:
    output, cache, port = layout(stage, attempt)
    if output.exists() or cache.exists():
        raise CampaignError(f"fresh output/cache already exists: {output} or {cache}")
    for label, parent in (("output", output.parent), ("cache", cache.parent)):
        existing = COMMON.nearest_existing(parent)
        fstype = COMMON.require_ok(
            COMMON.command(["findmnt", "-n", "-o", "FSTYPE", "-T", str(existing)]),
            f"{label} filesystem",
        )
        if fstype != "ext4":
            raise CampaignError(f"{label} root must be on ext4, got {fstype}")
    containers = COMMON.require_ok(
        COMMON.docker_command(["ps", "-q"]), "Docker container scan"
    )
    if containers:
        raise CampaignError("a Docker container is already running")
    listeners = COMMON.command(["ss", "-ltnH", "sport", "=", f":{port}"])
    if listeners.returncode != 0 or listeners.stdout.strip():
        raise CampaignError(f"port {port} scan failed or is occupied")
    processes = COMMON.command(
        ["pgrep", "-af", r"[E]ngineCore|[v]llm serve|[l]lama-server"]
    )
    if processes.returncode not in (0, 1):
        raise CampaignError("model-process scan failed")
    if processes.returncode == 0 and processes.stdout.strip():
        raise CampaignError("a model server process is already running")
    if COMMON.render_users():
        raise CampaignError("a process already owns a render node")


def stage_environment(stage: ExpansionStage) -> dict[str, str]:
    shared = COMMON.Stage(
        stage.stage_id,
        stage.rank,
        stage.directory,
        stage.cache_directory,
        stage.mtp,
        "f16",
        False,
        "full",
        stage.port_r1,
    )
    env = COMMON.stage_environment(shared, None)
    if any(variable in env for variable in COMMON.GRAPH_VARIABLES):
        raise CampaignError("graph-off expansion retained a graph variable")
    return env


def _identity_env(output: Path) -> dict[str, str]:
    path = output / "identity.env"
    if not path.is_file():
        raise CampaignError("run identity.env is missing")
    identity: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            identity[key] = value
    return identity


def verify_exact_run_identity(
    stage: ExpansionStage,
    output: Path,
    *,
    launch_head: str | None = None,
    expected_cache: Path | None = None,
) -> dict[str, Any]:
    identity = _identity_env(output)
    expected = {
        "tp": "1",
        "gpus": "0",
        "mtp": str(stage.mtp),
        "kv": "f16",
        "max_model_len": "32768",
        "cache_policy": "fresh",
        "pull_source_image": "0",
        "expected_image_id": IMAGE_ID,
        "resolved_image_id": IMAGE_ID,
        "vllm_xpu_graph": "unset",
        "require_graph_capture": "0",
        "natural_eos": "1",
        "return_token_ids": "1",
        "quality": "1",
        "quality_require_baseline": "1",
        "pythonhashseed": "0",
        "source_image_tag": "neural-download/vllm-openai-xpu:vllm-b2dd9ce73d-kernel-1e90ffa672-official",
        "source_image_repository": "neural-download/vllm-openai-xpu",
        "image_acquisition": "offline-replay",
        "registry_digest": IMAGE_ID,
        "tag_image_id": IMAGE_ID,
        "source_identity_path": "/opt/neural-download/source-identity.json",
        "expected_source_identity_sha256": SOURCE_IDENTITY_SHA256,
        "gpu_memory_utilization": "0.90",
        "prompt_ids": "all",
        "quality_baseline_json": str(BASELINE),
        "extra_vllm_args_json": '["--pipeline-parallel-size","1","--data-parallel-size","1","--enable-chunked-prefill","--async-scheduling"]',
    }
    if launch_head is not None:
        expected["lab_git_head"] = launch_head
    if expected_cache is not None:
        expected["cache_dir"] = str(expected_cache)
    mismatches = {
        key: {"expected": value, "observed": identity.get(key)}
        for key, value in expected.items()
        if identity.get(key) != value
    }
    if mismatches:
        raise CampaignError(f"exact run identity mismatch: {mismatches}")
    if identity.get("quality_baseline_sha256") != DEPENDENCIES[BASELINE]:
        raise CampaignError("quality baseline identity mismatch")
    image_id = (output / "image-id.txt").read_text(encoding="utf-8").strip()
    if image_id != IMAGE_ID:
        raise CampaignError("run image ID mismatch")
    source = _load_json(output / "source-identity.json")
    if sha256_file(output / "source-identity.json") != SOURCE_IDENTITY_SHA256:
        raise CampaignError("run source identity hash mismatch")
    if (source.get("vllm") or {}).get("head") != VLLM_HEAD:
        raise CampaignError("run vLLM source identity mismatch")
    if (source.get("kernel") or {}).get("head") != KERNEL_HEAD:
        raise CampaignError("run XPU-kernel source identity mismatch")

    args = (output / "server-args.txt").read_text(encoding="utf-8").splitlines()
    spec = json.dumps(
        {"method": "qwen3_next_mtp", "num_speculative_tokens": stage.mtp},
        separators=(",", ":"),
    )
    expected_args = [
        MODEL,
        "--host", "0.0.0.0",
        "--port", "8000",
        "--trust-remote-code",
        "--served-model-name", "qwen38-rolling-nightly-strict",
        "--tensor-parallel-size", "1",
        "--max-model-len", "32768",
        "--max-num-seqs", "1",
        "--max-num-batched-tokens", "1024",
        "--gpu-memory-utilization", "0.90",
        "--dtype", "float16",
        "--reasoning-parser", "qwen3",
        "--default-chat-template-kwargs", '{"enable_thinking": false}',
        "--enable-prompt-tokens-details",
        "--no-enable-prefix-caching",
        "--speculative-config", spec,
        "--pipeline-parallel-size", "1",
        "--data-parallel-size", "1",
        "--enable-chunked-prefill",
        "--async-scheduling",
    ]
    if args != expected_args:
        raise CampaignError("server argument vector does not match the frozen expansion identity")

    input_lines = (output / "input-files.sha256").read_text(encoding="utf-8").splitlines()
    recorded_inputs: dict[str, str] = {}
    for line in input_lines:
        digest, separator, path = line.partition("  ")
        if not separator or not path:
            raise CampaignError("run input manifest has an invalid line")
        recorded_inputs[path] = digest
    expected_inputs = {
        str(COMMON.MODEL_MANIFEST): COMMON.DEPENDENCIES[COMMON.MODEL_MANIFEST],
        str(SHORT_SUITE): DEPENDENCIES[SHORT_SUITE],
        str(COMMON.BENCH_HELPER): COMMON.DEPENDENCIES[COMMON.BENCH_HELPER],
        str(COMMON.QUALITY_HELPER): COMMON.DEPENDENCIES[COMMON.QUALITY_HELPER],
        str(COMMON.MODEL_VERIFIER): COMMON.DEPENDENCIES[COMMON.MODEL_VERIFIER],
        str(RUNNER): DEPENDENCIES[RUNNER],
    }
    if recorded_inputs != expected_inputs:
        raise CampaignError("run input manifest does not match the frozen inputs")
    return {
        "passed": True,
        "mtp_depth": stage.mtp,
        "speculative_method": "qwen3_next_mtp",
        "graph_mode": "off",
        "kv_cache_dtype": "f16",
        "tp": 1,
        "image_id": IMAGE_ID,
        "vllm_head": VLLM_HEAD,
        "xpu_kernel_head": KERNEL_HEAD,
    }


def acceptance_gate(output: Path) -> dict[str, Any]:
    metric_draft = "vllm:spec_decode_num_draft_tokens_total"
    metric_accept = "vllm:spec_decode_num_accepted_tokens_total"
    before_draft = COMMON.prometheus_total(output / "metrics.before.prom", metric_draft)
    after_draft = COMMON.prometheus_total(output / "metrics.after.prom", metric_draft)
    before_accept = COMMON.prometheus_total(output / "metrics.before.prom", metric_accept)
    after_accept = COMMON.prometheus_total(output / "metrics.after.prom", metric_accept)
    draft = after_draft - before_draft if None not in (before_draft, after_draft) else None
    accepted = after_accept - before_accept if None not in (before_accept, after_accept) else None
    passed = (
        isinstance(draft, float)
        and isinstance(accepted, float)
        and draft > 0
        and 0 < accepted <= draft
    )
    return {
        "passed": passed,
        "draft_tokens": draft,
        "accepted_tokens": accepted,
        "acceptance_rate": accepted / draft if passed else None,
    }


def target_oracle_gate(output: Path) -> dict[str, Any]:
    suite = _load_json(SHORT_SUITE)
    expected_ids = [prompt["id"] for prompt in suite.get("prompts") or []]
    control = _load_json(CONTROL_ROOT / "bench.json")
    candidate = _load_json(output / "bench.json")
    control_rows = {row.get("prompt_id"): row for row in control.get("rows") or []}
    candidate_rows = {row.get("prompt_id"): row for row in candidate.get("rows") or []}
    expected = set(expected_ids)
    details: dict[str, Any] = {}
    passed = len(expected_ids) == 25 and set(control_rows) == expected and set(candidate_rows) == expected
    for prompt_id in expected_ids:
        control_row = control_rows.get(prompt_id, {})
        candidate_row = candidate_rows.get(prompt_id, {})
        tokens_match = bool(control_row.get("token_ids")) and control_row.get("token_ids") == candidate_row.get("token_ids")
        hashes_match = isinstance(control_row.get("sha256"), str) and control_row.get("sha256") == candidate_row.get("sha256")
        details[prompt_id] = {
            "token_ids_match": tokens_match,
            "output_hash_match": hashes_match,
        }
        passed = passed and tokens_match and hashes_match
    return {
        "passed": passed,
        "expected_prompt_count": 25,
        "candidate_prompt_count": len(candidate_rows),
        "exact_token_id_matches": sum(row["token_ids_match"] for row in details.values()),
        "exact_output_hash_matches": sum(row["output_hash_match"] for row in details.values()),
        "rows": details,
    }


def evaluate(
    stage: ExpansionStage,
    output: Path,
    runner_rc: int,
    *,
    launch_head: str | None = None,
    expected_cache: Path | None = None,
) -> tuple[str, bool, dict[str, Any]]:
    gates: dict[str, Any] = {
        "runner_rc": runner_rc,
        "speed_gate_applied": False,
    }
    canary = COMMON.load_json(output / "canary.json")
    gates["canary"] = bool(
        canary and canary.get("content") == "14" and canary.get("cached_tokens") == 0
    )
    gates["runner_final_pass"] = (
        (output / "final.status").is_file()
        and (output / "final.status").read_text(encoding="utf-8").strip() == "pass"
    )
    try:
        gates["exact_run_identity"] = verify_exact_run_identity(
            stage,
            output,
            launch_head=launch_head,
            expected_cache=expected_cache,
        )
    except (CampaignError, OSError, json.JSONDecodeError) as exc:
        gates["exact_run_identity"] = {"passed": False, "error": str(exc)}
    bench = COMMON.load_json(output / "bench.json")
    bench_gate = (bench or {}).get("realistic_final_gate") or {}
    rows = (bench or {}).get("rows") or []
    gates["benchmark"] = {
        "passed": bench_gate.get("passed") is True and len(rows) == 25,
        "row_count": len(rows),
        "expected_rows": 25,
        "natural_eos_required": bench_gate.get("natural_eos_required"),
        "cached_tokens_all_zero": bench_gate.get("cached_tokens_all_zero"),
    }
    quality_pass, quality = COMMON.full_quality_passes(
        COMMON.load_json(output / "quality.json")
    )
    gates["quality"] = quality | {"passed": quality_pass}
    gates["acceptance"] = acceptance_gate(output)
    try:
        gates["target_oracle"] = target_oracle_gate(output)
    except CampaignError as exc:
        gates["target_oracle"] = {"passed": False, "error": str(exc)}

    passed = (
        gates["runner_final_pass"]
        and gates["canary"]
        and gates["exact_run_identity"].get("passed") is True
        and gates["benchmark"]["passed"]
        and gates["quality"]["passed"]
        and gates["acceptance"]["passed"]
        and gates["target_oracle"]["passed"]
    )
    if passed:
        return "passed", True, gates
    if bench is not None or (output / "quality.json").is_file():
        return "quarantined", True, gates
    return "failed", False, gates


def write_receipt(output: Path, receipt: dict[str, Any]) -> None:
    destination = output / "stage-receipt.json"
    if destination.exists():
        raise CampaignError(f"refusing to overwrite receipt: {destination}")
    temporary = output / f".stage-receipt.{os.getpid()}.tmp"
    temporary.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(destination)


def ensure_single_mtp4_actual() -> None:
    """Permit only the first E2 output/cache across every retry identity."""
    stage = STAGES["e2-mtp4-full-actual"]
    previous = []
    for attempt in range(1, 100):
        output, cache, _ = layout(stage, attempt)
        if output.exists():
            previous.append(str(output))
        if cache.exists():
            previous.append(str(cache))
    if previous:
        raise CampaignError(
            "the one preregistered MTP4 actual already has evidence; "
            f"refusing another launch: {previous}"
        )


def apply_post_git_gate(
    state: str,
    terminal: bool,
    gates: dict[str, Any],
    git_state: dict[str, Any],
) -> tuple[str, bool]:
    """Gate only immutable local state; retain remote movement as evidence."""
    gates["local_lab_unchanged"] = git_state.get("local_lab_unchanged") is True
    gates["live_origin_advanced_during_stage"] = git_state.get(
        "live_origin_advanced_during_stage"
    )
    gates["remote_movement_was_non_gating"] = True
    if not gates["local_lab_unchanged"]:
        return "failed", False
    return state, terminal


def execute(stage: ExpansionStage, attempt: int, acknowledgement: str) -> int:
    expected_ack = f"RUN {CAMPAIGN_ID} {stage.stage_id} r{attempt}"
    if acknowledgement != expected_ack:
        raise CampaignError(f"exact acknowledgement required: {expected_ack}")
    dependencies = verify_dependencies()
    output, cache, port = layout(stage, attempt)
    env = stage_environment(stage)
    args = [
        str(RUNNER),
        str(stage.mtp),
        "f16",
        "32768",
        "0",
        str(port),
        str(output),
        str(SHORT_SUITE),
        str(cache),
    ]
    runner_rc = 125
    cleanup_passed = False
    with COMMON.campaign_locks():
        # These gates must execute while holding the host/GPU locks. In
        # particular, an E2 launcher that waited behind another E2 launcher
        # must rescan every retry root after acquiring the lock; otherwise two
        # concurrent processes could both pass the one-actual precheck.
        launch_head = COMMON.git_clean_pushed_main()
        verify_stage_order(stage, attempt)
        if stage.stage_id == "e2-mtp4-full-actual":
            ensure_single_mtp4_actual()
        ensure_idle(stage, attempt)
        runner_rc = subprocess.run(args, cwd=REPO, env=env, check=False).returncode
        try:
            COMMON.ensure_post_cleanup(port)
            cleanup_passed = True
        except CampaignError:
            cleanup_passed = False
    if not output.is_dir():
        raise CampaignError(f"strict runner did not create its output: {output}")
    state, terminal, gates = evaluate(
        stage,
        output,
        runner_rc,
        launch_head=launch_head,
        expected_cache=cache,
    )
    gates["post_cleanup_passed"] = cleanup_passed
    if not cleanup_passed:
        state, terminal = "failed", False
    try:
        git_state = COMMON.git_post_run_snapshot(launch_head)
    except CampaignError as exc:
        git_state = {
            "launch_head": launch_head,
            "local_lab_unchanged": False,
            "post_run_check_error": str(exc),
            "remote_movement_is_non_gating_after_launch": True,
        }
    state, terminal = apply_post_git_gate(state, terminal, gates, git_state)
    receipt = {
        "schema": "neural.download.qwen38-tp1-eager-mtp-expansion-stage-receipt.v1",
        "campaign_id": CAMPAIGN_ID,
        "stage_id": stage.stage_id,
        "rank": stage.rank,
        "attempt": attempt,
        "state": state,
        "terminal": terminal,
        "output": str(output),
        "cache": str(cache),
        "port": port,
        "lab_git_head": launch_head,
        "git_state": git_state,
        "runner_return_code": runner_rc,
        "gates": gates,
        "frozen_dependency_sha256": dependencies,
        "protected_speed_evidence": {
            "manifest_sha256": PROTECTED_MANIFEST_SHA256,
            "canonical_values_sha256": PROTECTED_VALUES_SHA256,
            "historical_values_are_immutable": True,
            "speed_was_not_a_correctness_gate": True,
        },
        "context_semantics": {
            "short_suite_is_outside_active_context_axis": True,
            "configured_max_context_is_not_active_context": True,
        },
        "next_action": (
            "Run exactly the one preregistered MTP4 actual"
            if stage.stage_id == "e1-mtp2-full" and state == "passed"
            else "Preserve this attempt; do not expand unless its exact prerequisite passed"
        ),
    }
    write_receipt(output, receipt)
    print(
        json.dumps(
            {
                "stage": stage.stage_id,
                "attempt": attempt,
                "state": state,
                "terminal": terminal,
                "receipt": str(output / "stage-receipt.json"),
            },
            sort_keys=True,
        )
    )
    return 0 if state == "passed" else 20 if terminal else 1


def plan_payload(attempt: int) -> dict[str, Any]:
    return {
        "campaign_id": CAMPAIGN_ID,
        "attempt": attempt,
        "state": "preregistered-not-launched",
        "default_is_inert": True,
        "speed_is_not_a_correctness_gate": True,
        "stages": [
            {
                **dataclasses.asdict(stage),
                "output": str(layout(stage, attempt)[0]),
                "cache": str(layout(stage, attempt)[1]),
                "port": layout(stage, attempt)[2],
                "ack": f"RUN {CAMPAIGN_ID} {stage.stage_id} r{attempt}",
            }
            for stage in STAGES.values()
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate only; never launches")
    parser.add_argument("--plan", action="store_true", help="render plan only; never launches")
    parser.add_argument("--execute", action="store_true", help="execute exactly one stage")
    parser.add_argument("--stage", choices=tuple(STAGES))
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--ack", default="")
    args = parser.parse_args()
    selected = sum((args.check, args.plan, args.execute))
    if selected != 1:
        parser.error("choose exactly one of --check, --plan, or --execute")
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
    if not args.stage:
        parser.error("--execute requires --stage")
    return execute(STAGES[args.stage], args.attempt, args.ack)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CampaignError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
