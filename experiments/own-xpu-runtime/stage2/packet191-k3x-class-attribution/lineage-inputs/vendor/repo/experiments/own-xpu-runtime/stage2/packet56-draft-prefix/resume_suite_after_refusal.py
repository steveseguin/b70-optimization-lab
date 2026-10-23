#!/usr/bin/env python3
"""One reviewed continuation after the no-launch dispatch preflight refusal."""
import json, os
from cpu_campaign import P, B, PY, execute
from storage import digest

def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert os.environ.get('OMP_NUM_THREADS') == '2'
    refusal = json.loads((P/'suite-preflight-refusal.json').read_text())
    assert refusal['ranks_launched'] is False and refusal['device_executed'] is False
    rows = []
    for stage in ('resume-suite', 'resume-fixtures', 'resume-models',
                  'resume-captures', 'resume-real-intel'):
        row = json.loads((B/(stage+'-status.json')).read_text())
        assert row['returncode'] == 0 and row['device_executed'] is False, stage
        rows.append(row)
    rows.append(execute('resume-suite-corrected', [PY, '-B', P/'cpu_campaign.py', 'suite']))
    result = dict(passed=True, device_executed=False, rows=rows,
                  retained_refusal_sha256=digest(P/'suite-preflight-refusal.json'),
                  continuation='Reviewed correction to preflight dispatch identity; one launch, no automatic retry')
    (P/'resume-sequence-after-mini.json').write_text(json.dumps(result, indent=2)+'\n')

if __name__ == '__main__':
    main()
