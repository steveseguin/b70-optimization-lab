#!/usr/bin/env python3
"""Write a hash-bound promotion attestation for a Flash-Next deterministic-line realistic-suite result.

Binds the realistic-suite benchmark JSON (performance evidence) to the
repository evidence that supports each required promotion gate: the frozen
client summaries (quality 6/7 with the inherited miss, 16/16 repeat, exact
needle, output pins equal across servers) and, for the MTP1 line, the trace
comparison proving the verification step bit-identical to MTP0.

    build-q38-flash-next-promotion-attestation.py --bench <realistic json> --out <attestation json>
        --profile-id <id> --runtime-revision <overlay head> --optimization-identity <text>
        --headline-note <text> [--evidence path:gate1,gate2 ...]
"""
from __future__ import annotations
import argparse, datetime, hashlib, json, statistics, sys
from pathlib import Path
sys.path.insert(0, "/home/steve/llm-optimizations/scripts")
from promotion_evidence import REQUIRED_GATES, validate_promotion_attestation  # noqa: E402
from qualify_realistic_window_metrics import qualify, promotion_evidence_failures  # noqa: E402

REPO = Path("/home/steve/llm-optimizations")
MODEL_REVISION = "bcd9f01ddc9cff2316eb84281bebcd5b058bddce"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bench", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--profile-id", required=True)
    ap.add_argument("--runtime-revision", required=True)
    ap.add_argument("--optimization-identity", required=True)
    ap.add_argument("--headline-note", required=True)
    ap.add_argument("--evidence", action="append", default=[], help="repo-relative path:gate,gate,...")
    ap.add_argument("--decision", default="promote")
    a = ap.parse_args()
    bench = qualify(json.loads(a.bench.read_text()))
    failures = promotion_evidence_failures(bench)
    if failures:
        sys.exit(f"{a.bench}: not promotion eligible: {', '.join(failures)}")
    summary = bench["summary"]
    primary = summary.get("class_balanced_tok_s_1_100_intervals_after_ttft") or summary["tok_s_1_100_after_ttft"]
    evidence = []
    for spec in a.evidence:
        path, gates = spec.split(":", 1)
        gl = [g for g in gates.split(",") if g]
        assert all(g in REQUIRED_GATES for g in gl), gl
        evidence.append({"path": path, "sha256": sha(REPO / path), "supports": gl})
    data = {
        "schema": "neural.download.promotion-attestation.v1",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile_id": a.profile_id,
        "decision": a.decision,
        "promotion_authorized": a.decision == "promote",
        "headline": {"value": primary["median"], "unit": "tok/s", "aggregation": "median of prompt-class medians, 99 inter-token intervals after TTFT, fixed realistic suite run once cold",
                     "metric_events": bench["realistic_final_gate"].get("metric_tokens"), "metric_intervals": bench["fresh_response_validity"].get("primary_metric_intervals"), "note": a.headline_note},
        "performance_evidence": {"path": str(a.bench.resolve().relative_to(REPO)) if str(a.bench.resolve()).startswith(str(REPO)) else str(a.bench.resolve()), "sha256": sha(a.bench)},
        "identity": {"model_revision": MODEL_REVISION, "runtime_revision": a.runtime_revision, "optimization_identity": a.optimization_identity,
                     "suite_sha256": sha(REPO / "repro/rapid-model-snapshots-b70/realistic-suite-v1.json")},
        "gates": {g: True for g in REQUIRED_GATES},
        "quality_evidence": evidence,
    }
    a.out.write_text(json.dumps(data, indent=2) + "\n")
    validate_promotion_attestation(a.out, a.bench, expected_model_revision=MODEL_REVISION, expected_runtime_revision=a.runtime_revision)
    print(json.dumps({"headline": data["headline"]["value"], "out": str(a.out), "evidence": len(evidence)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
