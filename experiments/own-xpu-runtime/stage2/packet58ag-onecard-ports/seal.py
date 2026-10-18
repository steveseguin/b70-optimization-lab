"""Seal this private CPU-qualified implementation, never device performance."""
import argparse,json,resource,subprocess
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
GATES=('evidence/build.json','evidence/hc-gates.json','evidence/control-gate.json','evidence/report-gate.json','evidence/entry-gates.json','evidence/protocol-gates.json','evidence/k1-async-cpu.json',
       'evidence/fullshape-submit-cpu.json','evidence/postload-allocation-cpu.json','evidence/reset-gate.json',
       'evidence/startup-cpu.json','evidence/argument-gate.json','evidence/python-cpu-gates.json',
       'evidence/memory-budget.json','evidence/drain-fix.json','evidence/teardown-integration.json','evidence/oracle-gate.json')
def read(p):return json.loads(p.read_text())
def verify(root,pins):
    from input_scope import check_pins
    check_pins(root,pins)
    for name,digest in pins.items():
        assert sha(root/name)==digest,'changed sealed input: '+name

def create():
    limits();assert not (P/'evidence/card0-hcfusion-a').exists(),'never reseal started device output'
    sources={};gates={}
    for name in GATES:
        row=read(P/name);assert row.get('passed') is True and row.get('device_executed') is False,name
        if row.get('sources'):verify(ROOT,row['sources']);sources.update(row['sources'])
        gates[name]=sha(P/name)
    native=read(P/'evidence/build.json');artifacts=dict(native['artifacts'])
    for gate,binary in [('reset-gate','own-rt-iq3'),('startup-cpu','own-rt-iq3'),('fullshape-submit-cpu','fullshape-submit'),('postload-allocation-cpu','fullshape-submit'),('k1-async-cpu','p58-cache-fixtures')]:
        assert read(P/f'evidence/{gate}.json')['binary_sha256']==artifacts[f'build/gnu-host/{binary}'],gate
    args=read(P/'evidence/argument-gate.json');assert args['checks']==6
    assert {(r['candidate'],r['window']) for r in args['records']}=={(v,w) for v in ('p60fusion','smoke') for w in ('K1a','K1b','WSCREEN')}
    assert all(r['resource_limits_unchanged'] and r['native_exec_intercepted'] and r['real_queue_entry'] and r['real_unit_and_environment_gates'] and r['live_host_admission'] for r in args['records'])
    assert read(P/'evidence/python-cpu-gates.json')['checks']>=110
    hc=read(P/'evidence/hc-gates.json');assert len(hc['records'])==8 and all(r['passed'] for r in hc['records'])
    files=[*P.glob('*.py'),*P.glob('*.md'),P/'views.json',P/'admission.json',P/'copy-manifest.json',P/'oracle-binding.json',P/'library-path.json',P/'k1-cpu.json',P/'dispatch-speed6.json',P/'immutable-inputs.json',P/'readiness-policy.json',P/'old_unit_gate.txt',P/'teardown-templates.json']
    for folder in ('native','sources','lineage','selections','host-admission','proposals'):
        files += [f for f in (P/folder).rglob('*') if f.is_file() and '__pycache__' not in f.parts]
    for f in files:sources[str(f.relative_to(ROOT))]=sha(f)
    from shared_oracle import completed_binding
    binding=completed_binding();assert binding==read(P/'evidence/oracle-gate.json')
    from input_scope import allowed_inputs
    sources.update(allowed_inputs());verify(ROOT,sources);verify(P,artifacts)
    size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file());assert size<=300_000_000
    row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,gates=gates,
        runtime_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True,stdin=subprocess.DEVNULL).strip(),
        arithmetic='iq3-p49-split32-v1',gpu_count=1,decode_mode='plain',kv_dtype='BF16',retained_build_bytes=size,
        hc=['production','p60fusion'],cache_maintenance='overlap',cache_allocation_bytes=21552729600,oracle=binding,submission_eligible=False,
        qualification='CPU only; full-model device output equality and speed pending')
    save(P/'build-receipt.json',row);return row

def main():
    a=argparse.ArgumentParser();a.add_argument('--verify',action='store_true');args=a.parse_args()
    if args.verify:
        row=read(P/'build-receipt.json');verify(ROOT,row['sources']);verify(P,row['artifacts']);verify(P,row['gates'])
        from shared_oracle import completed_binding
        assert completed_binding()==row['oracle']
    else:row=create()
    print(json.dumps(dict(passed=True,device_executed=False,sources=len(row['sources']),build_bytes=row['retained_build_bytes'])))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));main()
