#!/usr/bin/env python3
"""Only the two GNU draft references required by the coordinator windows."""
import json
import capacity_draft_gate as cd
from draft_baseline import load,ORACLE

def main():
    table,inp=cd.prepare();baseline=load();baseline_hash=cd.sha(ORACLE);rows=[];sealed={}
    assert inp['source_capture_receipt_sha256']==baseline['source_receipts']['capture-input-'+cd.NAME+'.json']['sha256']
    for context in (4096,32768):
        output,run=cd.run_arm('gnu-host',context,table)
        valid={k:v for k,v in run['fixture_sha256'].items() if k.startswith('row-')}
        assert valid==baseline['valid_fixture_sha256']
        sealed[str(context)]=run['fixture_sha256']
        row=dict(passed=True,context=context,compiler='gnu-host',fixture_matches=len(sealed[str(context)]),
            baseline_fixture_matches=len(valid),baseline_oracle_sha256=baseline_hash,binary_sha256=run['binary_sha256'])
        cd.save(cd.P/f'draft-capacity-c{context}-comparison.json',row);rows.append(row)
    receipt=dict(passed=True,device_executed=False,scope='coordinator-required GNU KD references only; full six-arm draft matrix not run',
        arms=2,contexts=[4096,32768],generated_prefix_tokens=8,capture_rows=inp['capture_rows'],
        baseline_oracle_sha256=baseline_hash,baseline_compared_arms=2,baseline_fixture_files_per_arm=len(baseline['valid_fixture_sha256']),
        rows=rows,draft_capture_fixture_sha256_by_context=sealed,
        draft_capture_input_sha256={cd.NAME:cd.sha(cd.P/('capture-input-'+cd.NAME+'.json'))},
        retained_reference_bytes=sum(cd.build_size(cd.B/f'draft-reference-c{c}') for c in (4096,32768)))
    assert receipt['retained_reference_bytes']<300_000_000
    cd.save(cd.P/'capacity-draft-gates.json',receipt)
    print('PASS two coordinator KD host references',flush=True)
if __name__=='__main__':main()
