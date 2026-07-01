#!/usr/bin/env python3
"""Build a cache-versioned manifest for the accepted Qwen3.6 lane.

The goal is to keep speed experiments honest: record the exact graph cache,
extension binaries, launcher scrub state, quality artifacts, old token
sentinels, and p512/o512 speed artifact that a candidate must beat.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:18080"
DEFAULT_MODEL_PATH = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8"
    "/snapshots/cced56592e8c8935f8220836b4baa04dfd389118"
)
DEFAULT_CACHE_ROOT = (
    "/mnt/fast-ai/vllm-cache-exp/"
    "qwen36-35b-a3b-quark-int8-tp4-accepted-clean-after-routeparity-20260612cy"
)
DEFAULT_LOG = (
    "data/qwen36-quark-int8-tp4-accepted-restored-after-routeparity-clean-20260612cy.log"
)
DEFAULT_SPEED = (
    "data/qwen36-quark-int8-tp4-accepted-clean-routeparity-p512o512-metrics-20260612cy.json"
)
DEFAULT_QUALITY = (
    "data/qwen36-quark-int8-tp4-accepted-quality-after-routeparity-clean-nothink-smoke-20260612cy.json"
)
DEFAULT_PROVENANCE = (
    "data/qwen36-quark-int8-tp4-accepted-provenance-after-routeparity-clean-rerun-20260612cy.json"
)
DEFAULT_LAUNCHER = "scripts/launch-qwen36-quark-int8-accepted.sh"
DEFAULT_EXTENSIONS = (
    "/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so",
    "/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/libgrouped_gemm_xe_2.so",
    "/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/libgdn_attn_kernels_xe_2.so",
)
DEFAULT_REPOS = (
    "/home/steve/llm-optimizations",
    "/home/steve/src/vllm",
    "/home/steve/src/vllm-xpu-kernels",
)
SYMBOL_PATTERNS = (
    "cutlass_grouped_gemm_w8a8_int8_interface",
    "cutlass_grouped_gemm_w8a8_int8_offsets_interface",
    "cutlass_grouped_gemm_w8a8_int8_active_offset_interface",
    "qwen36_moe_onednn_sidecar",
)


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    exists = path.exists()
    record: dict[str, Any] = {
        "path": str(path),
        "exists": exists,
    }
    if not exists:
        return record
    stat = path.stat()
    record.update({
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
        "size_bytes": stat.st_size if path.is_file() else None,
        "mtime_unix": stat.st_mtime,
        "sha256": sha256_file(path),
    })
    return record


def tree_record(root: Path) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": str(root),
        "exists": root.exists(),
        "file_count": 0,
        "total_bytes": 0,
        "sha256": None,
        "largest_files": [],
    }
    if not root.exists():
        return record

    entries: list[tuple[str, int, str]] = []
    largest: list[tuple[int, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root))
        size = path.stat().st_size
        digest = sha256_file(path) or ""
        entries.append((rel, size, digest))
        largest.append((size, rel))
        record["file_count"] += 1
        record["total_bytes"] += size

    agg = hashlib.sha256()
    for rel, size, digest in entries:
        agg.update(rel.encode("utf-8", errors="replace"))
        agg.update(b"\0")
        agg.update(str(size).encode("ascii"))
        agg.update(b"\0")
        agg.update(digest.encode("ascii"))
        agg.update(b"\n")
    record["sha256"] = agg.hexdigest()
    record["largest_files"] = [
        {"path": rel, "size_bytes": size}
        for size, rel in sorted(largest, reverse=True)[:16]
    ]
    return record


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def try_get(url: str, timeout: float = 5.0) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed: Any = None
            try:
                parsed = json.loads(body) if body else None
            except json.JSONDecodeError:
                parsed = body
            return {
                "ok": 200 <= resp.status < 300,
                "status": resp.status,
                "elapsed_ms": (time.perf_counter() - started) * 1000,
                "body": parsed,
            }
    except Exception as exc:
        item: dict[str, Any] = {
            "ok": False,
            "elapsed_ms": (time.perf_counter() - started) * 1000,
            "error": repr(exc),
        }
        if isinstance(exc, urllib.error.HTTPError):
            item["status"] = exc.code
        return item


def parse_log(path: Path) -> dict[str, Any]:
    text = path.read_text(errors="replace") if path.exists() else ""
    aot_paths = sorted(set(re.findall(
        r"(?:Directly load AOT compilation from path|saved AOT compiled function to) (.*)",
        text,
    )))
    cache_directories = sorted(set(re.findall(
        r"Using cache directory: (.*?) for vLLM's torch\.compile",
        text,
    )))
    env_warnings = sorted(set(re.findall(
        r"Unknown vLLM environment variable detected: ([A-Z0-9_]+)",
        text,
    )))

    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": sha256_file(path),
        "cache_directories": cache_directories,
        "aot_paths": aot_paths,
        "aot_path_records": [file_record(Path(item)) for item in aot_paths],
        "using_xpu_int8_moe": "Using XPU Int8 MoE backend" in text,
        "graph_capturing_finished": "Graph capturing finished" in text,
        "env_warning_names": env_warnings,
        "available_kv_cache_memory_gib": extract_float(
            text, r"Available KV cache memory: ([0-9.]+) GiB"),
        "gpu_kv_cache_tokens": extract_int(
            text, r"GPU KV cache size: ([0-9,]+) tokens"),
        "init_engine_seconds": extract_float(
            text, r"init engine .* took ([0-9.]+) s"),
        "compilation_seconds": extract_float(
            text, r"init engine .* compilation: ([0-9.]+) s"),
    }


def extract_float(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def extract_int(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text)
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def launcher_record(path: Path) -> dict[str, Any]:
    text = path.read_text(errors="replace") if path.exists() else ""
    unset_vars = []
    export_vars = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("unset "):
            unset_vars.extend(stripped.split()[1:])
        elif stripped.startswith("export "):
            export_vars.append(stripped.split(" ", 1)[1].split("=", 1)[0])
    rejected_scrub = [
        "VLLM_XPU_W8A8_USE_OFFSETS",
        "VLLM_XPU_MOE_ONEDNN_SIDECAR_PROBE",
        "VLLM_XPU_MOE_ONEDNN_SIDECAR_OFFSETS",
        "VLLM_XPU_MOE_ONEDNN_SIDECAR_DRY_DESCRIPTORS",
        "VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT",
        "VLLM_XPU_MOE_LIVE_ABI_FILE",
        "VLLM_XPU_MOE_LIVE_ABI_MAX_LINES",
    ]
    return {
        **file_record(path),
        "unset_vars": sorted(set(unset_vars)),
        "export_vars": sorted(set(export_vars)),
        "rejected_diagnostic_scrub": {
            name: name in unset_vars for name in rejected_scrub
        },
        "scrub_complete": all(name in unset_vars for name in rejected_scrub),
    }


def extension_record(path: Path) -> dict[str, Any]:
    record = file_record(path)
    record["symbols"] = {name: False for name in SYMBOL_PATTERNS}
    if not path.is_file():
        return record
    try:
        proc = subprocess.run(
            ["nm", "-D", str(path)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        output = proc.stdout + proc.stderr
        record["nm_returncode"] = proc.returncode
        record["symbols"] = {
            name: name in output for name in SYMBOL_PATTERNS
        }
    except Exception as exc:
        record["nm_error"] = repr(exc)
    return record


def git_record(path: Path) -> dict[str, Any]:
    record: dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if not path.exists():
        return record
    for key, command in {
        "head": ["git", "-C", str(path), "rev-parse", "HEAD"],
        "branch": ["git", "-C", str(path), "branch", "--show-current"],
        "status_porcelain": ["git", "-C", str(path), "status", "--porcelain"],
    }.items():
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if key == "status_porcelain":
            lines = [line for line in proc.stdout.splitlines() if line.strip()]
            record["dirty_count"] = len(lines)
            record["dirty_sample"] = lines[:24]
        else:
            record[key] = proc.stdout.strip() or None
    return record


def speed_summary(path: Path) -> dict[str, Any]:
    data = load_json(path)
    summary = data.get("summary") or {}

    def mean(name: str) -> float | None:
        value = summary.get(name) or {}
        item = value.get("mean")
        return None if item is None else float(item)

    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "prompt_tokens_actual": data.get("prompt_tokens_actual"),
        "output_tokens_requested": data.get("output_tokens_requested"),
        "repeats": data.get("repeats"),
        "corrected_decode_tok_s": mean("tok_s_out_client_after_first_chunk_corrected"),
        "e2e_decode_tok_s": mean("tok_s_out_client_e2e"),
        "decode_ms_per_generation_token_vllm": mean(
            "decode_ms_per_generation_token_vllm_histogram"),
        "ttft_ms_client": mean("ttft_ms_client"),
        "iteration_tokens_per_step": mean("iteration_tokens_per_step_vllm_histogram"),
    }


def quality_summary(path: Path) -> dict[str, Any]:
    data = load_json(path)
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "pass_all": data.get("pass_all"),
        "baseline_match_all": data.get("baseline_match_all"),
        "exact_case_count": len(data.get("exact_cases") or []),
        "long_context_case_present": data.get("long_context_case") is not None,
    }


def provenance_summary(path: Path) -> dict[str, Any]:
    data = load_json(path)
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "ok": data.get("ok"),
        "case_prefix_matches": data.get("case_prefix_matches"),
        "sentinels": data.get("sentinels"),
        "error_count": len(data.get("errors") or []),
        "errors_head": (data.get("errors") or [])[:4],
    }


def write_markdown(manifest: dict[str, Any], path: Path) -> None:
    speed = manifest["speed_artifact"]
    quality = manifest["quality_artifact"]
    provenance = manifest["provenance_artifact"]
    gate = manifest["accepted_lane_gate"]
    cache = manifest["cache_root"]
    launcher = manifest["launcher"]
    lines = [
        "# Qwen3.6 Accepted Lane Manifest",
        "",
        f"- Created: `{manifest['created_at_unix']:.0f}`",
        f"- Endpoint health: `{manifest['endpoint']['health'].get('ok')}`",
        f"- Quality smoke pass: `{quality.get('pass_all')}`",
        f"- Quality baseline match: `{quality.get('baseline_match_all')}`",
        f"- Old token provenance pass: `{provenance.get('ok')}`",
        f"- Corrected p512/o512 decode: `{speed.get('corrected_decode_tok_s'):.3f} tok/s`",
        f"- vLLM decode: `{speed.get('decode_ms_per_generation_token_vllm'):.3f} ms/token`",
        f"- Cache files: `{cache.get('file_count')}` files, `{cache.get('total_bytes')}` bytes",
        f"- Cache digest: `{cache.get('sha256')}`",
        f"- Launcher diagnostic scrub complete: `{launcher.get('scrub_complete')}`",
        f"- Gate status: `{gate['status']}`",
        "",
        "## Gate Notes",
        "",
    ]
    for note in gate["notes"]:
        lines.append(f"- {note}")
    lines.extend(["", "## Next Candidate Requirements", ""])
    for item in manifest["next_candidate_requirements"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Extension Symbols", ""])
    for item in manifest["extensions"]:
        symbols = item.get("symbols") or {}
        lines.append(
            f"- `{item['path']}` sha `{item.get('sha256')}` symbols `{symbols}`"
        )
    path.write_text("\n".join(lines) + "\n")


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    log = parse_log(Path(args.log_path))
    cache = tree_record(Path(args.cache_root))
    speed = speed_summary(Path(args.speed_json))
    quality = quality_summary(Path(args.quality_json))
    provenance = provenance_summary(Path(args.provenance_json))
    launcher = launcher_record(Path(args.launcher))
    endpoint = {
        "health": try_get(f"{args.base_url.rstrip('/')}/health", args.timeout),
        "models": try_get(f"{args.base_url.rstrip('/')}/v1/models", args.timeout),
    }

    quality_ok = bool(quality.get("pass_all") and quality.get("baseline_match_all"))
    health_ok = bool(endpoint["health"].get("ok"))
    speed_ok = speed.get("corrected_decode_tok_s") is not None
    scrub_ok = bool(launcher.get("scrub_complete"))
    strict_old_token_ok = bool(provenance.get("ok"))

    notes = []
    if quality_ok:
        notes.append("No-thinking quality smoke and baseline comparison passed.")
    else:
        notes.append("Quality smoke or baseline comparison failed; do not use as accepted baseline.")
    if not strict_old_token_ok:
        notes.append(
            "Old exact-token provenance did not pass on this clean cache; treat token sentinels as cache-versioned."
        )
    if scrub_ok:
        notes.append("Accepted launcher scrubs rejected diagnostic MoE env vars.")
    if speed_ok:
        notes.append("p512/o512/c1 speed artifact is present and parseable.")

    status = (
        "accepted_quality_baseline_with_stale_token_sentinel"
        if health_ok and quality_ok and speed_ok and scrub_ok and not strict_old_token_ok
        else "accepted_strict"
        if health_ok and quality_ok and speed_ok and scrub_ok and strict_old_token_ok
        else "not_accepted"
    )

    return {
        "kind": "qwen36_accepted_lane_manifest",
        "created_at_unix": time.time(),
        "base_url": args.base_url,
        "model_path": args.model_path,
        "endpoint": endpoint,
        "log": log,
        "cache_root": cache,
        "launcher": launcher,
        "speed_artifact": speed,
        "quality_artifact": quality,
        "provenance_artifact": provenance,
        "extensions": [
            extension_record(Path(item))
            for item in (args.extension or DEFAULT_EXTENSIONS)
        ],
        "git_repositories": [
            git_record(Path(item)) for item in (args.repo or DEFAULT_REPOS)
        ],
        "accepted_lane_gate": {
            "status": status,
            "health_ok": health_ok,
            "quality_ok": quality_ok,
            "speed_ok": speed_ok,
            "launcher_scrub_ok": scrub_ok,
            "strict_old_token_provenance_ok": strict_old_token_ok,
            "notes": notes,
        },
        "next_candidate_requirements": [
            "Beat this manifest's corrected p512/o512/c1 decode speed on the same current model.",
            "Pass the no-thinking quality suite and baseline comparison.",
            "Report strict old-token provenance separately from cache-versioned clean-cache token baselines.",
            "Record cache root digest, AOT path hashes, extension SHA256, and launcher env scrub state.",
            "For kernel-path changes, pass graph-path or live compiled-path tensor parity before endpoint promotion.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--cache-root", default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--log-path", default=DEFAULT_LOG)
    parser.add_argument("--speed-json", default=DEFAULT_SPEED)
    parser.add_argument("--quality-json", default=DEFAULT_QUALITY)
    parser.add_argument("--provenance-json", default=DEFAULT_PROVENANCE)
    parser.add_argument("--launcher", default=DEFAULT_LAUNCHER)
    parser.add_argument("--extension", action="append", default=None)
    parser.add_argument("--repo", action="append", default=None)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--markdown-out", required=True)
    parser.add_argument("--timeout", type=float, default=5.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_manifest(args)
    out = Path(args.output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    md = Path(args.markdown_out)
    md.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(manifest, md)
    print(json.dumps(manifest["accepted_lane_gate"], indent=2, sort_keys=True))
    print(f"wrote={out}")
    print(f"wrote={md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
