#!/usr/bin/env python3
"""Packet177: price structural two-card options against the bundle-8 census.

CPU-only arithmetic. Reads no model bytes, opens no device, writes options.json
next to this file only when run with --write. Every input carries a label:
  measured    - a retained device receipt on this model (path given)
  transferred - a device receipt from a different identity (older bundle,
                synthetic layer micro, transport-only harness)
  assumed     - an engineering assumption, never evidence
Outputs are conditional planning numbers, never speeds.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
S2 = "experiments/own-xpu-runtime/stage2"


def inp(value, label, source):
    assert label in ("measured", "transferred", "assumed")
    return {"value": value, "label": label, "source": source}


I = {
    # packet160 record-interval reconstruction of packet136 bundle 8 (1,188 intervals)
    "record_tok_s": inp(58.798108759, "measured", f"{S2}/packet160-critical-path/PLAN.md"),
    "hits": inp(932, "measured", f"{S2}/packet160-critical-path/PLAN.md"),
    "misses": inp(256, "measured", f"{S2}/packet160-critical-path/PLAN.md"),
    "T_hit_ms": inp(14.704424, "measured", f"{S2}/packet160-critical-path/PLAN.md"),
    "T_miss_ms": inp(25.613427, "measured", f"{S2}/packet160-critical-path/PLAN.md"),
    "D_ms": inp(1.597226, "measured", "packet160 hit mean"),
    "A_ms": inp(12.482216, "measured", "packet160 hit mean (rank0 next-A host envelope)"),
    "B_ms": inp(13.086387, "measured", "packet160 hit mean (rank1 body+target head+suffix/merge)"),
    "R_ms": inp(0.551168, "measured", "packet160 miss mean"),
    "C_ms": inp(11.818807, "measured", "packet160 miss mean"),
    "rank0_capture_ms": inp(0.743247, "measured", "packet150 rank0 capture/accept/rollback host scope"),
    "rank0_draft_wait_ms": inp(1.23, "measured", "packet154 rank0 wait for rank1 draft (draft-line closure note)"),
    # packet168 census v3, ms per body pass summed over both ranks
    "dense_hc_ms": inp(11.53183, "measured", f"{S2}/packet168-twocard-body-census/evidence/device-census-B-v3/CENSUS.md"),
    "dense_hc_rank": inp([5.574, 5.955], "measured", "notes/2026-10-19-own-runtime-packet168.md"),
    "routed_experts_ms": inp(5.53478, "measured", "packet168 v3"),
    "router_shared_ms": inp(3.34122, "measured", "packet168 v3"),
    "gdn_ms": inp(2.0499, "measured", "packet168 v3"),
    "norms_glue_ms": inp(1.8347, "measured", "packet168 v3"),
    # share of dense_hc that is HC (replicated in any exact split): packet110 synthetic layers
    "hc_share_of_dense": inp(0.29, "transferred", f"{S2}/packet110-class-roofline/ROOFLINE.md (GDN 66.4/228 us, QSA 66.0/240 us)"),
    # transport
    "peer10k_event_us": inp(3.3, "transferred", f"{S2}/packet12-peer/cards2-3-20261011/receipt.json (device event time, 10 KiB peer copy)"),
    "peer10k_wall_us": inp(18.6, "transferred", "packet12 receipt, wall median incl. submit+wait"),
    "peer_round_us": inp(52.33, "transferred", "packet12 60 dependent peer rounds"),
    "bounce_hidden_idle_us": inp(15.19, "measured", f"{S2}/packet87t-transfer-micro/RESULT.json hidden/idle"),
    "bounce_hidden_busy_us": inp(66.44, "measured", "packet87t hidden/compute (export behind queued compute)"),
    # exact within-layer split (packet45 step-1 proof): 3 data phases/layer (+1 route check)
    "tp_data_phases": inp(144, "measured", "notes/2026-10-15-p45-within-layer-split-step1.md (48 layers x 3, dependency proof on executed plans)"),
    "tp_replicated_ms": inp(7.37714, "transferred", "p45 step-1 partial replicated work R (S7 K2 kernels; excludes norms/mixes/PLE/indexer)"),
    "tp_split_fixed_ms": inp(0.75, "assumed", "half-shape kernels keep their ~3-5 us launch/tail floor: ~10 split launches/layer x 48 x ~1.5 us"),
    "expert_imbalance_ms": inp(0.68, "transferred", "TWO-CARD-TP.md E[max]=6.23/10 uniform-routing model on 5.535 ms experts"),
    # closed placement / depth / format results
    "p120_25_23_pct": inp(-3.9, "measured", "notes/2026-10-18-own-runtime-packet120-grid-result.md"),
    "p127_head_rows_pct": inp(-1.95, "measured", "notes/2026-10-18-own-runtime-packet127-grid-result.md"),
    "p79_draft_rank0_pct": inp([-2.3, -1.3], "measured", "notes/2026-10-17-own-runtime-packet79.md"),
    "p71c_depth2_pct": inp(-46.8, "measured", "packet160 PLAN.md (d3)"),
    "p74_packed_dense_pct": inp([-0.8, -2.4, -2.9], "measured", f"{S2}/packet74-packed-dense/DO-NOT-REPEAT.md"),
    "p175_d2_ratio": inp(1.44, "measured", "notes/2026-10-19-own-runtime-packet175.md (dense 1.44x slower)"),
    "m2_layer_ratio": inp(1.60, "measured", f"{S2}/packet166-m2-layer-micro/evidence/layer-micro-B1/analysis.json (1.58-1.63, exact per row)"),
    "copy_stalls_two_card_ms": inp(0.1, "measured", "upper bound from p154 transport 0.051 ms + p160 G 0.021/0.013 ms per interval"),
    "d1_mid_pct": inp(0.68, "assumed", "packet173 lever table mid estimate (micro pending)"),
    # dense formats (loaded bytes per weight), packet110 BYTE-MODEL.md
    "q6_expanded_Bpw": inp(1.25, "measured", f"{S2}/packet110-class-roofline/BYTE-MODEL.md (K + 4K/16)"),
    "q6_gguf_Bpw": inp(210 / 256, "measured", "GGUF Q6_K block 210 B / 256 weights"),
    "q8_expanded_Bpw": inp(1.125, "measured", "BYTE-MODEL.md (K + 4K/32)"),
    "q8_gguf_Bpw": inp(34 / 32, "measured", "GGUF Q8_0 block 34 B / 32 weights"),
    "dense_bw_bound_frac": inp(0.85, "assumed", "share of non-HC dense time that scales with bytes (big GEMVs run 0.79-0.93 of the 537 GB/s copy reference, packet110)"),
}


def v(k):
    return I[k]["value"]


def interval_mean(t_hit, t_miss):
    h, m = v("hits"), v("misses")
    return (h * t_hit + m * t_miss) / (h + m)


BASE = interval_mean(v("T_hit_ms"), v("T_miss_ms"))  # pooled mean ms/token
REC_MS = 1000.0 / v("record_tok_s")                  # metric-equivalent ms/token


def pct_from_ms(t_ms):
    """Gain vs record using the pooled-mean ratio (metric is a median of medians)."""
    return 100.0 * (BASE / t_ms - 1.0)


def option_a():
    w = v("A_ms") + v("B_ms") - v("rank0_capture_ms")   # generous: drop capture
    compute = (w + v("tp_replicated_ms")) / 2.0
    rows = {}
    for name, lat in (("device_event_floor", v("peer10k_event_us")),
                      ("bounce_idle", v("bounce_hidden_idle_us")),
                      ("peer_wall", v("peer10k_wall_us")),
                      ("peer_round", v("peer_round_us"))):
        ex = v("tp_data_phases") * lat / 1000.0
        t_free = compute + ex
        t_real = t_free + v("tp_split_fixed_ms") + v("expert_imbalance_ms")
        rows[name] = {"phase_us": lat, "exchange_ms": round(ex, 3),
                      "T_ideal_ms": round(t_free, 3), "pct_ideal": round(pct_from_ms(t_free), 2),
                      "T_with_split_costs_ms": round(t_real, 3), "pct_with_split_costs": round(pct_from_ms(t_real), 2)}
    # break-even per-phase latency with zero split costs
    be = (BASE - compute) / v("tp_data_phases") * 1000.0
    return {"compute_ms": round(compute, 3), "rows": rows, "break_even_phase_us_ideal": round(be, 2)}


def option_b():
    # perfect redistribution of rank0's measured draft wait (zero transfer cost)
    save_hit = v("rank0_draft_wait_ms") / 2.0
    t = interval_mean(v("T_hit_ms") - save_hit, v("T_miss_ms"))
    return {"ceiling_save_ms_per_hit": round(save_hit, 3), "ceiling_pct": round(pct_from_ms(t), 2),
            "measured_moves_pct": [v("p120_25_23_pct"), v("p127_head_rows_pct")] + v("p79_draft_rank0_pct") + [v("p71c_depth2_pct")]}


def option_c():
    nonhc = v("dense_hc_ms") * (1 - v("hc_share_of_dense"))
    hc = v("dense_hc_ms") * v("hc_share_of_dense")
    f = v("dense_bw_bound_frac")
    out = {}
    # S1a: read the fp16 d + int8 sub-scales the expanded row already retains (no repack)
    # S1b: load-time re-layout to FP32 d + int8 sub-scales per 256 (Q8: FP32 d per 32)
    # S2:  6-bit planar codes + FP32 scales (needs a new unpack mechanism, p74 boundary)
    # S3:  GGUF packing with free unpack: the byte ceiling only (p74 measured a loss)
    for name, q6, q8 in (("S1a_retained_metadata_scales", 1.0 + 18 / 256, 1.0 + 2 / 32),
                         ("S1b_fp32_d_plus_int8_sc", 1.0 + 20 / 256, 1.125),
                         ("S2_planar6_codes_fp32_scales", 0.75 + 0.25, 1.125),
                         ("S3_gguf_pack_free_unpack", v("q6_gguf_Bpw"), v("q8_gguf_Bpw"))):
        cut_q6 = 1 - q6 / v("q6_expanded_Bpw")
        cut_q8 = 1 - q8 / v("q8_expanded_Bpw")
        lane_ms = nonhc * f * cut_q6            # p33::dense_lane scope (large Q6 projections, out-proj, shared)
        hc_ms = hc * 0.6 * cut_q8               # p60/p73 HC Q8 kernels run at only ~0.3-0.67 of roofline (assumed 0.6)
        row = {"q6_byte_cut": round(cut_q6, 3), "q8_byte_cut": round(cut_q8, 3)}
        for scope, card_ms in (("dense_lane_only", lane_ms), ("dense_lane_plus_hc", lane_ms + hc_ms)):
            # both halves shrink about equally: the hit path saves half, the miss path (C+B) saves all
            t = interval_mean(v("T_hit_ms") - card_ms / 2, v("T_miss_ms") - card_ms)
            row[scope] = {"card_ms_saved_if_free": round(card_ms, 3), "ceiling_pct": round(pct_from_ms(t), 2)}
        out[name] = row
    out["measured_p74_pct"] = v("p74_packed_dense_pct")
    return out


def option_d():
    # two independent sequences, pipeline-parallel, no draft/speculation/capture
    a = v("A_ms") - v("rank0_capture_ms")
    b = v("B_ms")
    slot = max(a, b) + v("bounce_hidden_idle_us") / 1000.0
    agg = 1000.0 / slot
    slot2 = max(a, b) * v("m2_layer_ratio") + v("bounce_hidden_idle_us") / 1000.0
    agg4 = 2000.0 / slot2
    return {"slot_ms": round(slot, 3), "aggregate_tok_s": round(agg, 2), "per_user_tok_s": round(agg / 2, 2),
            "vs_single_user_pct": round(100 * (agg / v("record_tok_s") - 1), 1),
            "four_seq_m2_slot_ms": round(slot2, 3), "four_seq_m2_aggregate_tok_s": round(agg4, 1),
            "localmaxxing_recordable": False,
            "note": "aggregate only; docs/localmaxxing.md withholds aggregate tokSOut; publishable as a neural.download concurrency profile"}


def option_e_transfer():
    # export behind queued compute on the critical handoff (87t), if any remains per interval
    d = (v("bounce_hidden_busy_us") - v("bounce_hidden_idle_us")) / 1000.0
    t = interval_mean(v("T_hit_ms") - d, v("T_miss_ms") - d)
    t2 = interval_mean(v("T_hit_ms") - v("copy_stalls_two_card_ms"), v("T_miss_ms") - v("copy_stalls_two_card_ms"))
    return {"busy_minus_idle_ms": round(d, 4), "ceiling_pct_one_handoff": round(pct_from_ms(t), 2),
            "all_copy_stalls_removed_pct": round(pct_from_ms(t2), 2),
            "wait_policy": "two-card already pure spin (P56X_SLEEP20=0); no fills; all copies on the in-order CCS queue"}


def table(a, b, c, d, e):
    s1 = c["S1a_retained_metadata_scales"]
    return [
        {"id": "a", "name": "intra-layer tensor parallelism of dense/HC GEMVs (exact row split, 3 data phases/layer)",
         "single_user_pct": {"ideal_at_device_copy_floor": a["rows"]["device_event_floor"]["pct_ideal"],
                             "with_split_costs_at_floor": a["rows"]["device_event_floor"]["pct_with_split_costs"],
                             "at_measured_peer_wall": a["rows"]["peer_wall"]["pct_with_split_costs"],
                             "at_measured_dependent_round": a["rows"]["peer_round"]["pct_with_split_costs"]},
         "break_even_phase_us": a["break_even_phase_us_ideal"],
         "labels": "compute from measured A/B; replicated work transferred (p45 K2); phase latency transferred (packet12); split costs assumed",
         "verdict": "closed: even a 3.3 us/phase device-copy floor with zero split overhead stays under +3%; it replaces the speculative pipeline and pays ~7.4 ms replicated HC/router/shared work per card",
         "prior": ["notes/2026-10-15-p45-within-layer-split-step1.md (REJECT)", "packet14-tp2 (41 exchanges, 1.53 ms/layer)", "packet160 (a1-a3, c)", "packet148 row/head cooperation +1.0-1.9%"]},
        {"id": "b", "name": "different layer placement / pipeline depth / interleave",
         "single_user_pct": {"ceiling_perfect_rebalance": b["ceiling_pct"], "measured": b["measured_moves_pct"]},
         "labels": "ceiling from measured rank0 draft wait 1.23 ms; moves measured",
         "verdict": "closed: every measured move lost (25/23 -3.9%, head rows -1.95%, draft on rank0 -2.3/-1.3%, depth-2 -46.8%); interleaving one sequence needs depth>=2 guessing",
         "prior": ["packet120", "packet127", "packet79", "packet71c", "packet123", "packet156", "draft-line closure"]},
        {"id": "c", "name": "lossless dense byte reduction (same values, different read layout)",
         "single_user_pct": {k: c[k]["dense_lane_only"]["ceiling_pct"] for k in c if k.startswith("S")},
         "measured_p74_pct": c["measured_p74_pct"],
         "labels": "byte cuts measured from the format; time transfer f=0.85 assumed; p74 measured",
         "verdict": "OPEN: S1 (read retained fp16 d + int8 sub-scales instead of expanded FP32 scales) cuts Q6 dense bytes 14.4%% with one multiply per 8-weight lane step; ceiling +%.2f%%. S2/S3 need a new unpack mechanism (p74)." % s1["dense_lane_only"]["ceiling_pct"],
         "recommended": True},
        {"id": "d", "name": "two-sequence pipeline (multi-user aggregate, separate class)",
         "aggregate_tok_s": d["aggregate_tok_s"], "per_user_tok_s": d["per_user_tok_s"],
         "four_seq_m2_aggregate_tok_s": d["four_seq_m2_aggregate_tok_s"],
         "labels": "slot from measured A/B; M2 ratio measured (packet166); schedule modelled",
         "verdict": "second metric only: exact by construction (M=1 kernels per sequence), +30% aggregate, but LocalMaxxing withholds aggregate tokSOut; neural.download concurrency profile only",
         "localmaxxing_recordable": False},
        {"id": "e1", "name": "host wait policy / copy engine on two cards",
         "single_user_pct": {"remove_all_copy_stalls": e["all_copy_stalls_removed_pct"]},
         "labels": "measured (p154/p160/p134); audit of base/ tree",
         "verdict": "nothing to port: two-card waits are already pure spin (sleep20=0, 0 voluntary switches/half), no fills exist, every copy is on the in-order CCS queue; total copy-related stall <0.1 ms/token"},
        {"id": "e2", "name": "3-card / 4-card pipelines",
         "verdict": "out of scope for the 2-card record class; a single sequence over more stages needs depth>=2 speculation (p71c -46.8%) or TP (closed above)"},
    ]


def main():
    a, b, c, d, e = option_a(), option_b(), option_c(), option_d(), option_e_transfer()
    res = {
        "schema": "packet177.structural-options.v1",
        "diagnostic_only": True, "device_executed": False,
        "note": "conditional planning numbers, not speeds; pct is vs the pooled interval mean of the 58.798109 record",
        "base_pooled_mean_ms": round(BASE, 4), "record_equivalent_ms": round(REC_MS, 4),
        "options": table(a, b, c, d, e),
        "detail": {"a_tensor_parallel": a, "b_placement_depth": b, "c_lossless_dense_bytes": c,
                   "d_two_sequence_pipeline": d, "e_transfer_behind_compute": e},
        "inputs": I,
    }
    s = json.dumps(res, indent=1, ensure_ascii=False)
    if "--write" in sys.argv:
        (HERE / "options.json").write_text(s + "\n")
    print(s)


if __name__ == "__main__":
    main()
