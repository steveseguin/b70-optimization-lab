#!/usr/bin/env python3
"""Packet183 win-path waiter (two cards). PREPARED, NOT ARMED (arming: chain/ARMING.md).

Mirrors packet182's guarded waiter. It never queues a row, never deletes a PAUSE
file, never restarts or retries anything, never stops or starts a service, and
never signals a GPU process.

  1. Wait for packet183-s1-bracket-B's terminal event in events-B.jsonl (deadline 3 h;
     the smoke + bracket take ~12 min). Anything but DONE: exit 2, nothing else.
  2. Chain rule (v5/s1_decision.py, the same rule the bracket summary records): every
     view 13/13 exact, identical draft proposals, drift <= 3%, both metadata views
     >= +2% over every control AND >= 1.02 x 58.798109 (record). Not met: exit 0
     (NOCHAIN is a normal end; the summary is the readout).
  3. Met: there is no derivable two-card record chain yet (a two-card record chain is a
     record bundle: packet136 + dense_scales=metadata with a fresh registered chain on
     cards 0+1, as packets 136/143 did; that is the next packet). The win action that
     exists and is entry-rehearsed is the lane-A confirmation bracket of THIS packet on
     cards 0+1 (packet136's two-card promotion policy required wins on both lanes):
       - refuse while any owner endpoint unit is active (exit 5);
       - refuse if the confirm output exists or the live queue code differs from the
         packet's planning snapshot (exit 4);
       - build the job from the proposal's bracket row with lane A, validate it, run the
         live pin guard and the job's --plan through the queue's own functions;
       - hold PAUSE-A/PAUSE-B (save their contents, write hold text; never delete);
       - wait for inflight/active markers (30 min), drain spacing, queue guards (kernel
         fault count == reviewed base, markers, latches), host memory and storage
         admission, endpoints again, a fresh fault review;
       - launch exactly lanequeue.command(job, review, receipt, ldp) (systemd-run --wait,
         unit screen-packet183-s1-confirm-A); no retry; a client timeout never signals the
         unit (it is left to its own watchdog and the coordinator);
       - restore the PAUSE files (saved contents back; a pause that did not exist before
         keeps this hold text, lanes stay paused until the window driver decides);
       - record both lanes' decisions in v5/evidence/waiter-decision.json.
P183_DRY_RUN=1 stops right before holding the PAUSE files (CPU rehearsal: chain/rehearse_waiter.py).
P183_REPO, FN, LOG, P183_ENDPOINT_UNITS exist for that rehearsal only.
"""
import hashlib,importlib.util,json,os,shutil,subprocess,sys,time,uuid
from pathlib import Path

REPO=Path(os.environ.get('P183_REPO','/home/steve/llm-optimizations'))
X=REPO/'experiments/own-xpu-runtime';L=X/'ops/lane-queue';P=X/'stage2/packet183-twocard-s1-micro';V5=P/'v5'
FN=Path(os.environ.get('FN','/tmp/claude-1000/-home-steve/fn-run'));LOG=Path(os.environ.get('LOG',str(FN/'p183-win.log')))
DRY=os.environ.get('P183_DRY_RUN')=='1'
ENDPOINTS=os.environ.get('P183_ENDPOINT_UNITS','qwen38-27b-fp8 qwen38-27b-fp8-tp1-test qwen38-27b-vision').split()
COORD=Path('/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1')
SUMMARY=V5/'evidence/device-metadata-v5-B-p183/bracket-summary.json'
EVENTS=L/'events-B.jsonl';DECISION=V5/'evidence/waiter-decision.json'
if DRY:
    # Rehearsal-only redirections (ignored unless P183_DRY_RUN=1): synthetic events/summary in
    # scratch, decision receipt to scratch, so a dry run against the real repository writes nothing in it.
    EVENTS=Path(os.environ.get('P183_EVENTS',str(EVENTS)));SUMMARY=Path(os.environ.get('P183_SUMMARY',str(SUMMARY)))
    DECISION=Path(os.environ.get('P183_DECISION',str(FN/'waiter-decision.json')))
CONFIRM_OUT=V5/'evidence/device-metadata-v5-A-p183'
PROPOSAL=L/'proposed-p183-two-card-B.txt'

def proposal_rows():
    return [json.loads(l) for l in PROPOSAL.read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]

