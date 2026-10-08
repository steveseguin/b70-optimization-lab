#!/usr/bin/env python3
"""Summarise LongMemEval trials per arm and stratum (stdlib only).

  longmemeval_summary.py RUNS_JOBS_DIR [--verdicts verdicts.jsonl ...] [--json out.json]

Per trial: arm, question, stratum, deterministic status, judged label (if a verdicts file is given; the
official judge is preferred over a --local one when both exist), void, wall time, tokens written, peak
context, model calls, recall calls, summaries, ended_by. Agent arms reuse summarize_results.trial_row;
arm F (longmemeval_direct.py) is read from its own files. Then a table per arm: judged (or, until judged,
deterministic) correct / n per stratum, overall, task-averaged, median wall time, tokens written.
THE HEADLINE IS THE JUDGED COLUMN; the deterministic column is a placeholder.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import summarize_results as sr  # noqa: E402

STRATA = ["single-session-user", "single-session-assistant", "single-session-preference", "multi-session",
          "temporal-reasoning", "knowledge-update", "abstention"]
SHORT = {"single-session-user": "ssu", "single-session-assistant": "ssa", "single-session-preference": "ssp",
         "multi-session": "multi", "temporal-reasoning": "temp", "knowledge-update": "ku", "abstention": "abs"}


def load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def rows(jobs_dir: Path) -> list[dict]:
    out = []
    for jp in sorted(jobs_dir.glob("*/*/verifier/judge_pair.json")):
        t, job = jp.parent.parent, jp.parent.parent.parent.name
        pair = load(jp) or {}
        det = load(t / "verifier" / "details.json") or {}
        r = {"job": job, "arm": job.split("__", 1)[0], "question_id": pair.get("question_id"),
             "stratum": "abstention" if pair.get("abstention") else pair.get("question_type"),
             "status": det.get("status"), "det_correct": det.get("score", 0) == 1.0, "void": det.get("void"),
             "violations": det.get("violations")}
        if (t / "agent" / "request_meta.json").exists():          # arm F
            m = load(t / "agent" / "request_meta.json") or {}
            u = load(t / "agent" / "usage.json") or {}
            r.update(wall_s=m.get("wall_s"), completion_tokens=u.get("completion_tokens"),
                     peak_ctx=u.get("prompt_tokens") or m.get("prompt_tokens_local"), lm_calls=1, recalls=None,
                     summaries=None, ended_by=m.get("status"), invalid=m.get("status") != "ok")
        else:
            x = sr.trial_row(t)
            st = load(t / "agent" / "improved_stats.json") or {}
            r.update(wall_s=x.get("wall_s"), completion_tokens=x.get("completion_tokens"),
                     peak_ctx=x.get("peak_sent_ctx"), lm_calls=x.get("lm_calls"), recalls=st.get("recall_calls"),
                     summaries=x.get("summaries"), ended_by=x.get("ended_by"), invalid=x.get("invalid"))
        out.append(r)
    return out


def main() -> None:
    args = sys.argv[1:]
    verdict_files, out_json = [], None
    while "--verdicts" in args:
        i = args.index("--verdicts"); verdict_files.append(args[i + 1]); del args[i:i + 2]
    if "--json" in args:
        i = args.index("--json"); out_json = args[i + 1]; del args[i:i + 2]
    rs = [r for d in args for r in rows(Path(d))]
    verdicts: dict[str, dict] = {}
    for vf in verdict_files:
        for ln in open(vf):
            v = json.loads(ln)
            old = verdicts.get(v["job"])
            if old is None or (old.get("secondary") and not v.get("secondary")):
                verdicts[v["job"]] = v
    for r in rs:
        v = verdicts.get(r["job"])
        r["judged"] = None if v is None else (bool(v["label"]) and not r["void"])
        r["judge"] = None if v is None else (v["judge_model"] + (" (secondary)" if v.get("secondary") else ""))
    cols = ["arm", "question_id", "stratum", "status", "judged", "void", "wall_s", "completion_tokens", "peak_ctx",
            "lm_calls", "recalls", "summaries", "ended_by"]
    print("\t".join(cols))
    for r in sorted(rs, key=lambda r: (r["arm"], STRATA.index(r["stratum"]) if r["stratum"] in STRATA else 9,
                                       str(r["question_id"]))):
        print("\t".join("" if r.get(c) is None else str(r.get(c)) for c in cols))
    print("\n# per arm (judged where available, else deterministic marked *); invalid/void trials count as wrong")
    print("\t".join(["arm", "n", "judged_n"] + [SHORT[s] for s in STRATA] + ["overall", "task_avg", "med_wall_s",
                                                                          "med_tokens_written", "invalid"]))
    for arm in sorted({r["arm"] for r in rs}):
        a = [r for r in rs if r["arm"] == arm]
        jn = sum(1 for r in a if r["judged"] is not None)
        use_j = jn == len(a)

        def ok(r):
            return bool(r["judged"]) if use_j else (r["det_correct"] and not r["void"])
        cells, accs = [], []
        for s in STRATA:
            b = [r for r in a if r["stratum"] == s]
            if b:
                c = sum(ok(r) for r in b)
                cells.append(f"{c}/{len(b)}")
                accs.append(c / len(b))
            else:
                cells.append("")
        mark = "" if use_j else "*"
        walls = [r["wall_s"] for r in a if isinstance(r.get("wall_s"), (int, float))]
        toks = [r["completion_tokens"] for r in a if isinstance(r.get("completion_tokens"), (int, float))]
        print("\t".join([arm, str(len(a)), str(jn)] + cells + [
            f"{sum(ok(r) for r in a)}/{len(a)}{mark}", f"{statistics.mean(accs):.3f}{mark}" if accs else "",
            f"{statistics.median(walls):.0f}" if walls else "", f"{statistics.median(toks):.0f}" if toks else "",
            str(sum(1 for r in a if r["invalid"] or r["void"]))]))
    if out_json:
        Path(out_json).write_text(json.dumps(rs, indent=1, default=str))


if __name__ == "__main__":
    main()
