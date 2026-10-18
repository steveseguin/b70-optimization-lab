"""Seal diagnostic scope without fabricating byte equality for changed-output arms."""
import json
import os
from pathlib import Path
from build_engine import P, ROOT, B, sha, save, limits
from policy import VIEWS, NONEXACT, selection, labels

def main():
    limits()
    from run_screen import verify_dependencies, view_path
    verify_dependencies()
    from placement import admission_gate
    memory=admission_gate(P)[1];ledger=json.loads((P/'memory-plan.json').read_text())
    build=json.loads((P/'build-device-receipt.json').read_text())
    cpu=json.loads((P/'evidence/cpu-gates.json').read_text())
    full=json.loads((P/'evidence/fullshape.json').read_text())
    op=json.loads((P/'evidence/operators.json').read_text())
    for row in (build,cpu,full,op):assert row['passed'] and not row['device_executed']
    assert cpu['build_receipt_sha256']==sha(P/'build-device-receipt.json')
    assert len(full['results'])==2*len(VIEWS)
    admissions=[]
    for row in full['results']:
        census=json.loads((ROOT/row['census']).read_text())
        admissions.append(dict(view=row['choice'],rank=row['result']['rank'],result=memory.check(census,ledger,row['result']['rank'],mtp=True,context=4096,draft_rank=1,target_split=0)))
    save(P/'evidence/fullshape-admission.json',dict(passed=True,device_executed=False,admissions=admissions))
    sources={**build['sources'],**cpu['sources'],**full['sources'],**op['sources'],**json.loads((P/'dependency-pins.json').read_text())}
    for f in [*P.glob('*.py'),*(P/'evidence').glob('*.json'),P/'evidence/python-tests.log']:
        if f.name not in ('screen-plans.json','queue-plans.json','final-check.json') and not f.name.endswith('-plan.json'):
            sources[str(f.relative_to(ROOT))]=sha(f)
    for n,h in sources.items():assert sha(ROOT/n)==h, n
    for view in VIEWS:
        d=view_path(view);d.mkdir(parents=True,exist_ok=True)
        assert not (d/'screen-seal.json').exists(),'never replace sealed views'
        save(d/'selection.json',selection(view))
        for n in ('dispatch-speed6.json','memory-plan.json'):(d/n).write_bytes((P/n).read_bytes())
        binary=d/'build/device/own-rt-iq3';binary.parent.mkdir(parents=True,exist_ok=True);os.link(B/'device/own-rt-iq3',binary)
        audit=dict(placement='1',draft_rank=1,target_split=0,layer_boundary=24,target_layers=[24,24],binary_sha256=sha(binary),dispatch_sha256=sha(d/'dispatch-speed6.json'),
                   engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','rank.hpp','mtp.hpp','p49d_submit.cpp','p49d_expert_submit.cpp','p60_submit.cpp','p86_expert.hpp','p86_hc.hpp','attribution.hpp')},**labels(view))
        save(d/'placement-audit.json',audit)
        plan=dict(schema='packet86.diagnostic-plan.v1',**labels(view),lanes=['A','B'],placement='1',timing='attribution',model_lifetimes=1,
                  arms=['control','attribution'],requests=25,token_counts=[64]+[128]*24,forced_token_count=True,sample_generated_indices=[9,16],
                  byte_identity_gate='SKIPPED: intentionally non-exact' if view in NONEXACT else 'production and loadkeep exact CPU gates required',
                  expected_output_mismatch_is_device_fault=False,safety_checks='unchanged shared v4',watchdog_seconds=3600,
                  estimated_work_seconds=420,device_measurements='pending')
        save(d/'diagnostic-plan.json',plan)
        local=dict(sources)
        for f in (d/'selection.json',d/'memory-plan.json',d/'dispatch-speed6.json',d/'placement-audit.json',d/'diagnostic-plan.json'):local[str(f.relative_to(ROOT))]=sha(f)
        bp=d/'build-receipt.json';gate=d/'diagnostic-gate.json'
        artifacts={'build/device/own-rt-iq3':sha(binary)}
        save(bp,dict(passed=True,device_executed=False,sources=local,artifacts=artifacts,**labels(view)))
        save(gate,dict(passed=True,device_executed=False,build_receipt_sha256=sha(bp),**labels(view),
                       gate='startup/allocation/admission/scope; output identity skipped for nonexact views',
                       production_cpu_evidence_sha256=sha(P/'evidence/cpu-gates.json'),operator_evidence_sha256=sha(P/'evidence/operators.json')))
        # Shared sealed() validates generic source/artifact/gate hashes and real
        # placement admission. No fake byte-fixture is presented to generic create().
        fixture_files={'diagnostic-plan.json':sha(d/'diagnostic-plan.json')}
        if view not in NONEXACT:
            assert sha(P/'evidence/fixture-expected.bin')==sha(P/'evidence/fixture-actual.bin')
            for kind in ('expected','actual'):
                name='fixture-'+kind+'.bin';os.link(P/'evidence'/name,d/name);fixture_files[name]=sha(d/name)
        save(d/'screen-seal.json',dict(schema='own-runtime.screen.cpu-seal.v1',passed=True,device_executed=False,
             arithmetic='iq3-p49-split32-v1',arithmetic_role='ancestry only; ablations are non-exact',profile='tp2',timing_modes=['attribution'],
             sources=local,artifacts=artifacts,gates={'build-receipt.json':sha(bp),'diagnostic-gate.json':sha(gate)},
             fixture_files=fixture_files,qualification='NEVER bundle/chain/submission/headline',**labels(view)))
        print(view,'diagnostic seal PASS',flush=True)
if __name__=='__main__':main()
