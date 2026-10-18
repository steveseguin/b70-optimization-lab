#!/usr/bin/env python3
"""Read frozen 58k with its own import namespace; never write its evidence."""
import json
from pathlib import Path
import sys

P = Path(__file__).resolve().parent
K = P.parent/'packet58k-onecard-screen'
sys.path.insert(0, str(K))
import compare_screen as C
import queue_runner as Q


def main():
    C.W.build_gate()
    rows, pins, boots = [], {}, []
    for name, view in Q.STAGES:
        row, sources, boot = C.verify_arm(Q.ROOT/name, view)
        requests = row['requests']
        C.W.require(len(requests) == 12 and all(r.get('passed') is True and r.get('exact_oracle') is True
                    and len(r['tokens']) == 128 for r in requests), '12/12 exact screen required')
        rows.append(row)
        pins.update(sources)
        boots.append(boot)
    C.W.require(len(set(boots)) == 1, 'screen boot changed')
    C.W.require(len({tuple(x) for r in rows for x in r['owners']}) == 9, 'screen owners reused')
    decision = C.decision(rows)
    print(json.dumps(dict(passed=True, device_executed=False, rows=rows, sources=pins,
                         boot_id=boots[0], inherited_decision=decision,
                         screen_build_sha256=C.D.sha(K/'build-receipt.json'),
                         screen_selection_sha256=C.digest('port'),
                         screen_native_artifacts={n:h for n,h in C.D.read(K/'build-receipt.json')['artifacts'].items()
                                                  if n.startswith('build/device/')})))


if __name__ == '__main__':
    main()
