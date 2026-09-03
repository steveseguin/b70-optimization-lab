#!/usr/bin/env python3
"""Compare repeatability-trace captures record by record.

Given a run directory holding ``gdn-trace-rank{r}.{i}.json`` files (one per
rank and capture), report for every rank the first label whose tensor digests
differ between captures, plus a per-label equality table across captures.
Also compares ranks pairwise for the same capture, which separates a local
(per-rank) difference from one introduced by a collective.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path: Path) -> list[tuple[str, dict[str, str]]]:
    data = json.loads(path.read_text())
    out = []
    for rec in data["records"]:
        digests = {
            name: (t["sha256"] if t is not None else "none")
            for name, t in rec["tensors"].items()
        }
        out.append((rec["label"], digests))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--prefix", default="gdn-trace-rank")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    files = sorted(args.run_dir.glob(f"{args.prefix}*.json"))
    captures: dict[int, dict[int, list]] = {}
    for f in files:
        stem = f.name[len(args.prefix) : -len(".json")]
        rank_s, _, idx_s = stem.partition(".")
        rank = int(rank_s)
        idx = int(idx_s) if idx_s else 0
        captures.setdefault(rank, {})[idx] = load(f)
    if not captures:
        print("no trace files", file=sys.stderr)
        return 2

    report: dict[str, object] = {"ranks": {}, "cross_rank": {}}
    for rank in sorted(captures):
        caps = captures[rank]
        idxs = sorted(caps)
        base = caps[idxs[0]]
        labels = [label for label, _ in base]
        first_diff = None
        table = []
        for pos, (label, digests) in enumerate(base):
            same = True
            for j in idxs[1:]:
                other = caps[j]
                if pos >= len(other) or other[pos][0] != label:
                    same = False
                    break
                if other[pos][1] != digests:
                    same = False
            table.append((label, same))
            if not same and first_diff is None:
                first_diff = label
                diff_tensors = sorted(
                    n
                    for n, d in digests.items()
                    if any(
                        pos < len(caps[j]) and caps[j][pos][1].get(n) != d
                        for j in idxs[1:]
                    )
                )
        n_same = sum(1 for _, s in table if s)
        print(
            f"rank {rank}: captures={idxs} records={len(labels)} "
            f"identical={n_same} first_diff={first_diff}"
            + (f" tensors={diff_tensors}" if first_diff else "")
        )
        report["ranks"][str(rank)] = {  # type: ignore[index]
            "captures": idxs,
            "records": len(labels),
            "identical_records": n_same,
            "first_differing_label": first_diff,
            "first_differing_tensors": diff_tensors if first_diff else [],
            "table": [{"label": l, "identical": s} for l, s in table],
        }
        # Show the neighbourhood of the first difference.
        if first_diff is not None:
            pos = labels.index(first_diff)
            for l, s in table[max(0, pos - 3) : pos + 4]:
                print(f"    {'same' if s else 'DIFF'}  {l}")

    ranks = sorted(captures)
    if len(ranks) > 1:
        for idx in sorted(captures[ranks[0]]):
            rows = []
            base = captures[ranks[0]][idx]
            for pos, (label, digests) in enumerate(base):
                agree = all(
                    idx in captures[r]
                    and pos < len(captures[r][idx])
                    and captures[r][idx][pos][1] == digests
                    for r in ranks[1:]
                )
                rows.append((label, agree))
            first = next((l for l, a in rows if not a), None)
            print(f"capture {idx}: ranks agree on {sum(a for _, a in rows)}/{len(rows)} records; first rank-divergent label={first}")
            report["cross_rank"][str(idx)] = {"first_rank_divergent_label": first}  # type: ignore[index]

    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
