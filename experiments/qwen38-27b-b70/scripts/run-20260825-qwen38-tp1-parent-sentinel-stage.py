#!/usr/bin/env python3
"""Stage-aware fail-closed launcher for the frozen b2dd TP1 parents.

The default action is read-only validation/plan rendering.  A GPU run requires
``--execute``, an exact per-stage acknowledgement, clean pushed ``main``, all
frozen dependency hashes, unused fresh roots, and idle container/port/model/
render state.  Server mechanics remain delegated to the rolling strict runner.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterator


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
CONTRACT = LANE / "data/2026-08-25-qwen38-b2dd9ce73d-tp1-parent-sentinel-campaign.json"
NOTE = LANE / "notes/2026-08-25-qwen38-b2dd9ce73d-tp1-parent-sentinel-preregistration.md"
VALIDATOR = LANE / "scripts/validate-20260825-qwen38-tp1-parent-sentinel-campaign.sh"
RUNNER = LANE / "scripts/run-20260823-qwen38-rolling-nightly-strict-smoke.sh"
BUILDER = LANE / "scripts/build-20260825-qwen38-tp1-context-sentinel-suite.py"
CONTEXT_HELPER = LANE / "scripts/qwen38_tp1_context_gate.py"
CONTEXT_SUITE = LANE / "data/2026-08-25-qwen38-b2dd9ce73d-tp1-context-sentinel-suite.json"
SHORT_SUITE = REPO / "patches/qwen36-27b-autoround-int4-b70/batch-invariant-rmsnorm-20260817/validation-suite.json"
BASELINE = Path("/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/nightly-strict-20260823/tp1-mtp0-f16-graph-seed0-natural-eos-replay-a-baseline-quality/quality.json")
MODEL_MANIFEST = REPO / "repro/qwen38-27b-autoround-int4-b70/manifests/model.json"
MODEL_VERIFIER = REPO / "repro/qwen38-27b-autoround-int4-b70/scripts/verify-model-direct.py"
BENCH_HELPER = REPO / "scripts/bench-openai-realistic-suite.py"
QUALITY_HELPER = REPO / "scripts/qwen38-text-quality-suite.py"
PROTECTED_MANIFEST = LANE / "data/2026-08-23-qwen38-current-main-overlay-manifest.json"

CAMPAIGN_ID = "qwen38-b2dd9ce73d-tp1-parent-sentinels-20260825-r1"
ROOT_R1 = Path("/home/steve/qwen38-current-main-runs/tp1-parent-sentinels-b2dd9ce73d-20260825-r1")
CACHE_R1 = Path("/home/steve/qwen38-current-main-runs/tp1-parent-sentinel-cache-b2dd9ce73d-20260825-r1")
CONTEXT_SUITE_SHA256 = "e8a8a470c8e0a9f6e73460e8d5e01d42d13659faf447e289ca4803c7aa7a683f"
PROTECTED_MANIFEST_SHA256 = "4eb3eeb81e40099a64ba0444743074e6b044295ff566c1abc11d864902abb454"
PROTECTED_VALUES_SHA256 = "e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f"

DEPENDENCIES = {
    CONTRACT: "9a96aa5bf9ebdad2b455e4b3d0c06d5ac2748cefba61a164003a1de560113400",
    NOTE: "8a59eb8108ed0088eb7956ca720205ab0f4bcfe3edb5ed0585d608ba2e2c4c93",
    VALIDATOR: "7dc156a11222a649147270e0217d409d1c953254311c0a69f455233eb4b4cbcd",
    RUNNER: "cb2bfd95e7ad9956dae5bc22ccfa575c8742847c963143291a21505533598202",
    BUILDER: "6c3ed20e1396e9e807a07bf92eadc1b75e81f14ad65228f1f803343804e759ea",
    CONTEXT_HELPER: "9508569ee33a23b250be2c552f288725ad9a8bea5994f9d308f82340a97d69e6",
    CONTEXT_SUITE: CONTEXT_SUITE_SHA256,
    SHORT_SUITE: "292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c",
    BASELINE: "738b8ed03746ed976c157bf9c392a2637de7c477b719c55f2d533b398adbef18",
    MODEL_MANIFEST: "731d851b39d37f3d58c5a74ad6a7cd3ade1c9e8543ef1612a5d55131ff8331b8",
    MODEL_VERIFIER: "5bca853ae644099cb18c58b458dd04dfcc0844d7644f074c4350539504d80ce9",
    BENCH_HELPER: "442e9777d864f94eca82424929d3875ac15a155fd9e510e5054ef199a9751ab4",
    QUALITY_HELPER: "67e65fc342393e5ae6903a332c929b3a2693e1f943c8a819b8447284fe835f6d",
    PROTECTED_MANIFEST: PROTECTED_MANIFEST_SHA256,
}


class CampaignError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class Stage:
    stage_id: str
    rank: int
    directory: str
    cache_directory: str
    mtp: int
    kv: str
    graph: bool
    mode: str
    port_r1: int
    required_stage: str | None = None
    required_state: str | None = None


STAGES = {
    "p1-context-spine": Stage("p1-context-spine", 1, "01-context-spine/sentinel-context", "01-context-spine", 0, "f16", True, "context", 19850),
    "p2-eager-control": Stage("p2-eager-control", 2, "02-eager-control/full-short", "02-eager-control", 0, "f16", False, "full", 19851, "p1-context-spine", "terminal"),
    "p3-eager-mtp2": Stage("p3-eager-mtp2", 3, "03-eager-mtp2/sensitive-screen", "03-eager-mtp2", 2, "f16", False, "sensitive", 19852, "p2-eager-control", "passed"),
    "p4-graph-mtp1": Stage("p4-graph-mtp1", 4, "04-graph-mtp1/sensitive-screen", "04-graph-mtp1", 1, "f16", True, "sensitive", 19853, "p2-eager-control", "passed"),
    "p5-e4m3-kv": Stage("p5-e4m3-kv", 5, "05-e4m3-kv/full-short", "05-e4m3-kv", 0, "fp8_e4m3", False, "full", 19854, "p4-graph-mtp1", "terminal"),
    "p6-e5m2-kv-init": Stage("p6-e5m2-kv-init", 6, "06-e5m2-kv-init/init-canary", "06-e5m2-kv-init", 0, "fp8_e5m2", False, "init", 19855, "p5-e4m3-kv", "terminal"),
}

TERMINAL_STATES = {"passed", "boundary-detected", "quarantined", "unsupported"}
GRAPH_VARIABLES = {
    "XPU_GRAPH",
    "VLLM_XPU_ENABLE_XPU_GRAPH",
    "VLLM_XPU_FORCE_GRAPH_WITH_COMM",
    "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE",
    "COMPILATION_CONFIG",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def command(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True, **kwargs)


def require_ok(result: subprocess.CompletedProcess[str], label: str) -> str:
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise CampaignError(f"{label} failed: {detail}")
    return result.stdout.strip()


def verify_dependencies() -> dict[str, str]:
    actual: dict[str, str] = {}
    for path, expected in DEPENDENCIES.items():
        if not path.is_file():
            raise CampaignError(f"missing frozen dependency: {path}")
        observed = sha256_file(path)
        if observed != expected:
            raise CampaignError(f"frozen dependency changed: {path} ({observed})")
        actual[str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)] = observed
    validator = command([str(VALIDATOR), "--validate"], cwd=REPO)
    require_ok(validator, "campaign static validator")
    protected = json.loads(PROTECTED_MANIFEST.read_text(encoding="utf-8"))
    canonical = json.dumps(
        protected["protected_target_only_decode_tok_s"],
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    observed_values = hashlib.sha256(canonical.encode()).hexdigest()
    if observed_values != PROTECTED_VALUES_SHA256:
        raise CampaignError("protected historical speed ledger changed")
    return actual


def git_clean_pushed_main() -> str:
    status = require_ok(command(["git", "-C", str(REPO), "status", "--porcelain=v1", "--untracked-files=all"]), "git status")
    if status:
        raise CampaignError("lab repository must be clean before execution")
    branch = require_ok(command(["git", "-C", str(REPO), "branch", "--show-current"]), "git branch")
    if branch != "main":
        raise CampaignError("lab repository must be on main")
    head = require_ok(command(["git", "-C", str(REPO), "rev-parse", "HEAD"]), "git HEAD")
    origin = require_ok(command(["git", "-C", str(REPO), "rev-parse", "origin/main"]), "local origin/main")
    if head != origin:
        raise CampaignError("local main must equal origin/main")
    live = require_ok(command(["git", "-C", str(REPO), "ls-remote", "--exit-code", "origin", "refs/heads/main"], timeout=30), "live origin/main").split()[0]
    if live != head:
        raise CampaignError("local main must equal live origin/main")
    return head


def git_post_run_snapshot(launch_head: str) -> dict[str, Any]:
    """Verify the local checkout without making later remote movement gating.

    A live-origin equality check belongs at launch. Once the immutable image,
    inputs, dependencies, and local checkout have passed that gate, unrelated
    commits pushed while a GPU stage is running cannot mutate the active
    process. The transition is still recorded in every receipt.
    """
    status = require_ok(
        command(
            [
                "git",
                "-C",
                str(REPO),
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            ]
        ),
        "post-run git status",
    )
    branch = require_ok(
        command(["git", "-C", str(REPO), "branch", "--show-current"]),
        "post-run git branch",
    )
    head = require_ok(
        command(["git", "-C", str(REPO), "rev-parse", "HEAD"]),
        "post-run git HEAD",
    )
    cached_origin = require_ok(
        command(["git", "-C", str(REPO), "rev-parse", "origin/main"]),
        "post-run cached origin/main",
    )
    live_result = command(
        [
            "git",
            "-C",
            str(REPO),
            "ls-remote",
            "--exit-code",
            "origin",
            "refs/heads/main",
        ],
        timeout=30,
    )
    live_origin = (
        live_result.stdout.strip().split()[0]
        if live_result.returncode == 0 and live_result.stdout.strip()
        else None
    )
    return {
        "launch_head": launch_head,
        "post_run_head": head,
        "post_run_branch": branch,
        "post_run_worktree_clean": not bool(status),
        "cached_origin_main_after": cached_origin,
        "live_origin_main_after": live_origin,
        "local_lab_unchanged": not bool(status)
        and branch == "main"
        and head == launch_head,
        "live_origin_query_passed": live_origin is not None,
        "live_origin_query_error": (
            None
            if live_origin is not None
            else (live_result.stderr.strip() or f"rc={live_result.returncode}")
        ),
        "live_origin_advanced_during_stage": (
            live_origin != launch_head if live_origin is not None else None
        ),
        "remote_movement_is_non_gating_after_launch": True,
    }


def layout(stage: Stage, attempt: int) -> tuple[Path, Path, int]:
    if attempt < 1 or attempt > 99:
        raise CampaignError("attempt must be between 1 and 99")
    suffix = f"r{attempt}"
    root = Path(re.sub(r"r1$", suffix, str(ROOT_R1))) / stage.directory
    cache = Path(re.sub(r"r1$", suffix, str(CACHE_R1))) / stage.cache_directory
    port = stage.port_r1 + (attempt - 1) * 10
    if port > 65535:
        raise CampaignError("retry port exceeds TCP range")
    return root, cache, port


def receipt_path(stage: Stage, attempt: int) -> Path:
    output, _, _ = layout(stage, attempt)
    return output / "stage-receipt.json"


def verify_stage_order(stage: Stage, attempt: int) -> None:
    if stage.required_stage is None:
        return
    predecessor = STAGES[stage.required_stage]
    path = receipt_path(predecessor, attempt)
    if not path.is_file():
        raise CampaignError(f"required predecessor receipt is missing: {path}")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    state = receipt.get("state")
    required = stage.required_state
    if required == "passed" and state != "passed":
        raise CampaignError(f"{stage.stage_id} requires {predecessor.stage_id}=passed, got {state}")
    if required == "terminal" and state not in TERMINAL_STATES:
        raise CampaignError(f"{stage.stage_id} requires a terminal predecessor, got {state}")


def nearest_existing(path: Path) -> Path:
    candidate = path
    while not candidate.exists():
        if candidate.parent == candidate:
            raise CampaignError(f"no existing ancestor for {path}")
        candidate = candidate.parent
    return candidate


def docker_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    direct = command(["docker", *args])
    if direct.returncode == 0:
        return direct
    password_file = Path(os.environ.get("SUDO_PASS_FILE", "/home/steve/SUDOPASSWORD.txt"))
    if not password_file.is_file():
        return direct
    with password_file.open("rb") as stdin:
        return subprocess.run(
            ["sudo", "-S", "-p", "", "docker", *args],
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )


def render_users() -> str:
    devices = sorted(Path("/dev/dri").glob("renderD*"))
    if not devices:
        raise CampaignError("no render devices were found")
    password_file = Path(
        os.environ.get("SUDO_PASS_FILE", "/home/steve/SUDOPASSWORD.txt")
    )
    if not password_file.is_file():
        raise CampaignError("render-node ownership scan requires SUDO_PASS_FILE")
    with password_file.open("rb") as stdin:
        result = subprocess.run(
            ["sudo", "-S", "-p", "", "fuser", "-a", *map(str, devices)],
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    if result.returncode not in (0, 1):
        raise CampaignError("render-node ownership scan failed")
    return result.stdout.strip()


def ensure_idle(stage: Stage, attempt: int) -> None:
    output, cache, port = layout(stage, attempt)
    if output.exists() or cache.exists():
        raise CampaignError(f"fresh output/cache already exists: {output} or {cache}")
    fstype = require_ok(command(["findmnt", "-n", "-o", "FSTYPE", "-T", str(nearest_existing(cache.parent))]), "cache filesystem")
    if fstype != "ext4":
        raise CampaignError(f"cache root must be on ext4, got {fstype}")
    containers = require_ok(docker_command(["ps", "-q"]), "Docker container scan")
    if containers:
        raise CampaignError("a Docker container is already running")
    listeners = command(["ss", "-ltnH", "sport", "=", f":{port}"])
    if listeners.returncode != 0:
        raise CampaignError("port listener scan failed")
    if listeners.stdout.strip():
        raise CampaignError(f"port {port} is already listening")
    processes = command(["pgrep", "-af", r"[E]ngineCore|[v]llm serve|[l]lama-server"])
    if processes.returncode not in (0, 1):
        raise CampaignError("model-process scan failed")
    if processes.returncode == 0 and processes.stdout.strip():
        raise CampaignError("a model server process is already running")
    if render_users():
        raise CampaignError("a process already owns a render node")


@contextlib.contextmanager
def campaign_locks() -> Iterator[None]:
    lock_paths = [
        Path("/run/lock/muse-glimmer-gpu-exclusive.lock"),
        Path("/tmp/b70-benchmark.lock"),
        Path(f"/run/user/{os.getuid()}/qwen36-b70-gpu-leases/gpu0.lock"),
    ]
    handles = []
    try:
        for path in lock_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = path.open("a+")
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise CampaignError(f"campaign lock is held: {path}") from exc
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            handle.close()


def stage_environment(stage: Stage, context_suite: Path | None) -> dict[str, str]:
    env = os.environ.copy()
    for variable in GRAPH_VARIABLES | {
        "EXTRA_VLLM_ARGS",
        "EXTRA_VLLM_ARGS_JSON",
        "QUALITY_BASELINE_JSON",
        "QUALITY_REQUIRE_BASELINE",
        "PROMPT_IDS",
        "BENCH_HELPER_PATH",
        "CACHE_POLICY",
        "EXPECTED_CACHE_MANIFEST_SHA256",
    }:
        env.pop(variable, None)
    env.update(
        {
            "SOURCE_IMAGE_REPOSITORY": "neural-download/vllm-openai-xpu",
            "SOURCE_IMAGE_TAG": "neural-download/vllm-openai-xpu:vllm-b2dd9ce73d-kernel-1e90ffa672-official",
            "PULL_SOURCE_IMAGE": "0",
            "EXPECTED_RESOLVED_IMAGE_DIGEST": "sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296",
            "EXPECTED_IMAGE_ID": "sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296",
            "SOURCE_IDENTITY_PATH": "/opt/neural-download/source-identity.json",
            "EXPECTED_SOURCE_IDENTITY_SHA256": "2a0ee74968dd68ba15b31eeef3e404807d125e6e52a0e96d25e8b955bd4ae0a0",
            "GPU_MEM_UTIL": "0.90",
            "PYTHONHASHSEED": "0",
            "RETURN_TOKEN_IDS": "1",
            "CANARY": "1",
            "CACHE_POLICY": "fresh",
            "SUDO_PASS_FILE": os.environ.get("SUDO_PASS_FILE", "/home/steve/SUDOPASSWORD.txt"),
        }
    )
    extra = [
        "--pipeline-parallel-size", "1",
        "--data-parallel-size", "1",
        "--enable-chunked-prefill",
        "--async-scheduling",
    ]
    if stage.graph:
        env["VLLM_XPU_GRAPH"] = "1"
        env["REQUIRE_GRAPH_CAPTURE"] = "1"
        extra += [
            "--compilation-config",
            '{"cudagraph_mode":"FULL_AND_PIECEWISE","cudagraph_capture_sizes":[1,2],"max_cudagraph_capture_size":2}',
        ]
    else:
        env["REQUIRE_GRAPH_CAPTURE"] = "0"
    env["EXTRA_VLLM_ARGS_JSON"] = json.dumps(extra, separators=(",", ":"))

    if stage.mode == "full":
        env.update({"MAX_TOKENS": "512", "BENCH": "1", "NATURAL_EOS": "1", "QUALITY": "1", "QUALITY_REQUIRE_BASELINE": "1", "QUALITY_BASELINE_JSON": str(BASELINE)})
    elif stage.mode == "sensitive":
        env.update({"MAX_TOKENS": "512", "BENCH": "1", "NATURAL_EOS": "1", "QUALITY": "0", "PROMPT_IDS": "selection--incident-retrospective,selection--technical-guide"})
    elif stage.mode == "context":
        if context_suite is None:
            raise CampaignError("context stage requires a generated suite")
        env.update({"MAX_TOKENS": "128", "BENCH": "1", "NATURAL_EOS": "0", "QUALITY": "0", "BENCH_HELPER_PATH": str(CONTEXT_HELPER), "PROMPT_IDS": "context-2048-early,context-2048-middle,context-2048-late,context-8192-early,context-8192-middle,context-8192-late,context-32000-early,context-32000-middle,context-32000-late"})
    elif stage.mode == "init":
        env.update({"MAX_TOKENS": "128", "BENCH": "0", "NATURAL_EOS": "0", "QUALITY": "0"})
    else:
        raise CampaignError(f"unknown stage mode: {stage.mode}")
    return env


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def prometheus_total(path: Path, metric: str) -> float | None:
    if not path.is_file():
        return None
    total = 0.0
    found = False
    pattern = re.compile(rf"^{re.escape(metric)}(?:\{{[^}}]*\}})?\s+([-+0-9.eE]+)$")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if match:
            total += float(match.group(1))
            found = True
    return total if found else None


def exact_e5m2_unsupported_evidence(output: Path) -> dict[str, Any] | None:
    """Return evidence only for an explicit E5M2 KV dtype rejection.

    Boot timeouts, imports, device failures, and generic ``ValueError`` lines
    stay ``failed``.  The exact frozen image ID and a line naming both the KV
    cache and E5M2 together with unsupported/invalid semantics are required.
    """
    image_id_path = output / "image-id.txt"
    if not image_id_path.is_file() or image_id_path.read_text(encoding="utf-8").strip() != "sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296":
        return None
    dtype = r"(?:fp8[_ -]?e5m2|e5m2)"
    kv = r"(?:kv[_ -]?cache(?:[_ -]?dtype)?|kv_cache_dtype)"
    rejection = r"(?:not\s+supported|unsupported|invalid\s+(?:value|dtype)|does\s+not\s+support)"
    patterns = (
        re.compile(rf"{kv}.{{0,160}}{dtype}.{{0,160}}{rejection}", re.IGNORECASE),
        re.compile(rf"{dtype}.{{0,160}}{kv}.{{0,160}}{rejection}", re.IGNORECASE),
        re.compile(rf"{rejection}.{{0,160}}{kv}.{{0,160}}{dtype}", re.IGNORECASE),
    )
    for name in ("server.log", "server-startup.log"):
        path = output / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if any(pattern.search(line) for pattern in patterns):
                return {
                    "log": name,
                    "line_sha256": hashlib.sha256(line.encode()).hexdigest(),
                    "classification": "explicit-fp8-e5m2-kv-dtype-rejection",
                }
    return None


def oracle_matches(output: Path, attempt: int) -> tuple[bool, dict[str, Any]]:
    control = receipt_path(STAGES["p2-eager-control"], attempt).parent / "bench.json"
    control_json = load_json(control)
    candidate_json = load_json(output / "bench.json")
    if control_json is None or candidate_json is None:
        return False, {"reason": "oracle-bench-missing"}
    wanted = {"selection--incident-retrospective", "selection--technical-guide"}
    controls = {row.get("prompt_id"): row for row in control_json.get("rows", []) if row.get("prompt_id") in wanted}
    candidates = {row.get("prompt_id"): row for row in candidate_json.get("rows", []) if row.get("prompt_id") in wanted}
    details: dict[str, Any] = {}
    passed = controls.keys() == candidates.keys() == wanted
    for prompt_id in sorted(wanted):
        control_row = controls.get(prompt_id, {})
        candidate_row = candidates.get(prompt_id, {})
        token_ids_match = bool(control_row.get("token_ids")) and control_row.get("token_ids") == candidate_row.get("token_ids")
        output_hash_match = control_row.get("sha256") == candidate_row.get("sha256") and isinstance(control_row.get("sha256"), str)
        details[prompt_id] = {"token_ids_match": token_ids_match, "output_hash_match": output_hash_match}
        passed = passed and token_ids_match and output_hash_match
    return passed, details


def full_quality_passes(quality: dict[str, Any] | None) -> tuple[bool, dict[str, Any]]:
    if quality is None:
        return False, {"reason": "quality-json-missing"}
    exact = quality.get("exact_cases")
    repeats = quality.get("repeat_case")
    long_case = quality.get("long_context_case")
    comparisons = quality.get("baseline_comparisons")
    cached: list[Any] = []
    if isinstance(exact, list):
        cached += [((row.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens") for row in exact]
    if isinstance(repeats, dict) and isinstance(repeats.get("runs"), list):
        cached += [((row.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens") for row in repeats["runs"]]
    if isinstance(long_case, dict):
        cached.append(((long_case.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens"))
    passed = (
        quality.get("pass_all") is True
        and quality.get("baseline_match_all") is True
        and isinstance(exact, list)
        and len(exact) == 7
        and all(row.get("pass") is True for row in exact)
        and isinstance(repeats, dict)
        and repeats.get("pass") is True
        and repeats.get("repeats") == 8
        and len(repeats.get("unique_hashes") or []) == 1
        and isinstance(long_case, dict)
        and long_case.get("pass") is True
        and quality.get("baseline_status") == "passed"
        and isinstance(comparisons, dict)
        and len(comparisons) == 24
        and all(value is True for value in comparisons.values())
        and len(cached) == 16
        and all(value == 0 for value in cached)
    )
    return passed, {"exact_count": len(exact) if isinstance(exact, list) else None, "repeat_count": repeats.get("repeats") if isinstance(repeats, dict) else None, "cached_zero_count": sum(value == 0 for value in cached), "cached_count": len(cached), "baseline_comparison_count": len(comparisons) if isinstance(comparisons, dict) else None, "baseline_status": quality.get("baseline_status"), "baseline_match_all": quality.get("baseline_match_all"), "pass_all": quality.get("pass_all")}


def evaluate(stage: Stage, output: Path, attempt: int, runner_rc: int) -> tuple[str, bool, dict[str, Any]]:
    gates: dict[str, Any] = {"runner_rc": runner_rc, "speed_gate_applied": False}
    canary = load_json(output / "canary.json")
    gates["canary"] = bool(canary and canary.get("content") == "14" and canary.get("cached_tokens") == 0)
    gates["runner_final_pass"] = (output / "final.status").read_text(encoding="utf-8").strip() == "pass" if (output / "final.status").is_file() else False
    if stage.mode == "context":
        bench = load_json(output / "bench.json")
        context_gate = (bench or {}).get("context_retrieval_gate") or {}
        gates["context"] = context_gate
        if gates["runner_final_pass"] and gates["canary"] and context_gate.get("passed") is True:
            return "passed", True, gates
        first = context_gate.get("first_failure") or {}
        if str(first.get("prompt_id", "")).startswith("context-32000-") and context_gate.get("rows_completed", 0) >= 7:
            return "boundary-detected", True, gates
        if bench is not None and first:
            return "quarantined", True, gates
        return "failed", False, gates
    if stage.mode == "init":
        if gates["runner_final_pass"] and gates["canary"]:
            return "passed", True, gates
        unsupported = exact_e5m2_unsupported_evidence(output)
        gates["unsupported_evidence"] = unsupported
        if unsupported is not None:
            return "unsupported", True, gates
        return "failed", False, gates

    bench = load_json(output / "bench.json")
    bench_gate = (bench or {}).get("realistic_final_gate") or {}
    expected_rows = 25 if stage.mode == "full" else 2
    gates["benchmark"] = {"passed": bench_gate.get("passed") is True, "row_count": len((bench or {}).get("rows") or []), "expected_rows": expected_rows}
    benchmark_pass = gates["benchmark"]["passed"] and gates["benchmark"]["row_count"] == expected_rows
    quality_pass = True
    if stage.mode == "full":
        quality_pass, quality_details = full_quality_passes(load_json(output / "quality.json"))
        gates["quality"] = quality_details | {"passed": quality_pass}
    if stage.mode == "sensitive":
        before_draft = prometheus_total(output / "metrics.before.prom", "vllm:spec_decode_num_draft_tokens_total")
        after_draft = prometheus_total(output / "metrics.after.prom", "vllm:spec_decode_num_draft_tokens_total")
        before_accept = prometheus_total(output / "metrics.before.prom", "vllm:spec_decode_num_accepted_tokens_total")
        after_accept = prometheus_total(output / "metrics.after.prom", "vllm:spec_decode_num_accepted_tokens_total")
        draft_delta = after_draft - before_draft if None not in (before_draft, after_draft) else None
        accept_delta = after_accept - before_accept if None not in (before_accept, after_accept) else None
        acceptance_pass = isinstance(draft_delta, float) and isinstance(accept_delta, float) and draft_delta > 0 and 0 < accept_delta <= draft_delta
        oracle_pass, oracle_details = oracle_matches(output, attempt)
        gates["acceptance"] = {"passed": acceptance_pass, "draft_tokens": draft_delta, "accepted_tokens": accept_delta}
        gates["target_oracle"] = oracle_details | {"passed": oracle_pass}
        quality_pass = acceptance_pass and oracle_pass
    passed = gates["runner_final_pass"] and gates["canary"] and benchmark_pass and quality_pass
    if passed:
        return "passed", True, gates
    if bench is not None and (stage.mode == "full" or stage.mode == "sensitive"):
        return "quarantined", True, gates
    return "failed", False, gates


def write_receipt(output: Path, payload: dict[str, Any]) -> None:
    destination = output / "stage-receipt.json"
    temporary = output / f".stage-receipt.{os.getpid()}.tmp"
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(destination)


def next_action_for(stage: Stage, state: str) -> str:
    if stage.stage_id == "p1-context-spine" and state == "boundary-detected":
        return (
            "Run the preregistered 16K then 24K serving-input fallback on the "
            "same frozen identity; do not call either an exact active-context cell."
        )
    if stage.stage_id == "p1-context-spine" and state == "passed":
        return (
            "The endpoint parent passed; 4K/16K/24K supporting probes are now "
            "eligible, but remain separate from exact active-context cells."
        )
    if state == "failed":
        return "Do not expand; preserve this attempt and retry only with a new rN root/cache/port."
    if state in {"quarantined", "unsupported"}:
        return "Do not expand descendants; publish the exact parent evidence and retry condition."
    return "Expand only according to the preregistered parent gate; never overwrite this output/cache."


def execute(stage: Stage, attempt: int, acknowledgement: str) -> int:
    expected_ack = f"RUN {CAMPAIGN_ID} {stage.stage_id} r{attempt}"
    if acknowledgement != expected_ack:
        raise CampaignError(f"exact acknowledgement required: {expected_ack}")
    dependency_hashes = verify_dependencies()
    head = git_clean_pushed_main()
    verify_stage_order(stage, attempt)
    output, cache, port = layout(stage, attempt)
    ensure_idle(stage, attempt)
    context_suite = CONTEXT_SUITE if stage.mode == "context" else None
    suite = context_suite or SHORT_SUITE
    env = stage_environment(stage, context_suite)
    args = [str(RUNNER), str(stage.mtp), stage.kv, "32768", "0", str(port), str(output), str(suite), str(cache)]
    runner_rc = 125
    post_cleanup_ok = False
    with campaign_locks():
        runner_rc = subprocess.run(args, cwd=REPO, env=env, check=False).returncode
        try:
            ensure_post_cleanup(port)
            post_cleanup_ok = True
        except CampaignError:
            post_cleanup_ok = False
    if not output.is_dir():
        raise CampaignError(f"strict runner did not create its output: {output}")
    state, terminal, gates = evaluate(stage, output, attempt, runner_rc)
    if not post_cleanup_ok:
        state, terminal = "failed", False
    gates["post_cleanup_passed"] = post_cleanup_ok
    try:
        post_git = git_post_run_snapshot(head)
    except CampaignError as exc:
        post_git = {
            "launch_head": head,
            "local_lab_unchanged": False,
            "post_run_check_error": str(exc),
            "remote_movement_is_non_gating_after_launch": True,
        }
    if not post_git["local_lab_unchanged"]:
        state, terminal = "failed", False
        gates["lab_head_unchanged"] = False
    else:
        gates["lab_head_unchanged"] = True
    gates["live_origin_advanced_during_stage"] = post_git.get(
        "live_origin_advanced_during_stage"
    )
    receipt = {
        "schema": "neural.download.tp1-parent-sentinel-stage-receipt.v1",
        "campaign_id": CAMPAIGN_ID,
        "stage_id": stage.stage_id,
        "rank": stage.rank,
        "attempt": attempt,
        "state": state,
        "terminal": terminal,
        "output": str(output),
        "cache": str(cache),
        "port": port,
        "lab_git_head": head,
        "git_state": post_git,
        "runner_return_code": runner_rc,
        "gates": gates,
        "protected_speed_evidence": {"manifest_sha256": PROTECTED_MANIFEST_SHA256, "canonical_values_sha256": PROTECTED_VALUES_SHA256, "historical_values_are_immutable": True, "speed_was_not_a_correctness_gate": True},
        "frozen_dependency_sha256": dependency_hashes,
        "next_action": next_action_for(stage, state),
    }
    write_receipt(output, receipt)
    print(json.dumps({"stage": stage.stage_id, "attempt": attempt, "state": state, "terminal": terminal, "receipt": str(output / "stage-receipt.json")}, sort_keys=True))
    return 0 if state == "passed" else 20 if terminal else 1


def infer_existing_runner_rc(output: Path) -> int:
    final = output / "final.status"
    if not final.is_file():
        raise CampaignError("existing stage has no final.status")
    value = final.read_text(encoding="utf-8").strip()
    if value == "pass":
        return 0
    match = re.fullmatch(r"fail rc=(\d+)", value)
    if match:
        return int(match.group(1))
    raise CampaignError(f"unrecognized existing final.status: {value!r}")


def existing_evidence_hashes(stage: Stage, output: Path) -> dict[str, str]:
    names = [
        "bench.json",
        "canary.json",
        "final.status",
        "server-startup.log",
        "cache-manifest.post.sha256",
        "input-files.sha256",
    ]
    if stage.mode == "full":
        names.append("quality.json")
    hashes: dict[str, str] = {}
    for name in names:
        path = output / name
        if not path.is_file():
            raise CampaignError(f"existing stage evidence is incomplete: {name}")
        hashes[name] = sha256_file(path)
    return hashes


def verify_existing_phase_statuses(stage: Stage, output: Path) -> dict[str, int]:
    expected = {"canary": 0, "bench": 0}
    if stage.mode == "full":
        expected["quality"] = 0
    observed: dict[str, int] = {}
    for phase, expected_rc in expected.items():
        path = output / f"{phase}.status"
        if not path.is_file():
            raise CampaignError(f"existing stage has no {phase}.status")
        match = re.fullmatch(
            rf"{re.escape(phase)}_rc=(\d+)",
            path.read_text(encoding="utf-8").strip(),
        )
        if not match:
            raise CampaignError(f"unrecognized existing {phase}.status")
        observed[phase] = int(match.group(1))
        if observed[phase] != expected_rc:
            raise CampaignError(f"existing {phase} phase did not pass")
    return observed


def verify_existing_run_identity(
    stage: Stage, output: Path, launch_head: str
) -> dict[str, Any]:
    identity_path = output / "identity.env"
    if not identity_path.is_file():
        raise CampaignError("existing stage has no identity.env")
    identity: dict[str, str] = {}
    for line in identity_path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            identity[key] = value
    expected_image = (
        "sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296"
    )
    expected = {
        "lab_git_head": launch_head,
        "tp": "1",
        "mtp": str(stage.mtp),
        "kv": stage.kv,
        "expected_image_id": expected_image,
        "resolved_image_id": expected_image,
        "pull_source_image": "0",
        "require_graph_capture": "1" if stage.graph else "0",
    }
    mismatches = {
        key: {"expected": value, "observed": identity.get(key)}
        for key, value in expected.items()
        if identity.get(key) != value
    }
    if mismatches:
        raise CampaignError(f"existing identity mismatch: {mismatches}")
    source = load_json(output / "source-identity.json")
    if source is None:
        raise CampaignError("existing stage has no source-identity.json")
    if (source.get("vllm") or {}).get("head") != "b2dd9ce73dce2ad09007d1db5c171454118981d7":
        raise CampaignError("existing stage vLLM source identity mismatch")
    if (source.get("kernel") or {}).get("head") != "1e90ffa672ba02f17a909da11838a4c55b199783":
        raise CampaignError("existing stage XPU kernel identity mismatch")
    manifest_path = output / "input-files.sha256"
    if not manifest_path.is_file():
        raise CampaignError("existing stage has no input-files.sha256")
    verified_inputs: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        digest, raw_path = line.split(maxsplit=1)
        path = Path(raw_path)
        if not path.is_file() or sha256_file(path) != digest:
            raise CampaignError(f"existing stage input hash mismatch: {path}")
        verified_inputs[str(path)] = digest
    if len(verified_inputs) != 6:
        raise CampaignError("existing stage input manifest must contain six files")
    return {
        "identity_env_sha256": sha256_file(identity_path),
        "source_identity_sha256": sha256_file(output / "source-identity.json"),
        "image_id": expected_image,
        "vllm_head": (source.get("vllm") or {}).get("head"),
        "xpu_kernel_head": (source.get("kernel") or {}).get("head"),
        "verified_input_count": len(verified_inputs),
        "verified_inputs": verified_inputs,
    }


def finalize_existing(
    stage: Stage,
    attempt: int,
    acknowledgement: str,
    launch_head: str,
) -> int:
    """Write a receipt for a complete stage stopped only by the old remote gate.

    This is report-only: it never launches Docker or a model process and refuses
    to overwrite a receipt. It exists for the completed p2 r1 arm whose old
    wrapper checked live origin a second time after cleanup.
    """
    expected_ack = (
        f"FINALIZE {CAMPAIGN_ID} {stage.stage_id} r{attempt} FROM {launch_head}"
    )
    if acknowledgement != expected_ack:
        raise CampaignError(f"exact acknowledgement required: {expected_ack}")
    if stage.stage_id != "p2-eager-control" or attempt != 1:
        raise CampaignError("existing-output finalization is scoped only to p2 r1")
    if not re.fullmatch(r"[0-9a-f]{40}", launch_head):
        raise CampaignError("--launch-head must be a full lowercase commit hash")
    dependency_hashes = verify_dependencies()
    receipt_head = git_clean_pushed_main()
    require_ok(
        command(
            ["git", "-C", str(REPO), "cat-file", "-e", f"{launch_head}^{{commit}}"]
        ),
        "launch commit identity",
    )
    require_ok(
        command(
            [
                "git",
                "-C",
                str(REPO),
                "merge-base",
                "--is-ancestor",
                launch_head,
                receipt_head,
            ]
        ),
        "launch commit ancestry",
    )
    verify_stage_order(stage, attempt)
    output, cache, port = layout(stage, attempt)
    if not output.is_dir() or not cache.is_dir():
        raise CampaignError("existing stage output/cache is missing")
    if (output / "stage-receipt.json").exists():
        raise CampaignError("existing stage receipt already exists")
    ensure_post_cleanup(port)
    runner_rc = infer_existing_runner_rc(output)
    phase_statuses = verify_existing_phase_statuses(stage, output)
    identity = verify_existing_run_identity(stage, output, launch_head)
    state, terminal, gates = evaluate(stage, output, attempt, runner_rc)
    gates["post_cleanup_passed"] = True
    gates["lab_head_unchanged"] = True
    gates["lab_head_unchanged_basis"] = (
        "original launch preflight passed at launch_head; the original wrapper "
        "reached its post-run live-origin check with the same local HEAD and a "
        "clean worktree, then aborted only because live origin/main advanced"
    )
    gates["live_origin_advanced_during_stage"] = True
    evidence_hashes = existing_evidence_hashes(stage, output)
    receipt = {
        "schema": "neural.download.tp1-parent-sentinel-stage-receipt.v1",
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
        "runner_return_code": runner_rc,
        "gates": gates,
        "protected_speed_evidence": {
            "manifest_sha256": PROTECTED_MANIFEST_SHA256,
            "canonical_values_sha256": PROTECTED_VALUES_SHA256,
            "historical_values_are_immutable": True,
            "speed_was_not_a_correctness_gate": True,
        },
        "frozen_dependency_sha256": dependency_hashes,
        "next_action": next_action_for(stage, state),
        "finalization": {
            "mode": "report-only-existing-output",
            "reason": "old post-run live-origin equality gate aborted before receipt",
            "gpu_or_container_launch_performed": False,
            "launch_head": launch_head,
            "receipt_git_head": receipt_head,
            "launch_head_is_ancestor_of_receipt_head": True,
            "phase_return_codes": phase_statuses,
            "identity": identity,
            "evidence_sha256": evidence_hashes,
        },
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
                "launch_performed": False,
            },
            sort_keys=True,
        )
    )
    return 0 if state == "passed" else 20 if terminal else 1


def ensure_post_cleanup(port: int) -> None:
    containers = require_ok(docker_command(["ps", "-q"]), "post-run Docker scan")
    if containers:
        raise CampaignError("a Docker container remains after the stage")
    listeners = command(["ss", "-ltnH", "sport", "=", f":{port}"])
    if listeners.returncode != 0 or listeners.stdout.strip():
        raise CampaignError(f"port {port} remains occupied after the stage")
    processes = command(["pgrep", "-af", r"[E]ngineCore|[v]llm serve|[l]lama-server"])
    if processes.returncode == 0 and processes.stdout.strip():
        raise CampaignError("a model server remains after the stage")
    if processes.returncode not in (0, 1):
        raise CampaignError("post-run model-process scan failed")
    if render_users():
        raise CampaignError("a process still owns a render node after the stage")


def plan_payload(attempt: int) -> dict[str, Any]:
    return {
        "campaign_id": CAMPAIGN_ID,
        "attempt": attempt,
        "execution_requires_explicit_ack": True,
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
    parser.add_argument("--check", action="store_true", help="validate frozen inputs only; never launches")
    parser.add_argument("--plan", action="store_true", help="render the stage plan; never launches")
    parser.add_argument("--execute", action="store_true", help="execute exactly one stage")
    parser.add_argument(
        "--finalize-existing",
        action="store_true",
        help="report-only receipt recovery for a complete existing stage; never launches",
    )
    parser.add_argument("--stage", choices=tuple(STAGES))
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--ack", default="")
    parser.add_argument("--launch-head", default="")
    args = parser.parse_args()
    selected = sum((args.check, args.plan, args.execute, args.finalize_existing))
    if selected != 1:
        parser.error(
            "choose exactly one of --check, --plan, --execute, or --finalize-existing"
        )
    if args.check:
        hashes = verify_dependencies()
        print(json.dumps({"campaign_id": CAMPAIGN_ID, "status": "PASS", "launch_performed": False, "dependencies": hashes}, sort_keys=True))
        return 0
    if args.plan:
        print(json.dumps(plan_payload(args.attempt), indent=2, sort_keys=True))
        return 0
    if not args.stage:
        parser.error("--execute/--finalize-existing requires --stage")
    if args.finalize_existing:
        if not args.launch_head:
            parser.error("--finalize-existing requires --launch-head")
        return finalize_existing(
            STAGES[args.stage], args.attempt, args.ack, args.launch_head
        )
    return execute(STAGES[args.stage], args.attempt, args.ack)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CampaignError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
