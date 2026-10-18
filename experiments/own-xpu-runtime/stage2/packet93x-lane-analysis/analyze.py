#!/usr/bin/env python3
"""Read-only CPU receipt analysis; writes only adjacent analysis.json.

Run with nice -n 19 taskset -c 8-15,24-31 python3 -B, stdin /dev/null.
Uses packet85's position-based interval join; never imports a runtime worker.
"""
import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import statistics as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = HERE.parent
EVIDENCE = STAGE / "screen/v4-lanes/evidence"
resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
SOURCES = {}


def read(path):
    raw = path.read_bytes()
    SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return raw.decode()


def load(path):
    return json.loads(read(path))


def jsonl(path):
    return [json.loads(x) for x in read(path).splitlines() if x.strip()]


def stats(v):
    v = sorted(x for x in v if x is not None)
    if not v:
        return {"n": 0, "median": None, "mean": None}
    return {"n": len(v), "median": st.median(v), "mean": st.mean(v)}


MODEL = STAGE / "packet85-critical-path/model.py"
read(MODEL)
spec = importlib.util.spec_from_file_location("packet85_accounting", MODEL)
p85 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p85)

CORE = ["elapsed_ms", "D", "B", "A", "R", "C", "rank0_slack_ms",
        "spec_start_offset_ms", "handoff_ready_to_rank1_ms",
        "draft_issue_after_emission_ms", "rollback_issue_after_emission_ms",
        "restore_to_corrected_start_ms", "emission_after_race_ms",
        "unresolved_control_gaps_ms", "rank0_exposed_tail_ms",
        "ready_ms", "race_ms"]
TIMERS = ["prepare_ms", "enqueue_loop_ms", "wait_ms", "p76_retirement_ms",
          "p76_profiling_ms", "process_major_faults", "process_minor_faults",
          "process_voluntary_context_switches", "process_involuntary_context_switches",
          "load_average_1m"]
DETAIL = ["D_busy_ms", "D_envelope_minus_busy_ms", "draft_wall_ms",
          "draft_gpu_event_sum_ms", "D_minus_draft_gpu_event_sum_ms",
          "B_busy_ms", "B_envelope_minus_busy_ms"]


def groups(rows, keys):
    return {name: {key: stats(r.get(key) for r in subset) for key in keys}
            for name, subset in [("all", rows),
                                 ("hit", [r for r in rows if r["hit"]]),
                                 ("miss", [r for r in rows if not r["hit"]])]}


