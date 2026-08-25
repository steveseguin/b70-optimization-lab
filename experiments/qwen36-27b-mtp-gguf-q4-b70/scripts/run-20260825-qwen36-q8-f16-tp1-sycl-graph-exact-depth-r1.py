#!/usr/bin/env python3
"""Run the sealed Qwen3.6 target-Q8/F16 TP1 SYCL-graph depth curve.

The default mode is inert. ``--check`` and ``--execute`` fail closed while
any build, DSO, or parent-receipt placeholder remains. Execution is one
isolated llama-bench process per context so every promoted cell has its own
positive capture-and-replay summary.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-q8-f16-tp1-sycl-graph-exact-depth-prereg.json"
GRAPH_OFF_RUNNER = LANE / "scripts/run-20260825-qwen36-q8-f16-tp1-exact-depth-r1.py"
PARSER = REPO / "scripts/parse-llama-bench-exact-depth.py"
CAMPAIGN_ID = "qwen36-q8-f16-tp1-sycl-graph-exact-depth-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
DEPTHS = [0, 2048, 4096, 8192, 16384, 24576, 32768]
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-sycl-graph-exact-depth-20260825-r1")
PLACEHOLDER_PREFIX = "FILL_AFTER_"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SUMMARY_RE = re.compile(
    r"\[SYCL-GRAPH\] summary device=(?P<device>\d+) "
    r"requested=(?P<requested>\d+) compatibility_rejected=(?P<compatibility_rejected>\d+) "
    r"device_unsupported=(?P<device_unsupported>\d+) cache_entries=(?P<cache_entries>\d+) "
    r"cache_limit=(?P<cache_limit>\d+) cache_hit=(?P<cache_hit>\d+) "
    r"cache_miss=(?P<cache_miss>\d+) cache_full=(?P<cache_full>\d+) "
    r"direct_replay=(?P<direct_replay>\d+) recorded=(?P<recorded>\d+) "
    r"created=(?P<created>\d+) updated=(?P<updated>\d+) "
    r"recreated=(?P<recreated>\d+) replayed=(?P<replayed>\d+)"
)


def _load_graph_off_runner():
    spec = importlib.util.spec_from_file_location("qwen36_q8_f16_graph_off_reference", GRAPH_OFF_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import graph-off lifecycle: {GRAPH_OFF_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


GRAPH_OFF = _load_graph_off_runner()
BASE = GRAPH_OFF.ENGINE
GateError = BASE.GateError


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GateError(f"JSON root must be an object: {path}")
    return value


def load_manifest() -> dict[str, Any]:
    return load_json(MANIFEST)


def validate_manifest(value: Mapping[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    model = value.get("model") or {}
    source = value.get("source") or {}
    runtime = value.get("runtime") or {}
    parent = value.get("parent_sentinel") or {}
    graph = value.get("graph_evidence") or {}
    lifecycle = value.get("lifecycle") or {}
    interpretation = value.get("interpretation") or {}
    template = value.get("argv_template")
    if not (
        value.get("schema") == "neural.download.qwen36-llama-sycl-graph-exact-depth-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and value.get("sealing_status") in {
            "UNSEALED_AWAITING_GRAPH_BINARY_BACKEND_DSOS_AND_PARENT_RECEIPTS",
            "sealed",
        }
        and selectors == {
            "revision": "qwen3.6-27b",
            "artifact_id": "qwen36-27b-unsloth-q8-0-82d411a",
            "quantization": "Q8_0",
            "runtime_family": "llama.cpp SYCL",
            "tp": 1,
            "mtp": 0,
            "graph_mode": "SYCL",
            "kv": "f16",
            "active_context_tokens": DEPTHS,
        }
        and model.get("path") == "/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf"
        and model.get("size_bytes") == 28595763424
        and model.get("sha256") == "f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce"
        and model.get("direct_sha256") == model.get("sha256")
        and model.get("ordinary_sha256") == model.get("sha256")
        and model.get("embedded_mtp_capability") is False
        and source.get("base_head") == "fa0f3b25a47f346858a4d0d169f5181aa424b110"
        and parent.get("campaign_id") == "qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r4"
        and parent.get("same_graph_backend_as_curve_required") is True
        and graph.get("required_for_every_context") == DEPTHS
        and graph.get("graph_estimates_forbidden") is True
        and lifecycle.get("output_root") == str(RUN_ROOT)
        and lifecycle.get("exact_ack") == ACK
        and lifecycle.get("output_fstype") == "ext4"
        and lifecycle.get("artifacts_are_create_only") is True
        and lifecycle.get("terminal_receipt_required") is True
        and interpretation.get("speed_floor") is None
        and interpretation.get("cell_gain_on_pass") == 7
        and interpretation.get("site_publication_authorized") is False
        and interpretation.get("record_or_submission_authorized") is False
        and interpretation.get("quality_claim_authorized") is False
        and interpretation.get("quality_gate_required_before_publication") is True
        and interpretation.get("graph_estimates_forbidden") is True
        and interpretation.get("protected_graph_off_values_must_not_be_replaced") is True
        and interpretation.get("historical_featured_speeds_are_immutable") is True
    ):
        raise GateError("SYCL-graph exact-depth manifest invariant failed")
    if not isinstance(template, list) or template.count("{active_context_tokens}") != 1:
        raise GateError("argv template must contain exactly one context placeholder")
    if any(flag not in template for flag in ("-d", "-ctk", "-ctv")):
        raise GateError("argv template is missing a required depth/KV selector")
    if template[0] != (runtime.get("binary") or {}).get("path"):
        raise GateError("argv template binary differs from runtime identity")
    if template[template.index("-ctk") + 1] != "f16" or template[template.index("-ctv") + 1] != "f16":
        raise GateError("curve must use F16 K/V cache")
    if "--spec-type" in template:
        raise GateError("target-only curve must not enable speculation")
    environment = value.get("environment") or {}
    if environment.get("GGML_SYCL_ENABLE_GRAPH") != "1" or environment.get("GGML_SYCL_GRAPH_CACHE_SIZE") != "8":
        raise GateError("SYCL graph and cache-size environment is not frozen")


def _require_hash(value: object, label: str) -> str:
    text = str(value or "")
    if text.startswith(PLACEHOLDER_PREFIX) or SHA256_RE.fullmatch(text) is None:
        raise GateError(f"unsealed {label} SHA-256")
    return text


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO / path


def _verify_ref(row: Mapping[str, Any], label: str) -> Path:
    path = _resolve(str(row.get("path", "")))
    expected = _require_hash(row.get("sha256"), label)
    if not path.is_file() or sha256_file(path) != expected:
        raise GateError(f"sealed {label} receipt/file is absent or changed: {path}")
    return path


def _require_binary(row: Mapping[str, Any], label: str) -> Path:
    path = Path(str(row.get("path", "")))
    size = row.get("size_bytes")
    expected = _require_hash(row.get("sha256"), label)
    if not isinstance(size, int) or size <= 0:
        raise GateError(f"unsealed {label} size")
    if not path.is_file() or path.stat().st_size != size or sha256_file(path) != expected:
        raise GateError(f"sealed {label} identity changed")
    return path


def require_sealed_dependencies(manifest: Mapping[str, Any]) -> None:
    if manifest.get("sealing_status") != "sealed":
        raise GateError("packet is unsealed; fill graph binary/backend/DSOs and parent receipts")
    runtime = manifest["runtime"]
    _require_binary(runtime["binary"], "llama-bench")
    backend = _require_binary(runtime["graph_backend"], "graph backend")
    rows = runtime.get("effective_shared_libraries")
    if not isinstance(rows, list) or len(rows) != 32:
        raise GateError("unsealed effective DSO closure; exactly 32 rows are required")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, list) or len(row) != 4:
            raise GateError("effective DSO row schema changed")
        soname, _reported, realpath, digest = row
        if not soname or soname in seen or not Path(realpath).is_absolute():
            raise GateError("effective DSO closure is duplicated or non-canonical")
        _require_hash(digest, f"DSO {soname}")
        if not Path(realpath).is_file() or sha256_file(Path(realpath)) != digest:
            raise GateError(f"sealed DSO identity changed: {soname}")
        seen.add(soname)
    parent = manifest["parent_sentinel"]
    verified_parent_paths = {
        key: _verify_ref(parent[key], f"parent {key}")
        for key in ("preregistration", "runner", "result", "terminal_receipt", "parity_receipt")
    }
    parent_manifest = load_json(_resolve(parent["preregistration"]["path"]))
    parent_backend = (parent_manifest.get("runtime_delta") or {}).get("graph_backend") or {}
    parent_base = parent_manifest.get("sealed_r2_base") or {}
    parent_base_path = _verify_ref(
        {
            "path": parent_base.get("manifest_path"),
            "sha256": parent_base.get("manifest_sha256"),
        },
        "parent sealed R2 base",
    )
    parent_base_manifest = load_json(parent_base_path)
    parent_base_backend = (parent_base_manifest.get("runtime") or {}).get("graph_backend") or {}
    if parent_backend.get("sha256") != runtime["graph_backend"]["sha256"]:
        raise GateError("curve and parent sentinel do not bind the same graph backend")
    if parent_backend.get("size_bytes") != runtime["graph_backend"]["size_bytes"]:
        raise GateError("curve and parent sentinel graph backend sizes differ")
    if Path(str(parent_base_backend.get("path", ""))).resolve() != backend.resolve():
        raise GateError("curve and parent sentinel graph backend paths differ")
    result = load_json(verified_parent_paths["result"])
    terminal = result.get("terminal") or {}
    parity = result.get("parity") or {}
    authority = result.get("authority") or {}
    if not (
        result.get("campaign_id") == parent["campaign_id"]
        and (result.get("runtime") or {}).get("graph_backend_sha256")
        == runtime["graph_backend"]["sha256"]
        and terminal.get("state") == "passed-parent-sentinel-only"
        and terminal.get("cleanup_passed") is True
        and parity.get("passed") is True
        and parity.get("same_binary") is True
        and parity.get("exact_output_bytes") is True
        and authority.get("mechanism_and_exact_output_parity") is True
        and authority.get("seven_cell_expansion") is False
        and authority.get("site_publication") is False
        and authority.get("record_or_submission") is False
    ):
        raise GateError("parent sentinel did not grant the required bounded authority")
    raw_terminal = load_json(verified_parent_paths["terminal_receipt"])
    raw_parity = load_json(verified_parent_paths["parity_receipt"])
    if not (
        raw_terminal.get("campaign_id") == parent["campaign_id"]
        and raw_terminal.get("state") == "passed-parent-sentinel-only"
        and raw_terminal.get("stage") == "complete"
        and raw_terminal.get("cleanup_passed") is True
        and raw_parity.get("passed") is True
        and raw_parity.get("same_binary") is True
        and raw_parity.get("exact_output_bytes") is True
        and raw_parity.get("cache_zero_both_arms") is True
    ):
        raise GateError("parent terminal/parity receipt content did not pass")
    if result.get("terminal_sha256") != parent["terminal_receipt"]["sha256"]:
        raise GateError("parent result does not bind the sealed terminal receipt")
    if parity.get("receipt_sha256") != parent["parity_receipt"]["sha256"]:
        raise GateError("parent result does not bind the sealed parity receipt")


def static_check() -> dict[str, Any]:
    manifest = load_manifest()
    validate_manifest(manifest)
    require_sealed_dependencies(manifest)
    if sha256_file(PARSER) != BASE.EXPECTED_PARSER_SHA256:
        raise GateError("exact-depth parser changed")
    if sha256_file(BASE.PROTECTED) != BASE.EXPECTED_PROTECTED_SHA256:
        raise GateError("protected historical speed manifest changed")
    return manifest


def parse_graph_summary(text: str) -> dict[str, int]:
    matches = list(SUMMARY_RE.finditer(text))
    if len(matches) != 1:
        raise GateError(f"expected exactly one SYCL graph summary, got {len(matches)}")
    summary = {name: int(value) for name, value in matches[0].groupdict().items()}
    if not (
        summary["device"] == 0
        and summary["cache_limit"] == 8
        and summary["compatibility_rejected"] == 0
        and summary["device_unsupported"] == 0
        and summary["cache_full"] == 0
        and summary["requested"] > 0
        and summary["recorded"] > 0
        and summary["created"] > 0
        and summary["cache_hit"] > 0
        and summary["direct_replay"] > 0
        and summary["replayed"] > 0
        and summary["replayed"] == summary["requested"]
    ):
        raise GateError(f"per-context graph evidence gate failed: {summary}")
    return summary


def argv_for_depth(manifest: Mapping[str, Any], depth: int) -> list[str]:
    return [str(depth) if item == "{active_context_tokens}" else item for item in manifest["argv_template"]]


def verify_source(manifest: Mapping[str, Any]) -> None:
    source = Path(manifest["source"]["path"])
    if BASE.git_output("rev-parse", "HEAD", cwd=source) != manifest["source"]["base_head"]:
        raise GateError("graph-port source HEAD changed")
    expected = manifest["source"]["required_modified_paths"]
    status = BASE.git_output("status", "--porcelain=v1", "--untracked-files=all", cwd=source).splitlines()
    if set(status) != {f" M {path}" for path in expected}:
        raise GateError("graph-port source contains non-frozen changes")
    for relative, digest in expected.items():
        if sha256_file(source / relative) != digest:
            raise GateError(f"ported source changed: {relative}")
    patch = manifest["source"]["patch"]
    if sha256_file(REPO / patch["path"]) != patch["sha256"]:
        raise GateError("focused graph port patch changed")


def preflight(manifest: Mapping[str, Any]) -> tuple[str, dict[str, str], list[list[str]]]:
    BASE.reject_inherited_runtime_environment(dict(os.environ))
    head = BASE.require_clean_pushed_main()
    verify_source(manifest)
    model = Path(manifest["model"]["path"])
    if not model.is_file() or model.stat().st_size != manifest["model"]["size_bytes"]:
        raise GateError("model size changed")
    verifier = GRAPH_OFF.REFERENCE.VERIFIER
    direct_digest, _mode = verifier.hash_direct(model)
    ordinary_digest = sha256_file(model)
    if direct_digest != manifest["model"]["direct_sha256"] or ordinary_digest != manifest["model"]["ordinary_sha256"]:
        raise GateError("direct/ordinary model identity changed")
    output_parent = RUN_ROOT.parent
    if RUN_ROOT.exists():
        raise GateError(f"create-only output root exists: {RUN_ROOT}")
    fstype = subprocess.check_output(
        ["/usr/bin/findmnt", "-n", "-o", "FSTYPE", "--target", str(output_parent)],
        text=True,
        timeout=30,
    ).strip()
    if fstype != "ext4":
        raise GateError(f"output parent must be ext4, got {fstype}")
    environment = BASE.oneapi_environment(RUN_ROOT, manifest["environment"])
    libraries = BASE.effective_libraries(Path(manifest["runtime"]["binary"]["path"]), environment)
    if libraries != manifest["runtime"]["effective_shared_libraries"]:
        raise GateError("effective shared-library closure changed")
    BASE.require_idle()
    return head, environment, libraries


def _write_json(path: Path, value: Any) -> None:
    BASE.write_json_exclusive(path, value)


def metadata(manifest: Mapping[str, Any], libraries: list[list[str]], evidence: Mapping[int, Mapping[str, Any]]) -> dict[str, Any]:
    per_context = {str(depth): dict(evidence[depth]) for depth in DEPTHS}
    return {
        "schema": "llama-bench-exact-depth-metadata-v1",
        "receipt_id": CAMPAIGN_ID,
        "declared_depths": DEPTHS,
        "binary": {**manifest["runtime"]["binary"], "source_head": manifest["source"]["base_head"], "effective_shared_libraries": libraries},
        "model": manifest["model"],
        "argv": manifest["argv_template"],
        "argv_semantics": "normalization template; exact executed argv is bound per context below",
        "execution_argv_by_context": {
            str(depth): argv_for_depth(manifest, depth) for depth in DEPTHS
        },
        "env": manifest["environment"],
        "cell_selectors": {
            key: value
            for key, value in manifest["selectors"].items()
            if key not in {"active_context_tokens", "graph_mode"}
        },
        "graph": {
            "requested": True,
            "capture": {"count": sum(row["created"] for row in evidence.values()), "source": "per-context SYCL graph summaries", "per_context": per_context},
            "replay": {"count": sum(row["replayed"] for row in evidence.values()), "source": "per-context SYCL graph summaries", "per_context": per_context},
        },
    }


def execute(acknowledgement: str) -> int:
    if acknowledgement != ACK:
        raise GateError(f"exact acknowledgement required: {ACK}")
    manifest = static_check()
    state = "failed"
    error: str | None = None
    head = ""
    cleanup = False
    launched_depths: list[int] = []
    with BASE.campaign_locks():
        head, environment, libraries = preflight(manifest)
        RUN_ROOT.mkdir(mode=0o700)
        for name in ("runtime-home", "runtime-cache/sycl", "runtime-tmp"):
            (RUN_ROOT / name).mkdir(parents=True, exist_ok=False)
        try:
            all_rows: list[Any] = []
            graph_evidence: dict[int, dict[str, Any]] = {}
            for depth in DEPTHS:
                stdout_path = RUN_ROOT / f"llama-bench-{depth}.json"
                stderr_path = RUN_ROOT / f"llama-bench-{depth}.stderr.log"
                with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
                    result = subprocess.run(
                        argv_for_depth(manifest, depth), cwd=REPO, env=environment,
                        stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                        timeout=manifest["lifecycle"]["timeout_seconds_per_context"], check=False,
                    )
                launched_depths.append(depth)
                if result.returncode != 0:
                    raise GateError(f"llama-bench depth {depth} exited {result.returncode}")
                rows = json.loads(stdout_path.read_text(encoding="utf-8"))
                if not isinstance(rows, list) or not rows:
                    raise GateError(f"llama-bench depth {depth} returned no JSON rows")
                if any(row.get("n_depth") != depth for row in rows if isinstance(row, dict)):
                    raise GateError(f"llama-bench depth {depth} returned a mismatched row")
                all_rows.extend(rows)
                summary = parse_graph_summary(stderr_path.read_text(encoding="utf-8", errors="replace"))
                graph_evidence[depth] = {**summary, "stderr_sha256": sha256_file(stderr_path)}
            _write_json(RUN_ROOT / "llama-bench.json", all_rows)
            _write_json(RUN_ROOT / "graph-evidence.json", {str(key): value for key, value in graph_evidence.items()})
            _write_json(RUN_ROOT / "metadata.json", metadata(manifest, libraries, graph_evidence))
            parser = subprocess.run(
                [sys.executable, "-B", str(PARSER), "--bench-json", str(RUN_ROOT / "llama-bench.json"),
                 "--metadata", str(RUN_ROOT / "metadata.json"), "--output", str(RUN_ROOT / "exact-depth-receipt.json"), "--create"],
                cwd=REPO, text=True, capture_output=True, check=False,
            )
            (RUN_ROOT / "parser.stdout.json").write_text(parser.stdout, encoding="utf-8")
            (RUN_ROOT / "parser.stderr.log").write_text(parser.stderr, encoding="utf-8")
            if parser.returncode != 0:
                raise GateError(f"exact-depth parser exited {parser.returncode}")
            receipt = load_json(RUN_ROOT / "exact-depth-receipt.json")
            cells = receipt.get("cells") or []
            if not (
                receipt.get("status") == "passed"
                and (receipt.get("gate") or {}).get("exact_cell_ready") is True
                and (receipt.get("graph") or {}).get("classification") == "verified-capture-and-replay"
                and len(cells) == 7
                and {cell.get("active_context_tokens") for cell in cells} == set(DEPTHS)
                and all((cell.get("selectors") or {}).get("graph_mode") == "on" for cell in cells)
                and set(graph_evidence) == set(DEPTHS)
            ):
                raise GateError("seven-cell graph receipt did not pass")
            BASE.require_idle()
            cleanup = True
            state = "passed-raw-graph-cells-quality-pending"
        except Exception as exc:
            error = str(exc)
            try:
                BASE.require_idle()
                cleanup = True
            except Exception as cleanup_exc:
                error = f"{error}; cleanup: {cleanup_exc}"
        terminal = {
            "schema": "neural.download.qwen36-llama-sycl-graph-exact-depth-terminal.v1",
            "campaign_id": CAMPAIGN_ID,
            "state": state,
            "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "lab_git_head": head,
            "launched_depths": launched_depths,
            "cleanup_passed": cleanup,
            "error": error,
            "cell_gain_if_ingested_after_quality_gate": 7 if state.startswith("passed-") else 0,
            "site_publication_authorized": False,
            "record_or_submission_authorized": False,
            "quality_claim_authorized": False,
            "graph_estimates_used": False,
            "protected_graph_off_values_replaced": False,
            "historical_featured_speeds_are_immutable": True,
        }
        _write_json(RUN_ROOT / "terminal-receipt.json", terminal)
    print(json.dumps(terminal, indent=2, sort_keys=True))
    return 0 if state.startswith("passed-") else 20


def plan(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "campaign_id": CAMPAIGN_ID,
        "state": manifest["state"],
        "sealing_status": manifest["sealing_status"],
        "default_is_inert": True,
        "output_root": str(RUN_ROOT),
        "declared_depths": DEPTHS,
        "ack": ACK,
        "graph_evidence_required_per_cell": True,
        "graph_estimates_forbidden": True,
        "site_publication_authorized": False,
        "protected_graph_off_values_must_not_be_replaced": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="run CPU-only sealed-identity checks")
    mode.add_argument("--execute", action="store_true", help="launch only the fully sealed GPU packet")
    parser.add_argument("--ack", default="", help="exact execution acknowledgement")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest()
        validate_manifest(manifest)
        if args.execute:
            return execute(args.ack)
        if args.check:
            static_check()
            result = {"status": "PASS", "launched": False, **plan(manifest)}
        else:
            result = plan(manifest)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (GateError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
