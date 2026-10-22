#!/usr/bin/env python3
"""One-card per-token critical-path arithmetic on the packet182c WS128 record intervals.

Everything here is arithmetic on ws128-rows.json (written by load_ws128.py).  No device, no model.
"""
import json, os, statistics, sys
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "ws128-rows.json")))
W = [r for r in rows if r["in_window"]]
RECORD = 35.92672010504166
EXPERT_MB = 1.9712            # ordinary-layer packed expert (gate+up+down), MB (1e6)
MB = 1e6


def mean(v): return statistics.mean(v) if v else float("nan")
def med(v): return statistics.median(v) if v else float("nan")
def pct(v, p):
    s = sorted(v); return s[min(len(s) - 1, int(len(s) * p))]


def metric(delta_fn):
    """class-balanced median of class medians of 99000/sum(interval) with per-token interval modified."""
    per = defaultdict(float)
    for r in W:
        per[(r["prompt_id"], r["prompt_class"])] += delta_fn(r)
    classes = defaultdict(list)
    for (pid, cls), tot in per.items():
        classes[cls].append(99000.0 / tot)
    cm = {c: med(v) for c, v in classes.items()}
    return med(list(cm.values()))


def ols(x, y):
    n = len(x); mx = mean(x); my = mean(y)
    sxx = sum((a - mx) ** 2 for a in x); sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    slope = sxy / sxx if sxx else float("nan")
    return slope, my - slope * mx


out = OrderedDict()
base = metric(lambda r: r["interval_ms"])
assert abs(base - RECORD) < 1e-9, base
out["record_replay"] = base

# ---------------------------------------------------------------- per-request view (cold first request)
pr = OrderedDict()
for r in W:
    pr.setdefault(r["prompt_id"], {"cls": r["prompt_class"], "iv": [], "fill": [], "wait": [], "enq": [], "plan": []})
    d = pr[r["prompt_id"]]
    d["iv"].append(r["interval_ms"]); d["fill"].append(r["fill_bytes"]); d["wait"].append(r["wait_ms"])
    d["enq"].append(r["enqueue_loop_ms"]); d["plan"].append(r["plan_ms"])
out["per_request"] = {pid: {"class": d["cls"], "tok_s": 99000.0 / sum(d["iv"]), "mean_interval_ms": mean(d["iv"]),
                            "fill_mb_per_token": mean(d["fill"]) / MB, "wait_ms": mean(d["wait"]),
                            "enqueue_ms": mean(d["enq"]), "plan_ms": mean(d["plan"])} for pid, d in pr.items()}

# ---------------------------------------------------------------- per-token anatomy (window means)
def anat(sel):
    n = len(sel)
    wall = mean([r["interval_ms"] for r in sel]); enq = mean([r["enqueue_loop_ms"] for r in sel])
    wait = mean([r["wait_ms"] for r in sel]); prep = mean([r["prepare_ms"] for r in sel])
    xfer = mean([r["transfer_wall_ms"] for r in sel]); pub = mean([r["pub_host_ms"] for r in sel])
    plan = mean([r["plan_ms"] for r in sel]); wm = mean([r["wall_ms"] for r in sel])
    other = wm - enq - wait - prep - xfer
    return OrderedDict(n=n, interval_ms=wall, wall_ms=wm, enqueue_loop_ms=enq, wait_ms=wait, prepare_ms=prep,
                       transfer_ms=xfer, publication_host_ms=pub, plan_ms=plan, other_host_ms=other,
                       device_span_lower_bound_ms=enq + wait, host_exclusive_gap_ms=wm - enq - wait,
                       fill_mb=mean([r["fill_bytes"] for r in sel]) / MB, fills=mean([r["fills"] for r in sel]),
                       ctx_switches=mean([r["thread_voluntary_context_switches"] for r in sel]))

out["anatomy_all"] = anat(W)
filled = [r for r in W if r["fills"] > 0]; unfilled = [r for r in W if r["fills"] == 0]
s1 = [r for r in W if r["cache_state"] == 1]; s2 = [r for r in W if r["cache_state"] == 2]
out["anatomy_filled"] = anat(filled); out["anatomy_unfilled"] = anat(unfilled)
out["anatomy_state1_plan"] = anat(s1); out["anatomy_state2_submit"] = anat(s2)

