import json,sys,shutil,resource
from pathlib import Path
O=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/ops/packet124c-orchestration')
sys.path.insert(0,str(O))
from source_decision import ROOT,P,sha,save
from composite_jobs import current,validate
from orchestrate import verify_tests
from drain_check import check
from chain_adapter import install

def main():
    _,config=current();validate(config);install()
    from chain_seal import verify
    sealed=verify();tests=verify_tests();drain=check()
    from argument_gate import verify as verify_arguments
    arguments=verify_arguments()
    assert len(arguments['windows'])==11 and sum(len(r['argv']) for r in arguments['windows'])==31
    assert arguments['queue']['queue_run_executed'] and len(arguments['queue']['oracle_checks'])==6
    assert arguments['old_packet124b_oracle']['expected_refusal'] and arguments['real_oracle']['ready']
    startup=json.loads((P/'startup103.json').read_text())
    shape=json.loads((P/'evidence/full-shape.json').read_text())
    limits=json.loads((O/'evidence/launch-limits.json').read_text())
    byte=json.loads((P/'evidence/cpu-byte-identity.json').read_text())
    assert len(byte['views'])==1
    runs=next(iter(byte['views'].values()))['runs'];assert len(runs)==4
    assert all(r['candidate_sha256']==r['expected_sha256']==r['packet118_output_sha256'] for r in runs)
    assert startup['total_windows']==11
    assert len(shape['runs'])==2 and all(r['passed'] for r in shape['runs'])
    assert limits['passed'] and len(limits['cases'])==4
    assert sum(len(c.get('observations',[])) for c in limits['cases'])==6
    build=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file() and not f.is_symlink())
    free=shutil.disk_usage('/').free;assert build<=250_000_000 and free>=25_000_000_000
    forbidden=('packet118-record-bundle/build-receipt.json','packet118-record-bundle/bundle-selection.json','packet118-record-bundle/selection.json','packet118-orchestration/ready.json','packet118-record-bundle/build/device-cards01-')
    assert not any(any(part in n for part in forbidden) for n in sealed['sources'])
    assert not (P/'build/device-cards01-a').exists()
    from verify_ready import evaluate
    ready=evaluate();save(O/'ready.json',ready);assert ready['ready'],ready.get('reason')
    sizes=[dict(path=str(f.relative_to(ROOT)),bytes=f.stat().st_size) for folder in (P,O) for f in folder.rglob('*') if f.is_file() and not f.is_symlink() and 'build' not in f.relative_to(folder).parts and f.stat().st_size>=1024**2]
    row=dict(passed=True,device_executed=False,services_started=False,live_queue_modified=False,
        all_python_windows=11,intercepted_native_arguments=31,queue_windows=11,queue_input_preflights=12,queue_oracle_checks=6,restored_symlinks=9,old_packet124b_oracle_rejected=True,k2_full_replay_passed=True,old_packet124_rejected=True,
        argument_gate_sha256=sha(O/'evidence/argument-gate.json'),packet124_identity_sha256=sha(O/'inputs/packet124-native-identity.json'),
        sealed_compositions=1,gnu_intel_fresh_repeats=4,all_startup_windows=11,actual_rank_exec_checks=6,
        old_limit_negative_control=True,drain=drain,build_bytes=build,root_free_bytes=free,
        selection_sha256=sha(P/'selection.json'),memory_plan_sha256=sha(P/'memory-plan.json'),
        startup_sha256=sha(P/'startup103.json'),cpu_tests_sha256=sha(O/'cpu-tests.json'),
        chain_seal_sha256=sha(P/'build-receipt.json'),ready=ready['ready'],readiness_reason=ready.get('reason'),
        tests_log=(O/'tests.log').read_text().strip(),large_retained_files=sizes,
        retained_large_file_policy='RETENTION.md: frozen source/provenance restored from Git; exact compressed fixtures from gzip or recorded CPU commands')
    save(O/'cpu-final.json',row)
    print(json.dumps({k:v for k,v in row.items() if k not in ('drain','large_retained_files')},indent=2))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    main()
