#!/usr/bin/env python3
"""Rejoin retained recursive guesses on equal observable cohorts; no speed forecast."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[1]/'engine'
sys.path.insert(0, str(ENGINE/'tools'))
from analyze_draft_depth import analyze


def read(path, pins):
    raw = path.read_bytes()
    pins[str(path)] = hashlib.sha256(raw).hexdigest()
    return raw


def main():
    root = HERE.parent/'review-2026-10-25/depth-suite-a'
    pins, result = {}, []
    for folder in sorted(root.iterdir()):
        if not (folder/'rank0/native-result.json').is_file():
            continue
        prompt = json.loads(read(folder/'prompt-token-ids.json', pins))
        native = json.loads(read(folder/'rank0/native-result.json', pins))
        probes = [json.loads(line) for line in read(folder/'rank0/draft-depth-probe-final.jsonl', pins).splitlines()]
        analyze(prompt, native, probes, require_verified=True)
        full = prompt + native['tokens']
        cohorts = {}
        for depth in (2, 3):
            buckets = [0]*(depth+1)
            censored = 0
            for row in probes:
                position = row['d1_position']
                assert len(row['guesses']) >= depth
                if position+depth > len(full):
                    censored += 1
                    continue
                hits = 0
                for offset in range(depth):
                    if row['guesses'][offset] != full[position+offset]:
                        break
                    hits += 1
                buckets[hits] += 1
            count = sum(buckets)
            cohorts[str(depth)] = dict(observable=count, end_censored=censored,
                exact_prefix_length_counts=buckets,
                complete_prefix_counts=[sum(buckets[d:]) for d in range(1, depth+1)])
        result.append(dict(id=folder.name, cohorts=cohorts))
    assert len(result) == 12
    pooled = {}
    for depth in (2, 3):
        rows = [r['cohorts'][str(depth)] for r in result]
        buckets = [sum(r['exact_prefix_length_counts'][d] for r in rows) for d in range(depth+1)]
        count = sum(buckets)
        pooled[str(depth)] = dict(observable=count, end_censored=sum(r['end_censored'] for r in rows),
            exact_prefix_length_counts=buckets,
            exact_prefix_length_fractions=[v/count for v in buckets],
            complete_prefix_counts=[sum(buckets[d:]) for d in range(1, depth+1)],
            mean_correct_recursive_prefix=sum(d*v for d,v in enumerate(buckets))/count)
    output = dict(schema='ownrt.recursive-common-cohort.v1', passed=True,
        diagnostic_only=True, speed_claim=False, training=False,
        definition='Retained true-prefix-seeded recursive probes, joined on all positions observable at each chosen depth. Bucket d counts exactly d correct consecutive guesses before the first miss; final bucket means every guess matches. These are not realized acceptance rates of a rolling scheduler.',
        inputs=pins, prompts=result, pooled=pooled)
    (HERE/'recursive-common-cohort.json').write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps(pooled, indent=2))


if __name__ == '__main__':
    main()
