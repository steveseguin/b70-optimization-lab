#!/usr/bin/env python3
"""Price the open one-card levers by arithmetic on the packet182c WS128 intervals.

Inputs: ws128-rows.json (load_ws128.py) and analyze-ws128-output.json (analyze_ws128.py).  Every
constant below is quoted from a retained receipt; the source is named next to it.  CPU only.
"""
import json, os, statistics
from collections import defaultdict, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "ws128-rows.json")))
A = json.load(open(os.path.join(HERE, "analyze-ws128-output.json")))
W = [r for r in rows if r["in_window"]]
RECORD = 35.92672010504166
CHAIN = RECORD * 1.02
SCREEN = RECORD * 1.005


def metric(fn):
    per = defaultdict(float)
    for r in W:
        per[(r["prompt_id"], r["prompt_class"])] += fn(r)
    classes = defaultdict(list)
    for (pid, cls), tot in per.items():
        classes[cls].append(99000.0 / tot)
    return statistics.median([statistics.median(v) for v in classes.values()])


def flat(ms):
    return metric(lambda r: r["interval_ms"] - ms)


def gain(ms):
    return (flat(ms) / RECORD - 1) * 100


out = OrderedDict()

# ------------------------------------------------------------------ 1. per-token accounting (ms)
an = A["anatomy_all"]
two_card_layer = 0.486        # packet190 lever-synthesis-4: rank-0 half 11.660 / 24 layers (all experts resident)
two_card_layer_lo, two_card_layer_hi = 0.469, 0.495   # boundary body / rank-1 per-layer rates
head_ms = 1.404               # packet190: 248,320-row head on rank 1 (839,321,600 B at ~598 GB/s)
device_lb = an["device_span_lower_bound_ms"]
miss_reg = A["miss_cost_ms_per_token"]["regression_visible"]
miss_k1_fills = A["miss_cost_ms_per_token"]["k1_linear_fills_only"]
miss_k1_p58y = A["miss_cost_ms_per_token"]["k1_linear_p58y_ratio"]
# parity triangulation: one-card device span minus head minus 48 two-card-rate layer bodies
excess_over_parity = device_lb - head_ms - 48 * two_card_layer
excess_range = (device_lb - head_ms - 48 * two_card_layer_hi, device_lb - head_ms - 48 * two_card_layer_lo)
# fill-related costs from packet182 B0 fill_split (kernel-I/O line) and this run's state split
f = A["anatomy_filled"]; u = A["anatomy_unfilled"]
plan_per_txn = statistics.mean([r["plan_ms"] for r in W if r["cache_state"] == 1])
fill_wait_excess = f["wait_ms"] - u["wait_ms"]                 # includes the plan hidden under state-1 waits
fill_contention = fill_wait_excess - plan_per_txn              # per filled token
fill_submit_host = f["host_exclusive_gap_ms"] - 0.66            # request-1 state-1 gap (plan 0.12) as the plan-free base
filled_frac = f["n"] / (f["n"] + u["n"])
req1_s1_gap = 0.658                                            # analyze run: incident-retrospective state-1 gap, plan 0.121
base_idle_gap = req1_s1_gap - 0.121
out["accounting_ms_per_token"] = OrderedDict(
    interval=an["interval_ms"], device_span_lower_bound=device_lb, host_exclusive_gap=an["host_exclusive_gap_ms"],
    plan_ms_per_transaction=plan_per_txn, plan_hidden_under_wait=True,
    base_device_idle_gap=base_idle_gap, fill_submit_host_per_filled_token=fill_submit_host,
    fill_contention_wait_per_filled_token=fill_contention, filled_fraction=filled_frac,
    fill_related_per_token=(fill_submit_host + fill_contention) * filled_frac,
    publication_host=an["publication_host_ms"], transfer=an["transfer_ms"], prepare=an["prepare_ms"],
    head=head_ms, layer_bodies_at_two_card_rate=48 * two_card_layer,
    miss_cost_regression=miss_reg, miss_cost_k1_fill_bytes=miss_k1_fills, miss_cost_k1_p58y_ratio=miss_k1_p58y,
    miss_cost_parity_triangulation=excess_over_parity, miss_cost_parity_range=excess_range,
)
miss_central = 1.2
fill_related = (fill_submit_host + fill_contention) * filled_frac
model_sum = 48 * two_card_layer + head_ms + miss_central + fill_related + base_idle_gap
out["accounting_ms_per_token"]["model_sum"] = model_sum
out["accounting_ms_per_token"]["residual_vs_interval"] = an["interval_ms"] - model_sum