def main():
    output = {"schema": "own-runtime.packet93x.lane-analysis.v1",
              "scope": "CPU-only retrospective screen analysis; no promotion or device experiment",
              "units": "milliseconds unless field says otherwise",
              "method": {
                  "primary_window": "99 intervals between generated events 1 and 100",
                  "secondary_window": "all 127 intervals of each 128-token capped request",
                  "components": "packet85 intervals(): D rank1 op9(pos); B rank1 op1(pos,false); A rank0 op1(pos+1,true); R op3(pos,true); C rank0 op1(pos,false)",
                  "duration": "1000*(rank_completed-rank_received), command envelopes, not isolated device kernels",
                  "hit_label": "guess_rows[position] at starting emission; miss correction acts before next emission",
                  "summary_hit_miss": "median across 12 per-request means over all 127 intervals; not pooled interval medians",
                  "draft_event_sum": "rank1 op1 gpu_ms carries deferred previous draft events; target half/head not event-profiled",
                  "draft_row_join": "receipt draft_rows[position+1], verified by draft_started_monotonic == op9.sent; rank1 draft-rows.jsonl draft_position == position-1",
                  "comparisons": "candidate minus arithmetic mean of two control summaries; also prompt/position matched first99 deltas",
                  "caution": "Medians are descriptive and not additive; means provide exact critical-path accounting. Gaps are residuals, so the accounting identity is not independent proof of causal completeness. Draft wall minus compute-event sum includes transfers, queue gaps, waits and host work; it is not pure CPU time. One fresh candidate per lane is not repeat evidence."
              }, "screens": {}, "comparisons": {},
              "decision": {"packet97_recommended_head": "production",
                           "record_lineage_head_transpose_admitted": False,
                           "classification": "Observed lane-A run regression in rank1 D and Bh; transient host/queue/placement interaction plausible, permanent physical-card effect unproven",
                           "excluded_explanations": ["draft using transposed target bytes", "different target-head virtual base alignment", "rank0 A becoming the hit bottleneck", "inter-command handoff gap increase"],
                           "unresolved": ["target-head isolated device duration on cards1/3", "draft host/transfer/queue overhead cause", "physical VRAM backing/cache placement", "repeatability on laneA"],
                           "next_device_evidence": "Card1 and card3 target-head plus shared/separate expanded-draft-prefix timings, per-stage draft copies/submission/event span/publication; two fresh matched engine brackets with unchanged output and acceptance gates"}}
    all_rows = {}
    signatures = {}
    for directory in sorted(EVIDENCE.glob("p93-B-grid-[AB]-[012]-*")):
        name = directory.name.removeprefix("p93-B-grid-")
        run = directory / "run"
        summary = load(run / "summary.json")
        assert summary["passed"] and summary["request_count"] == 12
        identity = load(directory / "identity.json")
        load(directory / "summary.json")
        window = load(directory / "window.json")
        kernel_lines = read(directory / "kernel-window.jsonl").strip().splitlines()
        assert not kernel_lines, "Unexpected retained kernel-window messages"
        for extra in ["device-isolation.json", "ranks/device-memory-admission.json"]:
            load(run / extra)
        screen = {"path": str(directory.relative_to(ROOT)),
                  "reported_tok_s": summary["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"],
                  "reported_hit_miss_ms": summary["hit_miss_cycle_statistics"],
                  "conditions": summary["conditions"],
                  "acceptance": summary["acceptance_statistics"],
                  "identity": identity,
                  "host_window": {key: window[key] for key in ("started_utc_ns", "finished_utc_ns", "whole_host_isolated", "memory_admission", "memory_last_sample", "anonymous_peak_bytes", "clients", "device_topology", "stop_reasons", "wrapper_seal_sha256")},
                  "kernel_window_nonempty_lines": len(kernel_lines),
                  "promotable": False,
                  "prompts": {}, "rank_placement": {}}
        for rank in (0, 1):
            rp = run / "ranks" / f"rank{rank}"
            load(rp / "receipt.json")
            load(run / "ranks" / f"rank{rank}-launch.json")
            census = load(rp / "census.json")
            screen["rank_placement"][str(rank)] = {
                "drm_after_load": read(rp / "drm-memory-after_load.txt"),
                "host_memory": jsonl(rp / "host-memory.jsonl"),
                "draft_prefix": load(rp / "draft-prefix.json") if (rp / "draft-prefix.json").exists() else None,
                "draft_memory": load(rp / "draft-memory.json") if (rp / "draft-memory.json").exists() else None,
                "census_totals": census["totals"],
                "head_allocations": [a for a in census["allocations"] if a["label"] in ("card0:weight:output.weight", "card0:draft:shared-head-host")],
                "host_environment": load(rp / "host-environment.json"),
                "host_status_after_load": {line.split(":", 1)[0]: line.split(":", 1)[1].strip() for line in read(rp / "host-status-after_load.txt").splitlines() if line.split(":", 1)[0] in ("VmSwap", "Mems_allowed_list", "Cpus_allowed_list")},
            }
            if rank == 1:
                args = jsonl(rp / "prepared-arguments-parity0.jsonl")
                logits, = [a for a in args if a["label"] == "logits"]
                raw = bytes.fromhex(logits["argument_hex"])
                assert len(raw) % 16 == 0
                n = len(raw) // 16
                pointers = [int.from_bytes(raw[8*(n+i):8*(n+i+1)], "little") for i in range(n)]
                screen["rank_placement"][str(rank)]["logits_arguments"] = {"site": logits["site"], "argument_hex": logits["argument_hex"], "pointers": [hex(p) for p in pointers], "target_base_mod_2MiB": pointers[0] % (2*1024**2)}
            # Hash allocation/dispatch evidence; no raw pointer dumps in the report.
            for fn in ("plan.json", "launch-plan.json", "draft-kernel-choices.json", "draft-tensor-reads.json"):
                if (rp / fn).exists():
                    read(rp / fn)
        first99, full127 = [], []
        cycle_means = defaultdict(list)
        screen_signatures = {}
        for embedded in summary["requests"]:
            prompt = embedded["prompt_id"]
            r = load(run / prompt / "receipt.json")
            for key in ("tokens", "rank_trace", "guess_rows", "generated_token_completion_timestamps"):
                assert r[key] == embedded[key], (name, prompt, key)
            assert len(r["tokens"]) == 128 and r["cached_tokens"] == 0
            screen_signatures[prompt] = (r["prompt_token_sha256"], r["output_token_sha256"],
                                          r["guess_sequence"], [(g["position"], g["hit"]) for g in r["guess_rows"]])
            index = {(t["rank"], t["op"], t["position"], t["speculative"]): t
                     for t in r["rank_trace"] if t["op"] in (1, 3, 9)}
            assert len(index) == sum(t["op"] in (1, 3, 9) for t in r["rank_trace"])
            timers = {}
            for rank in (0, 1):
                tt = jsonl(run / prompt / f"rank{rank}" / "timings.jsonl")
                timers[rank] = {(t["position"], t["speculative"]): t for t in tt}
                assert len(timers[rank]) == len(tt)
            draft_native_rows = jsonl(run / prompt / "rank1/draft-rows.jsonl")
            draft_native = {t["draft_position"]: t for t in draft_native_rows}
            drafts = {t["position"]: t for t in r["draft_rows"]}
            assert len(draft_native) == len(draft_native_rows)
            assert len(drafts) == len(r["draft_rows"])
            rows = p85.intervals(r, 127)
            for x in rows:
                pos = x["position"]
                x["prompt_id"] = prompt
                x["prompt_class"] = r["prompt_class"]
                x["ready_ms"] = max(x["D"], x["R"] + x["C"])
                x["rank0_exposed_tail_ms"] = max(0, -x["rank0_slack_ms"])
                x["race_ms"] = x["B"] + x["rank0_exposed_tail_ms"]
                assert abs(x["elapsed_ms"] - x["ready_ms"] - x["race_ms"] - x["unresolved_control_gaps_ms"]) < 1e-8
                d = index[1, 9, pos, True]
                b = index[1, 1, pos, False]
                dr = drafts[pos + 1]
                assert abs(dr["draft_started_monotonic"] - d["sent"]) < 1e-8
                dn = draft_native[pos - 1]
                assert dn["confirmed_token"] == d["token"]
                assert abs(dn["wall_ms"] - dr["draft_wall_ms"]) < 0.0001
                x.update(D_busy_ms=d["busy_ms"], D_envelope_minus_busy_ms=x["D"]-d["busy_ms"],
                         B_busy_ms=b["busy_ms"], B_envelope_minus_busy_ms=x["B"]-b["busy_ms"],
                         draft_wall_ms=dr["draft_wall_ms"], draft_gpu_event_sum_ms=b["gpu_ms"],
                         D_minus_draft_gpu_event_sum_ms=x["D"]-b["gpu_ms"])
                for label, rank, pp, speculative in [("B", 1, pos, False), ("A", 0, pos+1, True), ("C", 0, pos, False)]:
                    if label == "C" and x["hit"]:
                        continue
                    if (pp, speculative) not in timers[rank]:
                        assert label == "A" and x["i"] == 126
                        continue
                    for key in TIMERS:
                        x[f"{label}_{key}"] = timers[rank][pp, speculative][key]
            pr = rows[:99]
            first99.extend(pr)
            full127.extend(rows)
            screen["prompts"][prompt] = {"class": r["prompt_class"],
                "first99": groups(pr, ["elapsed_ms", "D", "B", "A", "R", "C", "unresolved_control_gaps_ms", "draft_gpu_event_sum_ms", "D_minus_draft_gpu_event_sum_ms"]),
                "start_monotonic": r["request_start_monotonic"],
                "prompt_sha256": r["prompt_token_sha256"], "output_sha256": r["output_token_sha256"]}
            for hit, label in [(True, "hit"), (False, "miss")]:
                cycle_means[label].append(st.mean(x["elapsed_ms"] for x in rows if x["hit"] == hit))
        signatures[name] = screen_signatures
        screen["first99"] = groups(first99, CORE + DETAIL + [f"{c}_{k}" for c in ("B", "A", "C") for k in TIMERS])
        screen["full127"] = groups(full127, CORE + DETAIL)
        screen["recomputed_summary_hit_miss_ms"] = {key: stats(v) for key, v in cycle_means.items()}
        for key, v in cycle_means.items():
            assert abs(st.median(v) - summary["hit_miss_cycle_statistics"][key]["median"]) < 0.0001
        all_rows[name] = first99
        output["screens"][name] = screen
    assert len(output["screens"]) == 6
    assert all(value == next(iter(signatures.values())) for value in signatures.values())
    output["checks"] = {"all_six_prompt_output_guess_and_hit_sequences_identical": True,
                        "summary_requests_equal_original_receipts": True,
                        "position_joins_unique": True, "draft_wall_rows_match_by_token_and_timestamp": True,
                        "all_interval_accounting_exact": True,
                        "all_summary_hit_miss_means_reproduced": True,
                        "intervals_per_screen_first99": 1188, "intervals_per_screen_full127": 1524}
    for lane in ("A", "B"):
        controls = [f"{lane}-0-production", f"{lane}-2-production"]
        candidate = f"{lane}-1-head-transpose"
        base = st.mean(output["screens"][n]["reported_tok_s"] for n in controls)
        comparison = {"control_mean_tok_s": base,
                      "candidate_delta_percent": 100*(output["screens"][candidate]["reported_tok_s"]/base-1),
                      "first99_delta_of_group_medians_ms": {},
                      "first99_paired_delta": {}}
        for group in ("hit", "miss", "all"):
            comparison["first99_delta_of_group_medians_ms"][group] = {
                k: output["screens"][candidate]["first99"][group][k]["median"] - st.mean(output["screens"][n]["first99"][group][k]["median"] for n in controls)
                for k in CORE + DETAIL
                if output["screens"][candidate]["first99"][group][k]["median"] is not None}
        lookups = [{(r["prompt_id"], r["i"]): r for r in all_rows[n]} for n in controls]
        deltas = []
        for r in all_rows[candidate]:
            key = r["prompt_id"], r["i"]
            d = {k: r[k]-st.mean(c[key][k] for c in lookups)
                 for k in CORE + DETAIL if r.get(k) is not None}
            d["hit"] = r["hit"]
            deltas.append(d)
        comparison["first99_paired_delta"] = groups(deltas, CORE + DETAIL)
        comparison["prompts_with_hit_D_median_increase"] = sum(
            output["screens"][candidate]["prompts"][p]["first99"]["hit"]["D"]["median"] >
            st.mean(output["screens"][n]["prompts"][p]["first99"]["hit"]["D"]["median"] for n in controls)
            for p in output["screens"][candidate]["prompts"])
        output["comparisons"][lane] = comparison
    for name in ("README.md", "DO-NOT-REPEAT.md", "main.cpp", "mtp.hpp", "rank.hpp", "owner.cpp", "p93_submit.cpp", "p93_head.hpp", "microbench.cpp"):
        read(STAGE / "packet93-packed-head2" / name)
    read(ROOT / "docs/host-stability-and-fault-diagnosis.md")
    output["microbenchmarks"] = {}
    for name in ("micro-B", "micro-B2"):
        path = STAGE / "packet93-packed-head2/evidence" / name
        q = load(path / "qualification.json")
        w = load(path / "window.json")
        raw = read(path / "samples.jsonl")
        assert hashlib.sha256(raw.encode()).hexdigest() == w["samples_sha256"]
        output["microbenchmarks"][name] = {"physical_cards": w["physical_cards"], "pci": w["pci"], "head_transpose": q["candidates"]["head-transpose"], "diagnostic_only": True}
    rank1 = [s["rank_placement"]["1"] for s in output["screens"].values()]
    assert len({r["logits_arguments"]["pointers"][0] for r in rank1}) == 1
    output["checks"]["all_six_target_head_virtual_bases_identical_2MiB_aligned"] = all(r["logits_arguments"]["target_base_mod_2MiB"] == 0 for r in rank1)
    for fn in ("census.json", "plan.json", "launch-plan.json", "draft-memory.json", "draft-prefix.json", "draft-kernel-choices.json", "draft-tensor-reads.json", "prepared-arguments-parity0.jsonl"):
        paths = [str((EVIDENCE / f"p93-B-grid-{lane}-1-head-transpose/run/ranks/rank1" / fn).relative_to(ROOT)) for lane in ("A", "B")]
        assert SOURCES[paths[0]] == SOURCES[paths[1]], fn
    output["checks"]["candidate_rank1_allocation_plan_and_prepared_arguments_identical_between_lanes"] = True
    output["host_topology_snapshot"] = load(HERE / "host-topology.json")
    output["source_sha256"] = dict(sorted(SOURCES.items()))
    encoded = json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n"
    target = HERE / "analysis.json"
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        assert target.read_text() == encoded, "analysis differs from frozen receipts"
        print("PASS: deterministic recomputation; joins, hashes, accounting and six-screen parity")
    else:
        target.write_text(encoded)
        print(f"Wrote {target.relative_to(ROOT)} ({len(encoded)} bytes)")


if __name__ == "__main__":
    main()
