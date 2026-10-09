#!/usr/bin/env python3
"""Probe accuracy by distance, speed as the history grows, and cost totals, per arm (stdlib only).

  probe_analysis.py OUT_DIR [--json out.json] [--bins 4,24,99,399]
  OUT_DIR = the run's output dir (holds runs/jobs/<arm>__<task>/<task>__<rand>/ and tasks/); a runs/ or
  jobs/ dir, a job dir or a trial dir also work (same discovery as summarize_results.expand).

Trials whose verifier says void, or that summarize_results marks invalid (harness cap, exception,
server window), are skipped and listed at the end. Arm = the job dir name before "__".

Section 1, probes. The task's tests/reference.json "probes" dict gives, per probe key, its type and
distance (items between the item the probe was delivered as and the item the answer comes from).
verifier/details.json per_key gives correct / blank / wrong / stale (a key missing there counts as
blank). Accuracy = correct / n, pooled over the arm's trials, per distance bin (--bins are the upper
edges; default 1-4, 5-24, 25-99, 100-399, 400+) and per type. Final query = the per_key keys that
are not probes. Tasks without probes print "no probes".

Section 2, speed. Source: agent/timing.json, the harness's per-LM-call record (llm_s = model call
seconds, bash_s = command seconds; no absolute timestamps exist in timing.json, trajectory.json or
trajectory.ctx.json). The k-th timing entry with llm_s is the k-th agent step of trajectory.ctx.json,
whose tool output "ITEM n/total (...)" says which item `next` delivered at that step. Elapsed time at
item n = the sum of llm_s + bash_s over all steps up to and including that step. History tokens at
item n = cumulative per-item size from the task's environment/stream.jsonl, characters scaled so the
whole stream equals task.toml stream_tokens (tokenizer count). If the verifier ever exports the
`next` delivery log with its time stamps (verifier/delivery.log, or details.delivery.log/times), that
real clock is used instead (source column says which). Not covered by timing.json: harness overhead
between calls and any separate summary/compaction model calls not logged there; the coverage column
(timing sum / Harbor agent-execution wall time) shows how much of the wall the step sum explains.
Without trajectory.ctx.json, the steps whose command is `next` are taken as items 1, 2, ... in order
(source "timing+next-order").
Reported: cumulative minutes at 100K, 200K, ... tokens of history, and minutes per 100K in each
segment (0-100K, 100-200K, ...), mean over the arm's trials that reached that milestone.

Section 3, totals (mean per trial): tokens written (completion tokens, summary calls included), model
calls, peak sent context, and management counters when present: real context edits, summaries
(ok/failed), ctxfold calls, fold batches, truncations (truncate_calls.json), compactions
(compact_calls.json), recalls, rollbacks, window refusals.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
import tomllib
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import summarize_results as sr  # noqa: E402

ITEM_LINE = re.compile(r"(?m)^ITEM (\d+)/(\d+) \(")
STEP = 100_000


def load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


# ---------------------------------------------------------------- task side
def task_dir_of(t: Path, out_dir: Path | None) -> Path | None:
    cfg = load(t / "config.json") or {}
    p = ((cfg.get("task") or {}).get("path")) if isinstance(cfg, dict) else None
    if p and Path(p).is_dir():
        return Path(p)
    name = t.name.rsplit("__", 1)[0]
    if out_dir is not None:
        for c in sorted((out_dir / "tasks").glob(f"**/{name}")):
            if (c / "tests").is_dir():
                return c
    return None


def item_tokens(td: Path | None) -> list[float]:
    """Approximate tokens per item (index 0 = item 1), scaled to the tokenizer total in task.toml."""
    if td is None:
        return []
    chars = []
    try:
        for ln in (td / "environment" / "stream.jsonl").read_text().splitlines():
            if ln.strip():
                it = json.loads(ln)
                chars.append(len(str(it.get("text") or "")) + len(str(it.get("last") or "")) + 24)
    except Exception:
        return []
    total = None
    try:
        md = tomllib.loads((td / "task.toml").read_text()).get("metadata", {})
        total = md.get("stream_tokens") or md.get("approx_stream_tokens")
    except Exception:
        pass
    s = sum(chars) or 1
    scale = (float(total) / s) if total else 0.25
    return [c * scale for c in chars]


def bin_names(edges: list[int]) -> list[str]:
    out, lo = [], 1
    for e in edges:
        out.append(f"{lo}-{e}")
        lo = e + 1
    out.append(f"{lo}+")
    return out


def bin_of(d, edges: list[int], names: list[str]) -> str:
    try:
        d = int(d)
    except Exception:
        return "unknown"
    for e, nm in zip(edges, names):
        if d <= e:
            return nm
    return names[-1]


# ---------------------------------------------------------------- timing
def step_items(agent: Path) -> tuple[dict[int, int], str]:
    """{agent step ordinal (1-based, = timing.json step): highest item delivered at that step}."""
    ctx = load(agent / "trajectory.ctx.json")
    out: dict[int, int] = {}
    if isinstance(ctx, dict) and ctx.get("segments"):
        k = 0
        for seg in ctx["segments"]:
            for st in seg.get("steps") or []:
                if st.get("source") != "agent":
                    continue
                k += 1
                ob = st.get("observation")
                if isinstance(ob, str):
                    ob = load_str(ob)
                texts = []
                if isinstance(ob, dict):
                    texts = [str(r.get("content") or "") for r in ob.get("results") or [] if isinstance(r, dict)]
                elif ob is not None:
                    texts = [str(ob)]
                for tx in texts:
                    for m in ITEM_LINE.finditer(tx):
                        out[k] = max(out.get(k, 0), int(m.group(1)))
        return out, "timing+ctx"
    tm = load(agent / "timing.json") or []
    n = 0
    for x in tm:
        if isinstance(x, dict) and re.match(r"\s*next\s*$", str(x.get("cmd") or "")) and x.get("return_code", 0) == 0:
            n += 1
            out[int(x["step"])] = n
    return out, ("timing+next-order" if out else "none")


def load_str(s: str):
    try:
        return json.loads(s)
    except Exception:
        return s


def delivery_clock(t: Path, details: dict) -> dict[int, float] | None:
    """Real `next` delivery times {item: seconds since first delivery}, if the verifier exported them."""
    recs = None
    dl = details.get("delivery") or {}
    if isinstance(dl.get("log"), list):
        recs = dl["log"]
    elif isinstance(dl.get("times"), (list, dict)):
        tt = dl["times"]
        recs = ([{"n": i + 1, "t": v} for i, v in enumerate(tt)] if isinstance(tt, list)
                else [{"n": int(k), "t": v} for k, v in tt.items()])
    elif (t / "verifier" / "delivery.log").exists():
        recs = []
        for ln in (t / "verifier" / "delivery.log").read_text(errors="replace").splitlines():
            try:
                recs.append(json.loads(ln))
            except Exception:
                pass
    if not recs:
        return None
    pts = {int(r["n"]): float(r["t"]) for r in recs if isinstance(r, dict) and "n" in r and "t" in r}
    if not pts:
        return None
    t0 = min(pts.values())
    return {n: v - t0 for n, v in pts.items()}


def elapsed_by_item(t: Path, details: dict) -> tuple[dict[int, float], str, float | None]:
    """{item: elapsed seconds when it was delivered}, source label, timing.json sum (s)."""
    agent = t / "agent"
    tm = load(agent / "timing.json") or []
    tsum = sum(float(x.get("llm_s") or 0) + float(x.get("bash_s") or 0) for x in tm if isinstance(x, dict)) or None
    clock = delivery_clock(t, details)
    if clock:
        return clock, "delivery-log", tsum
    if not tm:
        return {}, "none", None
    smap, src = step_items(agent)
    if not smap:
        return {}, "none", tsum
    cum, at_step = 0.0, {}
    for x in tm:
        if not isinstance(x, dict) or "llm_s" not in x:
            continue
        cum += float(x.get("llm_s") or 0) + float(x.get("bash_s") or 0)
        at_step[int(x["step"])] = cum
    out: dict[int, float] = {}
    for k, n in smap.items():
        if k in at_step and n not in out:
            out[n] = at_step[k]
    return out, src, tsum


def milestones(elapsed: dict[int, float], toks: list[float]) -> dict[int, float]:
    """{milestone tokens (100K multiples): cumulative minutes when the history first reached it}."""
    if not elapsed or not toks:
        return {}
    out, cum, nxt = {}, 0.0, STEP
    for n in range(1, len(toks) + 1):
        cum += toks[n - 1]
        while cum >= nxt:
            # the first delivered item at or after n (an item may be missing if delivered in a batch)
            later = [elapsed[m] for m in range(n, min(n + 5, len(toks)) + 1) if m in elapsed]
            if not later:
                return out
            out[nxt] = later[0] / 60.0
            nxt += STEP
    return out


def agent_exec_s(t: Path) -> float | None:
    res = load(t / "result.json") or {}
    ae = res.get("agent_execution") if isinstance(res, dict) else None
    try:
        return (datetime.fromisoformat(ae["finished_at"].replace("Z", "+00:00")) -
                datetime.fromisoformat(ae["started_at"].replace("Z", "+00:00"))).total_seconds()
    except Exception:
        return None


# ---------------------------------------------------------------- per trial
def trial_info(t: Path, out_dir: Path | None, edges: list[int]) -> dict:
    names = bin_names(edges)
    details = load(t / "verifier" / "details.json") or {}
    base = sr.trial_row(t)
    agent = t / "agent"
    td = task_dir_of(t, out_dir)
    ref = load(td / "tests" / "reference.json") if td else None
    probes = (ref or {}).get("probes") or {}
    per_key = details.get("per_key") or {}

    pr = []
    for k, p in probes.items():
        st = per_key.get(k, "blank")
        pr.append({"key": k, "type": p.get("type"), "distance": p.get("distance"),
                   "tokens_back": p.get("tokens_back"), "item": p.get("item"),
                   "bin": bin_of(p.get("distance"), edges, names), "status": st})
    final = {k: v for k, v in per_key.items() if k not in probes}

    toks = item_tokens(td)
    elapsed, src, tsum = elapsed_by_item(t, details)
    ms = milestones(elapsed, toks)
    ex = agent_exec_s(t)

    sc = load(agent / "summary_calls.json") or []
    tc = load(agent / "truncate_calls.json")
    cc = load(agent / "compact_calls.json")
    imp = load(agent / "improved_stats.json") or {}
    ws = load(agent / "window_stats.json") or {}
    u = load(agent / "usage.json") or {}
    return {
        "job": t.parent.name, "trial": t.name, "arm": sr.arm_of(t.parent.name), "task_dir": str(td) if td else None,
        "void": bool(details.get("void")), "invalid": base.get("invalid"), "ended_by": base.get("ended_by"),
        "rule": base.get("rule"), "score": details.get("score"),
        "probes": pr, "final_n": len(final), "final_correct": sum(1 for v in final.values() if v == "correct"),
        "total_n": len(per_key), "total_correct": sum(1 for v in per_key.values() if v == "correct"),
        "history_tokens": round(sum(toks)) if toks else None,
        "items_timed": len(elapsed), "time_source": src,
        "timing_sum_s": round(tsum, 1) if tsum else None, "agent_exec_s": round(ex, 1) if ex else None,
        "coverage": round(tsum / ex, 3) if (tsum and ex) else None,
        "milestones_min": {str(k): round(v, 2) for k, v in ms.items()},
        "completion_tokens": base.get("completion_tokens"), "lm_calls": base.get("lm_calls"),
        "peak_ctx": base.get("peak_sent_ctx") or None, "wall_s": base.get("wall_s"),
        "real_edits": base.get("real_edits"), "summaries": base.get("summaries") if sc else None,
        "summary_failed": base.get("summary_failed") if sc else None,
        "ctxfold_calls": base.get("ctxfold_calls"), "fold_batches": imp.get("fold_batches"),
        "truncations": len(tc) if isinstance(tc, list) else (tc.get("n") if isinstance(tc, dict) else None),
        "compactions": len(cc) if isinstance(cc, list) else (cc.get("n") if isinstance(cc, dict) else None),
        "recalls": imp.get("recall_calls"), "rollbacks": u.get("n_retry_on_limit"),
        "window_refusals": ws.get("window_refusals"),
    }


# ---------------------------------------------------------------- per arm
def acc(xs: list[dict]) -> str:
    if not xs:
        return "n/a"
    c = sum(1 for x in xs if x["status"] == "correct")
    return f"{c}/{len(xs)}={c / len(xs):.2f}"


def mean_or_na(vals, nd=0):
    v = [x for x in vals if isinstance(x, (int, float)) and not isinstance(x, bool)]
    if not v:
        return None
    m = statistics.mean(v)
    return round(m, nd) if nd else round(m)


def arm_tables(trials: list[dict], edges: list[int]) -> dict:
    names = bin_names(edges)
    arms: dict[str, dict] = {}
    for arm in sorted({t["arm"] for t in trials}):
        a = [t for t in trials if t["arm"] == arm]
        pr = [p for t in a for p in t["probes"]]
        types = sorted({p["type"] for p in pr if p["type"]})
        mks = sorted({int(k) for t in a for k in t["milestones_min"]})
        cum, seg = {}, {}
        for m in mks:
            v = [t["milestones_min"][str(m)] for t in a if str(m) in t["milestones_min"]]
            cum[m] = (round(statistics.mean(v), 2), len(v))
            pv = [t["milestones_min"][str(m)] - (t["milestones_min"].get(str(m - STEP), 0.0) if m > STEP else 0.0)
                  for t in a if str(m) in t["milestones_min"] and (m == STEP or str(m - STEP) in t["milestones_min"])]
            seg[m] = round(statistics.mean(pv), 2) if pv else None
        arms[arm] = {
            "n_trials": len(a), "n_probes": len(pr),
            "by_bin": {b: acc([p for p in pr if p["bin"] == b]) for b in names + (["unknown"] if any(p["bin"] == "unknown" for p in pr) else [])},
            "by_type": {ty: acc([p for p in pr if p["type"] == ty]) for ty in types},
            "probes_all": acc(pr),
            "final": (f"{sum(t['final_correct'] for t in a)}/{sum(t['final_n'] for t in a)}"
                      if sum(t["final_n"] for t in a) else "n/a"),
            "total": (f"{sum(t['total_correct'] for t in a)}/{sum(t['total_n'] for t in a)}"
                      if sum(t["total_n"] for t in a) else "n/a"),
            "cum_min": {str(k): v[0] for k, v in cum.items()}, "cum_n": {str(k): v[1] for k, v in cum.items()},
            "seg_min_per_100k": {str(k): v for k, v in seg.items()},
            "time_source": ",".join(sorted({t["time_source"] for t in a})),
            "coverage": mean_or_na([t["coverage"] for t in a], 3),
            "totals": {k: mean_or_na([t[k] for t in a]) for k in (
                "completion_tokens", "lm_calls", "peak_ctx", "wall_s", "real_edits", "summaries", "summary_failed",
                "ctxfold_calls", "fold_batches", "truncations", "compactions", "recalls", "rollbacks",
                "window_refusals")},
            "peak_ctx_max": max((t["peak_ctx"] or 0 for t in a), default=0) or None,
        }
    return arms


def na(v) -> str:
    return "n/a" if v is None or v == "" else str(v)


def report(trials: list[dict], skipped: list[dict], edges: list[int]) -> tuple[str, dict]:
    names = bin_names(edges)
    arms = arm_tables(trials, edges)
    L = []
    L.append("# 1. probe accuracy (correct/n=acc, pooled over trials; distance in items)")
    if not any(a["n_probes"] for a in arms.values()):
        L.append("no probes")
        L.append("\t".join(["arm", "trials", "final_query", "total_correct"]))
        for arm, a in arms.items():
            L.append("\t".join([arm, str(a["n_trials"]), a["final"], a["total"]]))
    else:
        types = sorted({ty for a in arms.values() for ty in a["by_type"]})
        L.append("\t".join(["arm", "trials", "probes"] + [f"d{b}" for b in names] + [f"t:{ty}" for ty in types]
                           + ["final_query", "total_correct"]))
        for arm, a in arms.items():
            if not a["n_probes"]:
                L.append("\t".join([arm, str(a["n_trials"]), "no probes"] + ["n/a"] * (len(names) + len(types))
                                   + [a["final"], a["total"]]))
                continue
            L.append("\t".join([arm, str(a["n_trials"]), a["probes_all"]] + [a["by_bin"].get(b, "n/a") for b in names]
                               + [a["by_type"].get(ty, "n/a") for ty in types] + [a["final"], a["total"]]))

    mks = sorted({int(k) for a in arms.values() for k in a["cum_min"]})
    lab = [f"{m // 1000}K" for m in mks]
    L.append("\n# 2a. speed: cumulative minutes when the history reached N tokens (mean over trials reaching it)")
    if not mks:
        L.append("n/a (no per-step timing)")
    else:
        L.append("\t".join(["arm", "source", "coverage"] + lab))
        for arm, a in arms.items():
            L.append("\t".join([arm, a["time_source"], na(a["coverage"])] + [na(a["cum_min"].get(str(m))) for m in mks]))
        L.append("\n# 2b. speed: minutes per 100K tokens of history in each segment (rises if the method slows down)")
        seg_lab = [f"{(m - STEP) // 1000}-{m // 1000}K" for m in mks]
        L.append("\t".join(["arm"] + seg_lab))
        for arm, a in arms.items():
            L.append("\t".join([arm] + [na(a["seg_min_per_100k"].get(str(m))) for m in mks]))

    L.append("\n# 3. totals (mean per trial; peak_ctx_max = max over trials)")
    cols = ["completion_tokens", "lm_calls", "peak_ctx", "wall_s", "real_edits", "summaries", "summary_failed",
            "ctxfold_calls", "fold_batches", "truncations", "compactions", "recalls", "rollbacks", "window_refusals"]
    L.append("\t".join(["arm", "trials", "tokens_written"] + cols[1:] + ["peak_ctx_max"]))
    for arm, a in arms.items():
        L.append("\t".join([arm, str(a["n_trials"])] + [na(a["totals"][c]) for c in cols] + [na(a["peak_ctx_max"])]))

    for s in skipped:
        L.append(f"# skipped {s['job']}/{s['trial']}: void={s['void']} ended_by={s['ended_by']} rule={s['rule']}")
    L.append(f"# trials used={len(trials)} skipped={len(skipped)}")
    return "\n".join(L), {"bins": names, "arms": arms, "trials": trials, "skipped": skipped}


def analyse(out_dir: Path, edges: list[int]) -> tuple[str, dict]:
    base = out_dir / "runs" if (out_dir / "runs").is_dir() else out_dir
    used, skipped = [], []
    for t in sr.expand([base]):
        info = trial_info(t, out_dir, edges)
        (skipped if (info["void"] or info["invalid"]) else used).append(info)
    return report(used, skipped, edges)


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    out_json, edges = None, [4, 24, 99, 399]
    if "--json" in args:
        i = args.index("--json"); out_json = args[i + 1]; del args[i:i + 2]
    if "--bins" in args:
        i = args.index("--bins"); edges = sorted(int(x) for x in args[i + 1].split(",") if x.strip()); del args[i:i + 2]
    if len(args) != 1:
        sys.exit(__doc__)
    text, data = analyse(Path(args[0]), edges)
    print(text)
    if out_json:
        Path(out_json).write_text(json.dumps(data, indent=1, default=str))


if __name__ == "__main__":
    main()