# ------------------------------------------------------------------ 2. thresholds
out["thresholds"] = OrderedDict(chain_tok_s=CHAIN, screen_tok_s=SCREEN,
                                flat_ms_for_chain=A["thresholds"]["flat_ms_per_token_for_chain"],
                                flat_ms_for_screen=A["thresholds"]["flat_ms_per_token_for_screen"],
                                per_layer_us_for_chain=A["thresholds"]["per_layer_us_for_chain_48_layers"],
                                per_layer_us_for_screen=A["thresholds"]["per_layer_us_for_screen_48_layers"])

# ------------------------------------------------------------------ 3. levers
L = OrderedDict()

# (1) cache capacity.  Elasticity of miss/fill bytes vs capacity:
#   replay (packet58x ADMISSION.md): 21.0 -> 21.5527 GB: 43.509 -> 41.283 MB (-5.1% per +2.63% capacity = -1.95 per %)
#   native (packet58y 18 GB overlap 42.61 MB fills/token vs 182c 21.55 GB 31.37 MB): -26.4% per +19.7% = -1.34 per %
elas_lo, elas_hi = 1.34, 1.95
device_bound = 29_963_128_848; census_live = 27_841_904_372; drm_peak = 27_774_044 * 1024
floor = 32_000_000_000; reserve = 1_500_000_000; driver_allow = 536_870_912
driver_measured = drm_peak - census_live
unallocated_allowance = device_bound - census_live
physical_room_under_rules = floor - reserve - drm_peak
out["memory_headroom_bytes"] = OrderedDict(device_owned_bound=device_bound, census_live_peak=census_live, drm_vram_peak=drm_peak,
                                           driver_overhead_measured=driver_measured, driver_allowance=driver_allow,
                                           unallocated_allowance_inside_bound=unallocated_allowance,
                                           physical_room_under_floor_and_reserve=physical_room_under_rules,
                                           workspace_live=295_612_132, workspace_plus_control_transaction_bound=1_073_479_680 + 1_073_741_824)
cache_now = 21_552_729_600
for extra_gb in (1.0, 1.5, 2.0):
    cap_pct = extra_gb * 1e9 / cache_now * 100
    byte_cut = (cap_pct * elas_lo / 100, min(0.5, cap_pct * elas_hi / 100))
    saved = tuple(b * (miss_central + fill_related) for b in byte_cut)
    saved_wide = (byte_cut[0] * (1.0 + fill_related), byte_cut[1] * (1.5 + fill_related))
    L[f"cache +{extra_gb} GB ({(cache_now + extra_gb*1e9)/1e9:.2f} GB)"] = OrderedDict(
        capacity_pct=cap_pct, miss_byte_cut_fraction=byte_cut, saved_ms_central=saved, saved_ms_wide=saved_wide,
        gain_pct_central=tuple(gain(s) for s in saved), gain_pct_wide=tuple(gain(s) for s in saved_wide),
        fits=(drm_peak + extra_gb * 1e9 + reserve) <= floor)
# all resident (impossible on 32 GB; 48.6 GB of experts)
L["all experts resident (impossible: 48.6 GB)"] = OrderedDict(saved_ms=(miss_reg + fill_related, miss_k1_fills + fill_related, miss_k1_p58y + fill_related),
                                                              gain_pct=tuple(gain(s) for s in (miss_reg + fill_related, miss_k1_fills + fill_related, miss_k1_p58y + fill_related)))
# bytes cut needed for the bars
for name, bar in (("chain", A["thresholds"]["flat_ms_per_token_for_chain"]), ("screen", A["thresholds"]["flat_ms_per_token_for_screen"])):
    need_frac = bar / (miss_central + fill_related)
    L[f"capacity needed for {name} bar"] = OrderedDict(miss_byte_cut_needed=need_frac, capacity_pct_needed=(need_frac * 100 / elas_hi, need_frac * 100 / elas_lo),
                                                      extra_gb_needed=(need_frac / elas_hi * cache_now / 1e9, need_frac / elas_lo * cache_now / 1e9))

