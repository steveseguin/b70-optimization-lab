"""Check every CPU gate, then write READY-FOR-DEVICE.json LAST.

READY is true only if every gate below passes; otherwise it is written false
with the failing gates as blockers. No device, model payload or queue access.
"""
import ast,json,re,resource,subprocess,sys,unittest
from pathlib import Path
from build_engine import P,ROOT,limits,save,sha
import package
import census_contract as C
RESERVED={'pins','files','gates','artifacts','sources','files_sha256'}
HEX=re.compile(r'^[0-9a-f]{64}$')

def pin_guard(value,path,problems):
    """Reserved maps hold only SHA256 values; no name->sha map may leave the packet."""
    if isinstance(value,dict):
        for key,item in value.items():
            if key in RESERVED and not(isinstance(item,dict)and all(isinstance(v,str)and HEX.match(v) for v in item.values())):
                problems.append(f'{path}:{key} reserved map with non-SHA256 values')
            if isinstance(item,dict) and item and all(isinstance(v,str)and HEX.match(v) for v in item.values()):
                for name in item:
                    target=(P/name)
                    if name.startswith('/') or '..' in Path(name).parts or not target.resolve().is_relative_to(P):
                        problems.append(f'{path}:{key} maps outside-packet {name} to a digest')
            pin_guard(item,path,problems)
    elif isinstance(value,list):
        for item in value:pin_guard(item,path,problems)

def gate(name,ok,detail,gates):
    gates.append(dict(gate=name,passed=bool(ok),detail=detail))

