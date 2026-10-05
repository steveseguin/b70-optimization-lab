#!/usr/bin/env python3
"""Score, cost and "what happened" tables for one or more Harbor job directories.

  summarize_results.py <job_dir> [<job_dir> ...] [--json out.json] [--check] [--brief]

Table 1 (one row per trial): arm, task kind, storage mode, stream size, seed, reward, LM calls,
edits (real context-file edits) / summaries (ok+failed), peak sent context, prompt tokens read
(summary calls included), completion tokens, wall seconds, ended_by and rule.

  ended_by  submit            the model ran the submit command
            submit(final)     it submitted on the budget's final-turn notice
            budget_stop       the plain arm's over-budget policy stopped it (a rule, not a cap)
            CAP:max_steps / CAP:lm_calls / CAP:iterations   a harness cap ended it  (INVALID)
            EXC:<type>        Harbor exception, e.g. AgentTimeoutError            (INVALID)
            server_window     the server refused the request (context window)     (INVALID)
            unknown                                                               (INVALID)
  rule      ok | VOID (memory-only task: stream data found in a file) | suspect (a command
            redirected or tee'd `next`, or wrote SET/update lines to a file; read the trajectory)

Table 2 (diagnostics): answer status counts (correct / blank / stale / wrong), items delivered
by `next`, items seen whole in the context, items cut by the harness (observation or
newest-output truncation), broken pipes, refused `next` calls, turns that hit max_tokens,
summary failures, rollbacks, and for kvstream the loss attribution of every missed key:
  never   its final value never appeared in any context the model was sent (never received
          whole, or kept only in files);
  dropped it appeared, but not in the last context before submitting (removed by an edit,
          summary or rollback);
  copy    it was in the last context, yet the answer was blank or wrong (recall/copy error).
For notes-mode kvstream tasks, stored = fraction of queried values present in files.

--check exits 1 if any trial is INVALID or VOID (second-comparison.sh uses it to fail loudly).
Legacy (first comparison) jobs work too; v2-only fields are then blank.
"""
from __future__ import annotations

import json
import re
import sys
import tomllib
from datetime import datetime
from pathlib import Path

SUBMIT = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
ITEM_RE = re.compile(r"ITEM (\d+)/(\d+) \(")
NEXT_STORE = [re.compile(r"\bnext\b[^\n;&|]*>"), re.compile(r"\bnext\b[^\n;&]*\|\s*tee\b")]
WRITE_RE = re.compile(r"(>>?\s*(?!/dev/null)[/\w.$~-]+|\btee\b|open\([^)]*['\"][wa]['\"])")
DATA_RE = re.compile(r"(SET k-[0-9a-f]{8} = \w+|\b(?:SET|ADD) [a-z]+\d\d -?\d+|\| memo:)")


def load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def msg_text(m: dict) -> str:
    parts = [m.get("reasoning_content") or ""]
    c = m.get("content")
    parts.append(c if isinstance(c, str) else json.dumps(c) if c else "")
    for tc in m.get("tool_calls") or []:
        fn = tc.get("function") if isinstance(tc, dict) else None
        if isinstance(fn, dict):
            parts.append(str(fn.get("arguments") or ""))
    return "\n".join(parts)


def commands(ctx: dict, traj: list) -> list[str]:
    out = []
    for seg in (ctx.get("segments") or []) if isinstance(ctx, dict) else []:
        for st in seg.get("steps") or []:
            for tc in st.get("tool_calls") or []:
                a = tc.get("arguments") or ""
                try:
                    out.append(str(json.loads(a).get("command", "")))
                except Exception:
                    out.append(str(a))
    if not out:
        for m in traj:
            if isinstance(m, dict) and m.get("role") == "assistant":
                for tc in m.get("tool_calls") or []:
                    try:
                        out.append(str(json.loads(tc["function"]["arguments"]).get("command", "")))
                    except Exception:
                        pass
    return out


