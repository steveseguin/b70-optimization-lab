#!/usr/bin/env python3
"""One row per trial of a keeper/retrieval arm: score by question type, agent minutes, calls, notes-call tokens,
where the time went (main loop / notes), and how many counters were ever wrong in the pinned NOTES (notes_audit).

  c10_table.py OUT_DIR ARM[:SEED] ... [--json FILE]
"""
import datetime as dt
import glob
import json
import re
import subprocess
import sys
from pathlib import Path


def row(od: str, arm: str, seed: str) -> dict | None:
    g = glob.glob(f"{od}/runs/jobs/{arm}__sparse-memory-t*k-s{seed}/*/")
    if not g or not Path(g[0] + "verifier/details.json").exists():
        return None
    t = g[0]
    load = lambda name: json.load(open(t + name)) if Path(t + name).exists() else None
    d, u, s, k, tm = load("verifier/details.json"), load("agent/usage.json"), load("agent/keeper_stats.json") or {}, load("agent/keeper_calls.json") or [], load("agent/timing.json") or []
    ref = json.load(open(json.load(open(t + "config.json"))["task"]["path"] + "/tests/reference.json"))["probes"]
    by: dict[str, list[int]] = {}
    for key, res in d["per_key"].items():
        a = by.setdefault(ref[key]["type"] if key in ref else "final", [0, 0])
        a[0] += res == "correct"
        a[1] += 1
    governed = None                                   # questions whose answer is the word of a rule by condition
    try:
        spec = json.load(open(json.load(open(t + "config.json"))["task"]["path"] + "/tests/spec.json"))
        word = (spec.get("rules") or {}).get("class_word")
        if word:
            gov = [k for k, v in spec["expected"].items() if v == word]
            governed = f"{sum(d['per_key'].get(k) == 'correct' for k in gov)}/{len(gov)}"
    except Exception:
        pass
    ex = json.load(open(t + "result.json"))["agent_execution"]
    f = lambda x: dt.datetime.fromisoformat(x.replace("Z", "+00:00"))
    total = (f(ex["finished_at"]) - f(ex["started_at"])).total_seconds()
    llm, sh = sum(x.get("llm_s", 0) for x in tm), sum(x.get("bash_s", 0) for x in tm)
    audit = None
    if s.get("notes_mode", "full") != "none":
        out = subprocess.run([sys.executable, str(Path(__file__).with_name("notes_audit.py")), od, arm, seed], capture_output=True, text=True).stdout
        m = re.search(r"counters ever wrong in NOTES: (\d+)", out)
        audit = int(m.group(1)) if m else None
    return {"arm": arm, "seed": int(seed), "correct": d["correct"], "n": d["n"], "void": d["void"], "by_type": {a: f"{b[0]}/{b[1]}" for a, b in by.items()},
            "seconds": round(total), "minutes": round(total / 60, 1), "calls": u["n_lm_calls"], "main_loop_s": round(llm), "shell_s": round(sh),
            "notes_s": round(total - llm - sh), "main_written": u["completion_tokens"], "notes_calls": s.get("notes_calls", 0),
            "cuts": sum(1 for c in k if c.get("reason") != "keep-inplace-failed"), "notes_written": sum(c.get("notes_completion_tokens", 0) for c in k), "notes_read": sum(c.get("notes_prompt_tokens", 0) for c in k),
            "prompt": u["prompt_tokens"], "cached": u["cached_tokens"], "fallbacks": s.get("delta_fallbacks", 0), "inplace_cuts": s.get("inplace_cuts", 0),
            "inplace_cached": s.get("inplace_cached_tokens", 0), "inplace_prompt": s.get("inplace_prompt_tokens", 0),
            "mention_reasks": s.get("mention_reasks", 0), "recalls": sum(1 for x in tm if str(x.get("cmd") or "").strip().startswith("recall")),
            "archive_reads": sum(1 for x in tm if "live_ctx/archive" in str(x.get("cmd") or "")), "retrievals": s.get("retrievals", 0),
            "retrieved_chars": s.get("retrieved_chars", 0), "notes_wrong_ever": audit, "archive": d.get("archive"),
            "rule_by_condition": governed}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    od, rows = args[0], []
    for spec in args[1:]:
        arm, _, seed = spec.partition(":")
        for sd in ([seed] if seed else ["0", "1"]):
            r = row(od, arm, sd)
            if r:
                rows.append(r)
    print("arm      s  score   final  cur   old   who   rule  meth  min   calls  main_s notes_s  notes: calls written  read    wrong  recalls")
    for r in rows:
        b = r["by_type"]
        print(f"{r['arm']:8s} {r['seed']}  {r['correct']:>3}/{r['n']:<3} {b.get('final', '-'):>6} {b.get('current', '-'):>5} {b.get('old_value', '-'):>5} {b.get('who', '-'):>5} "
              f"{b.get('rule', '-'):>5} {b.get('procedure', '-'):>5} {r['minutes']:>5} {r['calls']:>6} {r['main_loop_s']:>6} {r['notes_s']:>6}  {r['notes_calls']:>12} {r['notes_written']:>7} {r['notes_read']:>7} "
              f"{str(r['notes_wrong_ever']):>6} {r['recalls']:>6}" + (f"  archive_reads={r['archive_reads']}" if r["archive_reads"] else "")
              + (f"  rule_by_condition={r['rule_by_condition']}" if r.get("rule_by_condition") else ""))
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(rows, indent=1) + "\n")


if __name__ == "__main__":
    main()
