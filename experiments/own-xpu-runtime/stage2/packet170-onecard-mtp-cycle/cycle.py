#!/usr/bin/env python3
"""CPU-only, source-bound complete-cycle accounting; never imports a runtime."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import resource
import statistics as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = "experiments/own-xpu-runtime/stage2/"
PINS = {}
SNAPSHOTS = json.loads((HERE / "inputs.json").read_text())["files"]


def raw(path):
    p = ROOT / path
    assert p.suffix in {".json", ".jsonl", ".md", ".py", ".txt"}, path
    if path in SNAPSHOTS:
        item = SNAPSHOTS[path]
        archive = HERE / item["archive"]
        assert archive.resolve().is_relative_to(HERE / "inputs")
        packed = archive.read_bytes()
        assert hashlib.sha256(packed).hexdigest() == item["archive_sha256"]
        b = gzip.decompress(packed)
        assert len(b) == item["original_bytes"] < 10_000_000
        assert hashlib.sha256(b).hexdigest() == item["original_sha256"]
    else:
        assert p.stat().st_size < 10_000_000, path
        b = p.read_bytes()
    PINS[path] = hashlib.sha256(b).hexdigest()
    return b.decode()


def js(path):
    return json.loads(raw(path))


def ref(path, needle, pointer=None):
    lines = raw(path).splitlines()
    line = next(i for i, s in enumerate(lines, 1) if needle in s)
    return {"file_line": f"{path}:{line}", "json_pointer": pointer}


def micro_ref(path, index, op):
    text = raw(path)
    starts = list(re.finditer(r'"layer": \d+', text))
    begin = starts[index].start()
    end = starts[index+1].start() if index+1 < len(starts) else len(text)
    position = text.index(f'"{op}"', begin, end)
    return {"file_line": f"{path}:{text[:position].count(chr(10))+1}",
            "json_pointer": f"/layers/{index}/ops/{op}"}


def term(value, unit, label, sources, limitation):
    assert label in {"measured", "transferred", "assumed"}
    return dict(value=value, unit=unit, label=label, sources=sources,
                limitation=limitation)


def rate(periods, cycle_fn, acceptance):
    classes = {}
    for kind, period in periods:
        classes.setdefault(kind, []).append(1000 * (1 + acceptance) / cycle_fn(period))
    return st.median(st.median(v) for v in classes.values())


def compute():
    raw(str((HERE / "inputs.json").relative_to(ROOT)))
    paths = {
        "micro": STAGE + "packet166-m2-layer-micro/evidence/layer-micro-B1/analysis.json",
        "ao": STAGE + "packet58ao-onecard-next/analysis.json",
        "ao_doc": STAGE + "packet58ao-onecard-next/README.md",
        "aa": STAGE + "packet58aa-onecard-mtp-recheck/analysis.json",
        "aa_doc": STAGE + "packet58aa-onecard-mtp-recheck/ANALYSIS.md",
        "h": STAGE + "packet58h-onecard-mtp/feasibility.json",
        "h_doc": STAGE + "packet58h-onecard-mtp/FEASIBILITY.md",
        "aj": STAGE + "packet58aj-onecard-resident/evidence/card0-58aj-a/WS128/summary.json",
        "aj_mem": STAGE + "packet58aj-onecard-resident/MEMORY.md",
        "aj_census": STAGE + "packet58aj-onecard-resident/evidence/card0-58aj-a/WS128/run/run/census.json",
        "x": STAGE + "packet58x-cache-capacity/evidence/card0-capacity-d/max/WSCREEN/summary.json",
        "x_admission": STAGE + "packet58x-cache-capacity/admission.json",
        "aq": STAGE + "packet58aq-onecard-split/screen/evidence/card0-58aq-split-a/resident/WSCREEN/run/summary.json",
        "cpu": STAGE + "packet55-feasibility/evidence-copy/cpu-bench-receipt.json",
        "model": STAGE + "packet85-critical-path/model.json",
        "model_doc": STAGE + "packet85-critical-path/MODEL.md",
        "p77": STAGE + "screen/v4-lanes/evidence/packet77-attribution-B-a/run/summary.json",
    }
    d = {k: js(v) for k, v in paths.items() if v.endswith(".json")}
    micro, aa, h = d["micro"], d["aa"], d["h"]
    assert micro["finite_bytes_equal"] and micro["cpu_oracle_match"] and micro["zero_errors"]
    aj = d["aj"]
    assert aj["passed"] and aj["arithmetic"] == "iq3-p49-split32-v1"
    assert aj["gpu_count"] == 1 and aj["kv_dtype"] == "BF16" and aj["context"] == 4096
    assert aj["cache_bytes"] == 21_552_729_600 and len(aj["requests"]) == 12
    periods, stream_proofs = [], []
    for r in aj["requests"]:
        assert r["exact_oracle"] and r["cached_tokens"] == 0
        ts = r["token_timestamps"]
        assert len(ts) == r["output_tokens"] == 128
        periods.append((r["prompt_class"], (ts[99] - ts[0]) * 1000 / 99))
        path = paths["aj"].replace("/summary.json", f'/run/run/{r["prompt_id"]}/timings.jsonl')
        rows = [json.loads(s) for s in raw(path).splitlines()]
        assert len(rows) == 128 and [x["token_id"] for x in rows] == r["tokens"]
        assert all(x["gemv_device_ms"] == x["non_gemv_device_ms"] == 0
                   and x["enqueue_family_ms"] is None for x in rows)
        stream_proofs.append(dict(path=path, rows=len(rows), device_times="zero placeholders",
                                 enqueue_class_times=None, source=f"{path}:1"))
    measured_rate = rate(periods, lambda t: t, 0)
    assert abs(measured_rate - aj["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"]) < 1e-8
    baseline = 31.966820  # brief's rounded anchor; exact receipt is retained separately
    T = 1000 / baseline
    P = 1.11  # requested rounded publication AND drain boundary, not GPU compute
    D = h["timing"]["draft_ms"]
    R = h["timing"]["restore68_ms"]
    a_values = [0.70, 0.787, 0.85]
    feedback = d["model"]["depth2"]["op_duration_ms"]["r1_op17_spec0"]["mean"]

    refs = {
        "record": ref(paths["aj"], '"class_balanced_tok_s_1_100_intervals_after_ttft"',
                      "/class_balanced_tok_s_1_100_intervals_after_ttft/median"),
        "missing": ref(paths["ao_doc"], "measured per-kernel ranking"),
        "classes": ref(paths["ao_doc"], "Proxy rank"),
        "cache": ref(paths["x"], '"rates"', "/rates"),
        "replay": ref(paths["aa_doc"], "Current 21.553 GB, M1"),
        "union": ref(paths["aa_doc"], "16.515053"),
        "draft": ref(paths["h_doc"], "D = 1.794747301"),
        "feedback": ref(paths["model_doc"], "Confirmed draft feedback"),
        "restore": ref(paths["h_doc"], "0.980923 ms"),
        "selection": ref(paths["h_doc"], "Prefix selection copies"),
        "memory": ref(paths["aj_mem"], "full device-owned bound"),
        "publication": ref(paths["aq"], '"device_publication_and_drain"',
                           "/paired_differences/device_publication_and_drain"),
    }

    # Every micro operation has its own measured ratio; no layer ratio is
    # multiplied into the full wall period. Actual current-line shares stay null.
    class_rows = []
    for family in ("GDN", "QSA"):
        samples = [x for x in micro["layers"] if x["family"] == family]
        sample_indexes = [i for i,x in enumerate(micro["layers"]) if x["family"] == family]
        for op in samples[0]["ops"]:
            if op.startswith("layer_device_"):
                continue
            values = [x["ops"][op]["m2_over_m1"] for x in samples]
            class_rows.append(dict(family=family, op=op, ratio_min=min(values), ratio_max=max(values),
                                   ratio_label="measured", current_M1_ms=None,
                                   current_M1_share=None, current_V2_ms=None,
                                   sources=[micro_ref(paths["micro"], i, op)
                                            for i in sample_indexes]))

    # Historical rank1 body proxy, explicitly NOT packet58aj's measured shares.
    mapping = {
        "dense_attention": ["projection", "attention_projection"],
        "gate_up": ["expert_gate_up"], "hc_gate": ["hc_gate_mix"],
        "down": ["expert_down"],
        "small_remaining": ["expert_activation", "combine", "conv", "gdn_norm_gate", "qsa_prepare", "qsa_pool"],
        "hc_low": ["hc_low_inject"], "route": ["route_shared_activation"],
        "router_tuple": ["small_tuple"], "recurrence": ["gdn_recurrence"],
        "hc_norm": ["hc_norm"], "qsa_attention_select": ["qsa_attention", "qsa_select"],
        "shared_fused": ["shared_down_mix"], "small_dense": ["projection", "small_tuple"],
    }
    proxy = []
    for row in d["ao"]["class_ranking_proxy_only"]:
        assert row["one_card_ms"] is None
        ops = mapping[row["class"]]
        rs = [x["ops"][op]["m2_over_m1"] for x in micro["layers"] for op in ops if op in x["ops"]]
        m1 = 2 * row["diagnostic_two_card_half_ms"]
        proxy.append(dict(op_class=row["class"], mapped_ops=ops, label="transferred",
                          doubled_historical_M1_ms=m1, V2_low_ms=m1*min(rs), V2_high_ms=m1*max(rs),
                          sources=[refs["classes"]], ratio_min=min(rs), ratio_max=max(rs)))
    body1 = sum(x["doubled_historical_M1_ms"] for x in proxy)
    body2 = {k: sum(x[f"V2_{k}_ms"] for x in proxy) for k in ("low", "high")}
    residual = T - body1 - P
    assert residual > 0

    # Native measured capacity effect, not a native count of missed experts.
    rates = d["x"]["rates"]
    assert d["x"]["passed"] and len(rates) == 5
    deltas = [1000/rates[i] - 1000/rates[j] for i in (2, 4) for j in (1, 3)]
    replays = {}
    for name, replay in aa["replays"].items():
        row = replay["per_token"]  # field means per CYCLE for M2 in this source
        n = sum(row[f"zero_copy_bytes_layer{i}"] / (2_329_600 if i == 2 else 1_971_200)
                for i in range(48))
        replays[name] = dict(missing_expert_reads=n, logical_miss_bytes=row["zero_copy_bytes"],
                             fill_bytes=row["demand_bytes"], label="transferred",
                             denominator="cycle" if "M2" in name else "position",
                             source=ref(paths["aa"], f'"{name}"', f"/replays/{name}/per_token"))
    n1 = replays["current_M1"]["missing_expert_reads"]
    nr = replays["resident_M1"]["missing_expert_reads"]
    dn = nr - n1
    assert dn > 0
    # Normalization is a declared cross-workload assumption, NOT an isolated
    # measured miss latency; it includes native exposed fill/maintenance effects.
    effective = [min(deltas)/dn, max(deltas)/dn]
    cpu_prices = {}
    for threads in (8, 12):
        result_indexes = [i for i,r in enumerate(d["cpu"]["results"]) if r["threads"] == threads]
        rows = [c for r in d["cpu"]["results"] if r["threads"] == threads
                for c in r["cases"] if c["layer_latency_measured"]]
        cpu_prices[str(threads)] = dict(
            measured_ms_per_expert_min=min(c["median_us_per_expert"] for c in rows)/1000,
            measured_ms_per_expert_max=max(c["median_us_per_expert"] for c in rows)/1000,
            sources=[ref(paths["cpu"], f'"threads": {threads}', f"/results/{i}/cases")
                     for i in result_indexes],
            label="measured", scope="CPU exact synthetic experts, 4/6/10-miss batches; NOT GPU zero-copy latency")

    # Match prompt IDs AND hashes before claiming the acceptance suite matches.
    def prompt_map(summary):
        return {r["prompt_id"]: r["prompt_token_sha256"] for r in summary["requests"]}
    same_prompts = prompt_map(d["p77"]) == prompt_map(aj)

    # Complete symbolic cycle. Missing timings explicitly fail the positive gate.
    terms = {
        "V2_layer_compute": term(None, "ms/cycle", "transferred", [refs["missing"]],
                                 "Per-op micro ratios measured; packet58aj M1 shares absent. IQ3 layer2 unmeasured in micro."),
        "embedding_PLE": term(None, "ms/cycle", "assumed", [refs["missing"]],
                              "Two causal row preparations, provisional PLE/history private; use 2*E1 in charged sensitivity, E1 unknown."),
        "head_final_norm_argmax": term(None, "ms/cycle", "assumed", [refs["classes"]],
                                      "Two full target decisions, unchanged reduction/ties. Use 2*H1; no measured full-head M2 ratio."),
        "exposed_host_issue": term(None, "ms/cycle", "assumed", [refs["missing"]],
                                   "5.053453 ms enqueue and 0.206020 prepare are overlapping spans, not exclusive additive costs. I2 unknown; no graph/replay savings."),
        "target_cache_miss_service": term(None, "ms/cycle", "transferred", [refs["cache"], refs["replay"]],
                                          "Actual causal M2 cost and rejected-route misses absent; do not multiply union twice."),
        "D": term(D, "ms/cycle", "transferred", [refs["draft"]],
                  "Resident historical 91,392-prefix command on rank1, now serialized with all 48 target layers. No rank overlap."),
        "F_feedback_repair": term(None, "ms/cycle", "transferred", [refs["feedback"]],
                                  f"Historical feedback {feedback:.9f} ms when required; frequency and one-card repair unmeasured. Charged sensitivity pays one per cycle."),
        "R_rejected_row": term(R, "ms/rejection", "transferred", [refs["restore"]],
                               "Charge (1-a)*R. Proxy includes rollback, not the target re-evaluation (already in V2)."),
        "S_target_state_selection": term(None, "ms/cycle", "assumed", [refs["selection"], refs["restore"]],
                                        "Snapshot/init/select before releasing private rows; charged sensitivity assigns one R per cycle, not a proven bound."),
        "P_publication_and_drain": term(P, "ms/cycle", "transferred", [refs["publication"]],
                                        "Rounded 1.11 ms once per pair, conditional on preserved dependency/staging lifetime. Measured differences 1.107661/1.111002; drain alone ~1.071 ms."),
        "E_extra_fill_and_cache": term(None, "ms/cycle", "assumed", [refs["cache"], refs["replay"]],
                                       "Native capacity normalization below includes exposed fill cost; add zero separate fill in that sensitivity to avoid double charge. Actual M2 scheduling unknown."),
        "draft_cache_pollution": term(0, "ms/cycle", "assumed", [refs["replay"]],
                                      "Only resident-draft option: draft experts never enter target LRU; target cache capacity already reduced. Shared-cache cost is unknown, not zero."),
    }

    # A per-class sensitivity, NOT a conservative bound. Both endpoints retain
    # missing non-layer subdivisions rather than inventing measured shares.
    # Once/twice residual carries the same multiplicity of base miss service;
    # only N2-k*N1 is extra. This prevents counting M1 remote cost twice.
    scenarios = []
    for name, side, k, fill_price_index, feedback_n, select_n, cache_key in [
        ("favorable_missing_costs", "low", 1, 0, 0, 0, "resident_M2_union"),
        ("charged_sensitivity", "high", 2, 1, 1, 1, "resident_M2_two_reads"),
    ]:
        extra_misses = replays[cache_key]["missing_expert_reads"] - k*n1
        assert extra_misses > 0
        cache_charge = extra_misses * effective[fill_price_index]
        fixed = body2[side] + P + cache_charge + D + feedback_n*feedback + select_n*R
        for a in a_values:
            def cycle(t, a=a):
                return fixed + k*(t-body1-P) + (1-a)*R
            c = cycle(T)
            tps = 1000*(1+a)/c
            no_drain_tps = 1000*(1+a)/(c-P)
            rows = dict(name=name, acceptance=a, label="assumed", complete_supported_bound=False,
                        layer_V2_ms=body2[side], unpartitioned_nonlayer_ms=k*residual,
                        residual_multiplicity=k, cache_miss_delta_count=extra_misses,
                        cache_and_exposed_fill_delta_ms=cache_charge,
                        draft_ms=D, feedback_ms=feedback_n*feedback, state_selection_ms=select_n*R,
                        rejection_ms=(1-a)*R, publication_ms=P, cycle_ms=c,
                        aggregate_anchor_tps=tps, aggregate_gain_percent=100*(tps/baseline-1),
                        per_prompt_class_balanced_tps=rate(periods, cycle, a),
                        drain_free_baseline_tps=1000/(T-P), drain_free_MTP_tps=no_drain_tps,
                        drain_free_gain_percent=100*(no_drain_tps/(1000/(T-P))-1),
                        MTP_with_drain_vs_drain_free_baseline_percent=100*(tps/(1000/(T-P))-1),
                        sources=[refs["classes"], refs["cache"], refs["replay"], refs["draft"], refs["feedback"], refs["restore"], refs["publication"]])
            scenarios.append(rows)

    # Census-based declared lifetime design. Target canonical + two private rows;
    # sequential one-card draft/target work shares the existing workspace bound.
    census = d["aj_census"][0]
    categories = {}
    for x in census["allocations"]:
        if x["live"] and x["memory"] == "device":
            categories[x["category"]] = categories.get(x["category"], 0) + x["bytes"]
    mutable = sum(categories[x] for x in ("workspace", "KV", "recurrent-state"))
    assert mutable == h["memory"]["target_mutable_row_bytes"]
    hm = h["memory"]
    private = 2*mutable + hm["draft_kv_bytes"] + hm["draft_workspace_bytes"] + 262_144
    weights = sum(x["bytes"] for x in hm["draft_weight_rows"])
    assert weights == 3_326_953_472
    adm = d["x_admission"]["admission"]
    device_bound = adm["device_owned_bound_bytes"]
    reserve, driver = adm["device_reserve_bytes"], adm["driver_allowance_bytes"]
    floor = adm["physical_capacity_floor_bytes"]
    assert floor-device_bound-reserve-driver == 240
    resident_cost = weights+hm["draft_kv_bytes"]
    shared_cost = resident_cost-3_145_728_000+49_152
    host_base = 98_990_252_032  # current packet58aj, not old 58z's floor
    assert str(host_base).replace(",", "") in raw(paths["aj_mem"]).replace(",", "")
    excluded_bytes = 5 * 2 * 1024**3
    # Deliberately debit all five blocks even if four were already excluded.
    # This avoids depending on the historical snapshot's exact fence state.
    safe_host_floor = adm["historical_available_floor_bytes"] - excluded_bytes
    layouts = []
    for key, cost in [("resident_draft_experts", resident_cost), ("shared_cache_draft_experts", shared_cost)]:
        old = hm["options"][key]
        arena = (adm["cache_bytes"] - cost) // 256 * 256
        extra_device = old["extra_device_payload_bytes"]
        direct_host = old["extra_direct_host_payload_bytes"]
        required_host = host_base + extra_device + direct_host
        layouts.append(dict(layout=key, label="transferred", extra_device_bound=cost,
                            arena_bytes=arena, target_capacity_if_all_draft_resident=arena-(3_145_728_000 if key.startswith("shared") else 0),
                            new_device_owned_bound=device_bound-adm["cache_bytes"]+arena+cost,
                            driver_allowance=driver, device_reserve=reserve,
                            device_margin=floor-(device_bound-adm["cache_bytes"]+arena+cost+driver+reserve),
                            actual_payload_projection=census["totals"]["device"]+extra_device-(adm["cache_bytes"]-arena),
                            extra_payload_backing=extra_device, extra_direct_host=direct_host,
                            required_host_available=required_host,
                            host_margin_after_all_five_blocks_debited=safe_host_floor-required_host,
                            sources=[refs["memory"], ref(paths["h_doc"], "Extra actual device payload")]))
    memory = dict(device_categories=adm["device_categories"], current_actual_device=census["totals"]["device"],
                  original_device_bound=device_bound, current_spare_bytes=240,
                  current_host_required_available=host_base, layouts=layouts,
                  target_mutable_row_bytes=mutable, private_transaction_bytes=private,
                  private_transaction_margin=1024**3-private,
                  canonical_plus_draft_workspace=categories["workspace"]+hm["draft_workspace_bytes"],
                  workspace_margin=1024**3-categories["workspace"]-hm["draft_workspace_bytes"],
                  host_historical_floor=adm["historical_available_floor_bytes"],
                  excluded_blocks=[53,54,55,56,57], excluded_bytes=excluded_bytes,
                  deliberately_double_debited_floor=safe_host_floor,
                  declared_accounting_fits=all(x["device_margin"] >= 0 and x["host_margin_after_all_five_blocks_debited"] >= 0 for x in layouts),
                  implementation_lifetime_proven=False, live_admission=False,
                  limitation="Complete declared private-row layout fits existing allowances; no M2 implementation census proves scratch aliasing, extent/history metadata or staging lifetime.",
                  sources=[refs["memory"], ref(paths["h_doc"], "Two target mutable rows"),
                           ref(paths["h_doc"], "blocks 53–56 offline"),
                           ref(paths["x_admission"], '"historical_available_floor_bytes"')])
    assert private <= 1024**3 and memory["workspace_margin"] > 0 and memory["declared_accounting_fits"]
    ceilings = []
    for a in a_values:
        maximum = (1+a)*T/1.03
        ceilings.append(dict(acceptance=a, label="assumed", max_complete_cycle_ms=maximum,
                             max_V2_plus_F_S_E_excluding_publication_ms=maximum-D-(1-a)*R-P,
                             drain_free_max_complete_cycle_ms=(1+a)*(T-P)/1.03,
                             drain_amortization_credit_per_cycle=a*P,
                             drain_amortization_credit_ms_per_verified_token=a*P/(1+a)))
    unknowns = ["packet58aj per-class M1 shares", "non-layer embedding/PLE and full head M2 times",
                "exposed host issue", "native causal M2 cache misses including wrong proposals",
                "one-card draft/feedback cost and frequency", "target snapshot/selection lifetime and time"]
    # Every unavailable duration propagates to the complete cycle. In
    # particular, do not let the numeric sensitivities supply the primary gate.
    primary_cycle = None if any(t["value"] is None for t in terms.values()) else (
        sum(t["value"] for k,t in terms.items() if k != "R_rejected_row") + (1-0.787)*R)
    conservative_gain = None if primary_cycle is None else 100*((1+0.787)*T/primary_cycle-1)
    qualified = (conservative_gain is not None and conservative_gain >= 3
                 and memory["declared_accounting_fits"] and memory["implementation_lifetime_proven"])
    return dict(schema="packet170.complete-cycle-accounting.v1",
                decision="build-plan" if qualified else "close-no-build",
                build_gate_passed=qualified, device_executed=False, measured_MTP_speed=False,
                runtime_changed=False, target_arithmetic="iq3-p49-split32-v1", strict512=False,
                baseline=dict(rounded_tps=baseline, measured_tps=measured_rate, reciprocal_ms=T,
                              source=refs["record"], label="measured", reciprocal_is_modeling_anchor_not_mean=True),
                primary=dict(V2_ms=None, cycle_ms=primary_cycle, gain_percent=conservative_gain,
                             supported_conservative_gain_at_least_3_percent=conservative_gain is not None and conservative_gain >= 3,
                             missing_inputs=unknowns, class_rows=class_rows, terms=terms,
                             formula="C=V2_layers+embedding_PLE+head+exposed_issue+target_misses+D+F+S+(1-a)*R+P+E"),
                acceptance=dict(requested=0.787, historical_measured=h["timing"]["transferred_acceptance"],
                                label="transferred", same_prompt_ids_and_token_hashes=same_prompts,
                                source=ref(paths["model_doc"], "p = 100/127"),
                                historical_scope="Same IQ3 arithmetic, 12-prompt suite, two-card packet77, depth-one 91,392-prefix draft; not one-card causal M2 acceptance."),
                ceilings=ceilings, missing_class_stream_proofs=stream_proofs,
                proxy_per_class=proxy, proxy_M1_body_ms=body1, proxy_V2_body_ms=body2,
                proxy_nonlayer_residual_ms=residual,
                proxy_warning="Doubled p128b rank1 diagnostic, instrumentation gate failed, no one-card shares. Min/max class mapping and residual once/twice are sensitivities, not confidence bounds or measurements.",
                cache=dict(native_capacity_rates=rates, native_capacity_period_deltas_ms=deltas,
                           capacity_delta_label="measured", source=refs["cache"],
                           observed_18GB_miss_count=aa["diagnostic58y"]["counters_per_token"]["misses"],
                           observed_18GB_miss_bytes=aa["diagnostic58y"]["counters_per_token"]["miss_bytes"],
                           replay=replays, replay_shrink_extra_misses=dn,
                           effective_capacity_price_ms_per_extra_miss=effective,
                           effective_price_label="assumed",
                           normalization="Native 18-vs-21.553GB period delta / replay 18.216-vs-21.553GB M1 extra misses. Cross-workload sensitivity, NOT measured sparse-miss latency or interpolated 18.216GB measurement. Includes exposed fills; no second fill charge.",
                           union55=aa["union55"], union138=aa["union138"],
                           missing_native_M2=True, shared_draft_pollution_cost_ms=None),
                cpu_miss_alternative=dict(prices=cpu_prices, requested_rounded_ms_per_expert=0.5,
                                         round_value_label="assumed",
                                         resident_M1_shrink_extra_ms_at_0_5=dn*0.5,
                                         M2_union_miss_service_ms_at_0_5=replays["resident_M2_union"]["missing_expert_reads"]*0.5,
                                         M2_separate_miss_service_ms_at_0_5=replays["resident_M2_two_reads"]["missing_expert_reads"]*0.5,
                                         applies_to_current_zero_copy_path=False, reopened=False),
                memory=memory, scenarios=scenarios, sources_sha256=dict(sorted(PINS.items())))


def main():
    resource.setrlimit(resource.RLIMIT_AS, (2_000_000_000, 2_000_000_000))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="recompute and compare without writing")
    args = parser.parse_args()
    result = compute()
    # Fail closed independently of favorable arithmetic; all sensitivity cases
    # must retain their unsupported-bound marker and original target identity.
    assert not result["build_gate_passed"] and result["primary"]["cycle_ms"] is None
    assert not any(x["complete_supported_bound"] for x in result["scenarios"])
    charged = [x for x in result["scenarios"] if x["name"] == "charged_sensitivity"]
    assert all(y["aggregate_anchor_tps"] > x["aggregate_anchor_tps"] for x,y in zip(charged, charged[1:]))
    assert all(x["cycle_ms"] > x["publication_ms"] for x in result["scenarios"])
    output = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.check:
        assert (HERE / "cycle.json").read_text() == output, "cycle.json differs from source-bound recomputation"
    else:
        (HERE / "cycle.json").write_text(output)
    print(json.dumps({"check": args.check, "decision": result["decision"],
                      "primary_cycle_ms": None, "declared_memory_fits": result["memory"]["declared_accounting_fits"],
                      "inputs": len(PINS), "maxrss_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))


if __name__ == "__main__":
    main()
