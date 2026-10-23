#!/usr/bin/env python3
"""Where a 2M hostile seed's wall went: model, tool runs, around-call overhead, between-step client work.

  campaign_time_budget.py RUN ARM SEED [RUN ARM SEED ...] [--json out.json]

Reads the proxy's calls.jsonl (--log-calls: every upstream call with its start time and seconds) under
proxy-state/<RUN>-<ARM>-hostile2mk-s<SEED>/*/ and the client's agent/timing.json (llm_s and bash_s a step) under
runs/<RUN>/hostile2mk/jobs/<ARM>__sparse-memory-t2000k-poison-retro-s<SEED>/*/agent/. Reports, in seconds:
  wall       first main call's start to the last main call's end (the proxy's clock)
  main       sum of the main upstream calls' seconds (the model, including recall rounds)
  notes      sum of the notes calls' seconds (the model)
  bash       sum of the client's bash_s (tool runs)
  around     llm_s summed minus (main + notes): the proxy's and client's work inside a call
  between    wall - llm_s - bash: the client between steps (snapshots, token counts, bookkeeping)
and the gaps between consecutive main calls that hold no notes call, by position in the run (their growth is
what shows work proportional to the retained history). Numbers only; CPU only.
"""
import argparse, bisect, glob, json, statistics as st, sys
from pathlib import Path

O = Path("/mnt/fast-ai/bench-results/context-longrun-20261016")


def budget(run, arm, seed):
    state = glob.glob(f"{O}/proxy-state/{run}-{arm}-hostile2mk-s{seed}/*/calls.jsonl")
    timing = glob.glob(f"{O}/runs/{run}/hostile2mk/jobs/{arm}__sparse-memory-t2000k-poison-retro-s{seed}/*/agent/timing.json")
    if not state or not timing:
        sys.exit(f"{run} {arm} seed {seed}: missing {'calls.jsonl' if not state else 'timing.json'}")
    calls = []
    for line in open(state[0]):
        try:
            calls.append(json.loads(line))
        except ValueError:
            pass                                   # a line cut by a stop
    main = sorted((c for c in calls if c["kind"] == "main"), key=lambda c: c["at"])
    notes = sorted(((c["at"], c["s"]) for c in calls if c["kind"] == "notes"))
    steps = [x for x in json.load(open(timing[0])) if "llm_s" in x]
    wall = main[-1]["at"] + main[-1]["s"] - main[0]["at"]
    main_s, notes_s = sum(c["s"] for c in main), sum(s for _, s in notes)
    llm_s, bash_s = sum(x["llm_s"] for x in steps), sum(x.get("bash_s", 0) for x in steps)
    starts = [a for a, _ in notes]
    gaps = []                                      # (index, gap) for gaps holding no notes call
    for i, (a, b) in enumerate(zip(main, main[1:])):
        end = a["at"] + a["s"]
        k, j = bisect.bisect_left(starts, end - 1), bisect.bisect_right(starts, b["at"])
        if j <= k:
            gaps.append((i, b["at"] - end))
    by_pos = []
    for lo in range(0, len(main), 250):
        w = [g for i, g in gaps if lo <= i < lo + 250]
        if w:
            by_pos.append({"calls": f"{lo}-{lo + 250}", "n": len(w), "mean": round(st.mean(w), 2), "median": round(st.median(w), 2)})
    return {"run": run, "arm": arm, "seed": seed, "main_calls": len(main), "notes_calls": len(notes), "steps": len(steps),
            "wall_s": round(wall), "main_s": round(main_s), "notes_s": round(notes_s), "bash_s": round(bash_s),
            "around_s": round(llm_s - main_s - notes_s), "between_s": round(wall - llm_s - bash_s),
            "gaps_without_notes": {"n": len(gaps), "sum_s": round(sum(g for _, g in gaps)), "by_position": by_pos}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", nargs="+", help="RUN ARM SEED triples")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    if len(a.spec) % 3:
        sys.exit("RUN ARM SEED triples")
    out = [budget(a.spec[i], a.spec[i + 1], int(a.spec[i + 2])) for i in range(0, len(a.spec), 3)]
    print("run   arm  seed  wall  main  notes  bash  around  between   gaps(no notes) sum   first/last 250 mean")
    for b in out:
        g = b["gaps_without_notes"]
        print(f"{b['run']:<5} {b['arm']:<4} {b['seed']:>4} {b['wall_s']:>5} {b['main_s']:>5} {b['notes_s']:>6} {b['bash_s']:>5} "
              f"{b['around_s']:>7} {b['between_s']:>8}   {g['n']:>5} calls {g['sum_s']:>5} s   "
              f"{g['by_position'][0]['mean']:.2f} / {g['by_position'][-1]['mean']:.2f}")
    if a.json:
        a.json.write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
