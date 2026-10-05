#!/usr/bin/env python3
"""Score, cost and "what happened" tables for one or more Harbor job directories.

  summarize_results.py <path> [<path> ...] [--json out.json] [--check] [--brief]
  <path> = a trial dir, a Harbor job dir, a jobs/ dir or a runs/ dir (e.g. $OUT_DIR/runs)

Table 1 (one row per trial): arm, task kind, storage mode, stream size, seed, reward, LM calls,
edits (real context-file edits) / summaries (ok+failed), peak sent context, prompt tokens read
(summary calls included), cached prompt tokens (server-reported prompt_tokens_details, summed),
think_share (share of the sent context, by characters over all agent-call snapshots, that was
earlier turns' thinking; ~0 for the thinking-dropped arms), completion tokens split into
think_tok_est / other_tok_est (by characters; dropped thinking read from dropped_thinking.jsonl),
thinking_off_calls, prefix_stable_share (improved agent: share of calls whose messages, the pinned
state aside, extend the previous call's exactly), wall seconds, ended_by and rule.

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


HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?)\n\1[ \t]*(?=\n|$)", re.S)
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
ALLOWED = ("/tmp/.live_ctx/", "/app/answers.json", "/dev/null", "/dev/stdout", "/dev/stderr")


def is_suspect(c: str) -> bool:
    """Memory-only audit of one command: does it send `next` output into a file or tee, or write
    stream data somewhere other than the harness's own context files (the mirror and the improved
    agent's STATE.txt, which ARE the context) or /app/answers.json? Shell text and embedded code
    (heredoc bodies, quoted `python3 -c` code) are judged separately, so comparisons such as
    `si>0` inside Python are not mistaken for redirections."""
    bodies = [m.group(2) for m in HEREDOC.finditer(c)]
    shell = HEREDOC.sub("<<HEREDOC\n", c)
    bodies += [q[1:-1] for q in QUOTED.findall(shell)]
    shell = QUOTED.sub("''", shell)
    # stdout of `next` into a file or tee; stderr redirects (2>/dev/null, 2>&1), >/dev/null and
    # `which next` / `type next` are not storage
    sh2 = re.sub(r"\d*>&\d|\d+>>?\s*\S+|>>?\s*/dev/null", "", shell)
    if re.search(r"(?<!which )(?<!type )(?<!-v )\bnext\b[^\n;&|]*>|"
                 r"(?<!which )(?<!type )(?<!-v )\bnext\b[^\n;&]*\|\s*tee\b", sh2):
        return True
    if not DATA_RE.search(c):
        return False
    targets = [a or b for a, b in re.findall(
        r"(?:^|[^<>0-9&])>>?\s*([/\w.$~-]+)|\btee\s+(?:-a\s+)?([/\w.$~-]+)", shell)]
    if any(not t.startswith(ALLOWED) for t in targets if t):
        return True
    for body in bodies:
        if re.search(r"open\([^)]*['\"][wa]b?\+?['\"]|\.write_text\(", body):
            paths = re.findall(r"['\"](/(?:[\w.-]+/)+[\w.-]+)['\"]", body)  # real paths, not "/20"
            if any(not p.startswith(ALLOWED) for p in paths) or not paths:
                return True
    return False


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
    seen_whole, cut, headers_seen = set(), set(), set()
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
    think_chars = all_chars = 0
    for d in snaps:
        texts = []
        for m in d["messages"]:
            if not isinstance(m, dict):
                continue
            tx = msg_text(m)
            texts.append(tx)
            if d.get("kind") == "agent":
                all_chars += len(tx)
                think_chars += len(m.get("reasoning_content") or "")
            if m.get("role") in ("tool", "user"):
                for mm in ITEM_RE.finditer(tx):
                    n = int(mm.group(1))
                    headers_seen.add(n)
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
    suspect = sum(1 for c in cmds if is_suspect(c))

    # written tokens split into thinking vs the rest, by characters (approximate: numbers and JSON
    # tokenize denser than prose). Thinking-dropped arms keep it in agent/dropped_thinking.jsonl.
    think_c = other_c = 0
    for seg in (ctx.get("segments") or []) if isinstance(ctx, dict) else []:
        for st in seg.get("steps") or []:
            if st.get("source") != "agent":
                continue
            think_c += len(st.get("reasoning_content") or "")
            other_c += len(str(st.get("message") or ""))
            other_c += sum(len(str(tc.get("arguments") or "")) for tc in st.get("tool_calls") or [])
    dropped_c = 0
    if (agent / "dropped_thinking.jsonl").exists():
        for ln in (agent / "dropped_thinking.jsonl").read_text().splitlines():
            try:
                dropped_c += int(json.loads(ln).get("chars") or 0)
            except Exception:
                pass
    think_c = max(think_c, dropped_c)

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
    # a delivered item whose header never reached any context the model was sent: rolled back
    # (or cut away) before the next call. Memory-only tasks only (notes runs may write to files).
    n_deliv = dl.get("items_delivered")
    items_lost = (sum(1 for n in range(1, int(n_deliv) + 1) if n not in headers_seen)
                  if (mode == "memory" and n_deliv is not None and snaps) else None)
    imp = load(agent / "improved_stats.json") or {}
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
        "prompt_tokens": (u.get("prompt_tokens") or 0) + sum(x.get("prompt_tokens", 0) for x in sc)
                         + int(imp.get("extra_prompt_tokens") or 0),
        "completion_tokens": (u.get("completion_tokens") or 0) + sum(x.get("completion_tokens", 0) for x in sc),
        "think_share": round(think_chars / all_chars, 3) if all_chars else None,
        "cached_tokens": (u.get("cached_tokens") or 0) + sum(x.get("cached_tokens", 0) for x in sc), "peak_sent_ctx": peak,
        "pflops_cache_aware": round(kv_flops["cache_aware_flops"] / 1e15, 3) if kv_flops.get("cache_aware_flops") else None,
        "wall_s": wall, "ended_by": ended, "invalid": invalid, "rule": rule,
        "rule_violation": opt_violation, "exception": exc,
        "correct": counts.get("correct", details.get("correct")), "blank": counts.get("blank"),
        "stale": counts.get("stale"), "wrong": counts.get("wrong"),
        "items_lost": items_lost, "gate_refusals": imp.get("gate_refusals"),
        "protected_rollbacks": imp.get("protected_rollbacks"), "state_rejected": imp.get("state_rejected"),
        "think_cap_cont": imp.get("think_cap_continuations"), "loop_guard": imp.get("loop_guard_calls"),
        "thinking_off_calls": (imp.get("thinking_off_calls") if imp else
                               (u.get("n_lm_calls") if str(kw.get("enable_thinking")).lower() == "false" else 0)),
        "think_tok_est": (int((u.get("completion_tokens") or 0) * think_c / (think_c + other_c))
                          if (think_c + other_c) else None),
        "other_tok_est": (int((u.get("completion_tokens") or 0) * other_c / (think_c + other_c))
                          if (think_c + other_c) else None),
        "prefix_stable_share": (round(imp["prefix_stable"] / max(imp["prefix_calls"] - 1, 1), 3)
                                if imp.get("prefix_calls") else None),
        "prefix_unstable_no_edit": imp.get("prefix_unstable_no_edit"),
        "ctxfold_calls": sum(1 for c in cmds if re.search(r"(^|[;&|]\s*)ctxfold\b", c, re.M)) if imp else None,
        # from the full step record (a context edit turns old tool turns into user text)
        "ctxfold_refused": sum(1 for seg in (ctx.get("segments") or []) for st in seg.get("steps") or []
                               for res in ((st.get("observation") or {}).get("results") or [])
                               if "ctxfold: REFUSED" in str(res.get("content") or "")) if imp else None,
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


def is_trial(p: Path) -> bool:
    return p.is_dir() and ((p / "agent").is_dir() or (p / "verifier").is_dir())


def expand(paths: list[Path], depth: int = 3) -> list[Path]:
    """Trial dirs from any mix of trial dirs, job dirs, a jobs/ dir or a runs/ dir (a Harbor job
    dir also holds a job-level result.json, so result.json alone does not mark a trial)."""
    out: list[Path] = []
    for p in paths:
        if not p.is_dir():
            continue
        if is_trial(p):
            out.append(p)
        elif depth > 0:
            subs = sorted(x for x in p.iterdir() if x.is_dir())
            if (p / "jobs").is_dir():
                subs = [p / "jobs"]
            out.extend(expand(subs, depth - 1))
    return out


def main() -> None:
    args = sys.argv[1:]
    out_json, check, brief = None, "--check" in args, "--brief" in args
    args = [a for a in args if a not in ("--check", "--brief")]
    if "--json" in args:
        i = args.index("--json"); out_json = args[i + 1]; del args[i:i + 2]
    rows = []
    for t in expand([Path(j) for j in args]):
        jd = t.parent
        r = trial_row(t); r["job"] = jd.name; r["arm"] = arm_of(jd.name); rows.append(r)
    rows.sort(key=lambda r: (str(r.get("kind")), str(r.get("mode")), int(r.get("size") or 0),
                             str(r.get("arm")), int(r.get("seed") or 0)))
    t1 = ["arm", "kind", "mode", "size", "seed", "budget", "reward", "lm_calls", "real_edits", "summaries",
          "summary_failed", "peak_sent_ctx", "prompt_tokens", "cached_tokens", "think_share", "completion_tokens",
          "think_tok_est", "other_tok_est", "thinking_off_calls", "prefix_stable_share", "wall_s", "items_lost", "ended_by", "rule"]
    t2 = ["arm", "kind", "mode", "size", "seed", "correct", "blank", "stale", "wrong", "lost_never",
          "lost_dropped", "lost_copy", "stored_frac", "items", "delivered", "seen_whole", "items_lost", "cut",
          "gate_refusals", "protected_rollbacks", "state_rejected", "think_cap_cont", "loop_guard",
          "ctxfold_calls", "ctxfold_refused", "prefix_unstable_no_edit",
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
