"""Fail closed until the exact diagnostic device micro completed and drained."""
import json
from build_engine import P, ROOT, sha, check_map
MICRO=P
def require_micro(suffix):
    assert suffix in (81920,122880)
    build=json.loads((MICRO/'evidence/microbench-build.json').read_text())
    check_map(ROOT,build['sources']);check_map(MICRO,build['artifacts'])
    root=MICRO/('evidence/micro-B-'+str(suffix))
    row=json.loads((root/'window.json').read_text())
    assert row['passed'] and row['device_executed'] and row['drained'] and row['lease_released']
    assert not row.get('child_still_running') and not row.get('child_retained') and not row['stop_reasons']
    assert row['identity']['build_receipt_sha256']==sha(MICRO/'evidence/microbench-build.json')
    assert row['identity']['binary_sha256']==sha(MICRO/'build/microbench')
    assert row['samples_sha256']==sha(root/'samples.jsonl')
    assert row['device_isolation']['passed'] and row['lane']=='B'
    coordination=json.loads((root/'lane-coordination.json').read_text())
    assert coordination['passed'] and coordination['released_before_report']
    result=json.loads((root/'samples.jsonl').read_text().splitlines()[-1])
    assert result==row['native_summary'] and result['kind']=='summary' and result['passed'] and result['drained']
    assert result['suffix_rows']==suffix
    assert result['cases']==4096 and result['mismatches']==0 and result['suffix_winners']>=2000
    assert (result['ties'],result['nonfinite'],result['resets'],result['negative_control_mismatches'])==(256,768,256,1)
    return dict(passed=True,path=str(root),window_sha256=sha(root/'window.json'))
