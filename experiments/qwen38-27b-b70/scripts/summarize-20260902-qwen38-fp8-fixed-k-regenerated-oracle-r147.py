#!/usr/bin/env python3
"""Build the R147 structured result from the campaign artifact root.

Gates follow experiments/qwen38-27b-b70/data/
2026-09-02-qwen38-fp8-mtp1-fixed-k-regenerated-oracle-r147-prereg.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

R119_CENTER = 54.42460323814495
R62_FLOOR_99 = 53.88
R54_MTP0_CENTER = 33.733520
INCUMBENT = 51.80808698870573
MARKER = "Prepared MTP draft-only INT4 lm_head from the loaded target weight; the target verifier lm_head remains FP16."


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def compare(root: Path, name: str) -> str | None:
    p = root / f"compare-{name}.json"
    if not p.exists():
        return None
    c = json.loads(p.read_text())["comparison"]
    return f"{c['exact_prompts']}/{c['total_prompts']}"


def attempt(root: Path, label: str) -> dict:
    d = root / label
    out = {"label": label, "present": (d / "strict" / "performance.json").exists()}
    if not out["present"]:
        return out
    perf = json.loads((d / "strict" / "performance.json").read_text())
    can = json.loads((d / "strict" / "canaries.json").read_text())
    pre = json.loads((d / "pre-canaries.json").read_text()) if (d / "pre-canaries.json").exists() else {}
    log = (d / "server.log").read_text(errors="replace") if (d / "server.log").exists() else ""
    out.update({
        "class_balanced_median_tok_s": perf["summary"]["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"],
        "rows": len(perf["rows"]),
        "cached_tokens_all_zero": perf["fresh_response_validity"]["cached_tokens_all_zero"],
        "realistic_final_gate_passed": perf["realistic_final_gate"]["passed"],
        "pre_canaries_pass_all": pre.get("pass_all"),
        "post_canaries_pass_all": can.get("pass_all"),
        "fp16_target_int4_draft_marker_count": log.count(MARKER),
        "server_fault_lines": (d / "server-fault-lines.txt").stat().st_size if (d / "server-fault-lines.txt").exists() else None,
        "performance_sha256": sha(d / "strict" / "performance.json"),
        "server_log_sha256": sha(d / "server.log"),
    })
    return out


def probe(root: Path) -> dict | None:
    p = root / "mtp1-b" / "medium-prefill-probe.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    res = [{
        "prompt_tokens": r["actual_prompt_tokens"],
        "distinct_token_id_streams": r["distinct_token_id_streams"],
        "distinct_token_logprob_arrays": r["distinct_token_logprob_arrays"],
        "top_logprobs_identical": r["top_logprobs_identical"],
        "cached_tokens_all_zero": r["cached_tokens_all_zero"],
        "repeat_exact": r["token_ids_identical"] and r["token_logprobs_identical"] and r["top_logprobs_identical"],
    } for r in d["results"]]
    return {"results": res, "all_lengths_repeat_exact": all(r["repeat_exact"] and r["cached_tokens_all_zero"] for r in res), "sha256": sha(p)}


def ladder(root: Path) -> dict | None:
    p = root / "ladder" / "ladder.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    rc = (root / "ladder" / "ladder.rc").read_text().strip() if (root / "ladder" / "ladder.rc").exists() else None
    pts = [{"concurrency": b["concurrency"], "aggregate_tok_s_wall": b["aggregate_tok_s_wall"],
            "exact_vs_sequential_oracle": f"{b['oracle_exact_count']}/{b['oracle_exact_total']}",
            "cached_tokens_all_zero": b["cached_tokens_all_zero"]} for b in d["batches"]]
    iq = d["identity_qualification"]
    return {"classification": d["classification"], "harness_exit_status": rc, "points": pts,
            "complete_outputs_exact_vs_sequential_oracle": iq["complete_outputs_exact_vs_sequential_oracle"],
            "oracle_request_count": d["oracle"]["request_count"], "oracle_cached_tokens_all_zero": d["oracle"]["cached_tokens_all_zero"],
            "r63_reference_c64_tok_s": {"r62_candidate": 1080.8510149755805, "fp16_draft_control": 1061.6455536117264}, "sha256": sha(p)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/mnt/fast-ai/bench-results/qwen38-fp8-fixed-k-regenerated-oracle-20260902-r147"))
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    root = a.root
    atts = {l: attempt(root, l) for l in ("mtp0-a", "mtp0-b", "mtp1-a", "mtp1-b")}
    g = {
        "G1_mtp0_a_vs_mtp0_b": compare(root, "mtp0-a-vs-mtp0-b"),
        "G2_mtp1_a_vs_mtp1_b": compare(root, "mtp1-a-vs-mtp1-b"),
        "G3_mtp1_a_vs_mtp0_a": compare(root, "mtp1-a-vs-mtp0-a"),
        "G3_mtp1_b_vs_mtp0_a": compare(root, "mtp1-b-vs-mtp0-a"),
        "information_mtp0_a_vs_frozen_r54a": compare(root, "mtp0-a-vs-r54a"),
        "information_mtp1_a_vs_frozen_r54a": compare(root, "mtp1-a-vs-r54a"),
    }
    pr = probe(root)
    ld = ladder(root)
    g4 = all(x.get("present") and x["rows"] == 12 and x["cached_tokens_all_zero"] and x["realistic_final_gate_passed"]
             and x["pre_canaries_pass_all"] and x["post_canaries_pass_all"] for x in atts.values())
    mtp1_marker = all(atts[l].get("fp16_target_int4_draft_marker_count") == 2 for l in ("mtp1-a", "mtp1-b"))
    passed = {
        "G1": g["G1_mtp0_a_vs_mtp0_b"] == "12/12", "G2": g["G2_mtp1_a_vs_mtp1_b"] == "12/12",
        "G3": g["G3_mtp1_a_vs_mtp0_a"] == "12/12" and g["G3_mtp1_b_vs_mtp0_a"] == "12/12",
        "G4": g4 and mtp1_marker, "G5": bool(pr and pr["all_lengths_repeat_exact"]),
        "G6": bool(ld and ld["harness_exit_status"] == "0" and ld["complete_outputs_exact_vs_sequential_oracle"]),
    }
    identity = all(passed.values())
    m1 = [atts[l]["class_balanced_median_tok_s"] for l in ("mtp1-a", "mtp1-b") if atts[l].get("present")]
    m0 = [atts[l]["class_balanced_median_tok_s"] for l in ("mtp0-a", "mtp0-b") if atts[l].get("present")]
    perf = {"not_a_gate": True, "mtp1_attempts_tok_s": m1, "mtp0_attempts_tok_s": m0}
    if len(m1) == 2:
        c = statistics.median(m1); perf.update({"mtp1_center_tok_s": c, "delta_vs_r119_center_percent": (c / R119_CENTER - 1) * 100,
            "uplift_vs_incumbent_percent": (c / INCUMBENT - 1) * 100, "each_attempt_above_r62_99pct_floor": all(v >= R62_FLOOR_99 for v in m1),
            "within_r119_noise_band": c >= 0.99 * R119_CENTER})
    if len(m0) == 2:
        c0 = statistics.median(m0); perf.update({"mtp0_center_tok_s": c0, "mtp0_delta_vs_r54_control_percent": (c0 / R54_MTP0_CENTER - 1) * 100})
        if len(m1) == 2:
            perf["mtp1_over_mtp0_same_image_percent"] = (perf["mtp1_center_tok_s"] / c0 - 1) * 100
    aborted = (root / "ABORTED").read_text().strip() if (root / "ABORTED").exists() else None
    complete = (root / "campaign-end.txt").exists()
    if identity:
        cls = "identity-qualified within the noise band of R119" if perf.get("within_r119_noise_band") else f"identity-qualified, speed-regressed by {-perf.get('delta_vs_r119_center_percent', 0):.3f}% vs R119"
    else:
        cls = "aborted: " + aborted if aborted else "identity gate failed: " + ", ".join(k for k, v in passed.items() if not v)
    result = {
        "schema": "b70-lab.result.v1", "campaign_id": "qwen38-fp8-fixed-k-regenerated-oracle-20260902-r147",
        "preregistration": "experiments/qwen38-27b-b70/data/2026-09-02-qwen38-fp8-mtp1-fixed-k-regenerated-oracle-r147-prereg.json",
        "status": cls, "campaign_complete": complete, "aborted": aborted,
        "boot_id": (root / "boot-id.txt").read_text().strip() if (root / "boot-id.txt").exists() else None,
        "repo_head_at_launch": (root / "repo-head.txt").read_text().strip() if (root / "repo-head.txt").exists() else None,
        "image_id": "sha256:901ae9e0ade0109e94dd162d0cf2c398440325b1791f3191376fa0013dc29878",
        "gates_passed": passed, "identity_qualified": identity, "comparisons": g, "attempts": atts,
        "medium_prefill_repeat_probe": pr, "identity_ladder": ld, "performance": perf,
        "postflight_files": sorted(p.name for p in root.glob("*-post-*")),
    }
    a.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": cls, "gates": passed, "performance": {k: v for k, v in perf.items() if k != "not_a_gate"}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
