#!/usr/bin/env python3
"""Do byte-identical copies of one prompt, in the same batch, return the same completion?

A verbatim ladder (`--verbatim-prompts`) fills several slots with the same text, ids differing only by
a `-sNNN` suffix. Those copies share a batch, a set of decode steps and a set of neighbours, so if
they disagree, the branch a request takes is decided by neither the prompt nor the batch shape nor the
batch composition. That is a much sharper statement than any oracle comparison can make, and it is
what rules out an intervention like the determinism pad, whose whole mechanism is fixing the row count.

On the 9B fragile campaigns this reports 429 of 1920 copy-groups disagreeing, with a distinct-output
histogram of exactly {1, 2} - a third branch was never seen in 429 opportunities.

The `-sNNN` index is a client-side expansion index, not a server-side batch row: requests are launched
through a thread barrier, so arrival order and row assignment vary per pass. Which slot ends up in the
minority therefore says nothing about row position, and the per-slot table below is printed for
completeness rather than as evidence.

usage: analyze-copy-groups.py ROOT [ROOT ...] [--lane ladder|ladder-mtp0|both] [--json OUT]
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

SUFFIX = re.compile(r"(.+)-s(\d+)$")


def analyse(root: Path, lane: str):
    p = root / lane / "ladder.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    ids = [r["prompt_id"] for r in (d.get("oracle") or {}).get("rows", [])]
    if not ids or not SUFFIX.match(ids[0]):
        return {"verbatim": False}
    groups = total = split = 0
    hist = collections.Counter()
    minority_slots = collections.Counter()
    per_rung = collections.defaultdict(lambda: [0, 0])
    examples = []
    for b in d.get("batches", []):
        by_base = collections.defaultdict(list)
        for r in b.get("rows", []):
            m = SUFFIX.match(r.get("prompt_id", ""))
            if m and r.get("token_ids"):
                by_base[m.group(1)].append((int(m.group(2)), tuple(r["token_ids"])))
        for base, g in by_base.items():
            if len(g) < 2:
                continue
            groups += 1
            counts = collections.Counter(t for _, t in g)
            hist[len(counts)] += 1
            per_rung[b["concurrency"]][1] += 1
            if len(counts) > 1:
                split += 1
                per_rung[b["concurrency"]][0] += 1
                modal = counts.most_common(1)[0][0]
                mino = sorted(s for s, t in g if t != modal)
                for s in mino:
                    minority_slots[s] += 1
                if len(examples) < 8:
                    examples.append({"concurrency": b["concurrency"], "pass": b["repeat"], "prompt": base,
                                     "copies": len(g), "distinct": len(counts), "minority_slots": mino})
    total = groups
    return {
        "verbatim": True, "copy_groups": total, "disagreeing": split,
        "pct": round(100 * split / total, 2) if total else None,
        "distinct_output_histogram": dict(sorted(hist.items())),
        "per_rung": {c: {"disagreeing": v[0], "groups": v[1]} for c, v in sorted(per_rung.items())},
        "minority_slot_counts": dict(minority_slots.most_common(12)),
        "examples": examples,
    }


def main() -> int:
    argv = sys.argv[1:]
    lanes, out_path, roots = ["ladder", "ladder-mtp0"], None, []
    i = 0
    while i < len(argv):
        if argv[i] == "--lane":
            lanes = ["ladder", "ladder-mtp0"] if argv[i + 1] == "both" else [argv[i + 1]]; i += 2
        elif argv[i] == "--json":
            out_path = Path(argv[i + 1]); i += 2
        else:
            roots.append(Path(argv[i])); i += 1
    if not roots:
        print(__doc__)
        return 2
    report = {}
    for root in roots:
        for lane in lanes:
            res = analyse(root, lane)
            if res is None:
                continue
            if not res["verbatim"]:
                print(f"{root.name}/{lane}: not a verbatim run, no copy groups")
                continue
            report.setdefault(root.name, {})[lane] = res
            print(f"=== {root.name} / {lane} ===")
            print(f"  {res['disagreeing']}/{res['copy_groups']} copy-groups disagree ({res['pct']}%)")
            print(f"  distinct outputs per group: {res['distinct_output_histogram']}"
                  f"{'   <- a third branch never appears' if set(res['distinct_output_histogram']) <= {1, 2} else ''}")
            for c, v in res["per_rung"].items():
                print(f"     c{c}: {v['disagreeing']}/{v['groups']}")
    if out_path is not None:
        out_path.write_text(json.dumps(report, indent=1) + "\n")
        print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
