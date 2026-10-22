#!/usr/bin/env python3
"""CPU rehearsal of the packet183 win-path waiter (chain/p183_win.py) in scratch repo roots, dry run.

Nothing is launched, paused or queued: P183_DRY_RUN=1 makes the waiter stop right before it
would hold the PAUSE files; FN/LOG point at scratch. Scratch root R per case (removed after):
stage2/ and ops/ entries are symlinks to the real ones, except
  - stage2/packet183-twocard-s1-micro: a real byte copy (symlinks preserved); the synthetic
    bracket summary is written into ITS evidence tree, never into the real packet;
  - ops/lane-queue: real copies of lanequeue.py, pin_guard.py and the proposal file, a scratch
    events-B.jsonl, no PAUSE/queue/inflight files.
Cases:
  win        (REAL repository, scratch events/summary/decision) summary = packet153's REAL lane-B bracket summary (5 real exact views) with both
             candidate rates set to +4.4% over the best control (the expected-gain floor case),
             events DONE -> exit 0, log through 'dry run: would hold' (decision, endpoints, queue
             snapshot, validate, live pin guard, the job's own --plan, storage/host bounds, command);
  below      same, +1.0% -> exit 0, 'no confirmation (chain rule not met)', no plan run;
  failed     events FAILED -> exit 2;
  skipped    events SKIPPED-DEPENDENCY (the smoke failed) -> exit 2;
  exists     win case with the confirm output already present -> exit 4;
  drift      win case with the scratch lanequeue.py changed after planning -> exit 4;
  endpoints  win case with the REAL owner endpoint units (read-only is-active) -> exit 5 when
             any is active (skipped, and said so, if none is active).
Separately the hold()/restore() PAUSE functions run on a scratch lane directory: an existing
PAUSE-A is saved and restored byte for byte, an absent PAUSE-B is created with the hold text and
kept, nothing is deleted. Writes ../v5/evidence/waiter-rehearsal.json.
"""
import copy,hashlib,importlib.util,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path

HERE=Path(__file__).resolve().parent;PACKET=HERE.parent;REPO=PACKET.parents[3];X='experiments/own-xpu-runtime'
SCRATCH=Path('/tmp/claude-1000/-home-steve/1df77db8-272b-4a21-9a32-d0349da3fe39/scratchpad')
REAL=PACKET/'lineage-inputs/packet153-own/v5/evidence/device-static-v5-B-p153b/bracket-summary.json'
PROPOSAL=REPO/f'{X}/ops/lane-queue/proposed-p183-two-card-B.txt'
JOB=next(json.loads(l)['name'] for l in PROPOSAL.read_text().splitlines() if l.strip() and not l.lstrip().startswith('#') and json.loads(l).get('depends_on'))

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def build_root(base):
    R=base/'repo'
    for rel in (f'{X}/stage2',f'{X}/ops'):
        (R/rel).mkdir(parents=True)
        for e in (REPO/rel).iterdir():
            if e.name in ('lane-queue',PACKET.name):continue
            (R/rel/e.name).symlink_to(e)
    lq=R/f'{X}/ops/lane-queue';lq.mkdir()
    for n in ('lanequeue.py','pin_guard.py','proposed-p183-two-card-B.txt'):shutil.copy2(REPO/f'{X}/ops/lane-queue'/n,lq/n)
    shutil.copytree(PACKET,R/f'{X}/stage2'/PACKET.name,symlinks=True,ignore=shutil.ignore_patterns('__pycache__','s1-bytes','real-census','full-shape','fs-mirror','switch','controller-*'))
    for e in REPO.iterdir():
        if e.name not in ('experiments','.git'):(R/e.name).symlink_to(e)
    for e in (REPO/'experiments').iterdir():
        if e.name!='own-xpu-runtime':(R/'experiments'/e.name).symlink_to(e)
    for e in (REPO/X).iterdir():
        if e.name not in ('stage2','ops'):(R/X/e.name).symlink_to(e)
    return R

def summary(factor):
    s=json.loads(REAL.read_text());best=max(v['rate'] for v in s['views'] if v['choice']=='control')
    for v in s['views']:
        if v['choice']=='candidate':v['rate']=best*factor
    return s

