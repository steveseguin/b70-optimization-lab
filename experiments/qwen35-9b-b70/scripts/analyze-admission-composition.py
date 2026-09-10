#!/usr/bin/env python3
"""Does a request diverge because the batch composition changed underneath it?

Every ladder row records when its request started, when its first token arrived and when it ended, so
the batch composition over any request's own decode window can be reconstructed from the file without
running anything. The hypothesis left standing after the offline probes says a request should only
diverge when other requests join or leave while it is decoding. That predicts a rate that climbs with
the number of such events inside the request's window and a rate at zero events that is itself zero.

Prompt identity is the confound that matters: these suites are deliberately built from prompts with
very different flip propensities, so the comparison is made within prompt as well as pooled.
"""
import argparse, collections, json, math, statistics


def load(path):
    d = json.load(open(path))
    oracle = {}
    for r in d["oracle"]["rows"]:
        oracle.setdefault(r["prompt_sha256"], tuple(r["token_ids"]))
    return d, oracle


def events_in_window(row, rows):
    """Count starts and ends of *other* requests inside this row's decode window."""
    lo, hi = row["first_text_epoch_s"], row["request_ended_epoch_s"]
    n = 0
    for o in rows:
        if o is row:
            continue
        if lo <= o["request_started_epoch_s"] <= hi:
            n += 1
        if lo <= o["request_ended_epoch_s"] <= hi:
            n += 1
    return n


def concurrent_at_start(row, rows):
    t = row["first_text_epoch_s"]
    return sum(1 for o in rows
               if o["request_started_epoch_s"] <= t <= o["request_ended_epoch_s"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ladder_json", nargs="+")
    args = ap.parse_args()

    for path in args.ladder_json:
        d, oracle = load(path)
        obs = []
        for b in d["batches"]:
            rows = b["rows"]
            if len(rows) < 2:
                continue
            for r in rows:
                ok = oracle.get(r["prompt_sha256"])
                if ok is None:
                    continue
                obs.append({
                    "prompt": r["prompt_sha256"][:12],
                    "diverged": tuple(r["token_ids"]) != ok,
                    "events": events_in_window(r, rows),
                    "conc": concurrent_at_start(r, rows),
                    "arrival_rank": sorted(
                        rows, key=lambda x: x["request_started_epoch_s"]).index(r),
                    "conc_level": b["concurrency"],
                })

        print(f"\n=== {path}")
        print(f"observations {len(obs)}  diverged {sum(o['diverged'] for o in obs)} "
              f"({100.0*sum(o['diverged'] for o in obs)/max(1,len(obs)):.2f}%)")

        # Pooled: divergence rate against composition events in the request's own window.
        buckets = collections.defaultdict(lambda: [0, 0])
        for o in obs:
            e = o["events"]
            key = 0 if e == 0 else (1 if e <= 2 else (2 if e <= 8 else 3))
            buckets[key][0] += o["diverged"]
            buckets[key][1] += 1
        names = {0: "0 events", 1: "1-2", 2: "3-8", 3: "9+"}
        print("  composition events inside the request's decode window:")
        for k in sorted(buckets):
            dv, n = buckets[k]
            print(f"    {names[k]:>9}: {dv:5d}/{n:5d} = {100.0*dv/n:6.2f}%")

        # Within-prompt, so prompt flip-propensity cannot manufacture the trend.
        print("  within-prompt rate at zero events vs any events:")
        tot = [[0, 0], [0, 0]]
        for p in sorted({o["prompt"] for o in obs}):
            sub = [o for o in obs if o["prompt"] == p]
            z = [o for o in sub if o["events"] == 0]
            a = [o for o in sub if o["events"] > 0]
            if not z or not a:
                continue
            zr = sum(o["diverged"] for o in z)
            ar = sum(o["diverged"] for o in a)
            tot[0][0] += zr; tot[0][1] += len(z)
            tot[1][0] += ar; tot[1][1] += len(a)
            print(f"    {p}: zero {zr:4d}/{len(z):4d}={100.0*zr/len(z):6.2f}%   "
                  f"any {ar:4d}/{len(a):4d}={100.0*ar/len(a):6.2f}%")
        if tot[0][1] and tot[1][1]:
            print(f"    {'pooled':12s} zero {tot[0][0]:4d}/{tot[0][1]:4d}="
                  f"{100.0*tot[0][0]/tot[0][1]:6.2f}%   "
                  f"any {tot[1][0]:4d}/{tot[1][1]:4d}={100.0*tot[1][0]/tot[1][1]:6.2f}%")

        # Arrival rank, the other admission-order prediction.
        by_rank = collections.defaultdict(lambda: [0, 0])
        for o in obs:
            q = min(3, o["arrival_rank"] * 4 // max(1, o["conc_level"]))
            by_rank[q][0] += o["diverged"]; by_rank[q][1] += 1
        print("  by arrival quartile (0 = admitted earliest):")
        for k in sorted(by_rank):
            dv, n = by_rank[k]
            print(f"    Q{k}: {dv:5d}/{n:5d} = {100.0*dv/n:6.2f}%")


if __name__ == "__main__":
    main()
