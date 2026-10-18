#!/usr/bin/env python3
"""Re-seal the narrow long-suite wrapper amendment from its immutable parent.

Historical model gates remain under their original sources; only the wrapper
regressions rerun here. No binary is executed by this seal procedure.
"""
import argparse, gzip, hashlib, json
from pathlib import Path
from seal_context import sha, require, source_map
from build import sources
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
E=P/'evidence/long-wrapper-20261013'
PARENT='e014530229d187802e850794ddc1231b8dfb39037425afb3016a195584156010'
CHANGED={'suite.py','window.py','context_window_gate.py','integration_inventory.py'}
ADDED={'test_suite_long.py','long_suite_cpu_gate.py','amend_long_suite.py'}

def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',action='store_true');a=ap.parse_args()
    parent_raw=gzip.decompress((E/'parent-build-receipt.json.gz').read_bytes())
    require(hashlib.sha256(parent_raw).hexdigest()==PARENT,'parent seal changed')
    receipt=json.loads(parent_raw);prefix=str(P.relative_to(ROOT))+'/'
    current=sources();allowed={prefix+n for n in CHANGED};added={prefix+n for n in ADDED}
    changed={n for n,h in receipt['sources'].items() if sha(ROOT/n)!=h}
    require(changed==allowed,'unexpected changed parent sources: '+str(changed^allowed))
    require(set(current)-set(receipt['sources'])==added,'unexpected added sources')
    for name,h in receipt['artifacts_sha256'].items():require(sha(P/'build'/name)==h,'compiled artifact changed '+name)
    require(sha(P/'build/input/input.json')==receipt['input_sha256'],'input changed')
    require(json.loads((P/'memory-plan.json').read_text())==receipt['memory_plan'],'memory plan changed')
    gate=json.loads((P/'long-suite-wrapper-gates.json').read_text())
    require(gate['passed'] and not gate['device_executed'] and not gate['real_model_executed'],'wrapper gate failed/scope')
    source_map(gate['source_sha256']);require(gate['checks']==131 and gate['mini_requests']==8 and gate['mini_tokens']==256,'wrapper coverage')
    require(len(gate['oracle_admissions'])==2 and all(r['tokens']==32 and r['fixtures']==384 for r in gate['oracle_admissions']),'oracle admission coverage')
    require(sha(E/'suite-mini-dry.json')==gate['dry_receipt_sha256'],'mini receipt changed')
    for row in gate['rows']:
        if 'archive' in row:
            raw=gzip.decompress((P/row['archive']).read_bytes())
            require(hashlib.sha256(raw).hexdigest()==row['raw_sha256'],'wrapper log changed')
    checker=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261012-long/suite_check.py'
    manifest=ROOT/'experiments/own-xpu-runtime/stage2/long-inputs-20261012/suite-manifest.json'
    require(sha(checker)==gate['checker_sha256'] and sha(manifest)==gate['manifest_sha256'],'long input/checker changed')
    receipt['sources'].update(current)
    receipt['sources'].update({str(f.relative_to(ROOT)):sha(f) for f in (checker,manifest)})
    source_map(receipt['sources'],ROOT)
    # Gate receipts recording past model execution are deliberately not repinned.
    for name in ('context-window-gates.json','window-mocked-inherited-tests.json','long-suite-wrapper-gates.json','suite-warmup-gates.json'):
        row=json.loads((P/name).read_text());require(row['passed'] and not row.get('device_executed'),'CPU gate failed '+name)
        receipt['gate_receipts'][name]=sha(P/name)
    for name,h in receipt['gate_receipts'].items():require(sha(P/name)==h,'gate changed '+name)
    old_cpu=gzip.decompress((E/'parent-cpu-tests.json.gz').read_bytes())
    require(hashlib.sha256(old_cpu).hexdigest()==receipt['cpu_tests_sha256'],'parent CPU summary changed')
    cpu=json.loads(old_cpu);cpu.update(gate_count=len(receipt['gate_receipts']),gates=receipt['gate_receipts'],
       wrapper_amendment='long-suite-wrapper-gates.json; historical model gate identities retained')
    write(P/'cpu-tests.json',cpu);receipt['cpu_tests_sha256']=sha(P/'cpu-tests.json')
    receipt['seal_status']='complete_under_coordinator_reduced_cpu_plan_plus_long_suite_wrapper_amendment'
    receipt['long_suite_wrapper_amendment']=dict(date='2026-10-13',parent_build_receipt_sha256=PARENT,
        parent_archive=str((E/'parent-build-receipt.json.gz').relative_to(P)),
        gate_sha256=sha(P/'long-suite-wrapper-gates.json'),suite_manifest_sha256=sha(manifest),checker_sha256=sha(checker),
        changed_sources=sorted(CHANGED),added_sources=sorted(ADDED),compiled_artifacts_unchanged=True,
        prerequisite_scope='Only WS/WSs with this exact long manifest may consume the parent seal K0/K1a/K1b/K2/W0p/KD receipts; every other prerequisite identity and child hash remains required.',
        historical_gate_scope='Original model/rollback gates were not rerun or repinned. Their exact source identities remain in their receipts and the archived parent seal.',
        midprompt_scope='Oracle admission includes validation.json midprompt hashes. Missing actual midprompt bytes are disclosed; retained records must compare.')
    if a.candidate:
        receipt.pop('window_seal_admission_sha256',None)
        write(P/'build-admission-candidate.json',receipt);print('Wrapper candidate sealed; admission rehearsal required');return
    admission=json.loads((P/'window-seal-admission-gates.json').read_text())
    require(admission['passed'] and not admission['device_executed'],'admission failed')
    source_map(admission['source_sha256'])
    consumed={n:receipt[n] for n in admission['seal_fields']}
    require(hashlib.sha256(json.dumps(consumed,sort_keys=True).encode()).hexdigest()==admission['consumed_seal_sha256'],'admission stale')
    require(len(admission['rows'])==20 and all(r['admission_reached_blocked_launcher'] and not r['device_executed'] and not r['window_passed'] for r in admission['rows']),'admission coverage')
    receipt['window_seal_admission_sha256']=sha(P/'window-seal-admission-gates.json')
    write(P/'build-receipt.json',receipt)
    print('SEALED wrapper amendment:',sha(P/'build-receipt.json'))
if __name__=='__main__':main()
