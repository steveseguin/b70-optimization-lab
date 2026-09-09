#!/usr/bin/env python3
"""Is *which* copy diverges reproducible across passes?

The copy-group analyser answers whether byte-identical copies in one batch disagree. This answers the
follow-up the 9B lane asked for and could not run: given that they disagree, is it the *same* copy
every time?

For each prompt and each pass, take the set of slots holding the minority completion, then ask how
often a prompt's most common such set recurs. Under a barrier launch the 4B reads 33.8%; with
`--launch-stagger-ms 25`, which makes arrival order a deterministic function of the slot index, it
reads 95.5%. So the run-to-run component is arrival jitter rather than device nondeterminism: fix the
schedule and the outcome is reproducible per slot.

Two cautions on reading the number.

The slot index here is the client-side expansion index. It maps to a server position only through
arrival order, which is why the barrier and staggered numbers differ so much - without a stagger the
mapping is re-drawn every pass, and a low recurrence says nothing about position dependence.

A stagger also makes the cohort ramp: the harness requires the admission window to exceed
`(concurrency - 1) * stagger`, so early tokens are generated in a small batch and later ones in a full
one. High recurrence therefore means "a reproducible composition history gives a reproducible branch",
not "row position alone decides the branch".

usage: analyze-slot-consistency.py ROOT [ROOT ...] [--lane ladder|ladder-mtp0|both] [--json OUT]
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
    per_prompt: dict[str, dict[int, frozenset]] = collections.defaultdict(dict)
    for b in d.get("batches", []):
        groups = collections.defaultdict(list)
        for r in b.get("rows", []):
            m = SUFFIX.match(r.get("prompt_id", ""))
            if m and r.get("token_ids"):
                groups[m.group(1)].append((int(m.group(2)), tuple(r["token_ids"])))
        for base, rows in groups.items():
            counts = collections.Counter(t for _, t in rows)
            if len(counts) < 2:
                continue
            modal = counts.most_common(1)[0][0]
            per_prompt[base][b["repeat"]] = frozenset(s for s, t in rows if t != modal)
    total = recurring = 0
    detail = []
    for base, passes in per_prompt.items():
        sets = list(passes.values())
        if len(sets) < 2:
            continue
        top, n = collections.Counter(sets).most_common(1)[0]
        total += len(sets)
        recurring += n
        detail.append({"prompt": base, "disagreeing_passes": len(sets),
                       "modal_minority_slots": sorted(top), "times_seen": n})
    detail.sort(key=lambda x: -x["times_seen"])
    return {"verbatim": True, "disagreeing_passes": total, "modal_set_recurrences": recurring,
            "recurrence_pct": round(100 * recurring / total, 2) if total else None,
            "prompts": detail}


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
                print(f"{root.name}/{lane}: not a verbatim run")
                continue
            report.setdefault(root.name, {})[lane] = res
            print(f"=== {root.name} / {lane} ===")
            print(f"  modal minority-slot-set recurs in {res['modal_set_recurrences']}/"
                  f"{res['disagreeing_passes']} disagreeing passes ({res['recurrence_pct']}%)")
            for e in res["prompts"][:6]:
                print(f"     {e['prompt']:<20} {e['times_seen']}/{e['disagreeing_passes']} passes"
                      f"  minority slots {e['modal_minority_slots']}")
    if out_path is not None:
        out_path.write_text(json.dumps(report, indent=1) + "\n")
        print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
