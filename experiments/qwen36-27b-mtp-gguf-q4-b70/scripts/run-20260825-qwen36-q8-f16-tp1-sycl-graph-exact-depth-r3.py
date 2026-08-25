#!/usr/bin/env python3
"""R3 multi-summary evidence wrapper for the sealed R2 graph-depth curve.

R2's verbose argv and all runtime identities remain unchanged. R3 accepts one
or more graph summaries per isolated context only when every summary passes
the frozen accounting and mechanism gates, then returns one aggregate row.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
from typing import Any, Mapping


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
OVERLAY = LANE / "data/2026-08-25-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r3-prereg.json"
BASE_MANIFEST = LANE / "data/2026-08-25-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r2-prereg.json"
BASE_RUNNER = LANE / "scripts/run-20260825-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r2.py"
BASE_MANIFEST_SHA256 = "5c0446cf0b8b5cafdaf7a01f53045fba1a367c6c99fa7051a9b7d4e34e279b40"
BASE_RUNNER_SHA256 = "b9296c6c25caadd1542cab0a3b3da2317285a9851dcfaa1aae01b796b360d7d1"
CAMPAIGN_ID = "qwen36-q8-f16-tp1-sycl-graph-exact-depth-20260825-r3"
ACK = f"RUN {CAMPAIGN_ID}"
RUN_ROOT = Path("/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-sycl-graph-exact-depth-20260825-r3")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_r2():
    spec = importlib.util.spec_from_file_location("qwen36_q8_f16_sycl_graph_depth_r2_for_r3", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import R2 runner: {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


R2 = _load_r2()
R1 = R2.R1
GateError = R2.GateError
ORIGINAL_R2_LOAD_MANIFEST = R2.load_manifest


def _evidence_policy() -> dict[str, Any]:
    return {
        "collection": "one isolated llama-bench process per exact context; require one or more SYCL graph summaries and validate every summary independently before aggregation",
        "summary_count_minimum": 1,
        "validate_every_summary": True,
        "per_summary_requirements": {
            "device": 0,
            "cache_limit": 8,
            "compatibility_rejected": 0,
            "device_unsupported": 0,
            "cache_full": 0,
            "updated": 0,
            "recreated": 0,
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
        "aggregate": "sum all counters except cache_entries=max and summary_count=count",
    }


def load_overlay() -> dict[str, Any]:
    value = R1.load_json(OVERLAY)
    base = value.get("base") or {}
    delta = value.get("evidence_only_delta") or {}
    preserved = value.get("preserved") or {}
    lifecycle = value.get("lifecycle") or {}
    authority = value.get("authority") or {}
    expected_policy = _evidence_policy()
    if not (
        value.get("schema") == "neural.download.qwen36-llama-sycl-graph-exact-depth-multi-summary-overlay.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and base == {
            "manifest_path": str(BASE_MANIFEST.relative_to(REPO)),
            "manifest_sha256": BASE_MANIFEST_SHA256,
            "runner_path": str(BASE_RUNNER.relative_to(REPO)),
            "runner_sha256": BASE_RUNNER_SHA256,
        }
        and {key: delta.get(key) for key in expected_policy} == expected_policy
        and preserved == {
            "r2_verbose_argv": True,
            "contexts": R1.DEPTHS,
            "source_model_build_runtime_and_32_dso_closure": True,
            "selectors_environment_graph_gates_and_authority": True,
            "create_only_lifecycle": True,
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
        raise GateError("R3 multi-summary overlay invariant failed")
    return value


def load_manifest() -> dict[str, Any]:
    load_overlay()
    if sha256_file(BASE_MANIFEST) != BASE_MANIFEST_SHA256:
        raise GateError("sealed R2 base manifest changed")
    if sha256_file(BASE_RUNNER) != BASE_RUNNER_SHA256:
        raise GateError("sealed R2 base runner changed")
    value = copy.deepcopy(ORIGINAL_R2_LOAD_MANIFEST())
    value["campaign_id"] = CAMPAIGN_ID
    value["purpose"] += " R3 accepts multiple independently valid graph summaries per context and aggregates their counters."
    value["graph_evidence"].update(_evidence_policy())
    value["lifecycle"]["output_root"] = str(RUN_ROOT)
    value["lifecycle"]["exact_ack"] = ACK
    return value


def validate_manifest(value: Mapping[str, Any]) -> None:
    expected = load_manifest()
    if dict(value) != expected:
        raise GateError("R3 synthesized manifest differs from sealed overlay")
    base = ORIGINAL_R2_LOAD_MANIFEST()
    reconstructed = copy.deepcopy(dict(value))
    reconstructed["campaign_id"] = base["campaign_id"]
    reconstructed["purpose"] = base["purpose"]
    reconstructed["graph_evidence"] = copy.deepcopy(base["graph_evidence"])
    reconstructed["lifecycle"]["output_root"] = base["lifecycle"]["output_root"]
    reconstructed["lifecycle"]["exact_ack"] = base["lifecycle"]["exact_ack"]
    if reconstructed != base:
        raise GateError("R3 changes more than campaign lifecycle identity and graph-summary evidence policy")
    if value["argv_template"][-3:] != ["-v", "-o", "json"]:
        raise GateError("R3 must preserve R2's exact verbose argv")


def parse_graph_summary(text: str) -> dict[str, int]:
    matches = list(R1.SUMMARY_RE.finditer(text))
    if not matches:
        raise GateError("expected one or more SYCL graph summaries, got 0")
    summaries = [
        {name: int(item) for name, item in match.groupdict().items()}
        for match in matches
    ]
    for index, summary in enumerate(summaries, start=1):
        if not (
            summary["device"] == 0
            and summary["cache_limit"] == 8
            and summary["compatibility_rejected"] == 0
            and summary["device_unsupported"] == 0
            and summary["cache_full"] == 0
            and summary["updated"] == 0
            and summary["recreated"] == 0
            and summary["requested"] > 0
            and summary["recorded"] > 0
            and summary["created"] > 0
            and summary["cache_hit"] > 0
            and summary["direct_replay"] > 0
            and summary["replayed"] > 0
            and summary["requested"] == summary["cache_hit"] + summary["cache_miss"]
            and summary["cache_hit"] == summary["direct_replay"]
            and summary["cache_miss"] == summary["recorded"] == summary["created"]
            and summary["replayed"] == summary["requested"]
        ):
            raise GateError(f"graph summary {index} evidence gate failed: {summary}")
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
            "summary_count": len(summaries),
        }
    )
    return aggregate


# Rebind the R1 lifecycle reached through R2 to the distinct create-only R3 identity.
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
