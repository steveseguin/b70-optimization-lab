#!/usr/bin/env python3
"""Operation-count simulation only. No real I/O, clocks, endpoints or model requests."""
import hashlib
import json
from pathlib import Path

import proposal as P
from test_proposal import Fake, function


def simulate():
    raw = P.SOURCE.read_bytes()
    changed = P.transform(raw)
    old, new = function(raw, 'checkpoint'), function(changed, 'checkpoint')
    traces = {'constant_free': [3000]*100,
              'free_decreases_every_checkpoint': list(range(2999,2899,-1)),
              'free_changes_every_eight_checkpoints': [3000-(i//8)*4 for i in range(100)],
              'free_increases_every_checkpoint': list(range(3001,3101))}
    rows = []
    for name, trace in traces.items():
        a, b = Fake(trace), Fake(trace)
        for _ in trace:
            old(a); new(b)
            assert a.state == b.state == b.durable
        rows.append({'scenario':name,'checkpoints':len(trace),
                     'old_save_state_calls':len(a.saved),'proposed_save_state_calls':len(b.saved),
                     'avoided_save_state_calls':len(a.saved)-len(b.saved),
                     'old_check_fixed_calls':a.events.count('check_fixed'),
                     'proposed_check_fixed_calls':b.events.count('check_fixed'),
                     'old_free_probe_calls':a.events.count('free_probe'),
                     'proposed_free_probe_calls':b.events.count('free_probe'),
                     'states_equal_after_every_checkpoint':True,
                     'final_charged_write_bytes':b.state['charged_write_bytes']})
    return {'schema':'ltx.client-ledger104.simulation.v1','source':str(P.SOURCE),
            'source_sha256':P.SOURCE_SHA256,'proposal_sha256':hashlib.sha256(changed).hexdigest(),
            'scope':'Synthetic free-space traces and mocked persistence only. Counts are not wall-time/model-speed predictions.',
            'rows':rows,'limitations':['Actual unchanged-free frequency has not been measured.',
            'Skipping writes can itself alter future observed free-space values; same exogenous traces prove accounting behavior, not identical live I/O traces.',
            'Per-event log flush/fsync and every source/process/fault check remain unchanged.']}


if __name__ == '__main__':
    print(json.dumps(simulate(),indent=2,sort_keys=True))
