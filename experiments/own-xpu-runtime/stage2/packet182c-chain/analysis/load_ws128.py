#!/usr/bin/env python3
"""Load the packet182c WS128 record run (12 x 128 tokens) into per-token rows.

Read-only. Joins each request's timings.jsonl (one row per generated token) with the
run-level cache.jsonl (one row per position, cumulative fill/publication counters) and the
request result.json (completed_monotonic timestamps that define the record metric).
"""
import json, os, statistics, sys
from collections import OrderedDict

ROOT = "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet182c-chain/evidence/card0-182-a"
RUN = os.path.join(ROOT, "WS128/run/run")
SUMMARY = os.path.join(ROOT, "WS128/summary.json")
EXPERT_BYTES = 1_971_200          # packed gate+up+down bytes per ordinary-layer expert (packet58i)
EXPERT_BYTES_L2 = 2_329_600       # layer 2
EXPERTS_PER_POSITION = 480        # 48 layers x 10 routed experts


def load_summary():
    with open(SUMMARY) as f:
        return json.load(f)


def load_requests(summary):
    """Return OrderedDict prompt_id -> dict(request=..., tokens=[rows], result=...)."""
    reqs = OrderedDict()
    for r in summary["requests"]:
        pid = r["prompt_id"]
        d = os.path.join(RUN, pid)
        rows = [json.loads(l) for l in open(os.path.join(d, "timings.jsonl")) if l.strip()]
        rows = [x for x in rows if x.get("kind") == "generated_token"]
        res = json.load(open(os.path.join(d, "result.json")))
        cs = json.load(open(os.path.join(d, "cache-stats.json")))
        reqs[pid] = {"request": r, "tokens": rows, "result": res, "cache_stats": cs}
    return reqs


def load_cache_positions():
    rows = [json.loads(l) for l in open(os.path.join(RUN, "cache.jsonl")) if l.strip()]
    return rows


def join_cache(reqs, cache_rows):
    """cache.jsonl is one stream across the 12 requests in order: positions 1..N per request
    (prefill positions then decode positions).  Counters are cumulative across requests.
    Assign per-position deltas to generated tokens by walking requests in order."""
    i = 0
    prev = None
    out = OrderedDict()
    for pid, rq in reqs.items():
        n_prompt = rq["request"]["prompt_tokens"]
        n_out = rq["request"]["output_tokens"]
        # cache.jsonl positions are GLOBAL (1..2386 across the 12 requests, monotonic).  Each request
        # owns n_prompt - 1 prefill positions (prefill-timings.jsonl token_index 0..n_prompt-2) followed by
        # n_out generated positions (timings.jsonl generated_index 1..n_out); n_prompt + n_out - 1 in all.
        n_pos = n_prompt + n_out - 1
        rows = cache_rows[i:i + n_pos]; i += n_pos
        deltas = []
        for r in rows:
            if prev is None:
                d = dict(r)
                d["fill_bytes"] = r["fill_bytes_total"]; d["fills"] = r["fills_total"]
                d["pub_uploads"] = r["publication_uploads_total"]; d["pub_bytes"] = r["publication_bytes_total"]
                d["pub_host_ms"] = r["publication_host_ms_total"]
            else:
                d = dict(r)
                d["fill_bytes"] = r["fill_bytes_total"] - prev["fill_bytes_total"]
                d["fills"] = r["fills_total"] - prev["fills_total"]
                d["pub_uploads"] = r["publication_uploads_total"] - prev["publication_uploads_total"]
                d["pub_bytes"] = r["publication_bytes_total"] - prev["publication_bytes_total"]
                d["pub_host_ms"] = r["publication_host_ms_total"] - prev["publication_host_ms_total"]
            deltas.append(d); prev = r
        out[pid] = {"positions": deltas, "n_prompt": n_prompt, "n_out": n_out}
    assert i == len(cache_rows), (i, len(cache_rows))
    return out


