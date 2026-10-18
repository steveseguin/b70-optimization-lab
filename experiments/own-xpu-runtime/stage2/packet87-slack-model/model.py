#!/usr/bin/env python3
"""Packet87: CPU-only row-split DAG model; no runtime or device imports.

nice -n 19 taskset -c 8-15,24-31 python3 -B .../model.py [--check] </dev/null
Only DECISION.json beside this file is written. Unknown DMA stays unknown.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics as st

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = HERE.parents[3]
spec = importlib.util.spec_from_file_location("packet85_model", STAGE / "packet85-critical-path/model.py")
p85 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p85)  # functions only; main is not invoked; 4 GiB AS cap


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    prior = p85.load(STAGE / "packet85-critical-path/model.json")
    for path in (Path(__file__), STAGE / "packet85-critical-path/model.py",
                 STAGE / "packet85-critical-path/MODEL.md",
                 STAGE / "packet77-attribution/native_controller.hpp",
                 STAGE / "packet77-attribution/rank.hpp",
                 STAGE / "packet77-attribution/mtp.hpp",
                 STAGE / "packet77-attribution/p56_config.hpp",
                 STAGE / "packet77-attribution/core_v2.hpp",
                 STAGE / "packet79-draft-rank0/DO-NOT-REPEAT.md",
                 STAGE / "packet45-merged3/DO-NOT-REPEAT.md",
                 STAGE / "packet76-rank1-host/ATTRIBUTION.md"):
        p85.read(path)
    receipts = [p85.load(path) for path in sorted((p85.P77 / "control").glob("*/receipt.json"))]
    assert len(receipts) == 12
    requests = [(r, p85.intervals(r)) for r in receipts]
    rows = [row for _, rr in requests for row in rr]
    c = p85.components(rows)
    assert c == prior["baseline"]["components_ms"]
    assert len(rows) == 1188 and sum(r["hit"] for r in rows) == 936
    probability = prior["baseline"]["median_acceptance"]
    baseline_rate = p85.rate(c, probability)
    control_summary = p85.load(p85.P77 / "control/summary.json")
    root_summary = p85.load(p85.P77 / "summary.json")
    observed = control_summary["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]
    assert all(r["attribution_arm"] == "control" for r in control_summary["requests"])
    assert all(r["attribution_arm"] == "attribution" for r in root_summary["requests"])
    assert root_summary["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"] == prior["baseline"]["observed_class_balanced_tok_s"]
    attr = p85.load(p85.P77 / "attribution-summary.json")
    outside = {x["site"]: x["measured"]["mean_us"] / 1000 for x in attr["rank1_outside_split"]}
    draft = {x["category"]: x["measured"]["mean_us"] / 1000 for x in attr["draft_breakdown"]}
    head, prefix = outside["target_head"], draft["head_prefix"]
    target_argmax, draft_argmax = outside["argmax"], draft["argmax"]
    boundaries = {key: p85.stats(r[key] for r in rows) for key in (
        "handoff_ready_to_rank1_ms", "draft_issue_after_emission_ms", "emission_after_race_ms")}
    handoff = boundaries["handoff_ready_to_rank1_ms"]["mean"]
    issue = boundaries["draft_issue_after_emission_ms"]["mean"]
    collect = boundaries["emission_after_race_ms"]["mean"]
    # These are measured HOST boundary costs transplanted as a pricing proxy.
    # They do NOT measure reverse D2H/H2D or the pair readback. Missing DMA
    # durations remain explicit nonnegative variables, not zero measurements.
    known = {"export_publish": handoff, "import_issue": issue, "return_merge": handoff + collect}
    transfer_counts = {}
    for path, expected in attr["sources"].items():
        if path.endswith("rank1/sites.jsonl"):
            raw = p85.read(ROOT / path)
            assert p85.SOURCES[path] == expected
            for line in raw.splitlines():
                event = json.loads(line)
                if event.get("class") != "transfers":
                    continue
                label = event["label"]
                count = transfer_counts.setdefault(label, {"events": 0, "zero_width": 0})
                count["events"] += 1
                count["zero_width"] += event["start_ns"] == event["end_ns"]
    # Pin inputs already present in packet85's retained manifest.
    checked = 0
    for path, sha in p85.SOURCES.items():
        if path in prior["source_sha256"]:
            assert sha == prior["source_sha256"][path], f"packet85 source changed: {path}"
            checked += 1

    def costs(extra=(0.0, 0.0, 0.0)):
        return tuple(known[k] + u for k, u in zip(known, extra))

    def target_race(B, A, k, extra=(0.0, 0.0, 0.0), rank0_factor=1.0):
        if k == 248320:
            return max(B, A)  # untouched no-split control; no new charges
        E, I, V = costs(extra)
        fraction = k / 248320
        L = B - head - target_argmax
        # All retained non-head work is conservatively before head readiness.
        # Export stalls rank1; import waits for rank0 speculation, so there is
        # no assumed transfer/compute overlap on rank0 and no resource sharing.
        rank1 = L + E + fraction * head + target_argmax
        rank0 = max(A, L + E) + I + (1 - fraction) * head * rank0_factor + target_argmax
        return max(rank1, rank0) + V

    def draft_time(D, k, extra=(0.0, 0.0, 0.0), rank0_factor=1.0):
        if k == 91392:
            return D
        E, I, V = costs(extra)
        fraction = k / 91392
        # Both local argmaxes pay the measured FULL prefix reduction time.
        # Neither reduction nor the final norm is scaled down with row count.
        return (D - prefix - draft_argmax + E +
                max(fraction * prefix + draft_argmax,
                    I + (1 - fraction) * prefix * rank0_factor + draft_argmax) + V)

    def paths(option, config, k, extra=(0.0, 0.0, 0.0), rank0_factor=1.0):
        changed = dict(config)
        if option == "target":
            A = config["A"] + config["spec_offset"]
            changed["Bh"] = target_race(config["Bh"], A, k, extra, rank0_factor)
            changed["Bm"] = target_race(config["Bm"], A, k, extra, rank0_factor)
        else:
            changed["D"] = draft_time(config["D"], k, extra, rank0_factor)
        h, m = p85.paths(changed)
        if option == "draft":
            # Explicit hit-only dispatch: absolutely no new miss command,
            # transfer, allocation, reduction or wait in the timing model.
            m = p85.paths(config)[1]
        return h, m

    def evaluate(option, k, extra=(0.0, 0.0, 0.0), rank0_factor=1.0):
        h, m = paths(option, c, k, extra, rank0_factor)
        rate = 1000 / (probability * h + (1 - probability) * m)
        return {"k_rank1_rows": k, "rank0_rows": (248320 if option == "target" else 91392) - k,
                "hit_ms": h, "miss_ms": m, "predicted_tok_s": rate,
                "gain_percent_vs_measured_control": 100 * (rate / observed - 1),
                "gain_percent_vs_packet85_model": 100 * (rate / baseline_rate - 1),
                "unmeasured_extra_ms_export_import_return": list(extra),
                "rank0_head_time_multiplier": rank0_factor}

    def optimum(option, extra=(0.0, 0.0, 0.0), rank0_factor=1.0):
        n = 248320 if option == "target" else 91392
        grid = [evaluate(option, k, extra, rank0_factor) for k in range(256, n + 1, 256)]
        return max(grid, key=lambda r: (r["predicted_tok_s"], r["k_rank1_rows"]))

    def replay(option, k, extra=(0.0, 0.0, 0.0)):
        pairs, detail, miss_deltas, hit_deltas = [], [], [], []
        for request, rr in requests:
            times = []
            for row in rr:
                cc = {key: row[key] for key in ("A", "D", "R", "C")}
                cc.update(Bh=row["B"], Bm=row["B"], spec_offset=row["spec_start_offset_ms"],
                          Gh=row["unresolved_control_gaps_ms"], Gm=row["unresolved_control_gaps_ms"])
                h, m = paths(option, cc, k, extra)
                new = h if row["hit"] else m
                times.append(new)
                (hit_deltas if row["hit"] else miss_deltas).append(new - row["elapsed_ms"])
            predicted = 99000 / sum(times)
            pairs.append((request["prompt_class"], predicted))
            detail.append({"prompt_id": request["prompt_id"], "prompt_class": request["prompt_class"],
                           "hits": sum(row["hit"] for row in rr), "intervals": len(rr),
                           "observed_tok_s": request["tok_s_1_100_intervals_after_ttft"],
                           "predicted_tok_s": predicted})
        balanced = p85.balanced(pairs)
        return {"class_balanced_predicted_tok_s": balanced,
                "gain_percent_vs_measured": 100 * (balanced / observed - 1),
                "hit_change_ms": p85.stats(hit_deltas), "miss_change_ms": p85.stats(miss_deltas),
                "misses_worsened": sum(x > 1e-9 for x in miss_deltas), "requests": detail}

    options = {}
    for option in ("target", "draft"):
        best = optimum(option)
        k = best["k_rank1_rows"]
        n = 248320 if option == "target" else 91392
        # Reoptimize each uncertainty arm; never freeze a favorable k and
        # describe it as universally optimal. Zero is a lower-bound scenario.
        sensitivity = [{"extra_each_leg_ms": u, "extra_roundtrip_sum_ms": 3 * u,
                        "best": optimum(option, (u, u, u))} for u in (0, .025, .05, .075, .1, .2)]
        budgets = {}
        for label, direction in {"export_only": (1, 0, 0), "import_only": (0, 1, 0),
                                 "return_only": (0, 0, 1), "equal_three_legs": (1, 1, 1)}.items():
            lo, hi = 0.0, 1.0
            for _ in range(45):
                mid = (lo + hi) / 2
                arm = optimum(option, tuple(mid * x for x in direction))
                if arm["gain_percent_vs_measured_control"] >= .5:
                    lo = mid
                else:
                    hi = mid
            budgets[label] = {"maximum_extra_ms_per_active_leg": lo,
                              "maximum_extra_total_ms": lo * sum(direction),
                              "best_at_threshold": optimum(option, tuple(lo * x for x in direction))}
        perrow = replay(option, k)
        assert perrow["misses_worsened"] == 0
        no_split = evaluate(option, n)
        assert math.isclose(no_split["predicted_tok_s"], baseline_rate, abs_tol=1e-12)
        assert math.isclose(replay(option, n)["class_balanced_predicted_tok_s"], observed, abs_tol=1e-10)
        E, I, V = costs()
        continuous = (248320 * (1 - (c["Bh"] - c["A"] - c["spec_offset"] + E - I - target_argmax) / (2 * head))
                      if option == "target" else 91392 * (prefix + I) / (2 * prefix))
        options[option] = {
            "status": "closeout_inconclusive_for_sealing",
            "seal_ready": False,
            "reason": "Known-host-boundary scenario clears 0.5%, but new reverse DMA/readback costs are not identified by packet77; no full-cost prediction can be sealed.",
            "head_rows": n, "split_alignment": 256,
            "continuous_k_known_boundary_scenario": continuous,
            "known_boundary_only_optimum": best,
            "conditional_first99_replay": perrow,
            "unmeasured_transfer_sensitivity": sensitivity,
            "additional_transfer_budgets_for_0_5_percent_vs_measured": budgets,
            "rank0_bandwidth_sensitivity": [optimum(option, rank0_factor=f) for f in (1, 1.1, 1.25, 1.5, 2)],
            "rank0_added_head_allocation_bytes": best["rank0_rows"] * 3380,
            "rank0_added_logit_bytes": best["rank0_rows"] * 2,
            "miss_policy": "Same target split after unchanged parallel draft/repair" if option == "target" else "Entire original draft stays on rank1; split disabled before dispatch",
        }
    result = {
        "schema": "own-runtime.packet87.slack-model.v1",
        "date": "2026-10-18", "diagnostic": True, "device_executed": False,
        "engine_code_written": False, "submission_eligible": False,
        "decision": "closeout_inconclusive_for_sealing", "seal_ready": False,
        "identity": prior["identity"],
        "baseline": {"components_ms": c, "acceptance": probability,
                     "modeled_tok_s": baseline_rate, "measured_tok_s": observed,
                     "packet85_labeled_observed_tok_s": prior["baseline"]["observed_class_balanced_tok_s"],
                     "identity_correction": "packet85 read run/summary.json (attribution arm, 54.06389572), not run/control/summary.json (uninstrumented control, 54.10652897); components remain unchanged",
                     "hit_ms": p85.paths(c)[0], "miss_ms": p85.paths(c)[1],
                     "intervals": len(rows), "hits": sum(r["hit"] for r in rows), "misses": 252},
        "measured_head_ms": {"target": head, "draft_prefix": prefix,
                             "target_argmax": target_argmax, "draft_argmax": draft_argmax},
        "handoff_accounting": {
            "measured_host_boundaries_ms": boundaries,
            "new_host_boundary_proxy_ms": known,
            "measured_total_new_host_boundary_proxy_ms": sum(known.values()),
            "missing": ["rank1 D2H final.mix and its wait", "rank0 H2D final.mix and its wait",
                        "rank0 local-best/finite-status readback and wait",
                        "incremental rank1 local-best value/status readback", "incremental host merge work"],
            "missing_cost_value": None,
            "zero_means": "Optimistic lower-bound scenario only; not measured zero DMA latency",
            "transfer_events": transfer_counts,
            "old_Gh_Gm": "Retained unchanged; new boundary proxies price only additional operations",
        },
        "equations": {
            "target_L": "B - target_head - target_argmax (conservative virtual ready time)",
            "target_race": "max(L+E+k/N*head+J, max(A+offset,L+E)+I+(1-k/N)*head*rank0_factor+J)+V",
            "target_hit": "D + target_race(Bh) + Gh",
            "target_miss": "max(D,R+C) + target_race(Bm) + Gm",
            "draft_hit_D": "D-P-Jd+E+max(k/Np*P+Jd,I+(1-k/Np)*P*rank0_factor+Jd)+V",
            "draft_hit": "draft_hit_D + max(Bh,A+offset) + Gh",
            "draft_miss": "unchanged max(D,R+C)+max(Bm,A+offset)+Gm",
            "rate": "1000/(p*H+(1-p)*M), one verified token per interval",
            "E_I_V": "new host-boundary proxy plus respectively unknown export/import/return cost",
        },
        "assumptions": [
            "Head time linear in whole vocabulary rows; same per-row arithmetic and bytes, rank0_factor=1 by default. No new device measurement.",
            "Final.mix is normalized BF16, 2560 elements (5120 bytes); copy exact bytes, do not re-run normalization or transfer guessed state.",
            "Keep full existing local argmax time on both cards; merge BF16-rounded logit values with global indices, lowest index wins ties; OR finite/error status.",
            "No rank0 head/target compute concurrency, and no hidden-copy overlap with rank0 compute assumed.",
            "Target non-head remainder precedes head readiness as a conservative accounting surrogate, not a measured intra-command timestamp.",
            "Draft hits are known at interval entry from the completed verifier. On misses do not issue a rank0 head or wait for it.",
            "Two new cross-rank notifications and one new rank0 issue use existing measured host boundaries as proxies, not measurements of the proposed protocol.",
            "Unchanged acceptance, target arithmetic, draft prefix rows, BF16 KV and rollback semantics; no gains from cached prompts.",
            "No memory admission or real-shape partition validation performed; allocations exclude workspace and transport staging.",
        ],
        "options": options,
        "validation": {"packet85_component_reproduction": True, "packet85_shared_source_hashes_checked": checked,
                       "unsplit_replays_observed_class_balanced_rate": True,
                       "nominal_no_worsened_miss_intervals_both_options": True,
                       "search": "all nonempty 256-row-aligned splits plus untouched no-split control; optimize packet85 expected-time rate",
                       "scope": "CPU mathematical/accounting checks, not output parity, speed qualification or runtime sealing"},
        "source_sha256": dict(sorted(p85.SOURCES.items())),
    }
    output = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    destination = HERE / "DECISION.json"
    if args.check:
        assert destination.read_text() == output, "DECISION.json differs from fresh recomputation"
        print("PASS: exact recomputation, input hashes, baseline, split search and miss checks")
    else:
        destination.write_text(output)
        print("Wrote", destination.relative_to(ROOT))
    print(json.dumps({name: {"optimistic_known_boundary_scenario": data["known_boundary_only_optimum"],
                             "seal_ready": data["seal_ready"],
                             "missing_cost_thresholds": data["additional_transfer_budgets_for_0_5_percent_vs_measured"]}
                      for name, data in options.items()}, indent=2))


if __name__ == "__main__":
    main()