def bracket_row():
    # The proposal file is the one source of job identities: the bracket is the row that depends on the smoke.
    rows=[r for r in proposal_rows() if r.get('depends_on')]
    if len(rows)!=1 or rows[0]['lane']!='B':raise SystemExit(4)
    return rows[0]
TERMINAL={'DONE','FAILED','REFUSED','REFUSED-fast','REPORT-FAILED','REFUSED-PREDEVICE','SKIPPED-DEPENDENCY'}
HOLD='held for packet183 two-card S1 lane-A confirmation (whole host; p183-win {})'

def log(msg):
    FN.mkdir(parents=True,exist_ok=True)
    with LOG.open('a') as f:f.write(time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())+' p183-win '+msg+'\n')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def terminal_event(path,name):
    try:lines=path.read_text().splitlines()
    except FileNotFoundError:return None
    for line in reversed(lines):
        try:row=json.loads(line)
        except ValueError:continue
        if row.get('name')==name and row.get('event') in TERMINAL:return row['event']
    return None

def endpoints_active():
    active=[]
    for unit in ENDPOINTS:
        s=subprocess.run(['/usr/bin/systemctl','--user','is-active',unit],capture_output=True,text=True,timeout=20).stdout.strip()
        if s in ('active','activating','reloading','deactivating'):active.append(f'{unit}={s}')
    return active

def hold(lanes_dir,saved_prefix,stamp):
    """Save existing PAUSE contents, then write the hold text into both. Never deletes."""
    for lane in 'AB':
        saved=Path(f'{saved_prefix}-{lane}');saved.unlink(missing_ok=True)
        pause=lanes_dir/f'PAUSE-{lane}'
        if pause.exists():shutil.copy2(pause,saved)
        pause.write_text(HOLD.format(stamp)+'\n')

def restore(lanes_dir,saved_prefix):
    """Put saved contents back; a pause that did not exist before keeps the hold text."""
    for lane in 'AB':
        saved=Path(f'{saved_prefix}-{lane}')
        if saved.exists():shutil.copy2(saved,lanes_dir/f'PAUSE-{lane}');saved.unlink()

def queue_module():
    live=L/'lanequeue.py';snap=P/'lineage-inputs/queue/lanequeue.py'
    if sha(live)!=sha(snap):raise SystemExit(4)
    if str(L) not in sys.path:sys.path.insert(0,str(L))  # lanequeue imports its sibling pin_guard
    spec=importlib.util.spec_from_file_location('p183_live_lanequeue',live);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def confirm_job(row):
    job=json.loads(json.dumps(row));job['name']=row['name'].removesuffix('-bracket-B')+'-confirm-A';job['lane']='A';job.pop('depends_on',None)
    argv=job['argv'];argv[argv.index('--lane')+1]='A';argv[argv.index('--output')+1]=str(CONFIRM_OUT)
    return job

def save_decision(row):
    path=DECISION
    try:old=json.loads(path.read_text())
    except (FileNotFoundError,ValueError):old={}
    old.update(row);path.write_text(json.dumps(old,indent=1)+'\n')

