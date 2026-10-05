#!/usr/bin/env python3
"""Calibration table for calibrate-reading.sh (also usable offline on a saved log).

  calib_table.py CALIBRATION_LOG

Reads the probe's --sweep summary lines (`<dir>/<task>\\tsetting=..\\tdensity=..\\tthinking=..\\tvariant=..\\t
changed_right=R/N (..%)\\tfull_table=..%\\t...`), prints one row per density x setting x variant, then pooled
rows per density and variant over the single-feature settings (plain, words, pronouns, corrections,
plans) with the per-change error rate and a 95 % Wilson interval, and finally the hardest setting that
passes (changed-counter accuracy >= 98 % and full-table accuracy >= 99.5 %) as SPARSE_ARGS.

Bug fixed 2026-10-05: the old inline printer required a "/" before "d<density>-", but the probe prints
the task's parent folder name first ("d3-words/sparse-memory-b12-s0"), so no row ever matched.
"""
from __future__ import annotations

import math
import re
import sys

ROW = re.compile(r"(?:^|/)d([\d.]+)-(\w+)/\S+\tsetting=\S+\tdensity=\S+\tthinking=(\w+)\tvariant=(\w+)\t"
                 r"changed_right=(\d+)/(\d+) \([\d.]+%\)\tfull_table=([\d.]+)%\tperfect_batches=(\d+)/(\d+)\t"
                 r"wrong_extra=(\d+)\tparseable=(\d+)/(\d+)")
ORDER = {"plain": 0, "words": 1, "pronouns": 2, "corrections": 3, "plans": 4, "relative": 5, "all": 6}
SINGLE = ("plain", "words", "pronouns", "corrections", "plans")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def main() -> None:
    rows = {}
    for ln in open(sys.argv[1]):
        if ln.startswith("#"):
            continue
        m = ROW.search(ln)
        if m:
            d, s, th, v, r, n, full, pb, nb, extra, pa, calls = m.groups()
            rows[(float(d), s, th, v)] = (int(r), int(n), float(full), int(pb), int(nb), int(extra), int(pa), int(calls))
    print("# calibration table")
    print("density\tsetting\tthinking\tvariant\tchanged_right\tchanged%\tfull_table%\tperfect_batches\twrong_extra"
          "\tparseable\tpass(>=98 and >=99.5)")
    for k in sorted(rows, key=lambda k: (k[0], ORDER.get(k[1], 9), k[2], k[3])):
        r, n, full, pb, nb, extra, pa, calls = rows[k]
        acc = 100 * r / n if n else float("nan")
        ok = acc >= 98 and full >= 99.5
        print(f"{k[0]:g}\t{k[1]}\t{k[2]}\t{k[3]}\t{r}/{n}\t{acc:.1f}\t{full:.2f}\t{pb}/{nb}\t{extra}\t{pa}/{calls}\t"
              f"{'PASS' if ok else '-'}")
    print("\n# pooled over the single-feature settings (plain, words, pronouns, corrections, plans):"
          " per-change error rate, 95 % Wilson interval")
    print("density\tthinking\tvariant\twrong/changes\terror%\t95% interval\twrong_extra\tunparseable_replies")
    for d in sorted({k[0] for k in rows}):
        for th in sorted({k[2] for k in rows}):
            for v in sorted({k[3] for k in rows}):
                ks = [k for k in rows if k[0] == d and k[2] == th and k[3] == v and k[1] in SINGLE]
                if not ks:
                    continue
                r = sum(rows[k][0] for k in ks); n = sum(rows[k][1] for k in ks)
                extra = sum(rows[k][5] for k in ks); unp = sum(rows[k][7] - rows[k][6] for k in ks)
                lo, hi = wilson(n - r, n)
                print(f"{d:g}\t{th}\t{v}\t{n - r}/{n}\t{100 * (n - r) / n:.1f}\t{100 * lo:.1f}-{100 * hi:.1f}\t{extra}\t{unp}")
    ok = [k for k in rows if rows[k][1] and 100 * rows[k][0] / rows[k][1] >= 98 and rows[k][2] >= 99.5]
    if ok:
        best = max(ok, key=lambda k: (ORDER.get(k[1], 0), k[0], k[3] == "plain"))
        flag = "" if best[1] == "plain" else f" --{best[1]}"
        print(f"\n# hardest passing setting: density {best[0]:g}, {best[1]}, variant {best[3]} "
              f"(one cell of {rows[best][1]} changes: check the pooled rate above before trusting it)")
        print(f'SPARSE_ARGS="--density {best[0]:g}{flag}" READ_REASONS={1 if best[3] == "reason" else 0}')
    else:
        print("\n# no setting passed: do not start the long run; make the steps easier")


if __name__ == "__main__":
    main()
