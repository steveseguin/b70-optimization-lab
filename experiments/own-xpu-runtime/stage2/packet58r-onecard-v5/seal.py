"""Seal immutable native dependencies, all CPU gates and wrapper inputs."""
import argparse,json,os,resource,subprocess
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits

GATES=('evidence/build.json','evidence/byte-gates.json','evidence/reset-gate.json',
       'evidence/fullshape-submit-cpu.json','evidence/postload-allocation-cpu.json',
       'evidence/startup-cpu.json','evidence/argument-gate.json','evidence/python-cpu-gates.json',
       'evidence/memory-budget.json','evidence/drain-fix.json','evidence/teardown-integration.json')

def read(path):return json.loads(path.read_text())

def verify(root,pins):
    assert pins,'empty seal'
    for name,digest in pins.items():
        path=(root/name).resolve()
        assert path.is_relative_to(ROOT) and sha(path)==digest,'changed sealed input: '+name

def create():
    limits()
    assert not (P/'evidence/card0-v5-a').exists(),'cannot reseal a started bracket'
    sources={};gates={}
    for name in GATES:
        row=read(P/name)
        assert row.get('passed') is True and row.get('device_executed') is False,name
        if row.get('sources'):
            verify(ROOT,row['sources']);sources.update(row['sources'])
        gates[name]=sha(P/name)
    native=read(P/'evidence/build.json');artifacts=dict(native['artifacts'])
    relinks=native['parent_relinks']
    assert len(relinks)==2 and {r['mode'] for r in relinks}=={'gnu-host','device'}
    assert all(r['passed'] is True for r in relinks)
    for mode in ('gnu-host','device'):
        name=f'build/{mode}/p58-cache-fixtures'
        parent=P.parent/'packet58j-onecard-port'/name
        assert sha(P/name)==sha(parent)
        artifacts[name]=sha(P/name);sources[str(parent.relative_to(ROOT))]=sha(parent)
    for gate,binary in [('reset-gate','own-rt-iq3'),('fullshape-submit-cpu','fullshape-submit'),
                        ('postload-allocation-cpu','fullshape-submit'),('startup-cpu','own-rt-iq3')]:
        assert read(P/f'evidence/{gate}.json')['binary_sha256']==artifacts[f'build/gnu-host/{binary}'],'stale native gate '+gate
    assert read(P/'evidence/startup-cpu.json')['fullshape_receipt_sha256']==sha(P/'evidence/fullshape-submit-cpu.json')
    from views import VIEWS,validate
    for view in VIEWS:validate(view)
    assert len(read(P/'evidence/byte-gates.json')['records'])==12
    assert len(read(P/'evidence/reset-gate.json')['records'])==6
    full=read(P/'evidence/fullshape-submit-cpu.json')
    assert full['checks']==8 and full['switches_per_check']==5
    assert {(r['view'],r['miss_path']) for r in full['rows']}=={(v,m) for v in VIEWS for m in ('zero-copy','streamed')}
    args=read(P/'evidence/argument-gate.json')
    assert args['checks']==12
    assert {(r['candidate'],r['window'],r['miss_path']) for r in args['records']}=={
        (v,w,m) for v in VIEWS[1:] for w in ('K1a','K1b','WSCREEN') for m in (('zero-copy','streamed') if w=='WSCREEN' else ('zero-copy',))}
    assert all(r['resource_limits_unchanged'] and r['native_exec_intercepted'] and not r['finite_address_space_limit'] for r in args['records'])
    assert read(P/'evidence/startup-cpu.json')['checks']==6
    assert read(P/'evidence/python-cpu-gates.json')['checks']>=75
    for f in [*P.glob('*.py'),P/'views.json',P/'copy-manifest.json',P/'oracle-binding.json',P/'k1-cpu.json',
              P/'dispatch-speed6.json',*(P/'selections').glob('*.json'),*(P/'sources').glob('*'),*(P/'native').glob('*'),*(P/'lineage').glob('*')]:
        sources[str(f.relative_to(ROOT))]=sha(f)
    for folder in ('evidence/58c-supervisor','evidence/58c-kd'):
        for f in (P/folder).rglob('*'):
            if f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
    import memory_plan as M
    budget=M.plan();sources.update(budget['allocation_inventory']['sources'])
    sources[budget['census']['source_path']]=budget['census']['source_sha256']
    sources.update(read(P/'oracle-binding.json')['files_sha256'])
    from suite_driver import oracle_inputs
    # Results are an authoritative external-store symlink. Their fixed root
    # hash lives in our sealed local oracle-binding, not a repo-contained file.
    oracle_inputs()
    for name in ('packet94-hc-norm-fusion/compile_turn.py','packet56-draft-prefix/p56_head_support.py',
                 'packet56-draft-prefix/suite_metrics.py','packet34-replay-bench/window.py'):
        path=P.parent/name;sources[str(path.relative_to(ROOT))]=sha(path)
    for name in ('scripts/check_drain_fix.py','scripts/check_teardown_on_error.py'):
        sources[name]=sha(ROOT/name)
    fault_driver=ROOT/'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py'
    sources[str(fault_driver.relative_to(ROOT))]=sha(fault_driver)
    assert not any('/ops/' in n or n.endswith(('/ready.json','/queue.json','/submission-pins.json')) for n in sources)
    verify(ROOT,sources);verify(P,artifacts)
    size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file())
    assert size<=200_000_000
    row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,gates=gates,
        runtime_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True,stdin=subprocess.DEVNULL).strip(),
        arithmetic='iq3-p49-split32-v1',gpu_count=1,decode_mode='plain',kv_dtype='BF16',views=list(VIEWS),retained_build_bytes=size,
        native_recompiled=True,immutable_inputs_only=True,submission_eligible=False,qualification='CPU preparation; every device token and speed remain pending')
    save(P/'build-receipt.json',row);return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    if a.verify:
        row=read(P/'build-receipt.json');verify(ROOT,row['sources']);verify(P,row['artifacts']);verify(P,row['gates'])
    else:row=create()
    print(json.dumps(dict(passed=True,device_executed=False,sources=len(row['sources']),build_bytes=row['retained_build_bytes'])))

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    main()
