"""Read-only build checks and coordinator launch gate; never authorizes itself."""
import hashlib,json,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent.parent
REPO=P.parents[3]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def require(ok,message):
    if not ok:raise ValueError(message)
def build_gate():
    build=read(P/'evidence/build.json')
    require(build['passed'] and not build['device_executed'],'CPU native build required')
    for name,digest in build['sources'].items():
        if name.startswith(('native/','build/native/','vendor/')):require(sha(P/name)==digest,'compiled source changed')
    artifacts=dict(build['artifacts'])
    artifacts['build/device/p58-cache-fixtures']=read(P/'lineage/p58amc-before/READY-FOR-DEVICE.json')['artifacts']['build/device/p58-cache-fixtures']
    artifacts['build/device/p58-cache-fixtures-cli']=read(P/'evidence/k1-cli.json')['binary_sha256']
    for name,digest in artifacts.items():require(sha(P/name)==digest,'native artifact changed')
    for row in read(P/'lineage/harness58aj.json')['files']:
        require(sha(REPO/row['source'])==row['source_sha256'],'parent harness changed')
        require(sha(P/row['snapshot'])==row['source_sha256'],'vendored harness snapshot changed')
    return dict(build,artifacts=artifacts)
def demand_report(view,root):
    kind='smoke' if view=='smoke' else 'v5'
    result=subprocess.run([sys.executable,'-B',str(P/'read_run.py'),str(P/'proposals'/f'{kind}.json'),str(root),'--output',str(root.parent/'demand-summary.json')],stdin=subprocess.DEVNULL,capture_output=True,text=True)
    require(result.returncode==0,'full demand report failed: '+result.stderr[-2000:])
    return read(root.parent/'demand-summary.json')
def verify_smoke():
    import queue_runner as Q
    proposal=read(P/'proposals/smoke.json');root=Path(proposal['output'])
    for name in Q.ORDER:Q.verify_success(name,root,0,0)
    report=demand_report('smoke',root/'WSCREEN/run/run')
    require(report.get('smoke_passed') is True and report.get('exact') is True and report.get('same_parent') is True,'same-parent exact eligible overlap and overhead smoke required')
    return report
def authorize(kind):
    if kind=='checked':
        from checked_release import authorize_checked
        return authorize_checked()
    ready=read(P/'READY-FOR-DEVICE.json')
    require(ready.get('ready_for_device') is True,'device release withheld: resident-parent native support and full entry checks required')
    require(ready.get('release_condition')=='coordinator direct-screen release (RELEASE-AMENDMENT.md)' and ready.get('release_amendment_sha256')==sha(P/'RELEASE-AMENDMENT.md'),'coordinator release amendment binding')
    require(ready.get('packaging_sha256')==sha(P/'screen-packaging.json'),'packaging binding')
    package=read(P/'screen-packaging.json')
    require(package.get('passed') is True,'packaging incomplete')
    for name,digest in package['files'].items():require(sha(REPO/name)==digest,'screen source/proposal changed')
    queue=REPO/'experiments/own-xpu-runtime/ops/lane-queue'
    require((queue/'PAUSE-B').exists(),'coordinator must retain PAUSE-B whole-host hold')
    # The inherited whole-host reservation rejects foreign live owners. Empty
    # queues alone are not admission; both are required before K1a.
    for lane in ('A','B'):
        path=queue/f'queue-{lane}.txt'
        if path.exists():
            for line in path.read_text().splitlines():
                if line.strip() and not line.lstrip().startswith('#'):
                    row=json.loads(line)
                    require(row.get('name')==read(P/'proposals'/f'{kind}.json')['job_name'],'foreign queued job under whole-host hold')
    smoke=verify_smoke() if kind=='v5' else None
    # Run the exact packet admission in a fresh namespace to avoid the
    # screen's analyzer sharing a module name with the demand analyzer.
    import importlib.util
    spec=importlib.util.spec_from_file_location('demand_admission',P/'admit.py');m=importlib.util.module_from_spec(spec)
    sys.path.insert(0,str(P))
    try:spec.loader.exec_module(m);m.device_admission(read(P/'proposals'/f'{kind}.json'),ready,{},smoke)
    finally:sys.path.pop(0)