def main():
    sys.path.insert(0,str(V5))
    from s1_decision import from_summary
    try:row=bracket_row()
    except (OSError,ValueError,SystemExit):log('ALERT proposal file unreadable or without exactly one lane-B bracket row; nothing armed');return 4
    JOB=row['name']
    log(f'armed: waiting for {JOB}'+(' (dry run)' if DRY else ''))
    deadline=time.time()+3*3600
    while (event:=terminal_event(EVENTS,JOB)) is None:
        if time.time()>deadline:log(f'deadline: no terminal event for {JOB} in 3 h; no confirmation');return 3
        time.sleep(15)
    if event!='DONE':log(f'{JOB} ended {event}; no confirmation');return 2
    if not DRY:time.sleep(30)
    if not SUMMARY.is_file():log(f'no bracket summary at {SUMMARY}; no confirmation');return 2
    try:decision=from_summary(json.loads(SUMMARY.read_text()))
    except (ValueError,KeyError) as e:log(f'bracket summary refused by the decision rule: {e}; no confirmation');return 2
    save_decision(dict(lane_B=dict(decision,summary=str(SUMMARY),summary_sha256_record=sha(SUMMARY))))
    log('lane-B decision: min gain {:+.3f}% slower metadata {:.3f} best control {:.3f} drift {:.3f}% screen_winner={} chain_rule_met={}'.format(
        decision['min_gain_percent'],decision['slower_candidate_rate'],decision['best_control_rate'],decision['control_drift_percent'],decision['screen_winner'],decision['chain_rule_met']))
    if not decision['chain_rule_met']:log('no confirmation (chain rule not met); the bracket summary is the readout');return 0
    busy=endpoints_active()
    if busy:log('ALERT endpoint(s) active: '+' '.join(busy)+'; no confirmation (the driver must wait for p183-win before restoring endpoints)');return 5
    if CONFIRM_OUT.exists():log(f'ALERT {CONFIRM_OUT} already exists; no confirmation (never reuse an output)');return 4
    try:q=queue_module()
    except SystemExit:log('ALERT live lanequeue.py differs from the packet planning snapshot; re-plan before confirming');return 4
    job=confirm_job(row);CONFIRM=job['name'];q.validate(job,'A');pins=q.check_pins(job)
    ldp=q.library_path();planned=q.plan_job(job,ldp)
    need=planned['host_required_available_bytes'];storage=planned['storage_admission']
    log(f'confirm job validated: pins={pins.get("pins") if isinstance(pins,dict) else pins} plan={planned["plan"]} host_required={need} storage_free={storage["root_free_bytes"]}')
    receipt=FN/f'{CONFIRM}-receipt.json'
    if DRY:
        cmd=q.command(job,'<fresh-fault-review>',receipt,ldp)
        log('dry run: would hold PAUSE-A/B, wait for markers/drain/guards/admission/endpoints, run a fresh fault review and launch: '+' '.join(cmd[:4])+' ... '+' '.join(cmd[-14:]))
        return 0
    saved=FN/'p183-pause-saved';hold(L,saved,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()));log('PAUSE-A/B held (contents saved; never deleted)')
    try:
        until=time.time()+1800
        while any(p.exists() for p in (L/'inflight-A.json',L/'inflight-B.json',COORD/'active-lane-A.json',COORD/'active-lane-B.json')):
            if time.time()>until:log('ALERT lane still inflight/active after 30 min; no confirmation');return 6
            time.sleep(10)
        while (w:=q.drain_spacing_deadline()-time.monotonic())>0:time.sleep(min(1.0,max(0.0,w)))
        backend=q.Backend();faults=backend.guards('A')
        avail=q.mem_available()
        if avail<need+1024**3:log(f'ALERT MemAvailable {avail} below {need}+1 GiB; no confirmation');return 7
        if shutil.disk_usage('/').free<25_000_000_000+1_200_000_000:log('ALERT root free below the 25 GB floor + writes; no confirmation');return 7
        busy=endpoints_active()
        if busy:log('ALERT endpoint(s) became active: '+' '.join(busy)+'; no confirmation');return 5
        review=backend.review(job,L)
        cmd=q.command(job,review,receipt,ldp)
        log(f'faults={faults} review={review}; launching {CONFIRM} on cards 0+1')
        try:rc=subprocess.run(cmd,stdin=subprocess.DEVNULL,timeout=2*3600).returncode
        except subprocess.TimeoutExpired:
            log('ALERT confirmation client deadline (2 h); the unit is left to its own watchdog; PAUSE files restored to their prior contents');return 9
        log(f'{CONFIRM} unit returned rc={rc}')
        summary=CONFIRM_OUT/'bracket-summary.json'
        if rc!=0 or not summary.is_file():log('ALERT confirmation did not produce a passed summary');return 8
        d=from_summary(json.loads(summary.read_text()))
        save_decision(dict(lane_A=dict(d,summary=str(summary),summary_sha256_record=sha(summary))))
        log('lane-A decision: min gain {:+.3f}% slower metadata {:.3f} chain_rule_met={}; record bundle (packet136 + dense_scales=metadata, fresh chain on cards 0+1) is the next packet'.format(
            d['min_gain_percent'],d['slower_candidate_rate'],d['chain_rule_met']))
        return 0
    finally:
        restore(L,saved);log('PAUSE files restored or kept (never deleted)')

if __name__=='__main__':raise SystemExit(main())
