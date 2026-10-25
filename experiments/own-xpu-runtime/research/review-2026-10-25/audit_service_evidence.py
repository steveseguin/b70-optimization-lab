#!/usr/bin/env python3
"""CPU-only audit of retained SC117 observations; does not contact an endpoint.

Run from any directory; stdout is deterministic JSON. Original evidence is
never rewritten. Statistics here do not qualify a benchmark or establish GPU
correctness. Paths and hashes bind every input actually read by this audit.
"""
import hashlib
import json
from pathlib import Path
import statistics
import subprocess


ROOT = Path(__file__).resolve().parents[4]
LANE = Path("experiments/own-xpu-runtime")
SUITES = LANE / "gsq-rco-iq3s/service-speed/d-mtp-fp8/suite"
INPUTS = {}
PRODUCER_REVISION = '11eb60fb20a631d62158bcf91f3c81948657c32a'


def read(path, historical=False):
    data = (subprocess.check_output(["git", "show", f"{PRODUCER_REVISION}:{path}"], cwd=ROOT)
            if historical else (ROOT / path).read_bytes())
    INPUTS[str(path)] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    if historical:
        INPUTS[str(path)]["git_revision"] = PRODUCER_REVISION
    return data


def load(path):
    return json.loads(read(path))


def rows_by_id(doc):
    rows = doc["rows"]
    result = {row["prompt_id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError("duplicate prompt id")
    return result


def main():
    baseline_path = SUITES / "f32-suite-63ab006a.json"
    current_path = SUITES / "f32-suite-297b388764e9.json"
    baseline, current = load(baseline_path), load(current_path)
    a, b = rows_by_id(baseline), rows_by_id(current)
    pair = []
    for prompt in sorted(a.keys() | b.keys()):
        left, right = a.get(prompt), b.get(prompt)
        if left is None or right is None:
            raise ValueError("baseline/current prompt sets differ")
        pair.append({"prompt_id": prompt,
                     "prompt_token_ids_equal": left["prompt_token_ids"] == right["prompt_token_ids"],
                     "output_token_ids_present": isinstance(left.get("output_token_ids"), list)
                     and isinstance(right.get("output_token_ids"), list),
                     "output_token_ids_equal": left.get("output_token_ids") == right.get("output_token_ids"),
                     "stored_text_sha256_equal": left["output_sha256"] == right["output_sha256"],
                     "output_tokens": right["output_tokens"]})
    suite_stats = []
    for path in sorted((ROOT / SUITES).glob("f32-suite-*.json")):
        rel = path.relative_to(ROOT)
        doc = load(rel)
        rates = [row["decode_tok_s"] for row in doc["rows"]]
        guesses = sum(row["mtp"]["guesses"] for row in doc["rows"])
        hits = sum(row["mtp"]["hits"] for row in doc["rows"])
        suite_stats.append({"path": str(rel), "prompts": len(rates),
                            "reported_median_decode_tok_s": doc["median_decode_tok_s"],
                            "conventional_median_decode_tok_s": statistics.median(rates),
                            "upper_middle_decode_tok_s": sorted(rates)[len(rates) // 2],
                            "reported_uses_upper_middle": doc["median_decode_tok_s"] == sorted(rates)[len(rates) // 2],
                            "pooled_acceptance_recomputed": hits / guesses,
                            "totals_match": doc["hits"] == hits and doc["guesses"] == guesses,
                            "stored_scope": doc["scope"]})
    prefill_dir = LANE / "research/prefill"
    group_a = load(prefill_dir / "2026-10-25-pj-base-summary.json")
    group_b = load(prefill_dir / "2026-10-25-pj-group-summary.json")
    read(prefill_dir / "2026-10-25-grouped-attention.md")
    tp_dir = LANE / "research/tp/evidence"
    tp_timings = []
    for path in sorted((ROOT / tp_dir).glob("*-summary.json")):
        doc = load(path.relative_to(ROOT))
        vals = doc["half_ms"]
        tp_timings.append({"path": str(path.relative_to(ROOT)), "steps": len(vals),
                           "median_all_steps_ms": statistics.median(vals),
                           "median_omitting_first_two_ms": statistics.median(vals[2:]),
                           "first_two_steps_ms": vals[:2], "exit_code": doc["rc"],
                           "scope": "synthetic rank-1 half execution; not full-model decode"})
    comparisons = []
    for path in sorted((ROOT / tp_dir).glob("*-vs-*.json")):
        comparisons.append({"path": str(path.relative_to(ROOT)), "stored_comparison": load(path.relative_to(ROOT))})
    reference_path = LANE / "gsq-rco-iq3s/service-speed/e-reference/RESULT-F32.md"
    read(reference_path)
    # Preserve the identities of the producers whose limits matter here.
    for path in [SUITES / "run_suite.py", LANE / "engine/tools/tp_rank1_driver.py",
                 LANE / "gsq-rco-iq3s/serving/lan/service.py",
                 LANE / "gsq-rco-iq3s/serving/lan/adapter6.py",
                 LANE / "engine/src/stage2/packet194-expert-diet-engine/native_controller.hpp",
                 LANE / "research/tp/2026-10-25-exact-tp-closeout.md",
                 LANE / "stage2/packet126-early-draft/RESULTS.md",
                 LANE / "stage2/packet66-mtp-depth2-probe/README.md",
                 LANE / "stage2/packet66-mtp-depth2-probe/analyze.py",
                 LANE / "stage2/packet85-critical-path/MODEL.md",
                 Path("notes/2026-10-17-own-runtime-packet71c.md")]:
        read(path, historical=True)
    med_a = statistics.median(row["decode_tok_s"] for row in baseline["rows"])
    med_b = statistics.median(row["decode_tok_s"] for row in current["rows"])
    result = {
        "schema": "ownrt.retained-service-evidence-audit.v1",
        "scope": "offline arithmetic and stored-evidence audit; no GPU, endpoint, replay, or publication qualification",
        "producer_revision": PRODUCER_REVISION,
        "baseline_current": {"baseline": str(baseline_path), "current": str(current_path),
                             "median_decode_tok_s": [med_a, med_b], "ratio": med_b / med_a,
                             "per_prompt": pair,
                             "all_recorded_prompt_and_output_ids_match": all(
                                 row["prompt_token_ids_equal"] and row["output_token_ids_present"]
                                 and row["output_token_ids_equal"] and row["stored_text_sha256_equal"] for row in pair),
                             "limits": ["Text hashes are compared as stored; original response text is not in these summaries.",
                                        "Rates cover full natural responses (up to 512 tokens), not first-99 intervals or class-balanced primary rates.",
                                        "The historical suite producer checked cached_tokens but did not retain that field; missing usage defaulted to zero. Later harness fixes do not retroactively qualify these observations.",
                                        "These summary files alone do not bind the complete runtime and hardware identities."]},
        "suite_statistics": suite_stats,
        "grouped_prefill": {"rank": 1, "prompt_rows": group_a["prompt"],
                            "per_row_ms": [group_a["prompt_ms"] / group_a["prompt"], group_b["prompt_ms"] / group_b["prompt"]],
                            "elapsed_time_reduction_percent": 100 * (1 - group_b["prompt_ms"] / group_a["prompt_ms"]),
                            "throughput_increase_percent": 100 * (group_a["prompt_ms"] / group_b["prompt_ms"] - 1),
                            "four_decode_tokens_equal": group_a["tokens"] == group_b["tokens"],
                            "linked_summaries_include_state_hashes": False,
                            "scope": "one synthetic rank-1 warm-JIT harness pair, 3000 prompt rows and 4 decode steps",
                            "exactness_limit": "The note reports 1079 buffers equal; neither linked JSON includes the comparison or state hashes. This audit cannot independently substantiate that claim.",
                            "full_service_speedup_measured": False},
        "tp_timings": tp_timings,
        "tp_state_comparisons": comparisons,
        "tp_limits": ["Both all-step and first-two-omitted medians are exposed; this audit does not choose a new benchmark warmup policy.",
                      "The closeout's 16.72 ms balanced-slot figure matches a warm subset more closely than all 16 steps; keep timing definition explicit.",
                      "The 1.0-1.1x four-card expectation is a projection from this TP approach, not measured four-card performance or a general hardware ceiling."],
        "cpu_reference": {"source": str(reference_path), "positions": 5965, "disagreements": 6,
                          "agreement_percent": 100 * (5965 - 6) / 5965,
                          "scope": "reported teacher-forced CPU argmax on engine-generated prefixes; not free-running exact output parity",
                          "unresolved": True},
        "deeper_mtp": {"current_suite_retains_only_aggregate_guess_counts": True,
                       "k2_k3_accuracy_derivable_from_current_suite": False,
                       "reason": "Recursive proposals require the draft's own hypothetical prefix/state. Consecutive teacher-forced one-step hits do not measure recursive accuracy.",
                       "prior_depth_two_result": "packet126 RESULTS reports packet71c matched first99 loss of 46.758%; different historical arithmetic/runtime, not a result for current F32 SC117.",
                       "reusable_probe": "stage2/packet66-mtp-depth2-probe has a discarded recursive d2 probe, full draft-state backup/restore, and analyze.py joining actual proposals to confirmed outputs. Its retained fixtures and preparation are not current-model measured acceptance.",
                       "historical_trace_location": "stage2/packet71c-depth2-engine/screen/evidence/candidate-B/run/summary.json contains per-request guess_rows/rank_trace for the older depth-two engine. Not an input to this arithmetic audit; use packet85-critical-path/MODEL.md's per-tile interpretation before reanalysis.",
                       "next_measurement": "Retain actual recursive guesses, conditioning/state identity, target-confirmed tokens, per-depth prefix acceptance, and draft/rollback cost on untrained prompts."},
        "inputs": dict(sorted(INPUTS.items())),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
