#!/usr/bin/env python3
"""Prepare four kernel choices; each will have two immutable placement views."""
import copy
import json
from pathlib import Path
from build_engine import sha, save
P = Path(__file__).resolve().parent
CHOICES = ('production-control', 'production-batch', 'draft-hc-control', 'draft-hc-batch')

def configs():
    candidate = json.loads((P.parent / 'packet63-balance/selections/draft-hc/selection.json').read_text())
    result = {}
    for draft in ('production', 'draft-hc'):
        for miss in ('control', 'batch'):
            row = copy.deepcopy(candidate)
            if draft == 'production':
                row['draft'] = {key:'production' for key in row['draft']}
            row['choices']['miss'] = miss
            result[draft + '-' + miss] = row
    return result

def main():
    for name, row in configs().items():
        dest = P / 'selections' / name
        dest.mkdir(parents=True, exist_ok=False)
        save(dest / 'selection.json', row)
        for leaf in ('selection-decision.json', 'memory-plan.json', 'dispatch-speed6.json'):
            (dest / leaf).write_bytes((P / leaf).read_bytes())

if __name__ == '__main__': main()
