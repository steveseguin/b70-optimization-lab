#!/usr/bin/env python3
"""R4 phase-aware cache-8 evidence wrapper for the sealed R3 curve."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r4-prereg.json"
BASE_MANIFEST = LANE / "data/2026-08-25-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r3-prereg.json"
BASE_RUNNER = LANE / "scripts/run-20260825-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r3.py"
BASE_MANIFEST_SHA256 = "4b00014de1684b945679ff4e9afe686c6549d519b6a5c8808e0184a280b2a447"
BASE_RUNNER_SHA256 = "281a15e0c2327028cb042a6d3f9a9a78e93998427c341dc3b36334556c26dd19"
CAMPAIGN_ID = "qwen36-q8-f16-tp1-sycl-graph-exact-depth-20260825-r4"
ACK = f"RUN {CAMPAIGN_ID}"
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-sycl-graph-exact-depth-20260825-r4")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_r3():
    spec = importlib.util.spec_from_file_location("qwen36_q8_f16_sycl_graph_depth_r3_for_r4", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import R3 runner: {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


R3 = _load_r3()
R1 = R3.R1
GateError = R3.GateError
ORIGINAL_R3_LOAD_MANIFEST = R3.load_manifest


def _evidence_policy() -> dict[str, Any]:
    return {
        "collection": "one isolated llama-bench process per exact context; require exactly two ordered SYCL graph summaries mapped by llama-bench contract to prefill then decode",
        "summary_count_exact": 2,
        "ordered_phases": ["prefill", "decode"],
        "common_requirements": {
            "device": 0,
            "cache_limit": 8,
            "compatibility_rejected": 0,
            "device_unsupported": 0,
            "updated": 0,
            "recreated": 0,
        },
        "prefill_requirements": {
            "cache_full_permitted": True,
            "requested_equals_cache_hit_plus_cache_miss": True,
            "cache_hit_equals_direct_replay": True,
            "recorded_equals_created": True,
            "replayed_equals_cache_hit_plus_created": True,
            "cache_full_equals_cache_miss_minus_created": True,
            "requested_equals_replayed_plus_cache_full": True,
            "requested_positive": True,
            "recorded_positive": True,
            "created_positive": True,
            "replayed_positive": True,
        },
        "decode_requirements": {
            "cache_full": 0,
            "requested_equals_cache_hit_plus_cache_miss": True,
            "cache_hit_equals_direct_replay": True,
            "cache_miss_equals_recorded_equals_created": True,
            "replayed_equals_requested": True,
            "requested_positive": True,
            "recorded_positive": True,
            "created_positive": True,
            "cache_hit_positive": True,
            "direct_replay_positive": True,
            "replayed_positive": True,
        },
        "aggregate": "sum all counters except cache_entries=max and summary_count=2; retain raw ordered prefill/decode summaries",
        "prefill_classification_when_cache_full_positive": "mixed-partial-graph; not fully graph certified",
    }


def load_overlay() -> dict[str, Any]:
    value = R1.load_json(OVERLAY)
    base = value.get("base") or {}
    runtime = value.get("runtime_identity") or {}
    evidence = value.get("evidence_delta") or {}
    preserved = value.get("preserved") or {}
    lifecycle = value.get("lifecycle") or {}
    authority = value.get("authority") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-sycl-graph-exact-depth-phase-aware-overlay.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and base == {
            "manifest_path": str(BASE_MANIFEST.relative_to(REPO)),
            "manifest_sha256": BASE_MANIFEST_SHA256,
            "runner_path": str(BASE_RUNNER.relative_to(REPO)),
            "runner_sha256": BASE_RUNNER_SHA256,
        }
        and runtime == {"identical_to_r3": True, "GGML_SYCL_GRAPH_CACHE_SIZE": "8"}
        and evidence == _evidence_policy()
        and preserved == {
            "r3_verbose_argv": True,
            "contexts": R1.DEPTHS,
            "source_model_build_runtime_and_32_dso_closure": True,
            "selectors_and_environment": True,
            "create_only_lifecycle": True,
            "authority": True,
        }
        and lifecycle == {"output_root": str(RUN_ROOT), "exact_ack": ACK}
        and authority == {
            "raw_cells_require_all_existing_gates": True,
            "site_publication_authorized": False,
            "record_or_submission_authorized": False,
            "quality_claim_authorized": False,
            "graph_estimates_forbidden": True,
            "protected_graph_off_values_must_not_be_replaced": True,
        }
    ):
        raise GateError("R4 phase-aware cache-8 overlay invariant failed")
    return value


def load_manifest() -> dict[str, Any]:
    load_overlay()
    if sha256_file(BASE_MANIFEST) != BASE_MANIFEST_SHA256:
        raise GateError("sealed R3 base manifest changed")
    if sha256_file(BASE_RUNNER) != BASE_RUNNER_SHA256:
        raise GateError("sealed R3 base runner changed")
    value = copy.deepcopy(ORIGINAL_R3_LOAD_MANIFEST())
    value["campaign_id"] = CAMPAIGN_ID
    value["purpose"] += " R4 interprets exactly two cache-8 summaries as ordered prefill and decode phases with phase-specific conservation gates."
    value["graph_evidence"].update(_evidence_policy())
    value["lifecycle"]["output_root"] = str(RUN_ROOT)
    value["lifecycle"]["exact_ack"] = ACK
    return value


def validate_manifest(value: Mapping[str, Any]) -> None:
    expected = load_manifest()
    if dict(value) != expected:
        raise GateError("R4 synthesized manifest differs from sealed overlay")
    base = ORIGINAL_R3_LOAD_MANIFEST()
    reconstructed = copy.deepcopy(dict(value))
    reconstructed["campaign_id"] = base["campaign_id"]
    reconstructed["purpose"] = base["purpose"]
    reconstructed["graph_evidence"] = copy.deepcopy(base["graph_evidence"])
    reconstructed["lifecycle"]["output_root"] = base["lifecycle"]["output_root"]
    reconstructed["lifecycle"]["exact_ack"] = base["lifecycle"]["exact_ack"]
    if reconstructed != base:
        raise GateError("R4 changes more than campaign identity and phase-aware evidence policy")
    if value["argv_template"][-3:] != ["-v", "-o", "json"]:
        raise GateError("R4 must preserve R3's exact verbose argv")


def parse_graph_summary(text: str) -> dict[str, Any]:
    matches = list(R1.SUMMARY_RE.finditer(text))
    if len(matches) != 2:
        raise GateError(f"expected exactly two ordered SYCL graph summaries, got {len(matches)}")
    summaries = [
        {name: int(item) for name, item in match.groupdict().items()}
        for match in matches
    ]
    for phase, summary in zip(("prefill", "decode"), summaries, strict=True):
        if not (
            summary["device"] == 0
            and summary["cache_limit"] == 8
            and summary["compatibility_rejected"] == 0
            and summary["device_unsupported"] == 0
            and summary["updated"] == 0
            and summary["recreated"] == 0
        ):
            raise GateError(f"{phase} graph summary common gate failed: {summary}")
    prefill, decode = summaries
    if not (
        prefill["requested"] > 0
        and prefill["recorded"] > 0
        and prefill["created"] > 0
        and prefill["replayed"] > 0
        and prefill["requested"] == prefill["cache_hit"] + prefill["cache_miss"]
        and prefill["cache_hit"] == prefill["direct_replay"]
        and prefill["recorded"] == prefill["created"]
        and prefill["replayed"] == prefill["cache_hit"] + prefill["created"]
        and prefill["cache_full"] == prefill["cache_miss"] - prefill["created"]
        and prefill["requested"] == prefill["replayed"] + prefill["cache_full"]
    ):
        raise GateError(f"prefill graph summary evidence gate failed: {prefill}")
    if not (
        decode["cache_full"] == 0
        and decode["requested"] > 0
        and decode["recorded"] > 0
        and decode["created"] > 0
        and decode["cache_hit"] > 0
        and decode["direct_replay"] > 0
        and decode["replayed"] > 0
        and decode["requested"] == decode["cache_hit"] + decode["cache_miss"]
        and decode["cache_hit"] == decode["direct_replay"]
        and decode["cache_miss"] == decode["recorded"] == decode["created"]
        and decode["replayed"] == decode["requested"]
    ):
        raise GateError(f"decode graph summary evidence gate failed: {decode}")
    aggregate = {
        key: sum(summary[key] for summary in summaries)
        for key in summaries[0]
        if key not in {"device", "cache_entries", "cache_limit"}
    }
    aggregate.update(
        {
            "device": 0,
            "cache_entries": max(summary["cache_entries"] for summary in summaries),
            "cache_limit": 8,
            "summary_count": 2,
            "phases": {"prefill": prefill, "decode": decode},
            "prefill_graph_classification": (
                "mixed-partial-cache-full" if prefill["cache_full"] > 0
                else "capture-and-replay-without-cache-full"
            ),
            "prefill_fully_graph_certified": prefill["cache_full"] == 0,
            "decode_graph_classification": "verified-capture-and-replay",
        }
    )
    return aggregate


# Rebind the inherited mature lifecycle to the distinct create-only R4 identity.
R1.MANIFEST = OVERLAY
R1.CAMPAIGN_ID = CAMPAIGN_ID
R1.ACK = ACK
R1.RUN_ROOT = RUN_ROOT
R1.load_manifest = load_manifest
R1.validate_manifest = validate_manifest
R1.parse_graph_summary = parse_graph_summary


def main(argv: list[str] | None = None) -> int:
    return R1.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