# ---------------------------------------------------------------- fill/miss intensity regressions
# fills at position t+2 are the misses planned from position t's routes (packet58v pipeline).  Join each
# token with the fill bytes of the next fill boundary (same request).
by_req = defaultdict(list)
for r in rows: by_req[r["prompt_id"]].append(r)
for pid, lst in by_req.items():
    lst.sort(key=lambda r: r["generated_index"])
    for i, r in enumerate(lst):
        nxt = None
        for j in range(i + 1, min(i + 4, len(lst))):
            if lst[j]["fills"] > 0: nxt = lst[j]["fill_bytes"]; break
        r["next_fill_bytes"] = nxt
        r["fill_t2"] = lst[i + 2]["fill_bytes"] if i + 2 < len(lst) else None
xs = [r["fill_bytes"] / MB for r in W]; ys = [r["interval_ms"] for r in W]; ws_ = [r["wait_ms"] for r in W]
out["regress_wall_on_same_token_fill_mb"] = dict(zip(("slope_ms_per_mb", "intercept_ms"), ols(xs, ys)))
out["regress_wait_on_same_token_fill_mb"] = dict(zip(("slope_ms_per_mb", "intercept_ms"), ols(xs, ws_)))
u = [r for r in W if r["fills"] == 0 and r.get("next_fill_bytes") is not None]
out["regress_unfilled_wall_on_next_fill_mb"] = dict(zip(("slope_ms_per_mb", "intercept_ms"),
                                                        ols([r["next_fill_bytes"] / MB for r in u], [r["interval_ms"] for r in u])))
out["regress_unfilled_wait_on_next_fill_mb"] = dict(zip(("slope_ms_per_mb", "intercept_ms"),
                                                        ols([r["next_fill_bytes"] / MB for r in u], [r["wait_ms"] for r in u])))
t2 = [r for r in W if r.get("fill_t2") is not None]
out["regress_wall_on_fill_t_plus_2_mb"] = dict(zip(("slope_ms_per_mb", "intercept_ms"),
                                                   ols([r["fill_t2"] / MB for r in t2], [r["interval_ms"] for r in t2])))
out["regress_wait_on_fill_t_plus_2_mb"] = dict(zip(("slope_ms_per_mb", "intercept_ms"),
                                                   ols([r["fill_t2"] / MB for r in t2], [r["wait_ms"] for r in t2])))

# ---------------------------------------------------------------- hit/miss cycle proxies
# No route IDs are retained (packet58ai never ran).  Three labelled proxies:
fills_tok = mean([r["fills"] for r in W])
out["expert_cache"] = OrderedDict(
    fills_per_token=fills_tok, fill_mb_per_token=mean([r["fill_bytes"] for r in W]) / MB,
    hit_rate_if_fills_equal_misses=1 - fills_tok / 480,
    misses_per_token_at_p58y_ratio=fills_tok * (47.11531986531987 / 21.755892255892256),
    hit_rate_at_p58y_ratio=1 - fills_tok * (47.11531986531987 / 21.755892255892256) / 480,
    miss_mb_per_token_at_p58y_ratio=mean([r["fill_bytes"] for r in W]) / MB * (93402268.01346801 / 43128371.71717171),
    p58y_reference="packet58y analysis/report.json (18 GB cache, overlap, poll era): misses 47.12/token, fills 21.76/token, miss bytes 93.40 MB, fill bytes 43.13 MB",
)
# K1 penalty: 33.792 MB fixture all-host 1.933 ms vs VRAM 0.384 ms (182c K1a)
k1_pen_ms_per_mb = (1.93294 - 0.384453) / 33.792
out["k1_zero_copy_penalty_ms_per_mb"] = k1_pen_ms_per_mb
miss_mb_lo = out["expert_cache"]["fill_mb_per_token"]; miss_mb_hi = out["expert_cache"]["miss_mb_per_token_at_p58y_ratio"]
out["miss_cost_ms_per_token"] = OrderedDict(
    regression_visible=out["regress_unfilled_wall_on_next_fill_mb"]["slope_ms_per_mb"] * out["expert_cache"]["fill_mb_per_token"],
    k1_linear_fills_only=k1_pen_ms_per_mb * miss_mb_lo, k1_linear_p58y_ratio=k1_pen_ms_per_mb * miss_mb_hi)