# (2) prefetch next layer's experts on the copy engine: routes unknown until the router (packet125 DNR; packet138 closed);
#     post-router demand transfer measured -52.6% (packet58am).  Exposed fraction of miss reads = 100% (zero-copy inside kernels, single CCS).
L["prefetch next layer experts (copy engine)"] = OrderedDict(open=False, exposed_fraction_of_miss_reads=1.0, closed_by=["packet125 DNR", "packet138 DNR", "packet58am -52.6%"], gain_pct=0.0)
# (3) draft-route placement: no draft on this line
L["expert placement keyed by draft routes"] = OrderedDict(open=False, reason="decode_mode plain; MTP closed by packet58h/58aa/170; packet138 router-predicted prefetch closed", gain_pct=0.0)
# (4) draft on one card: cycle arithmetic
acc = 0.787; m2_row_per_half = 9.21  # packet151e measured partial M=2 half cost (24 layers)
cycle_favorable = an["interval_ms"] + 2 * m2_row_per_half + 1.531 + 0.45  # + draft wall + 25% more miss bytes (3.1 GB draft residency)
cycle_p170 = 63.613909
L["one-card MTP draft (M=2)"] = OrderedDict(open=False, cycle_ms_favorable=cycle_favorable, ms_per_token_favorable=cycle_favorable / (1 + acc),
                                             tok_s_favorable=1000 / (cycle_favorable / (1 + acc)) * (RECORD / (1000 / an["interval_ms"])),
                                             cycle_ms_p170_sensitivity=cycle_p170, tok_s_p170=1000 / (cycle_p170 / (1 + acc)) * (RECORD / (1000 / an["interval_ms"])),
                                             closed_by=["packet58h", "packet58aa", "packet170"], note="favorable case charges only the measured two-card M=2 row cost, draft wall and a 25% miss increase; packet170 charged feedback/state/head/pollution")
# (5) ports: dispatch identical; per-layer parity
L["unported two-card kernel wins"] = OrderedDict(open=False, dispatch_tables_identical=True,
                                                 one_card_ms_per_layer_net=(device_lb - head_ms - miss_central - fill_contention * filled_frac) / 48,
                                                 two_card_ms_per_layer=(two_card_layer_lo, two_card_layer, two_card_layer_hi), gain_pct=0.0)
# (6) host issue path
items = OrderedDict(publication_construct_upload_scatter=0.142 + 0.038 + 0.019, publication_drain_under_spin=0.018,
                    nonblocking_token_input_assumed=(0.05, 0.30), spin_tail_assumed=(0.05, 0.08), timing_row=0.035)
realistic = (0.10, 0.35)
L["host issue path trims"] = OrderedDict(base_device_idle_gap_ms=base_idle_gap, items=items, realistic_saved_ms=realistic,
                                         gain_pct=tuple(gain(s) for s in realistic), ceiling_if_gap_zero_pct=gain(base_idle_gap))
# (7) fills free / fill contention
L["fill contention + submission (bytes set the cost)"] = OrderedDict(per_token_ms=fill_related, ceiling_pct=gain(fill_related), open=False,
                                                                     closed_by=["packet174", "packet182 (pacing/deferral 0 to +0.3%)"],
                                                                     note="packet182 DNR revisit condition (>= 1.1 ms per filled token outside transfer) is numerically met (1.115 B0 / 1.213 chain) but no mechanism moves fewer bytes")
# kernel class saving on all 48 layers
L["per-layer kernel saving"] = OrderedDict(us_per_layer_for_chain=A["thresholds"]["per_layer_us_for_chain_48_layers"],
                                           us_per_layer_for_screen=A["thresholds"]["per_layer_us_for_screen_48_layers"],
                                           pct_of_layer_for_chain=A["thresholds"]["per_layer_us_for_chain_48_layers"] / 486 * 100,
                                           best_open_item="packet104b gate/up tile16 + half-cache <= +1.16% at 100% transfer (packet190 synthesis)")
out["levers"] = L
json.dump(out, open(os.path.join(HERE, "price-onecard-levers-output.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
