"""Compare arms by decode STEP TIME, not tok/s.

tok/s = tokens_per_step / step_time. Any arm that perturbs the model's
arithmetic also perturbs speculative acceptance, hence tokens_per_step, so a
tok/s delta conflates the structural change with an acceptance change. Each
verifier step is one draft cycle, so:

    tokens_per_step = completion_tokens / drafts
    step_time       = tokens_per_step / decode_tok_s
"""

import json
import sys


def load(path):
    with open(path) as handle:
        doc = json.load(handle)
    return {row["case_id"]: row for row in (doc.get("rows") or [])}


def stats(row):
    timing = row.get("timing") or {}
    spec = row.get("spec_decode") or {}
    rate = timing.get("conventional_99_interval_first_100_tok_s")
    drafts = spec.get("drafts") or 0
    completion = row.get("completion_tokens") or 0
    if not rate:
        return None
    per_step = completion / drafts if drafts else 1.0
    return rate, per_step, per_step / rate * 1e3, completion, drafts


def main():
    control, candidate, label = sys.argv[1], sys.argv[2], sys.argv[3]
    ctl, cand = load(control), load(candidate)
    header = f"{'case':<34}{'arm':>10}{'tok/s':>9}{'tok/step':>10}{'step ms':>9}{'gen':>6}"
    print(header)
    print("-" * len(header))
    for case, row in cand.items():
        a, b = stats(ctl.get(case, {})) if case in ctl else None, stats(row)
        if a:
            print(f"{case:<34}{'control':>10}{a[0]:>9.3f}{a[1]:>10.3f}{a[2]:>9.2f}{a[3]:>6}")
        if b:
            print(f"{'':<34}{label:>10}{b[0]:>9.3f}{b[1]:>10.3f}{b[2]:>9.2f}{b[3]:>6}")
        if a and b:
            print(f"{'':<34}{'delta':>10}{(b[0]-a[0])/a[0]*100:>8.1f}%"
                  f"{(b[1]-a[1])/a[1]*100:>9.1f}%{(b[2]-a[2])/a[2]*100:>8.1f}%")
        print()


if __name__ == "__main__":
    main()
