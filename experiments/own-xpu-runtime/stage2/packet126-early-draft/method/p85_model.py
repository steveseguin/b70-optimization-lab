#!/usr/bin/env python3
"""CPU-only packet 85 accounting. Reads evidence; writes only model.json here.

Run from any directory with nice -n 19 taskset -c 8-15,24-31 python3 -B.
--check recomputes and compares without writing. Standard library only.
This is a diagnostic model, not a benchmark or a performance qualification.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import resource
import statistics as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = ROOT / "experiments/own-xpu-runtime/stage2"
SHARED = STAGE / "screen/v4-lanes/evidence"
P77 = SHARED / "packet77-attribution-B-a/run"
LIMIT = 4 * 1024**3
resource.setrlimit(resource.RLIMIT_AS, (LIMIT, LIMIT))
SOURCES = {}


def read(path):
    path = Path(path)
    raw = path.read_bytes()
    SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return raw.decode()


def load(path):
    return json.loads(read(path))


def stats(values):
    v = sorted(values)
    if not v:
        return {"n": 0, "mean": None, "median": None}
    return {"n": len(v), "mean": st.mean(v), "median": st.median(v),
            "min": v[0], "max": v[-1]}


def duration(t):
    return 1000 * (t["rank_completed"] - t["rank_received"])


def balanced(pairs):
    groups = defaultdict(list)
    for label, value in pairs:
        groups[label].append(value)
    return st.median(st.median(v) for v in groups.values())


def intervals(r, limit=99):
    """Join by position, never by trace serialization order (ranks overlap).

    Each row starts at a verified emission and ends at the next emission.
    Hit/miss refers to the guess just verified at the starting emission.
    Rank 0's NEXT speculation races the next rank 1 half; its exposed tail
    is retained. Copies inside commands stay inside those command durations.
    """
    trace = r["rank_trace"]
    index = {(t["rank"], t["op"], t["position"], t["speculative"]): t
             for t in trace if t["op"] in (1, 3, 9)}
    stamps = r["generated_token_completion_timestamps"]
    draft_rank = next(t["rank"] for t in trace if t["op"] == 9)
    guesses = {d["position"]: d["hit"] for d in r["guess_rows"]}
    out = []
    for i, (start, end) in enumerate(zip(stamps, stamps[1:])):
        if i >= limit:
            break
        pos = r["prompt_tokens"] + i
        hit = guesses[pos]
        b = index[(1, 1, pos, False)]
        d = index[(draft_rank, 9, pos, True)]
        spec_next = index.get((0, 1, pos + 1, True))
        spec_previous = index[(0, 1, pos, True)]
        rollback = index.get((0, 3, pos, True)) if not hit else None
        corrected = index.get((0, 1, pos, False)) if not hit else None
        D, B = duration(d), duration(b)
        R = duration(rollback) if rollback else 0.0
        C = duration(corrected) if corrected else 0.0
        A = duration(spec_next) if spec_next else 0.0
        offset = 1000 * (spec_next["rank_received"] - b["rank_received"]) if spec_next else 0.0
        race = max(B, A + offset)
        if draft_rank == 1:
            ready = max(D, R + C)
        else:
            ready = D + R + C
        elapsed = 1000 * (end - start)
        branch_end = max(d["rank_completed"],
                         corrected["rank_completed"] if corrected else spec_previous["rank_completed"])
        out.append({"i": i, "position": pos, "hit": hit, "draft_rank": draft_rank,
                    "elapsed_ms": elapsed, "D": D, "B": B, "A": A, "R": R, "C": C,
                    "spec_start_offset_ms": offset,
                    "rank0_slack_ms": B - A - offset,
                    "handoff_ready_to_rank1_ms": 1000 * (b["rank_received"] - branch_end),
                    "draft_issue_after_emission_ms": 1000 * (d["rank_received"] - start),
                    "rollback_issue_after_emission_ms": 1000 * (rollback["rank_received"] - start) if rollback else None,
                    "restore_to_corrected_start_ms": 1000 * (corrected["rank_received"] - rollback["rank_completed"]) if corrected else None,
                    "emission_after_race_ms": 1000 * (end - max(b["rank_completed"], spec_next["rank_completed"] if spec_next else b["rank_completed"])),
                    "prediction_without_gaps_ms": ready + race,
                    "unresolved_control_gaps_ms": elapsed - ready - race})
    assert len(out) == min(limit, len(stamps) - 1)
    return out


def components(rows):
    h = [r for r in rows if r["hit"]]
    m = [r for r in rows if not r["hit"]]
    return {"A": st.mean(r["A"] for r in rows),
            "Bh": st.mean(r["B"] for r in h), "Bm": st.mean(r["B"] for r in m),
            "D": st.mean(r["D"] for r in rows),
            "R": st.mean(r["R"] for r in m), "C": st.mean(r["C"] for r in m),
            "Gh": st.mean(r["unresolved_control_gaps_ms"] for r in h),
            "Gm": st.mean(r["unresolved_control_gaps_ms"] for r in m),
            "spec_offset": st.mean(r["spec_start_offset_ms"] for r in rows)}


def paths(c, draft_rank=1):
    hit = c["D"] + max(c["Bh"], c["A"] + c["spec_offset"]) + c["Gh"]
    miss_ready = max(c["D"], c["R"] + c["C"]) if draft_rank == 1 else c["D"] + c["R"] + c["C"]
    miss = miss_ready + max(c["Bm"], c["A"] + c["spec_offset"]) + c["Gm"]
    return hit, miss


def rate(c, p, draft_rank=1):
    h, m = paths(c, draft_rank)
    return 1000 / (p * h + (1 - p) * m)


def changed(c, savings):
    result = dict(c)
    for key, value in savings.items():
        result[key] -= value
    return result


def summary_path(packet, name):
    return STAGE / packet / "screen/evidence" / name / "run/summary.json"


def summarize_run(path):
    r = load(path)
    requests = r["requests"]
    estimates = []
    errors = []
    for request in requests:
        rows = intervals(request)
        prediction = 99000 / sum(x["prediction_without_gaps_ms"] for x in rows)
        observed = request["tok_s_1_100_intervals_after_ttft"]
        estimates.append((request["prompt_class"], prediction))
        errors.append(prediction - observed)
    return {"path": str(path.relative_to(ROOT)),
            "observed_tok_s": r["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"],
            "component_predicted_tok_s": balanced(estimates),
            "request_error_tok_s": stats(errors),
            "acceptance_median": r["acceptance_statistics"]["median"],
            "split": requests[0]["target_split"],
            "reported_hit_ms": r["hit_miss_cycle_statistics"]["hit"]["median"],
            "reported_miss_ms": r["hit_miss_cycle_statistics"]["miss"]["median"]}


def comparison(label, controls, candidate):
    base = [summarize_run(x) for x in controls]
    cand = summarize_run(candidate)
    measured = 100 * (cand["observed_tok_s"] / st.mean(x["observed_tok_s"] for x in base) - 1)
    predicted = 100 * (cand["component_predicted_tok_s"] / st.mean(x["component_predicted_tok_s"] for x in base) - 1)
    return {"name": label, "kind": "retrospective command-cost substitution; no rate fitting",
            "controls": base, "candidate": cand, "observed_percent": measured,
            "predicted_percent": predicted, "error_percentage_points": predicted - measured,
            "sign_correct": measured * predicted > 0}


def transfer_check(training, test):
    """Learn A component deltas; predict B without B candidate timings/rate.

    The B outcome is read only after producing the prediction. Controls supply
    B's baseline and acceptance. This tests transport of measured costs, not
    inference of GPU costs from source code.
    """
    def rows(path):
        return [x for r in load(ROOT / path)["requests"] for x in intervals(r)]
    train_control = components([x for control in training["controls"] for x in rows(control["path"])])
    train_candidate = components(rows(training["candidate"]["path"]))
    delta = {key: train_control[key] - train_candidate[key] for key in ("A", "Bh", "Bm", "C", "D", "R")}
    predicted_rates = []
    for control in test["controls"]:
        for request in load(ROOT / control["path"])["requests"]:
            rr = intervals(request)
            base = components(rr)
            acceptance = st.mean(x["hit"] for x in rr)
            # Apply modeled ratio to measured control; no candidate timing.
            predicted = request["tok_s_1_100_intervals_after_ttft"] * rate(changed(base, delta), acceptance) / rate(base, acceptance)
            predicted_rates.append((request["prompt_class"], predicted))
    predicted_rate = balanced(predicted_rates)
    observed_base = st.mean(x["observed_tok_s"] for x in test["controls"])
    predicted_percent = 100 * (predicted_rate / observed_base - 1)
    return {"train": training["name"], "test": test["name"], "component_savings_ms": delta,
            "predicted_tok_s": predicted_rate, "predicted_percent": predicted_percent,
            "observed_percent": test["observed_percent"],
            "error_percentage_points": predicted_percent - test["observed_percent"],
            "sign_correct": predicted_percent * test["observed_percent"] > 0,
            "kind": "lane-A measured component changes transferred to held-out lane B; no B candidate timing input"}


def depth2(path):
    """Controller DAG cost per actual tile; output counts are verified emissions.

    At each op19: draft -> optional current R0 tile -> max(R1 tile,
    future R0 tile) -> feedback/commit OR discard/restore. Commands 15/18
    carry position 0; assign by send timestamps, not their position field.
    Compare against complete decode, then separately report first-99 metric.
    """
    summary = load(path)
    ops = defaultdict(list)
    predictions, observed_full = [], []
    events = []
    for r in summary["requests"]:
        start, end = r["generated_token_completion_timestamps"][0], r["generated_token_completion_timestamps"][-1]
        trace = sorted([x for x in r["rank_trace"] if start <= x["sent"] < end and x["op"]], key=lambda x: x["sent"])
        boundaries = [i for i, x in enumerate(trace) if x["op"] == 19]
        total = 0.0
        tile_count = rebuild_count = 0
        for j, at in enumerate(boundaries):
            stop = boundaries[j + 1] if j + 1 < len(boundaries) else len(trace)
            tile = trace[at:stop]
            groups = defaultdict(list)
            for t in tile:
                key = f'r{t["rank"]}_op{t["op"]}_spec{int(t["speculative"])}'
                groups[key].append(duration(t)); ops[key].append(duration(t))
            tile_count += 1
            rebuild_count += bool(groups["r0_op14_spec0"])
            # Exclude overlapped future tile and final odd-row draft from the
            # serial sum, then insert max for each true concurrent branch.
            serial = sum(duration(t) for t in tile if t["op"] not in (14, 16))
            current = sum(groups["r0_op14_spec0"])
            concurrent = max(sum(groups["r1_op14_spec0"]), sum(groups["r0_op14_spec1"]))
            total += serial + current + concurrent
        n = len(r["tokens"]) - 1
        pred = n * 1000 / total
        actual = n * 1000 / ((end - start) * 1000)
        predictions.append((r["prompt_class"], pred)); observed_full.append((r["prompt_class"], actual))
        events.append({"prompt_id": r["prompt_id"], "tiles": tile_count, "current_rebuilds": rebuild_count,
                       "verified_tokens": n, "predicted_decode_ms": total, "observed_decode_ms": (end - start) * 1000})
    return {"kind": "retrospective tile-DAG command-cost accounting; not depth-one hit/miss formula",
            "path": str(path.relative_to(ROOT)), "op_duration_ms": {k: stats(v) for k, v in sorted(ops.items())},
            "requests": events, "predicted_full_decode_tok_s": balanced(predictions),
            "observed_full_decode_tok_s": balanced(observed_full),
            "observed_first99_tok_s": summary["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"],
            "warning": "Depth2 hit/miss summary rows are decisions per tile, not one emission per cycle; never mix with depth1 acceptance formula."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = [load(p) for p in sorted((P77 / "control").glob("*/receipt.json"))]
    assert len(raw) == 12
    all_rows = [x for r in raw for x in intervals(r)]
    c = components(all_rows)
    p = 0.7874015748031495  # requested median acceptance; exact 100/127
    empirical_p = st.mean(x["hit"] for x in all_rows)
    h, m = paths(c)
    baseline = rate(c, p)
    attr = load(P77 / "attribution-summary.json")
    band = load(STAGE / "packet72-occupancy/BANDWIDTH.json")
    host = load(STAGE / "packet76-rank1-host/ATTRIBUTION.json")
    load(STAGE / "packet69-rank1-head/evidence/existing-analysis.json")
    # Pin raw GPU events and host half timers used by the retained attribution
    # report. Never execute old report modules or read any model payload.
    for path, expected in attr["sources"].items():
        full = ROOT / path
        if path.endswith(("sites.jsonl", "timings.jsonl")):
            read(full)
            assert SOURCES[path] == expected, f"attribution source changed: {path}"
    def src(packet, name):
        return summary_path(packet, name)
    validations = []
    for lane in "AB":
        controls = [src("packet65-expert-occupancy", f"p65-quick-{lane}-{n:02}-production") for n in (1, 6)]
        validations.append(comparison(f"p65 wide64 {lane}", controls, src("packet65-expert-occupancy", f"p65-quick-{lane}-{'02' if lane == 'A' else '05'}-wide64")))
        controls = [src("packet73-hc-experts2", f"p73-quick-{lane}-{n}-production-a") for n in ((1, 6) if lane == "A" else (1, 3))]
        validations.append(comparison(f"p73 hc-wide {lane}", controls, src("packet73-hc-experts2", f"p73-quick-{lane}-2-{'hc-wide' if lane == 'A' else 'best-of-lane-A'}-a")))
        controls = [SHARED / f"p76-{lane}-{n}-production/run/summary.json" for n in (0, 2)]
        validations.append(comparison(f"p76 ordered {lane}", controls, SHARED / f"p76-{lane}-1-ordered/run/summary.json"))
    controls = [src("packet74-packed-dense", f"p74-quick-A-{n}-production-a") for n in (1, 5)]
    for n, name in ((2, "head-packed"), (3, "dense-packed"), (4, "combined")):
        validations.append(comparison(f"p74 {name}", controls, src("packet74-packed-dense", f"p74-quick-A-{n}-{name}-a")))
    for n, name in ((1, "0-split23"), (2, "0")):
        controls = [SHARED / f"p79-A-{j}-1/run/summary.json" for j in (0, 3)]
        validations.append(comparison(f"p79 draft-rank0 {name}", controls, SHARED / f"p79-A-{n}-{name}/run/summary.json"))
    for name, lane, candidate, end in (("route-fast", "A", "1-route-fast", 5), ("small+hc-wide", "B", "1-small+hc-wide", 2)):
        controls = [SHARED / f"p78-{lane}-{n}-production/run/summary.json" for n in (0, end)]
        validations.append(comparison(f"p78 {name} {lane}", controls, SHARED / f"p78-{lane}-{candidate}/run/summary.json"))
    p78_norm = load(SHARED / "p78-A-2-norm-fused/run/summary.json")
    p78_small = load(SHARED / "p78-A-3-small-combined/run/summary.json")
    p78_base = st.mean(x["observed_tok_s"] for x in validations[-2]["controls"])
    p78_negatives = {name: 100 * (r["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"] / p78_base - 1)
                     for name, r in (("norm-fused", p78_norm), ("small-combined", p78_small))}
    d2 = depth2(src("packet71c-depth2-engine", "candidate-B"))
    d2control = summarize_run(src("packet71c-depth2-engine", "control-B"))
    d2control_raw = load(src("packet71c-depth2-engine", "control-B"))
    d2["control_full_decode_tok_s"] = balanced([(r["prompt_class"], 1000 * (len(r["tokens"]) - 1) /
        (1000 * (r["generated_token_completion_timestamps"][-1] - r["generated_token_completion_timestamps"][0])))
        for r in d2control_raw["requests"]])
    d2["matched_full_predicted_percent"] = 100 * (d2["predicted_full_decode_tok_s"] / d2["control_full_decode_tok_s"] - 1)
    d2["matched_full_observed_percent"] = 100 * (d2["observed_full_decode_tok_s"] / d2["control_full_decode_tok_s"] - 1)
    d2["first99_measured_change_percent"] = 100 * (d2["observed_first99_tok_s"] / d2control["observed_tok_s"] - 1)
    d2["predicted_full_rate_vs_first99_control_percent"] = 100 * (d2["predicted_full_decode_tok_s"] / d2control["observed_tok_s"] - 1)
    d2["cross_window_error_percentage_points"] = d2["predicted_full_rate_vs_first99_control_percent"] - d2["first99_measured_change_percent"]
    d2["matched_window_error_tok_s"] = d2["predicted_full_decode_tok_s"] - d2["observed_full_decode_tok_s"]
    sensitivity = {}
    for label, keys in {"rank0 speculative half": ["A"], "rank0 corrected half": ["C"],
                        "rollback including restore": ["R"], "draft": ["D"],
                        "rank1 target half or one serial subcomponent": ["Bh", "Bm"],
                        "both target halves": ["A", "C", "Bh", "Bm"],
                        "hit-only handoff/control gap": ["Gh"], "miss-only handoff/control gap": ["Gm"]}.items():
        cc = changed(c, {k: 0.1 for k in keys})
        hh, mm = paths(cc)
        sensitivity[label] = {"hit_ms_saved": h - hh, "miss_ms_saved": m - mm,
                              "hit_only_tok_s_gain": 1000 / (p * hh + (1 - p) * m) - baseline,
                              "miss_only_tok_s_gain": 1000 / (p * h + (1 - p) * mm) - baseline,
                              "combined_tok_s_gain": rate(cc, p) - baseline}
    # Counterfactual budgets are assumptions, not fitted savings or new measurements.
    scenarios = []
    costs = {(x["rank"], x["site"]): x["estimated_us_per_half"] / 1000 for x in attr["lever_ranking"]}
    experts = [sum(costs[(rank, site)] for site in ("expsgate", "expsdown")) for rank in (0, 1)]
    recurrence = [costs[(rank, "gdn.recurrence")] for rank in (0, 1)]
    def both(fraction, values):
        return {"A": fraction * values[0], "C": fraction * values[0], "Bh": fraction * values[1], "Bm": fraction * values[1]}
    configs = [
        ("experts: 5-15% of current gate/up+down cost", both(.05, experts), both(.15, experts)),
        ("rank balance 23/25 -> 24/24, layer23 sample", {}, {}),
        ("miss: save 0.1-0.3 ms restore plus 0.3-1.0 ms corrected half", {"R": .1, "C": .3}, {"R": .3, "C": 1.0}),
        ("draft: save 0.1-0.3 ms at unchanged acceptance", {"D": .1}, {"D": .3}),
        ("HC/route: save 0.1-0.25 ms per target half", {"A": .1, "C": .1, "Bh": .1, "Bm": .1}, {"A": .25, "C": .25, "Bh": .25, "Bm": .25}),
        ("host: save 0.05-0.15 ms exposed rank1 work", {"Bh": .05, "Bm": .05}, {"Bh": .15, "Bm": .15}),
        ("recurrence: save 10-25% of current class", both(.1, recurrence), both(.25, recurrence)),
    ]
    layer23_ms = sum(x["measured_call_median_us"] for x in attr["sites"] if x["rank"] == 0 and x["layer"] == 23) / 1000
    split23 = changed(c, {"A": layer23_ms, "C": layer23_ms, "Bh": -layer23_ms, "Bm": -layer23_ms})
    for label, low, high in configs:
        if label.startswith("rank balance"):
            base = rate(split23, p)
            gains = [baseline - base] * 2
            percents = [100 * (baseline / base - 1)] * 2
        else:
            gains = [rate(changed(c, z), p) - baseline for z in (low, high)]
            percents = [100 * x / baseline for x in gains]
        scenarios.append({"name": label, "assumed_savings_low_ms": low, "assumed_savings_high_ms": high,
                          "predicted_tok_s_gain_range": gains, "predicted_percent_range": percents,
                          "is_measurement": False})
    # Search exactly the requested evidence sets. Keep only relevant short lines
    # for machine review; all scanned documents receive a content hash.
    import re
    pattern = re.compile(r"packet(?:45|65|67|69|71|72|73|74|76|77|78|79|81|82|83)|rank.?0|rollback|restore|recurrence|wide64|hc-wide|route-fast|ordered retirement|depth.?2", re.I)
    searches = []
    files = list(STAGE.glob("*/DO-NOT-REPEAT.md"))
    files += [x for x in (ROOT / "notes").glob("2026-10-1[5-7]*") if x.is_file() and x.name != "2026-10-17-own-runtime-packet85.md"]
    files += [ROOT / "results/localmaxxing-submissions.md"]
    for path in sorted(files):
        lines = read(path).splitlines()
        hits = [{"line": i + 1, "text": line[:650]} for i, line in enumerate(lines) if pattern.search(line)]
        if hits:
            searches.append({"path": str(path.relative_to(ROOT)), "matches": hits})
    for path in [STAGE / "packet77-attribution/native_controller.hpp", STAGE / "packet77-attribution/rank.hpp",
                 STAGE / "packet71c-depth2-engine/depth2_controller.hpp", STAGE / "packet76-rank1-host/ATTRIBUTION.md",
                 STAGE / "packet71c-depth2-engine/rank.hpp", STAGE / "packet71c-depth2-engine/mtp.hpp",
                 STAGE / "packet72-occupancy/BANDWIDTH.md", STAGE / "packet69-rank1-head/ROOFLINE.md"]:
        read(path)
    baseline_summary = load(P77 / "summary.json")
    transfer_tests = [transfer_check(validations[i], validations[i + 3]) for i in range(3)]
    acceptance_budget = []
    for saving in (.1, .2, .3):
        cc = changed(c, {"D": saving})
        hh, mm = paths(cc)
        break_even = (mm - 1000 / baseline) / (mm - hh)
        acceptance_budget.append({"draft_ms_saved": saving, "break_even_acceptance": break_even,
                                  "maximum_acceptance_loss_percentage_points": 100 * (p - break_even)})
    # Two deliberately imperfect forecasts retain their errors. Sparse class
    # samples and device-only M2 costs do not identify complete command costs.
    old_experts = [sum(x["measured_us_per_half"] for x in band["ranking"]
                      if x["rank"] == rank and x["site"] in ("expsgate", "expsdown")) / 1000
                   for rank in (0, 1)]
    old_c = changed(c, both(1, [experts[k] - old_experts[k] for k in (0, 1)]))
    sparse_wide_percent = 100 * (baseline / rate(old_c, p) - 1)
    # Historical measured device-only H2s (p68c) and restore (p68), not p71c
    # endpoint times. Three draft passes from op19 source; independence of
    # two guesses is explicitly an assumption, not measured acceptance.
    prior_tile_ms = 3 * c["D"] + (1 - p * p) * 21.89 + max(21.89, 23.03) + 2 * .980923 + p * (c["D"] - .52076615625)
    prior_depth_rate = 1000 * (1 + p) / prior_tile_ms
    prior_forecasts = {
        "wide64_sparse_classes": {"old_expert_ms": old_experts, "new_expert_ms": experts,
                                  "predicted_percent": sparse_wide_percent,
                                  "observed_B_percent": validations[3]["observed_percent"],
                                  "error_percentage_points": sparse_wide_percent - validations[3]["observed_percent"],
                                  "limitation": "Historical packet72/64 sampled classes versus packet77, different sessions; not a matched whole-half mechanism measurement."},
        "depth2_prior_components": {"assumed_H2_rank0_ms": 21.89, "assumed_H2_rank1_ms": 23.03,
                                    "assumed_rebuild_probability": 1 - p * p,
                                    "assumed_verified_tokens_per_tile": 1 + p,
                                    "assumed_tile_ms": prior_tile_ms, "predicted_tok_s": prior_depth_rate,
                                    "predicted_percent": 100 * (prior_depth_rate / baseline - 1),
                                    "observed_first99_percent": d2["first99_measured_change_percent"],
                                    "error_percentage_points": 100 * (prior_depth_rate / baseline - 1) - d2["first99_measured_change_percent"],
                                    "limitation": "Rejects the gain but fails magnitude: device-only p68c H2 omits complete p71c command costs; independent guesses and unchanged acceptance are unverified."}}
    lever_specs = [
        ("Rank balance, keep draft on rank1", 1, "Move layer23 from rank1 to rank0 when starting at 23/25; packet77 is already 24/24.",
         "p77 layer23 sampled 0.505106 ms; mean rank0 hit slack 0.543719 ms. 555 GB/s is irrelevant to moving work.",
         "p45 SPEED5/6 history is a different arithmetic/memory identity; p76 supports only 23/25; p77 establishes current 24/24. p79 rank0 draft is closed.",
         "Small: placement/admission and full-state parity; no new arithmetic. Estimate 0.5-1 engineer-day.",
         "No added gain on an already-24/24 record; independently confirm the composed ordered/HC record at identical split and memory reserve."),
        ("Small target kernels: HC/route, then recurrence", 4, "Reduce launch/reduction work with exact per-chain sums; recurrence shares independent gate work without a new prepass.",
         "p77 rank1 HC gates 1.198 ms, norms 0.409 ms, route 0.472 ms; reference excess 0.877/0.404/0.472 ms. Recurrence 0.628 ms, reference excess 0.576 ms.",
         "p73 HC-wide won 0.73% B; p78 route-fast +0.54% A, small+hc-wide +0.51% B; norm-fused alone lost 0.65%. p67 HC four-stream/shared-head-prepass lost; p82 uses a distinct mechanism, device verdict pending at this snapshot.",
         "Small for merging independently qualified choices; medium for a new kernel: 1-3 engineer-days.",
         "Preserve normalization, top-k ordering/ties, BF16 boundaries, recurrence state and reduction order. Do not add HC/route/recurrence scenario gains blindly."),
        ("Expert dequantization ALU/latency", 0, "Reduce IQ2/IQ4 decode dependency or lookup latency while retaining raw operands and each FP32 chain.",
         "p77 gate/up+down 2.729/2.754 ms per rank; reference excess 1.876/1.901 ms. These are sampled-class estimates, not attainable savings.",
         "p65 wide64 won 4.80-5.39%; p73 experts2 lost; p81 fewer activation loads was neutral (+0.07/+0.13/-0.10%). p52/53 SLM/persistent/free-order and V16 gate/up remain closed.",
         "Medium/large: new decode schedule plus compiler byte and real-shape gates; 3-5 engineer-days.",
         "No new load-count campaign. Require an ALU/latency mechanism and exact target arithmetic; the 5-15% component saving is only a decision budget."),
        ("Cheaper draft on rank1", 3, "Reduce draft-only prefix/head work or approximate draft weights; target still verifies every emitted token.",
         "p77 D 1.795 ms; draft prefix 0.521, attention 0.387, HC 0.251, experts 0.251 ms. Prefix already about 561 GB/s.",
         "p69 head-width/attention/HC variants below promotion bar; p79 relocation closed. p83 independent-text prefixes/Q4 draft prepared; acceptance/speed still pending at snapshot.",
         "Small/medium with existing packet83: 1-2 engineer-days to evaluate/integrate a qualified choice.",
         "Draft is free to change; target, verifier and BF16 KV are not. Saving 0.2 ms permits only about 1.33 percentage points acceptance loss at break-even."),
        ("Miss restore and corrected-half work", 2, "Remove only proved redundant restore/setup; optimize corrected rank0 without replaying or reusing prompt/KV output.",
         "p77 rollback/restore 0.569 ms and corrected half 12.655 ms, paid on about 21.3% of emissions; restore has no separate timer.",
         "p45 SPEED4 already skips proved spare banks on confirmed redo; p64/70 already batch rollback. Terminal/full-state rollback remains observable. p71 depth2 is closed.",
         "Medium/large: state ownership and overwrite proof, terminal/failure-path tests; 2-5 engineer-days.",
         "Keep every canonical state byte and metadata; no masking hashes, omitted terminal restore or speculative unverified output."),
        ("Exposed host issue/retirement", 5, "Reduce actual serial rank1 cleanup; separate it from enqueue that overlaps GPU work.",
         "p77 instrumented residual 1.544 ms; p76 control housekeeping only 0.666 ms and about 0.791 ms observer overhead; only 0.00125 ms sampled tail gaps.",
         "p76 ordered won 0.41% B (A 1.05% vs both controls); graph replay packet34 neutral historically; p76 forbids treating the residual as idle or enqueue as serial.",
         "Small/medium: 1-2 engineer-days for focused host ownership/retirement changes and timings.",
         "Keep synchronization, errors and graceful drain. Ordered gain may already be in the proposed record; do not count it twice.")]
    lever_specs = [lever_specs[i] for i in (1, 3, 2, 4, 5, 0)]
    ranked_levers = [{"rank": i + 1, "name": name, "mechanism": mechanism, "measured_headroom_and_scope": headroom,
                      "model_scenario": scenarios[index], "prior_attempts_and_do_not_repeat": prior,
                      "engineering_size_estimate": size, "constraint_and_decision": constraint,
                      "evidence_status": "conditional model budget, not a measured gain"}
                     for i, (name, index, mechanism, headroom, prior, size, constraint) in enumerate(lever_specs)]
    component_sensitivity = []
    for row in attr["lever_ranking"]:
        role = "rank1 target half or one serial subcomponent" if row["rank"] == 1 else "rank0 corrected half"
        component_sensitivity.append({"rank": row["rank"], "site": row["site"],
                                      "sample_scaled_half_ms": row["estimated_us_per_half"] / 1000,
                                      "reference_excess_ms": row["estimated_headroom_us_per_half"] / 1000,
                                      "sensitivity": sensitivity[role],
                                      "note": "rank0 speculative savings have zero local value until balance changes; 0.1 ms is a normalized derivative, not an achievable saving for smaller sites"})
    extraction = {key: stats(row[key] for row in all_rows if row[key] is not None)
                  for key in all_rows[0] if key not in ("i", "position", "hit", "draft_rank")}
    conditional = {name: stats(row["elapsed_ms"] for row in all_rows if row["hit"] == hit)
                   for name, hit in (("hit", True), ("miss", False))}
    # A genuine held-out check: fit command means on the first 48 intervals of
    # each prompt; predict remaining 51 using their observed hit count, not times.
    holdout = []
    for r in raw:
        rows = intervals(r)
        fit = components(rows[:48])
        test = rows[48:]
        ph = st.mean(x["hit"] for x in test)
        observed = 1000 * len(test) / sum(x["elapsed_ms"] for x in test)
        predicted = rate(fit, ph)
        holdout.append({"prompt_id": r["prompt_id"], "train_intervals": 48, "test_intervals": len(test),
                        "observed_tok_s": observed, "predicted_tok_s": predicted,
                        "error_percent": 100 * (predicted / observed - 1)})
    result = {
        "schema": "own-runtime.packet85.critical-path.v1", "diagnostic": True,
        "device_executed": False, "submission_eligible": False,
        "identity": {"reference": "packet77 control / packet70 wide64 / draft-HC / batched rollback",
                     "target_split": [24, 24], "draft_rank": 1, "kv": "BF16", "target_arithmetic": "iq3-p49-split32-v1",
                     "scope": "12 prompts, first 99 emission intervals per prompt; one loaded pair"},
        "definitions": {"H": "D + max(Bh,A+offset) + Gh", "M": "max(D,R+C) + max(Bm,A+offset) + Gm",
                        "T": "p*H + (1-p)*M", "tok_s": "1000/T; one verified emission per depth1 interval",
                        "rank0_draft_M": "D + R + C + max(Bm,A+offset) + Gm; reverse transfer may add cost",
                        "gaps": "observed elapsed minus dependency command durations; signed accounting, not a free optimization budget"},
        "baseline": {"components_ms": c, "median_acceptance": p, "first99_empirical_acceptance": empirical_p,
                     "predicted_hit_ms": h, "predicted_miss_ms": m, "predicted_tok_s": baseline,
                     "observed_class_balanced_tok_s": baseline_summary["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"],
                     "conditional_emission_intervals_ms": conditional, "raw_fields_ms": extraction,
                     "rank0_draft_structural_predicted_percent": 100 * (rate(c, p, 0) / baseline - 1),
                     "rank0_speculation_slack_at_mean_ms": c["Bh"] - c["A"] - c["spec_offset"],
                     "draft_slack_on_miss_ms": c["R"] + c["C"] - c["D"]},
        "heldout_baseline": holdout, "heldout_lane_transfer": transfer_tests,
        "imperfect_prior_forecasts": prior_forecasts,
        "draft_acceptance_tradeoff": acceptance_budget,
        "sensitivity_per_0_1ms_saved": sensitivity, "site_sensitivities": component_sensitivity,
        "validation": validations, "depth2": d2, "ranked_levers": ranked_levers,
        "p78_component_negatives_percent": p78_negatives,
        "rank_balance": {"sampled_layer23_ms": layer23_ms, "hypothetical_split23_components_ms": split23,
                         "hypothetical_split23_tok_s": rate(split23, p), "is_measurement": False},
        "scenarios": scenarios,
        "attribution": {"rank_halves": attr["rank_halves"], "outside_layers": attr["outside_layers"],
                        "rank1_outside_split": attr["rank1_outside_split"], "draft_breakdown": attr["draft_breakdown"],
                        "class_headroom": attr["lever_ranking"], "older_packet72_ranking": band["ranking"],
                        "instrumentation": {k: attr[k] for k in ("sampled_cycles", "full_cycles", "draft_wall")}},
        "prior_art_search": {"method": "regex over every stage2/*/DO-NOT-REPEAT.md, notes/2026-10-1[5-7]* and results/localmaxxing-submissions.md", "results": searches},
        "limitations": ["Command-cost substitution is retrospective; not blind kernel-speed prediction.",
                        "The 555 GB/s excess is a reference gap, not realizable savings or DRAM counter data.",
                        "No separate restore-vs-rollback or valid DMA latency survives; keep them combined/unknown.",
                        "New kernel mechanisms require component timings; bytes/static instructions alone cannot predict their sign.",
                        "Do not add overlapping scenario gains or transfer old model/topology timings as current measurements.",
                        "Screens and first-99 model do not qualify a new record; no performance promotion in packet85."],
        "source_sha256": dict(sorted(SOURCES.items())),
    }
    content = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    target = HERE / "model.json"
    if args.check:
        assert target.read_text() == content, "model.json differs from a fresh evidence recomputation"
        print("PASS: model.json reproduces exactly; all pinned attribution inputs match")
    else:
        target.write_text(content)
        print("Wrote", target.relative_to(ROOT), len(content), "bytes")
    print(json.dumps({"baseline": result["baseline"]["components_ms"], "predicted_tok_s": baseline,
                      "validation": [{k: v[k] for k in ("name", "observed_percent", "predicted_percent", "error_percentage_points", "sign_correct")} for v in validations],
                      "depth2": {k: d2[k] for k in ("predicted_full_decode_tok_s", "observed_full_decode_tok_s", "observed_first99_tok_s", "matched_window_error_tok_s")}}, indent=2))


if __name__ == "__main__":
    main()