def trial_row(t: Path) -> dict:
    agent = t / "agent"
    u = load(agent / "usage.json") or {}
    sc = load(agent / "summary_calls.json") or []
    res = load(t / "result.json") or {}
    cfg = load(t / "config.json") or {}
    kw = ((cfg.get("agent") or {}).get("kwargs") or {}) if isinstance(cfg, dict) else {}
    task_dir = Path(((cfg.get("task") or {}).get("path")) or "/nonexistent") if isinstance(cfg, dict) else Path("/x")
    md = {}
    if (task_dir / "task.toml").exists():
        md = tomllib.loads((task_dir / "task.toml").read_text()).get("metadata", {})
    spec = load(task_dir / "tests" / "spec.json") or {}
    details = load(t / "verifier" / "details.json") or {}

    reward = None
    vr = (res.get("verifier_result") or {}).get("rewards") if isinstance(res, dict) else None
    if isinstance(vr, dict):
        reward = vr.get("reward", next(iter(vr.values()), None))
    if reward is None and (t / "verifier" / "reward.txt").exists():
        try:
            reward = float((t / "verifier" / "reward.txt").read_text().strip())
        except ValueError:
            pass

    # snapshots: peak context, items seen / cut, loss attribution
    snaps = []
    for s in sorted((agent / "context_snapshots").glob("turn-*.json")):
        d = load(s) or {}
        if d.get("kind") in ("agent", None) and d.get("messages") is not None:
            snaps.append(d)
    peak = max((int(d.get("sent_tokens") or d.get("tokens") or 0) for d in snaps
                if d.get("kind") == "agent"), default=0)
    seen_whole, cut = set(), set()
    # an item counts as seen whole only if its LAST line reached the context (a `| head -1`
    # shows the header but not the batch)
    tails = {}
    try:
        for i, ln in enumerate((task_dir / "environment" / "stream.jsonl").read_text().splitlines(), 1):
            tails[i] = json.loads(ln)["text"].rstrip().splitlines()[-1].strip()
    except Exception:
        pass
    exp = spec.get("expected") or {}
    want = {k: " ".join(str(v).split()) for k, v in exp.items()} if spec.get("kind") == "kv" else {}
    seen_val = set()
    last_text = ""
    for d in snaps:
        texts = []
        for m in d["messages"]:
            if not isinstance(m, dict):
                continue
            tx = msg_text(m)
            texts.append(tx)
            if m.get("role") in ("tool", "user"):
                for mm in ITEM_RE.finditer(tx):
                    n = int(mm.group(1))
                    if tails.get(n, "") in tx and "elided" not in tx:
                        seen_whole.add(n)
                    elif "elided" in tx:
                        cut.add(n)
        if want:
            blob = " ".join(" ".join(texts).split())
            seen_val.update(k for k, v in want.items() if k not in seen_val and v in blob)
            if d.get("kind") == "agent":
                last_text = blob
    cut -= seen_whole

    traj = load(agent / "trajectory.json") or []
    ctx = load(agent / "trajectory.ctx.json") or {}
    cmds = commands(ctx, traj)
    opt_violation = any("/opt/kvstream" in c for c in cmds)
    suspect = sum(1 for c in cmds if any(p.search(c) for p in NEXT_STORE)
                  or (WRITE_RE.search(c) and DATA_RE.search(c)))

    # turns that hit max_tokens
    mx = int(kw.get("max_tokens") or 0)
    hit_max = 0
    for seg in (ctx.get("segments") or []) if isinstance(ctx, dict) else []:
        for st in seg.get("steps") or []:
            ct = ((st.get("metrics") or {}).get("completion_tokens")) or 0
            if mx and ct >= mx:
                hit_max += 1

    # why the run ended
    timing = load(agent / "timing.json") or []
    steps = sum(1 for x in timing if isinstance(x, dict) and "llm_s" in x) - \
        sum(1 for x in timing if isinstance(x, dict) and x.get("free_ctx_turn"))
    last_tool = next((m for m in reversed(traj) if isinstance(m, dict) and m.get("role") == "tool"), None)
    submitted = bool(last_tool) and str(last_tool.get("content") or "").startswith(SUBMIT)
    exc = (res.get("exception_info") or {}).get("exception_type") if isinstance(res, dict) else None
    max_steps = int(u.get("max_steps") or kw.get("max_steps") or 0)
    retries = int(u.get("max_num_retry_on_limit") or 0)
    max_iters = 2 * max_steps + 8 + min(retries, max_steps)
    tlog = (t / "trial.log").read_text(errors="replace") if (t / "trial.log").exists() else ""
    if exc:
        ended = f"EXC:{exc}"
    elif submitted:
        ended = "submit(final)" if u.get("budget_finalized") else "submit"
    elif u.get("hit_lm_call_cap"):
        ended = "CAP:lm_calls"
    elif u.get("budget_finalized"):
        ended = "budget_stop"
    elif max_steps and steps >= max_steps:
        ended = "CAP:max_steps"
    elif u.get("total_iters") and int(u["total_iters"]) >= max_iters:
        ended = "CAP:iterations"
    elif "Context window exceeded" in tlog or "Context overflow" in tlog:
        ended = "server_window"
    else:
        ended = "unknown"
    invalid = ended.startswith(("CAP:", "EXC:", "server_window", "unknown"))

    void = bool(details.get("void"))
    mode = md.get("mode") or spec.get("mode")
    rule = "VOID" if void else ("suspect" if (mode == "memory" and suspect) else "ok")
    if opt_violation:
        rule += "+opt"

    counts = details.get("counts") or {}
    per_key = details.get("per_key") or {}
    attr = {"never": 0, "dropped": 0, "copy": 0}
    if want and per_key:
        for k, st in per_key.items():
            if st == "correct":
                continue
            if k not in seen_val:
                attr["never"] += 1
            elif want[k] not in last_text:
                attr["dropped"] += 1
            else:
                attr["copy"] += 1
    dl = details.get("delivery") or {}
    wall = None
    try:
        st, fi = res.get("started_at"), res.get("finished_at")
        if st and fi:
            wall = (datetime.fromisoformat(fi) - datetime.fromisoformat(st)).total_seconds()
    except Exception:
        pass
    kv_flops = (((ctx.get("final_metrics") or {}).get("extra") or {}).get("kv_cache_flops") or {}) \
        if isinstance(ctx, dict) else {}
    ok_sum = [x for x in sc if "after" in x]
    return {
        "trial": t.name, "task": res.get("task_name") if isinstance(res, dict) else None,
        "kind": md.get("kind") or ("kvstream" if "kvstream" in t.name else None), "mode": mode or "legacy",
        "size": md.get("stream_tokens") or md.get("approx_stream_tokens"),
        "items": md.get("n_items") or ((md.get("n_batches") or 0) + 1 if md else None),
        "seed": md.get("seed"), "budget": u.get("context_budget_tokens"),
        "reward": reward, "score_raw": details.get("score_raw", reward), "void": void,
        "lm_calls": u.get("n_lm_calls"), "bash_turns": u.get("n_bash"),
        "free_edit_turns": u.get("free_ctx_turns"), "real_edits": u.get("n_ctx_syncs_real"),
        "nudges": u.get("n_nudges"), "rollbacks": u.get("n_retry_on_limit"),
        "turns_rolled_back": u.get("n_turns_rolled_back"),
        "budget_final": u.get("budget_finalized"), "summaries": len(ok_sum),
        "summary_failed": len(sc) - len(ok_sum),
        "prompt_tokens": (u.get("prompt_tokens") or 0) + sum(x.get("prompt_tokens", 0) for x in sc),
        "completion_tokens": (u.get("completion_tokens") or 0) + sum(x.get("completion_tokens", 0) for x in sc),
        "cached_tokens": (u.get("cached_tokens") or 0) + sum(x.get("cached_tokens", 0) for x in sc), "peak_sent_ctx": peak,
        "pflops_cache_aware": round(kv_flops["cache_aware_flops"] / 1e15, 3) if kv_flops.get("cache_aware_flops") else None,
        "wall_s": wall, "ended_by": ended, "invalid": invalid, "rule": rule,
        "rule_violation": opt_violation, "exception": exc,
        "correct": counts.get("correct", details.get("correct")), "blank": counts.get("blank"),
        "stale": counts.get("stale"), "wrong": counts.get("wrong"),
        "delivered": dl.get("items_delivered"), "seen_whole": len(seen_whole) if snaps else None,
        "cut": len(cut), "broken_pipe": dl.get("items_broken_pipe"), "to_file": dl.get("items_to_file"),
        "tee": dl.get("items_with_tee"), "refused": dl.get("refused"), "hit_max_tokens": hit_max,
        "suspect_cmds": suspect, "lost_never": attr["never"] if want else None,
        "lost_dropped": attr["dropped"] if want else None, "lost_copy": attr["copy"] if want else None,
        "stored_frac": details.get("stored_frac"), "violations": details.get("violations"),
    }


