"""Packet176 proposal gates: device-path imports, temporary lanequeue plan,
shared rehearse_entry --report and the pin guard. CPU only; no queue write."""
import json,shutil,subprocess,sys,tempfile
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
OPS=P.parents[1]/'ops';LQ=OPS/'lane-queue'
PROPOSAL=LQ/'proposed-p176-v5-A.txt'
LDP=json.loads((P/'library-path.json').read_text())['LD_LIBRARY_PATH']

def job():
    rows=[json.loads(s) for s in PROPOSAL.read_text().splitlines() if s.strip() and not s.startswith('#')]
    assert len(rows)==1 and rows[0]['name']=='packet176-v5-A' and rows[0]['lane']=='A';return rows[0]

def imports():
    # Real launch environment of the queue runner (closed env, recorded oneAPI path).
    code=('import sys;sys.path.insert(0,%r);import queue_runner,window,suite_driver,mechanism,compare_bracket,views,fault_review,live_check;'
          'import json;print(json.dumps(dict(modules=sorted(m for m in sys.modules if m in ("queue_runner","window","suite_driver","mechanism","compare_bracket","views","fault_review","live_check")))))')%str(P/'screen')
    cp=subprocess.run(['/usr/bin/env','-i','PATH=/usr/bin:/bin','OMP_NUM_THREADS=2','LD_LIBRARY_PATH='+LDP,'/usr/bin/python3','-B','-c',code],
                      cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
    assert cp.returncode==0,cp.stderr[-2000:]
    mods=json.loads(cp.stdout.splitlines()[-1])['modules'];assert len(mods)==8,mods
    save(P/'evidence/entry-imports.json',dict(passed=True,device_executed=False,environment='env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH=<library-path.json>',
        cwd='repository root',python='/usr/bin/python3 -B',modules=mods,model_reads=False))

def plan():
    with tempfile.TemporaryDirectory(dir=P/'build') as d:
        d=Path(d);shutil.copy2(PROPOSAL,d/'queue-A.txt')
        cp=subprocess.run(['/usr/bin/python3','-B',str(LQ/'lanequeue.py'),'plan','--lane','A','--directory',str(d)],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
        (P/'evidence/queue-plan-v5.log').write_text(cp.stdout+cp.stderr)
        assert cp.returncode==0,cp.stdout[-2000:]+cp.stderr[-2000:]
        rows=[json.loads(s) for s in cp.stdout.splitlines() if s.startswith('{')]
        assert len(rows)==1 and rows[0]['name']=='packet176-v5-A' and rows[0]['plan']=='passed' and rows[0]['storage_admission']['passed'],rows
    save(P/'evidence/queue-plans.json',dict(passed=True,device_executed=False,temporary_queue=True,queued=False,
        records=[dict(proposal=str(PROPOSAL.relative_to(ROOT)),proposal_sha256=sha(PROPOSAL),plan=rows)]))

def report():
    cmd=[sys.executable,'-B',str(OPS/'rehearse_entry.py'),str(PROPOSAL),'--report','--json']
    cp=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
    try:row=json.loads(cp.stdout)
    except ValueError:row=dict(passed=False,raw_stdout=cp.stdout[-4000:])
    save(P/'evidence/shared-entry-report.json',dict(row,returncode=cp.returncode,stderr_tail=cp.stderr[-2000:]))
    jobrow=(row.get('jobs') or [{}])[0];limits_=[]
    ok=cp.returncode==0 and row.get('passed') is True
    if ok:
        assert all(b['passed'] for b in jobrow['binaries']) and jobrow['report']['passed'] and jobrow['shared_environment_matches']
        assert jobrow['storage_floor']['passed'] and jobrow['wall_deadlines']['passed'] and jobrow['gate_identity']['status']!='FAIL'
        limits_.append('Shared --report passes. Its generic report rehearsal is synthetic only; no separate smoke row exists.')
    if 'preparation_path' in jobrow and jobrow['preparation_path'].get('status')!='PASS':
        limits_.append('Shared preparation adapter has no unranked one-card CPU transport probe. Private preparation_gate.py exercised the real device argv/plan and all reset paths (evidence/preparation.json); synthetic transport/weights, no GPU.')
    save(P/'evidence/shared-entry-report-final.json',dict(passed=ok,device_executed=False,proposal=str(PROPOSAL.relative_to(ROOT)),proposal_sha256=sha(PROPOSAL),
        returncode=cp.returncode,shared_report=str((P/'evidence/shared-entry-report.json').relative_to(P)),shared_tool_limitations=limits_,jobs=row.get('jobs')))
    assert ok,'shared rehearse_entry --report failed; see evidence/shared-entry-report.json'

def pins():
    sys.path.insert(0,str(LQ));import pin_guard
    pin_guard.check_job(job(),pin_guard.ROOT,pin_guard.STAGE)
    bad=[]
    def walk(v,path):
        if isinstance(v,dict):
            for k,x in v.items():
                if k in ('pins','files','gates','artifacts','sources') and isinstance(x,dict):
                    bad.extend(f'{path}/{k}:{n}' for n,h in x.items() if not (isinstance(h,str) and len(h)==64 and all(c in '0123456789abcdef' for c in h)))
                walk(x,path+'/'+str(k))
        elif isinstance(v,list):
            for i,x in enumerate(v):walk(x,f'{path}[{i}]')
    scanned=0
    for f in sorted(P.rglob('*.json')):
        rel=f.relative_to(P)
        if rel.parts[0] in ('build','lineage','frozen-inputs') or f.is_symlink():continue
        walk(json.loads(f.read_text()),str(rel));scanned+=1
    assert not bad,bad[:10]
    save(P/'evidence/pin-guard.json',dict(passed=True,device_executed=False,shared_pin_guard='ops/lane-queue/pin_guard.check_job passed on packet176-v5-A',
        packet_json_files_scanned=scanned,non_hash_pin_maps=0,parent_digests='{name, parent_relpath, parent_digest} records only'))

if __name__=='__main__':
    limits();step=sys.argv[1] if len(sys.argv)>1 else 'all'
    for name,fn in (('imports',imports),('plan',plan),('report',report),('pins',pins)):
        if step in ('all',name):fn();print('PASS',name,flush=True)