def run_case(name,factor,event,endpoints=None,mutate=None):
    base=Path(tempfile.mkdtemp(prefix='p183-waiter-'+name+'-',dir=SCRATCH))
    try:
        R=build_root(base);P=R/f'{X}/stage2'/PACKET.name;lq=R/f'{X}/ops/lane-queue'
        out=P/'v5/evidence/device-metadata-v5-B-p183';out.mkdir(parents=True)
        (out/'bracket-summary.json').write_text(json.dumps(summary(factor),indent=1))
        (lq/'events-B.jsonl').write_text(json.dumps(dict(event='START',lane='B',name=JOB,utc='rehearsal'))+'\n'+json.dumps(dict(event=event,lane='B',name=JOB,utc='rehearsal'))+'\n')
        if mutate:mutate(R,P,lq)
        fn=base/'fn';log=fn/'p183-win.log'
        env=dict(PATH='/usr/bin:/bin',HOME=os.environ.get('HOME','/home/steve'),XDG_RUNTIME_DIR=os.environ.get('XDG_RUNTIME_DIR','/run/user/1000'),
                 P183_REPO=str(R),FN=str(fn),LOG=str(log),P183_DRY_RUN='1',P183_ENDPOINT_UNITS=endpoints or 'p183-rehearsal-no-such-unit')
        t=time.monotonic()
        cp=subprocess.run(['/usr/bin/bash',str(P/'chain/p183-win.sh')],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=900)
        text=log.read_text() if log.exists() else ''
        decision=json.loads((P/'v5/evidence/waiter-decision.json').read_text()) if (P/'v5/evidence/waiter-decision.json').exists() else None
        return dict(case=name,rc=cp.returncode,seconds=round(time.monotonic()-t,1),log=text.splitlines(),stderr=cp.stderr[-2000:],decision=decision)
    finally:shutil.rmtree(base,ignore_errors=True)

def run_real_win(factor):
    """Win case against the REAL repository: live queue module, live pin guard, the lane-A job's
    own --plan; only the events file, the summary and the decision receipt are scratch (dry-run-only
    redirections), so nothing is written into the repository."""
    base=Path(tempfile.mkdtemp(prefix='p183-waiter-realwin-',dir=SCRATCH))
    try:
        events=base/'events-B.jsonl';summ=base/'bracket-summary.json';dec=base/'waiter-decision.json'
        summ.write_text(json.dumps(summary(factor),indent=1))
        events.write_text(json.dumps(dict(event='START',lane='B',name=JOB,utc='rehearsal'))+'\n'+json.dumps(dict(event='DONE',lane='B',name=JOB,utc='rehearsal'))+'\n')
        fn=base/'fn';log=fn/'p183-win.log'
        env=dict(PATH='/usr/bin:/bin',HOME=os.environ.get('HOME','/home/steve'),XDG_RUNTIME_DIR=os.environ.get('XDG_RUNTIME_DIR','/run/user/1000'),
                 FN=str(fn),LOG=str(log),P183_DRY_RUN='1',P183_ENDPOINT_UNITS='p183-rehearsal-no-such-unit',P183_EVENTS=str(events),P183_SUMMARY=str(summ),P183_DECISION=str(dec))
        before={str(p):p.stat().st_mtime_ns for p in (PACKET/'v5/evidence').iterdir()}
        t=time.monotonic();cp=subprocess.run(['/usr/bin/bash',str(PACKET/'chain/p183-win.sh')],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=900)
        after={str(p):p.stat().st_mtime_ns for p in (PACKET/'v5/evidence').iterdir()}
        new=sorted(set(after)-set(before))
        return dict(case='win',rc=cp.returncode,seconds=round(time.monotonic()-t,1),log=(log.read_text() if log.exists() else '').splitlines(),
                    stderr=cp.stderr[-2000:],decision=json.loads(dec.read_text()) if dec.exists() else None,real_repository=True,
                    packet_evidence_written=[n for n in new if 'lanequeue-review-' not in n],confirm_output_absent=not (PACKET/'v5/evidence/device-metadata-v5-A-p183').exists())
    finally:shutil.rmtree(base,ignore_errors=True)

