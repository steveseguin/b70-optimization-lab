#!/usr/bin/env python3
"""Score and token/turn table for one or more Harbor job directories.

  summarize_results.py <job_dir> [<job_dir> ...] [--json out.json]

Per trial: reward, LM calls, task steps (bash turns), free context-edit turns, real edits,
nudges, rollbacks, summary calls (SummaryAgent), prompt/completion/cached tokens (summary
calls added), peak sent context (from context_snapshots), FLOPs if exported, wall time, and a
flag if any command named /opt/kvstream (against the kvstream rules).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def trial_row(t: Path) -> dict:
    agent = t / "agent"
    u = load(agent / "usage.json") or {}
    sc = load(agent / "summary_calls.json") or []
    res = load(t / "result.json") or {}
    reward = None
    vr = (res.get("verifier_result") or {}).get("rewards") if isinstance(res, dict) else None
    if isinstance(vr, dict):
        reward = vr.get("reward", next(iter(vr.values()), None))
    if reward is None and (t / "verifier" / "reward.txt").exists():
        try:
            reward = float((t / "verifier" / "reward.txt").read_text().strip())
        except ValueError:
            pass
    peak = 0
    for s in sorted((agent / "context_snapshots").glob("turn-*.json")):
        d = load(s) or {}
        if d.get("kind") == "agent":
            peak = max(peak, int(d.get("sent_tokens") or d.get("tokens") or 0))
    traj = load(agent / "trajectory.json") or []
    cheat = any("/opt/kvstream" in json.dumps(m.get("tool_calls") or "") for m in traj
                if isinstance(m, dict) and m.get("role") == "assistant")
    timing = load(agent / "timing.json") or []
    cheat = cheat or any("/opt/kvstream" in str(x.get("cmd", "")) for x in timing if isinstance(x, dict))
    ctx = load(agent / "trajectory.ctx.json") or {}
    kv = (((ctx.get("final_metrics") or {}).get("extra") or {}).get("kv_cache_flops") or {}) \
        if isinstance(ctx, dict) else {}
    wall = None
    try:
        from datetime import datetime
        st, fi = res.get("started_at"), res.get("finished_at")
        if st and fi:
            wall = (datetime.fromisoformat(fi) - datetime.fromisoformat(st)).total_seconds()
    except Exception:
        pass
    exc = (res.get("exception_info") or {}).get("exception_type") if isinstance(res, dict) else None
    return {
        "trial": t.name, "task": res.get("task_name") if isinstance(res, dict) else None,
        "reward": reward, "lm_calls": u.get("n_lm_calls"), "bash_turns": u.get("n_bash"),
        "free_edit_turns": u.get("free_ctx_turns"), "real_edits": u.get("n_ctx_syncs_real"),
        "nudges": u.get("n_nudges"), "rollbacks": u.get("n_retry_on_limit"),
        "budget_final": u.get("budget_finalized"), "summaries": len([x for x in sc if "after" in x]),
        "prompt_tokens": (u.get("prompt_tokens") or 0) + sum(x.get("prompt_tokens", 0) for x in sc),
        "completion_tokens": (u.get("completion_tokens") or 0) + sum(x.get("completion_tokens", 0) for x in sc),
        "cached_tokens": u.get("cached_tokens"), "peak_sent_ctx": peak,
        "prefill_cache_aware": kv.get("cache_aware_prefill_tokens"),
        "prefill_naive": kv.get("naive_prefill_tokens"),
        "pflops_cache_aware": round(kv["cache_aware_flops"] / 1e15, 3) if kv.get("cache_aware_flops") else None,
        "wall_s": wall, "rule_violation": cheat, "exception": exc,
    }


def main() -> None:
    args = sys.argv[1:]
    out_json = None
    if "--json" in args:
        i = args.index("--json"); out_json = args[i + 1]; del args[i:i + 2]
    rows = []
    for j in args:
        jd = Path(j)
        for t in sorted(p for p in jd.iterdir() if p.is_dir() and (p / "agent").exists() or (p / "result.json").exists()):
            r = trial_row(t); r["job"] = jd.name; rows.append(r)
    cols = ["job", "task", "reward", "lm_calls", "bash_turns", "free_edit_turns", "real_edits",
            "summaries", "nudges", "rollbacks", "prompt_tokens", "completion_tokens",
            "cached_tokens", "peak_sent_ctx", "prefill_cache_aware",
            "prefill_naive", "pflops_cache_aware", "wall_s", "rule_violation", "exception"]
    print("\t".join(cols))
    for r in rows:
        print("\t".join("" if r.get(c) is None else (f"{r[c]:.3f}" if isinstance(r[c], float) else str(r[c])) for c in cols))
    if rows:
        rs = [r["reward"] for r in rows if isinstance(r["reward"], (int, float))]
        print(f"# trials={len(rows)} mean_reward={sum(rs)/len(rs):.4f}" if rs else f"# trials={len(rows)} no rewards",
              f"prompt_tokens={sum(r['prompt_tokens'] for r in rows)} completion_tokens={sum(r['completion_tokens'] for r in rows)}",
              f"lm_calls={sum(r['lm_calls'] or 0 for r in rows)}")
    if out_json:
        Path(out_json).write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
