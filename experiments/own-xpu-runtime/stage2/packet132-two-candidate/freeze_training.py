#!/usr/bin/env python3
"""Freeze training choices before reading held-out confidence rows."""
import hashlib
import json
import os
from pathlib import Path
import resource
from datetime import datetime, timezone
from analyze import P, costs, metrics, policies


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    resource.setrlimit(resource.RLIMIT_AS, (512_000_000, 512_000_000))
    rows, sources = [], {}
    for i in range(3):
        root = P/f'build/capture/doc-{i}'
        target = json.loads((root/'target/result.json').read_text())
        receipt = json.loads((root/'draft-receipt.json').read_text())
        raw = (root/'draft-rows.jsonl').read_bytes()
        records = [json.loads(line) for line in raw.splitlines()]
        assert target['status'] in ('token-cap', 'eos') and target['error'] == ''
        assert target['device_executed'] is False
        assert [r['target_token'] for r in records] == target['tokens']
        assert len(records) == receipt['count']
        assert target['status'] == 'eos' or len(records) == 24
        assert all(r['source_index'] == i+1 and r['draft_prefix_rows'] == 80128 for r in records)
        rows.extend(records)
        sources[str(i+1)] = hashlib.sha256(raw).hexdigest()
    decisions = []
    for scenario in costs()[1]:
        candidates = [dict(policy=p, train=metrics(rows, p, scenario)) for p in policies()]
        selected = min(candidates, key=lambda r: (r['train']['delta_ms'], r['train']['flags']))
        decisions.append(dict(scenario=scenario['name'], **selected))
    result = dict(recorded_utc=datetime.now(timezone.utc).isoformat(), sources=sources,
                  positions=len(rows), heldout_confidence_rows_read=False, decisions=decisions)
    with (P/'evidence/training-selection.json').open('x') as out:
        json.dump(result, out, indent=2, allow_nan=False)
        out.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
