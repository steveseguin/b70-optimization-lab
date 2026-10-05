#!/usr/bin/env python3
"""Report for the reading run (sparse prose; arms B32ir, Ar, E32r, any arm really). CPU only, read-only.

  reading_run_report.py PATH [PATH ...] [--json out.json]
  PATH = a trial dir, a job dir, a jobs/ dir or a runs/ dir (e.g. .../context-clm-ninth-20261005/client/rd120-*/runs)

Per trial:
  score, answer status counts, VOID / rule, ended_by          (summarize_results.trial_row)
  per-batch state accuracy against tests/reference.json        (replay_state_check.check_trial): batches
      compared, first batch where the agent's table went wrong, error classes (persistent / transient),
      the agent's table accuracy at the last compared batch
  calls, thinking-on vs thinking-off calls                      (improved_stats.json; plain arms: from the
                                                                 agent's enable_thinking setting)
  tokens written: thinking vs other (character split, as summarize_results), prompt tokens, cache share,
      peak context
  time split (time_and_reuse_census.py's method): per call, reading = cold-read time of the prompt minus
      that of its cached part (measured 832-piece read speeds), writing = call time - reading; tools =
      sandbox command time; other = trial wall - calls - tools
  drops refused (`ctxfold: REFUSED`), room-check refusals, window refusals
  parser check: did the model write a program to fold the reports? (commands containing re.compile /
      re.match / re.findall / re.search / def fold / FOLD.py / split(" | ") applied to report text ...),
      with the first such command quoted
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import replay_state_check as rsc          # noqa: E402
import summarize_results as sr            # noqa: E402
from time_and_reuse_census import t_read_new  # noqa: E402

PARSER = re.compile(r"re\.(?:compile|match|findall|search|finditer|sub)\(|def\s+fold\b|>\s*/tmp/\.live_ctx/FOLD\.py"
                    r"|\.split\(\s*['\"]\.\s*['\"]\)|(?:went up|lost|set to|stands at)['\"]\s*in\b")


def load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def time_split(t: Path) -> dict:
    ctx = load(t / "agent" / "trajectory.ctx.json") or {}
    timing = load(t / "agent" / "timing.json") or []
    res = load(t / "result.json") or {}
    steps = [st for seg in (ctx.get("segments") or []) for st in seg.get("steps") or [] if st.get("metrics")]
    llm = [x for x in timing if isinstance(x, dict) and "llm_s" in x]
    reading = 0.0
    for st in steps:
        m = st["metrics"]
        reading += t_read_new(m.get("prompt_tokens") or 0, m.get("cached_tokens") or 0)
    llm_s = sum(x["llm_s"] for x in llm)
    tools = sum(x.get("bash_s", 0) or 0 for x in timing if isinstance(x, dict))
    wall = None
    try:
        from datetime import datetime
        wall = (datetime.fromisoformat(res["finished_at"]) - datetime.fromisoformat(res["started_at"])).total_seconds()
    except Exception:
        pass
    return {"wall_s": wall, "calls_s": round(llm_s), "reading_s": round(reading), "writing_s": round(llm_s - reading),
            "tools_s": round(tools), "other_s": round(wall - llm_s - tools) if wall else None}


def parser_use(cmds: list[str]) -> tuple[int, str]:
    hits = [c for c in cmds if PARSER.search(c) and not c.strip().startswith("cat /")]
    return len(hits), (hits[0][:300].replace("\n", "\\n") if hits else "")


def report(t: Path) -> dict:
    row = sr.trial_row(t)
    try:
        rep = rsc.check_trial(t)
    except Exception as e:
        rep = {"error": f"{type(e).__name__}: {e}"}
    imp = load(t / "agent" / "improved_stats.json") or {}
    cfg = load(t / "config.json") or {}
    kw = (cfg.get("agent") or {}).get("kwargs") or {}
    ws = load(t / "agent" / "window_stats.json") or {}
    if imp.get("thinking_on_calls") is not None:
        th_on, th_off = imp.get("thinking_on_calls"), imp.get("thinking_off_calls")
    else:
        on = str(kw.get("enable_thinking", True)).lower() != "false"
        th_on, th_off = (row["lm_calls"], 0) if on else (0, row["lm_calls"])
    ctx = load(t / "agent" / "trajectory.ctx.json") or {}
    cmds = sr.commands(ctx, load(t / "agent" / "trajectory.json") or [])
    obs = [r.get("content") or "" for seg in (ctx.get("segments") or []) for st in seg.get("steps") or []
           for r in ((st.get("observation") or {}).get("results") or [])]
    n_parser, first_parser = parser_use(cmds)
    pt = row.get("prompt_tokens") or 0
    out = {
        "trial": f"{t.parent.name}/{t.name}", "arm": sr.arm_of(t.parent.name), "kind": row.get("kind"),
        "size": row.get("size"), "seed": row.get("seed"), "reward": row.get("reward"),
        "counts": {k: row.get(k) for k in ("correct", "blank", "stale", "wrong")},
        "void": row.get("void"), "rule": row.get("rule"), "ended_by": row.get("ended_by"),
        "batches": rep.get("batches"), "states_compared": rep.get("states_compared"),
        "first_divergence": rep.get("first_divergence"), "errors_persistent": rep.get("classes"),
        "errors_transient": rep.get("transient"), "final_state_wrong": rep.get("final_state_wrong"),
        "final_state_batch": rep.get("final_state_batch"),
        "answers_wrong_though_state_right": rep.get("answers_wrong_though_state_right"),
        "calls": row.get("lm_calls"), "thinking_on_calls": th_on, "thinking_off_calls": th_off,
        "written": row.get("completion_tokens"), "think_tok_est": row.get("think_tok_est"),
        "other_tok_est": row.get("other_tok_est"), "prompt_tokens": pt,
        "cache_share": round((row.get("cached_tokens") or 0) / pt, 3) if pt else None,
        "peak_ctx": row.get("peak_sent_ctx"), "time": time_split(t),
        "drops_refused": sum("ctxfold: REFUSED" in o for o in obs),
        "drops_ok": sum("ctxfold: removed items" in o for o in obs),
        "room_refusals": imp.get("gate_refusals"), "window_refusals": ws.get("window_refusals"),
        "parser_commands": n_parser, "first_parser_command": first_parser,
    }
    return out


def fmt(r: dict) -> str:
    tm = r["time"]
    fd = r.get("first_divergence") or {}
    return "\n".join([
        f"== {r['trial']}  arm={r['arm']} kind={r['kind']} size={r['size']} seed={r['seed']}",
        f"   score {r['reward']}  {r['counts']}  void={r['void']} rule={r['rule']} ended_by={r['ended_by']}",
        f"   state vs reference: {r['states_compared']} states over {r['batches']} batches; last compared batch "
        f"{r['final_state_batch']} with {r['final_state_wrong']} counters wrong; first wrong at batch "
        f"{fd.get('batch')} ({fd.get('counter')}: {fd.get('class')}, agent {fd.get('agent')} vs {fd.get('truth')})",
        f"   errors persistent {r['errors_persistent']}  transient {r['errors_transient']}  "
        f"answer lookups wrong though state right: {r['answers_wrong_though_state_right']}",
        f"   calls {r['calls']} (thinking on {r['thinking_on_calls']}, off {r['thinking_off_calls']}); written "
        f"{r['written']} (thinking ~{r['think_tok_est']}, other ~{r['other_tok_est']}); prompt {r['prompt_tokens']} "
        f"(cached {r['cache_share']}); peak context {r['peak_ctx']}",
        f"   time: wall {tm['wall_s']} s = calls {tm['calls_s']} (reading ~{tm['reading_s']}, writing ~{tm['writing_s']}) "
        f"+ tools {tm['tools_s']} + other {tm['other_s']}",
        f"   drops ok {r['drops_ok']} refused {r['drops_refused']}; room-check refusals {r['room_refusals']}; "
        f"window refusals {r['window_refusals']}",
        f"   wrote a parser/fold program: {'YES, ' + str(r['parser_commands']) + ' commands; first: ' + r['first_parser_command'] if r['parser_commands'] else 'no'}",
    ])


def main() -> None:
    args = sys.argv[1:]
    out_json = None
    if "--json" in args:
        i = args.index("--json"); out_json = args[i + 1]; del args[i:i + 2]
    res = []
    for t in sr.expand([Path(a) for a in args]):
        r = report(t)
        res.append(r)
        print(fmt(r))
    if out_json:
        Path(out_json).write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
