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
    """Validate existing packet70 views without changing selections or artifacts."""
    from bundle_selection import EXPERTS
    from prepare_packet import PRESET, read, check
    from chain_seal import check_map
    original = read(PRESET/'selection.json')
    for expert in EXPERTS:
        view = P/'selections'/('1-draft-hc-batch-'+expert)
        expected = copy.deepcopy(original)
        expected['choices']['experts'] = expert
        assert read(view/'selection.json') == expected, 'selection bytes/config changed'
        for name in ('memory-plan.json', 'dispatch-speed6.json'):
            assert (view/name).read_bytes() == (PRESET/name).read_bytes(), name
        seal = read(view/'screen-seal.json')
        check_map(P.parents[3], seal['sources'])
        for key in ('artifacts', 'gates', 'fixture_files'):
            check_map(view, seal[key])
    print('PASS: five unchanged packet70 selection views; no device execution')

if __name__ == '__main__': main()
