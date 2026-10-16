#!/usr/bin/env python3
"""summarize_c21.py: one row per campaign 21/22 arm from the proxy's call log, its status and the task's grade.

  python3 summarize_c21.py RUN [RUN ...] [--json out.json]     # RUN = c21b, c22, ... (prefix of the state dirs)

Run with the servers down (it reads every calls.jsonl). Columns: score; wall minutes (first call to last); cuts and
recalls; seconds the server spent on main calls and on notes calls (and the notes share); tokens read per main call
and the cached share; the largest single call (read + written: the window the run really needed); main-call
writing speed (tokens written per second of main-call time, a rough decode rate).
"""
import glob
import json
import os
import sys

O = "/mnt/fast-ai/bench-results/context-longrun-20261016"


def grade(job_glob: str) -> str:
    for d in glob.glob(job_glob + "/*/verifier/details.json"):
        v = json.load(open(d))
        if "fixed" in v:
            a = v.get("audit") or {}
            return f"fixed {v['fixed']} clean {v['clean']} audit {a.get('right')}/{a.get('asked')}"
        return f"{v.get('correct')}/{v.get('n')}" + (" VOID" if v.get("void") else "")
    return "no grade"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out_json = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else ""
    if out_json in args:
        args.remove(out_json)
    rows = []
    for run in args:
        for sd in sorted(glob.glob(f"{O}/proxy-state/{run}-*")):
            tag = os.path.basename(sd)
            _, arm, kind, seed = tag.split("-", 3)
            calls = []
            for f in glob.glob(sd + "/*/calls.jsonl"):
                calls += [json.loads(line) for line in open(f) if line.strip()]
            if not calls:
                continue
            st = {}
            try:
                st = next(iter(json.load(open(f"{O}/proxy-status-{tag}.json")).values()))
            except Exception:
                pass
            seed = seed[1:]
            job = {"rules": f"{O}/runs/rules/jobs/{arm}__sparse-memory-t240k-s{seed}",
                   "1m": f"{O}/runs/1m/jobs/{arm}__sparse-memory-t1000k-s{seed}",
                   "repair": f"{O}/runs/repair/jobs/{arm}__repair-n40-s{seed}"}.get(kind, "")
            main_c = [c for c in calls if c["kind"] == "main"]
            notes_c = [c for c in calls if c["kind"] == "notes"]
            ms = sum(c.get("s") or 0 for c in main_c)
            ns = sum(c.get("s") or 0 for c in notes_c)
            t0 = min(c["at"] for c in calls)
            t1 = max(c["at"] + (c.get("s") or 0) for c in calls)
            read = sum(c.get("prompt") or 0 for c in main_c)
            cached = sum(c.get("cached") or 0 for c in main_c)
            wrote = sum(c.get("written") or 0 for c in main_c)
            rows.append(dict(
                run=run, arm=arm, kind=kind, score=grade(job) if job else "-", minutes=round((t1 - t0) / 60, 1),
                cuts=st.get("cuts"), inplace=st.get("inplace_cuts"), failed=st.get("inplace_failed"),
                reasks=st.get("inplace_reasks"), recalls=st.get("recalls"), main_calls=len(main_c),
                main_s=round(ms), notes_calls=len(notes_c), notes_s=round(ns),
                notes_share=round(ns / (ms + ns), 3) if ms + ns else None,
                read_per_main=round(read / max(len(main_c), 1)), cached_share=round(cached / read, 3) if read else None,
                largest=max((c.get("prompt") or 0) + (c.get("written") or 0) for c in calls),
                main_written=wrote, main_tok_s=round(wrote / ms, 1) if ms else None,
                notes_written=sum(c.get("written") or 0 for c in notes_c),
                length_stops=sum(c.get("finish") == "length" for c in main_c)))
    keys = ["arm", "kind", "score", "minutes", "cuts", "inplace", "failed", "recalls", "main_s", "notes_s",
            "notes_share", "read_per_main", "cached_share", "largest", "main_tok_s", "length_stops"]
    print("  ".join(f"{k:>13}" for k in keys))
    for r in rows:
        print("  ".join(f"{str(r[k]):>13}" for k in keys))
    if out_json:
        json.dump(rows, open(out_json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