def arm_of(job: str) -> str:
    return job.split("__", 1)[0] if "__" in job else job.split("-", 1)[0]


def fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.3f}" if v <= 1.0 else f"{v:.0f}"
    return str(v)


def main() -> None:
    args = sys.argv[1:]
    out_json, check, brief = None, "--check" in args, "--brief" in args
    args = [a for a in args if a not in ("--check", "--brief")]
    if "--json" in args:
        i = args.index("--json"); out_json = args[i + 1]; del args[i:i + 2]
    rows = []
    for j in args:
        jd = Path(j)
        if not jd.is_dir():
            continue
        for t in sorted(p for p in jd.iterdir() if p.is_dir() and ((p / "agent").exists() or (p / "result.json").exists())):
            r = trial_row(t); r["job"] = jd.name; r["arm"] = arm_of(jd.name); rows.append(r)
    rows.sort(key=lambda r: (str(r.get("kind")), str(r.get("mode")), int(r.get("size") or 0),
                             str(r.get("arm")), int(r.get("seed") or 0)))
    t1 = ["arm", "kind", "mode", "size", "seed", "budget", "reward", "lm_calls", "real_edits", "summaries",
          "summary_failed", "peak_sent_ctx", "prompt_tokens", "cached_tokens", "completion_tokens", "wall_s", "ended_by", "rule"]
    t2 = ["arm", "kind", "mode", "size", "seed", "correct", "blank", "stale", "wrong", "lost_never",
          "lost_dropped", "lost_copy", "stored_frac", "items", "delivered", "seen_whole", "cut",
          "broken_pipe", "to_file", "tee", "refused", "hit_max_tokens", "rollbacks", "nudges",
          "suspect_cmds", "score_raw"]
    print("\t".join(t1))
    for r in rows:
        print("\t".join(fmt(r.get(c)) for c in t1))
    if not brief:
        print("\n# diagnostics")
        print("\t".join(t2))
        for r in rows:
            print("\t".join(fmt(r.get(c)) for c in t2))
    if rows:
        rs = [r["reward"] for r in rows if isinstance(r["reward"], (int, float))]
        print(f"# trials={len(rows)} mean_reward={sum(rs)/len(rs):.4f}" if rs else f"# trials={len(rows)} no rewards",
              f"prompt_tokens={sum(r['prompt_tokens'] for r in rows)} cached_tokens={sum(r['cached_tokens'] or 0 for r in rows)} completion_tokens={sum(r['completion_tokens'] for r in rows)}",
              f"lm_calls={sum(r['lm_calls'] or 0 for r in rows)}")
    bad = [r for r in rows if r["invalid"] or r["void"]]
    for r in bad:
        print(f"!!! {r['job']}/{r['trial']}: ended_by={r['ended_by']} rule={r['rule']} "
              f"violations={r.get('violations')}  -> this trial does not count; fix and re-run it")
    if out_json:
        Path(out_json).write_text(json.dumps(rows, indent=1, default=str))
    if check and bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