def pause_test():
    spec=importlib.util.spec_from_file_location('p183_win_rehearsal',HERE/'p183_win.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    d=Path(tempfile.mkdtemp(prefix='p183-pause-',dir=SCRATCH))
    try:
        (d/'PAUSE-A').write_text('owner pause text\n');before=sha(d/'PAUSE-A')
        m.hold(d,d/'saved','T');held={l:(d/f'PAUSE-{l}').read_text() for l in 'AB'}
        assert all(v.startswith('held for packet183') for v in held.values()) and (d/'saved-A').exists() and not (d/'saved-B').exists()
        m.restore(d,d/'saved')
        assert sha(d/'PAUSE-A')==before and (d/'PAUSE-B').read_text().startswith('held for packet183') and not list(d.glob('saved-*'))
        return dict(passed=True,existing_pause_restored_byte_for_byte=True,absent_pause_kept_as_hold=True,deleted=0)
    finally:shutil.rmtree(d,ignore_errors=True)

def active(units):
    return [u for u in units if subprocess.run(['/usr/bin/systemctl','--user','is-active',u],capture_output=True,text=True).stdout.strip() in ('active','activating')]

def main():
    rows=[]
    rows.append(run_real_win(1.044))
    rows.append(run_case('below',1.010,'DONE'))
    rows.append(run_case('failed',1.044,'FAILED'))
    rows.append(run_case('skipped',1.044,'SKIPPED-DEPENDENCY'))
    rows.append(run_case('exists',1.044,'DONE',mutate=lambda R,P,lq:(P/'v5/evidence/device-metadata-v5-A-p183').mkdir(parents=True)))
    rows.append(run_case('drift',1.044,'DONE',mutate=lambda R,P,lq:(lq/'lanequeue.py').write_text((lq/'lanequeue.py').read_text()+'\n# drift\n')))
    units=['qwen38-27b-fp8','qwen38-27b-fp8-tp1-test','qwen38-27b-vision'];live=active(units)
    rows.append(run_case('endpoints',1.044,'DONE',endpoints=' '.join(units)) if live else dict(case='endpoints',skipped='no owner endpoint unit active now'))
    expect={'win':(0,'dry run: would hold'),'below':(0,'no confirmation (chain rule not met)'),'failed':(2,'ended FAILED'),'skipped':(2,'ended SKIPPED-DEPENDENCY'),
            'exists':(4,'already exists'),'drift':(4,'differs from the packet planning snapshot'),'endpoints':(5,'ALERT endpoint(s) active')}
    for r in rows:
        if 'skipped' in r:continue
        rc,needle=expect[r['case']];r['passed']=r['rc']==rc and any(needle in l for l in r['log'])
        if r['case']!='win':r['passed']=r['passed'] and not any('dry run: would hold' in l for l in r['log'])
        if r['case']=='win':r['passed']=r['passed'] and not r['packet_evidence_written'] and r['confirm_output_absent'] and any('confirm job validated' in l for l in r['log'])
        if r['case'] in ('below','failed','skipped'):r['passed']=r['passed'] and not any('confirm job validated' in l for l in r['log'])
    pause=pause_test()
    ok=all(r.get('passed',True) for r in rows) and pause['passed']
    row=dict(passed=ok,device_executed=False,dry_run=True,cases=rows,pause_files=pause,endpoint_units_live=live,
             sources={str(f.relative_to(REPO)):sha(f) for f in (HERE/'p183_win.py',HERE/'p183-win.sh',HERE/'rehearse_waiter.py',PACKET/'v5/s1_decision.py')})
    (PACKET/'v5/evidence/waiter-rehearsal.json').write_text(json.dumps(row,indent=1)+'\n')
    for r in rows:print(r['case'],r.get('rc'),r.get('passed',r.get('skipped')),r.get('seconds'))
    print('pause files',pause);print('WAITER REHEARSAL',('PASS' if ok else 'FAIL'))
    return 0 if ok else 1

if __name__=='__main__':raise SystemExit(main())