def main():
    limits();package.seal();gates=[]
    # 1. Sources parse; JSON pin guard over every packet JSON (evidence included).
    py=0;problems=[]
    for f in P.rglob('*'):
        if not f.is_file() or f.relative_to(P).parts[0]=='build' or 'device-census' in str(f):continue
        if f.suffix=='.py':ast.parse(f.read_text(),filename=str(f));py+=1
        if f.suffix=='.json':pin_guard(json.loads(f.read_text()),str(f.relative_to(P)),problems)
    gate('pin-guard',not problems,dict(python_sources=py,problems=problems),gates)
    from cpu_seal import verify
    verify()
    build=json.loads((P/'evidence/build.json').read_text())
    gate('device-build',build['passed'] and build['binary_sha256']==sha(P/'build/device/own-rt-iq3'),build['binary_sha256'],gates)
    native=json.loads((P/'evidence/native-lifecycle.json').read_text())
    rows=native.get('results',[])
    gate('native-real-arm-sequence',native.get('final_arm_sequence_passed') is True and native.get('native_order')==list(C.NATIVE_ORDER)
      and sorted(r['rank'] for r in rows)==[0,1] and all(r['observations']==len(C.NATIVE_ORDER)*len(C.IDS)*C.REPEATS and r['returncode']==0 for r in rows),
      dict(observations=[r.get('observations') for r in rows],sensors=[r.get('real_sensor_samples') for r in rows],
           peak_rss=[r.get('peak_rss_bytes') for r in rows],compute_is_marker_only=native.get('compute_is_marker_only')),gates)
    worker=json.loads((P/'evidence/worker-gate.json').read_text())
    gate('worker-real-arm-sequence',worker['passed'] and worker['good']['report_passed'] and all(b['refused'] for b in worker['refusals']),
      dict(good=worker['good'],refusals=[b['error'] for b in worker['refusals']]),gates)
    tests=unittest.TextTestRunner(stream=open('/dev/null','w')).run(unittest.defaultTestLoader.loadTestsFromName('test_analyze'))
    save(P/'evidence/analyzer-tests.json',dict(passed=tests.wasSuccessful(),tests=tests.testsRun,failures=len(tests.failures)+len(tests.errors)))
    gate('analyzer-tests',tests.wasSuccessful(),dict(tests=tests.testsRun),gates)
    replay=json.loads((P/'evidence/real-parent-replay.json').read_text())
    gate('analyzer-real-parent-evidence',replay['passed'] and sum(r['actual_census_control_validator_checks'] for r in replay['records'])==60
      and any(r['parent']=='packet136' and abs(r['primary_tok_s']-58.798108759182306)<1e-9 for r in replay['records']),
      [(r['parent'],r['primary_tok_s']) for r in replay['records']],gates)
    adapter=json.loads((P/'evidence/report-adapter.json').read_text())
    gate('report-adapter',adapter['passed'] and len(adapter['results'])==11,len(adapter['results']),gates)
    launch=json.loads((P/'evidence/launch-checks.json').read_text())
    gate('flags-help-imports',launch['passed'] and launch['binary_sha256']==sha(P/'build/device/own-rt-iq3') and len(launch['results'])==2,
      [r['imports'] for r in launch['results']],gates)
    qual=json.loads((P/'qualification.json').read_text());memory=qual['memory']
    gate('census-memory-plan',memory['rank1_planned_free_bytes']>=1_500_000_000 and memory['rank1_arena_headroom_bytes']>0
      and memory['device_validation']['device_rank0_image_bytes']==memory['device_validation']['fixture_rank0_image_bytes'],memory,gates)
    shared=json.loads((P/'evidence/shared-packaging.json').read_text())
    plans=[r for r in shared['results'] if r['kind']=='plan']
    gate('lanequeue-plan-temp-copies',len(plans)==2 and all(r['passed'] for r in plans),plans,gates)
    rehearse=[r for r in shared['results'] if r['kind']=='rehearse']
    budget=json.loads((P/'budget.json').read_text())
    gate('waits-floor-bounds',budget['wait_seconds']>=4*budget['cold_phase_reference_seconds'] and budget['wait_seconds']>=300
      and budget['device_floor_bytes']==25_000_000_000 and budget['wall_clock_data_proof_limit'] is None
      and budget['planned_write_bytes']<=3*budget['projected_census_bytes'],
      {k:budget[k] for k in ('wait_seconds','controller_wait_seconds','device_floor_bytes','planned_write_bytes','projected_census_bytes')},gates)
    plan=subprocess.run(['/usr/bin/python3','-B',str(P/'entry.py'),'--lane','B','--kind','census','--output',str(P/'evidence/never-created'),'--plan'],
      cwd=P,stdin=subprocess.DEVNULL,capture_output=True,text=True)
    gate('entry-plan',plan.returncode==0 and json.loads(plan.stdout.strip().splitlines()[-1])['model_loads']==1,plan.stdout[-400:]+plan.stderr[-400:],gates)
    import readiness
    try:readiness.verify_ready()
    except ValueError:denied=True
    else:denied=False
    gate('device-entry-denied-before-ready',denied,'verify_ready refuses while READY is absent/false',gates)
    failed=[g['gate'] for g in gates if not g['passed']]
    save(P/'evidence/final-audit.json',dict(passed=not failed,device_executed=False,gate_results=gates,
      rehearse_receipts=rehearse,failed=failed))
    receipts={str(f.relative_to(P)):sha(f) for f in sorted((P/'evidence').glob('*.json'))}
    ready=not failed
    # This is the final write. All source edits and shared receipts precede it.
    save(P/'READY-FOR-DEVICE.json',dict(schema='packet168.readiness.v2',ready=ready,ready_for_device=ready,
      device_executed=False,model_loads_planned=1,measured_ranked_table_available=False,
      seal_sha256=sha(P/'seal.json'),evidence_sha256=receipts,blockers=failed,
      lane='B',cards=[2,3],alternative_lane='A',proposals=[f'proposed-p168-body-census-{l}-{package.VERSION}.txt' for l in 'BA'],
      jobs=[f'packet168-body-census-{l}-{package.VERSION}' for l in 'BA'],
      supersedes=dict(job='packet168-body-census-B-v2',evidence='evidence/device-census-B-v2',
        root_cause='control-pass sticky error: probe ran at unadmitted position 128 (benchmark-analysis) with qsa launch extent 128'),
      measured_classes=list(C.CLASSES),residual=dict(definition='exact native control ms/token minus sum of five measured class marginals',
        includes=['attention (no arm since v3)','cross-card transfer','split head/argmax/merge','controller/mailbox','overlap'],causally_isolated=False),
      shared_tool_limitations=[] if all(r['passed'] for r in rehearse) else [
        'Shared ops/rehearse_entry.py --report cannot run this custom census report (receipts evidence/shared-rehearse-*-'+package.VERSION+'.*.log retained); '
        'qualified instead by the packet-private report adapter (evidence/report-adapter.json: real entry/parser/analyzer/report, 11 cases) '
        'and the worker gate (evidence/worker-gate.json), as accepted for packet58aq.',
        'Shared rehearsal also WARNs that no preparation-path probe is declared: the census uses the parent-proven packet165 Transport '
        'start path unchanged except --census-probe; the native CPU fixture (evidence/native-lifecycle.json) runs the real parser, '
        'allocation and probe lifecycle with the device argv on both ranks.'],
      optional_smoke=False,
      opening_checks='No optional smoke: the single load opens with a distinct excluded warm-up and then the exact C0 control on all 12 prompts '
        '(oracle-prefix checked in-run; any mismatch stops before a probe). Chain-only K1a/K1b windows do not apply to this one-window screen.',
      arms_reported_as_speed=False,no_performance_claim=True,submission_eligible=False))
    print('READY written LAST: ready_for_device=%s; failed=%s'%(ready,failed))
    return 0 if ready else 1
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);raise SystemExit(main())