def per_token_rows(reqs, cache_join):
    """One row per generated token with the record-interval flag.
    token_index in timings.jsonl is the absolute position (prompt_tokens + generated_index - 1).
    cache.jsonl position p (1-based) corresponds to the step that produced token_index p-1?  We
    align by the fact that each request has n_prompt + n_out - 1 steps producing n_out tokens:
    the prefill step (positions 1..n_prompt) produces generated token 1; decode step k (k>=2)
    is position n_prompt + k - 1.
    """
    rows = []
    for pid, rq in reqs.items():
        toks = rq["tokens"]
        cj = cache_join[pid]
        pos = cj["positions"]
        n_prompt = cj["n_prompt"]
        assert len(pos) == n_prompt + cj["n_out"] - 1, (pid, len(pos), n_prompt, cj["n_out"])
        ts = [x["completed_monotonic"] for x in rq["result"]["timing_rows"]]
        assert len(ts) == len(toks) == cj["n_out"]
        for k, t in enumerate(toks):
            gi = t["generated_index"]
            assert gi == k + 1
            # generated token gi is produced at request-local position (n_prompt - 1) + gi (1-based)
            p = pos[n_prompt - 2 + gi]
            fill_bytes = p["fill_bytes"]; fills = p["fills"]; pub_ms = p["pub_host_ms"]; plan_ms = p["plan_ms"]
            if gi == 1:  # charge the prefill positions' fills to the first token too (reported separately)
                cpos = pos[:n_prompt - 1]
                prefill_fill_bytes = sum(q["fill_bytes"] for q in cpos)
            else:
                prefill_fill_bytes = 0
            interval = None
            if 2 <= gi <= 100:
                interval = (ts[gi - 1] - ts[gi - 2]) * 1000.0
            r = dict(t)
            r.update({"prompt_id": pid, "prompt_class": rq["request"]["prompt_class"], "fill_bytes": fill_bytes,
                      "fills": fills, "pub_host_ms": pub_ms, "plan_ms": plan_ms, "interval_ms": interval,
                      "in_window": 2 <= gi <= 100, "prefill_fill_bytes": prefill_fill_bytes,
                      "cache_state": p["state"]})
            rows.append(r)
    return rows


def class_balanced(reqs):
    """Reproduce the record metric: per prompt 99/(t100-t1); median per class; median of class medians."""
    per_prompt = {}
    for pid, rq in reqs.items():
        ts = [x["completed_monotonic"] for x in rq["result"]["timing_rows"]]
        per_prompt[pid] = (99.0 / (ts[99] - ts[0]), rq["request"]["prompt_class"])
    classes = {}
    for pid, (rate, cls) in per_prompt.items():
        classes.setdefault(cls, []).append(rate)
    cm = {c: statistics.median(v) for c, v in classes.items()}
    return statistics.median(cm.values()), cm, per_prompt


def replay(rows, delta_fn):
    """Replay the metric with per-token interval modification delta_fn(row) -> new interval ms."""
    per_prompt = {}
    for r in rows:
        if not r["in_window"]:
            continue
        per_prompt.setdefault((r["prompt_id"], r["prompt_class"]), 0.0)
        per_prompt[(r["prompt_id"], r["prompt_class"])] += delta_fn(r)
    classes = {}
    for (pid, cls), tot in per_prompt.items():
        classes.setdefault(cls, []).append(99000.0 / tot)
    cm = {c: statistics.median(v) for c, v in classes.items()}
    return statistics.median(cm.values())


if __name__ == "__main__":
    s = load_summary()
    reqs = load_requests(s)
    cj = join_cache(reqs, load_cache_positions())
    rows = per_token_rows(reqs, cj)
    m, cm, pp = class_balanced(reqs)
    print("record metric replay", m, "stored", s["class_balanced_tok_s_1_100_intervals_after_ttft"]["median"])
    print("replay via intervals", replay(rows, lambda r: r["interval_ms"]))
    w = [r for r in rows if r["in_window"]]
    print("window tokens", len(w))
    keys = ["wall_ms", "interval_ms", "enqueue_loop_ms", "wait_ms", "prepare_ms", "transfer_wall_ms", "head_transfer_ms",
            "tail_transfer_ms", "route_log_ms", "fill_bytes", "fills", "pub_host_ms", "plan_ms", "kernel_submissions",
            "host_waits", "thread_voluntary_context_switches", "process_major_faults", "process_minor_faults"]
    for k in keys:
        v = [r[k] for r in w if r.get(k) is not None]
        print(f"{k:38s} mean {statistics.mean(v):12.4f} median {statistics.median(v):12.4f} p10 {sorted(v)[len(v)//10]:12.4f} p90 {sorted(v)[len(v)*9//10]:12.4f}")
    json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ws128-rows.json"), "w"))