# ---------------------------------------------------------------- replays
def price(name, fn):
    m = metric(fn); out.setdefault("prices", OrderedDict())[name] = {"tok_s": m, "gain_pct": (m / RECORD - 1) * 100}
    return m

price("identity", lambda r: r["interval_ms"])
for ms in (0.1, 0.2, 0.3, 0.5, 0.72, 1.0, 1.5, 2.0, 3.0):
    price(f"flat -{ms} ms/token", lambda r, ms=ms: r["interval_ms"] - ms)
# fills free (packet182 ceiling reproduction on this run): remove the filled-vs-unfilled excess on filled tokens
exc = out["anatomy_filled"]["interval_ms"] - out["anatomy_unfilled"]["interval_ms"]
price("filled tokens cost the same as unfilled (fill excess removed, upper bound)", lambda r: r["interval_ms"] - (exc if r["fills"] > 0 else 0))
# host-exclusive gap removed entirely (device never idles between positions)
gap = out["anatomy_all"]["host_exclusive_gap_ms"]
price("host-exclusive gap removed entirely (impossible ceiling)", lambda r: r["enqueue_loop_ms"] + r["wait_ms"] + (r["interval_ms"] - r["wall_ms"]))
price("host-exclusive gap halved", lambda r: r["interval_ms"] - 0.5 * (r["wall_ms"] - r["enqueue_loop_ms"] - r["wait_ms"]))
# miss cost scenarios (per-token proportional to that token's miss proxy = fill_t2 bytes; mean-matched)
for label, per_tok in (("regression-visible", out["miss_cost_ms_per_token"]["regression_visible"]),
                       ("k1 fills-only", out["miss_cost_ms_per_token"]["k1_linear_fills_only"]),
                       ("k1 p58y ratio", out["miss_cost_ms_per_token"]["k1_linear_p58y_ratio"])):
    for frac in (0.15, 0.25, 0.5, 1.0):
        price(f"miss cost ({label}, {per_tok:.2f} ms/token) reduced by {int(frac*100)}%", lambda r, c=per_tok * frac: r["interval_ms"] - c)
# plan on the critical path? price moving plan_ms off the host gap on state-1 tokens
price("plan_ms removed from state-1 tokens (upper bound if it is exposed)", lambda r: r["interval_ms"] - (r["plan_ms"] if r["cache_state"] == 1 else 0))
price("publication host 0.24 ms removed", lambda r: r["interval_ms"] - r["pub_host_ms"])
price("enqueue loop 4.89 ms fully hidden (device starts at first submission; it already overlaps)", lambda r: r["interval_ms"])
# two-card-style per-layer saving on all 48 layers
for d in (0.005, 0.01, 0.0151, 0.02, 0.05, 0.1):
    price(f"per-layer saving {d} ms on all 48 layers", lambda r, d=d: r["interval_ms"] - 48 * d)
# cold first request excluded (what the metric would be with request 1 warm): replace its intervals with the mean of its class sibling
# thresholds
out["thresholds"] = {"chain +2%": RECORD * 1.02, "screen +0.5%": RECORD * 1.005}
# flat ms/token needed for +2% and +0.5%: solve by bisection
def need(target):
    lo, hi = 0.0, 10.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if metric(lambda r: r["interval_ms"] - mid) < target: lo = mid
        else: hi = mid
    return hi
out["thresholds"]["flat_ms_per_token_for_chain"] = need(RECORD * 1.02)
out["thresholds"]["flat_ms_per_token_for_screen"] = need(RECORD * 1.005)
out["thresholds"]["per_layer_us_for_chain_48_layers"] = out["thresholds"]["flat_ms_per_token_for_chain"] / 48 * 1000
out["thresholds"]["per_layer_us_for_screen_48_layers"] = out["thresholds"]["flat_ms_per_token_for_screen"] / 48 * 1000

# ---------------------------------------------------------------- distributions
iv = [r["interval_ms"] for r in W]
out["interval_distribution"] = dict(mean=mean(iv), p5=pct(iv, .05), p50=med(iv), p95=pct(iv, .95), min=min(iv), max=max(iv))
# per class medians reproduction
json.dump(out, open(os.path.join(HERE, "analyze-ws128-output.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
