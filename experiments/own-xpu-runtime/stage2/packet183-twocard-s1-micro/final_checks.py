#!/usr/bin/env python3
"""Packet183 final checks; --ready writes READY-FOR-DEVICE.json last, then re-runs the pin guard.

Default (verification only):
  * the CPU seal verifies and every sealed gate receipt passed with unchanged sources;
  * S1 receipts carry their required results: byte gate (lanes/submissions/mutation proofs, GNU+Intel),
    real-weight census (0 non-finite d, 0 word mismatches), production-shape coverage (S1 sites on
    both ranks and the draft head; non-S1 commands byte-identical), expected gain >= +2% (floor);
  * package-rows/check-queue-rows/waiter-rehearsal receipts passed; the proposal file equals its
    sealed mirror; the waiter files are the rehearsed bytes;
  * drain-fix scan: every UNFIXED copy is a vendored historical v4-lanes file under lineage-inputs,
    and an import trace of the real bracket entry (plan mode) loads only the packet's FIXED drain code.
--ready: all of the above, then READY-FOR-DEVICE.json (with a `checks` path->sha256 map so the pin
  guard walks every receipt), then the live pin guard (check_job on both proposal rows) and a direct
  classification of every pin in the closure; any cross-packet mutable pin withdraws READY.
Writes v5/evidence/final-checks.json and, with --ready, v5/evidence/final-pin-guard.json.
"""
import argparse,datetime,hashlib,importlib.util,json,os,re,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];V5=HERE/'v5';EV=V5/'evidence'
LQ=HERE.parents[1]/'ops/lane-queue';NAME='proposed-p183-two-card-B.txt'
SEALED=('build','s1-bytes','real-census','full-shape','admission','analysis','submission-rehearsal','controller','safety','exec-limits','loader','switch','expected-gain')
READY_GATES=('entry-gate','launch-limits','worker-gate','report-gate','queue-plan','pin-guard')
EXTRA=('package-rows','check-queue-rows','waiter-rehearsal')
CHAIN=('chain/p183_win.py','chain/p183-win.sh','chain/rehearse_waiter.py','chain/ARMING.md')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name):return json.loads((EV/(name+'.json')).read_text())
def rel(p):return str(Path(p).relative_to(ROOT))

def drain_scan():
    r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/check_drain_fix.py'),str(HERE)],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
    rows=[l.split(None,1) for l in r.stdout.splitlines() if l.startswith(('FIXED','UNFIXED'))]
    unfixed=[p for k,p in rows if k=='UNFIXED']
    vendored=[p for p in unfixed if '/lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/screen/v4-lanes/' in p]
    assert unfixed==vendored,'UNFIXED drain copy outside the vendored historical v4-lanes tree: '+str(sorted(set(unfixed)-set(vendored)))
    code=('import sys,runpy,json,os\nsys.path.insert(0,%r)\nsys.argv=["bracket_job.py","--variant","metadata","--kind","bracket","--lane","B","--output",%r,"--plan"]\n'
          'rc=None\ntry: runpy.run_path(%r,run_name="__main__")\nexcept SystemExit as e: rc=e.code\n'
          'mods=sorted({getattr(m,"__file__","") or "" for m in list(sys.modules.values())})\n'
          'sys.stderr.write("TRACE="+json.dumps(dict(rc=rc,mods=[m for m in mods if "drain" in m or "conditions" in m or "v4-lanes" in m]))+"\\n")\n')%(str(V5),str(EV/'import-trace-plan-out'),str(V5/'bracket_job.py'))
    t=subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
    trace=json.loads(next(l[6:] for l in t.stderr.splitlines() if l.startswith('TRACE=')))
    assert trace['rc'] in (0,None),trace;loaded=trace['mods']
    assert loaded and all(m.startswith(str(V5)) for m in loaded) and not any('v4-lanes' in m for m in loaded),loaded
    return dict(scan_rc=r.returncode,fixed=[p for k,p in rows if k=='FIXED'],unfixed_vendored_historical=vendored,
                entry_plan_import_trace=dict(rc=trace['rc'],drain_and_condition_modules=[rel(m) for m in loaded]))

def verify():
    sys.path.insert(0,str(V5))
    from cpu_seal import verify as seal_verify,check_sources
    seal=seal_verify()
    out={}
    for name in SEALED+READY_GATES+EXTRA:
        row=load(name);assert row['passed'] is True and row['device_executed'] is False,name
        if row.get('sources'):check_sources(row['sources'])
        out[name]=sha(EV/(name+'.json'))
    b=load('s1-bytes');assert len(b['runs'])==4 and all(r['mutation_checks']==18 and r['lane_checks']>100000 and r['submission_checks']==80 for r in b['runs'])
    c=load('real-census')['census'];assert c['nonfinite_d']==0 and c['word_mismatches']==0 and c['groups']>200_000_000 and c['lane_checks']>1_000_000
    cov=load('full-shape')['s1_coverage']
    assert cov['rank0']['converted_total']>=80 and cov['rank1']['converted_total']>=80 and cov['rank1']['converted'].get('logits')==1 and cov['rank1']['draft']['converted']==1
    gain=load('expected-gain');assert gain['scenarios']['floor']['gain_percent']>=2.0
    w=load('waiter-rehearsal');assert all(r.get('passed',True) for r in w['cases']) and w['pause_files']['passed']
    for f in CHAIN:assert (HERE/f).is_file(),f
    live,mirror=LQ/NAME,HERE/'proposals'/NAME;assert sha(live)==sha(mirror)==load('package-rows')['proposal_sha256']
    assert load('queue-plan')['sha256']==sha(live)
    drain=drain_scan()
    pauses={p.name:sha(p) for p in sorted(LQ.glob('PAUSE-*'))};queues={p.name:sha(p) for p in sorted(LQ.glob('queue-*.txt'))}
    row=dict(passed=True,device_executed=False,queued=False,cpu_seal_sha256=sha(V5/'cpu-seal.json'),binary_sha256=seal['binary_sha256'],
             receipts=out,drain=drain,expected_gain_floor_percent=gain['scenarios']['floor']['gain_percent'],
             expected_gain_proportional_percent=gain['scenarios']['proportional']['gain_percent'],
             coverage={r:cov[r]['converted'] for r in ('rank0','rank1')},draft_head_converted=cov['rank1']['draft']['converted'],
             lane_state_observed=dict(pause_files=sorted(pauses),queue_files=sorted(queues),note='observed only; never written by preparation'),
             proposal=rel(live),proposal_sha256=sha(live))
    (EV/'final-checks.json').write_text(json.dumps(row,indent=1)+'\n')
    return row

def pin_guard():
    spec=importlib.util.spec_from_file_location('p183_pin_guard_live',LQ/'pin_guard.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    rows=[json.loads(l) for l in (LQ/NAME).read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]
    checks=[m.check_job(r) for r in rows];assert all(c['passed'] for c in checks)
    pins,manifests=m.collect_pins(HERE)
    oracle={(p,h) for p,h,s in pins if s.name=='oracle-binding.json'}
    classes={};cross=[]
    for p,h,s in pins:
        if p.is_relative_to(HERE) and p.resolve().is_relative_to(HERE.resolve()):key='packet-private'
        else:
            reason=m.immutable_reason(p,h,HERE,oracle,m.STAGE)
            if not reason:cross.append(str(p));key='CROSS-PACKET MUTABLE'
            else:key=reason
        classes[key]=classes.get(key,0)+1
    return dict(check_job=[dict(job=r['name'],passed=c['passed'],pins=c.get('pins')) for r,c in zip(rows,checks)],
                collected_pins=len(pins),manifests=len(manifests),ready_in_closure=any(Path(x).name=='READY-FOR-DEVICE.json' for x in manifests),
                classes=classes,cross_packet_mutable_pins=len(cross),cross_examples=cross[:10])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ready',action='store_true');a=ap.parse_args()
    ready=HERE/'READY-FOR-DEVICE.json'
    if a.ready and ready.exists():sys.exit('READY-FOR-DEVICE.json already exists; withdraw it first')
    row=verify()
    print('final checks PASS: seal',row['cpu_seal_sha256'][:16],'binary',row['binary_sha256'][:16],'expected gain floor %.2f%%'%row['expected_gain_floor_percent'])
    if not a.ready:return
    commit=subprocess.run(['git','-C',str(ROOT),'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()
    checks={rel(EV/(n+'.json')):sha(EV/(n+'.json')) for n in SEALED+READY_GATES+EXTRA+('final-checks',)}
    checks.update({rel(HERE/f):sha(HERE/f) for f in CHAIN})
    checks[rel(V5/'cpu-seal.json')]=sha(V5/'cpu-seal.json')
    marker=dict(schema='packet183.ready-for-device.v1',commit=commit,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        passed=True,ready_for_device=True,device_executed=False,queued=False,lane='B',arithmetic='iq3-p49-split32-v1',
        cpu_seal_sha256=sha(V5/'cpu-seal.json'),cpu_gate_sha256={n:sha(EV/(n+'.json')) for n in READY_GATES},
        proposal_sha256s={rel(LQ/NAME):sha(LQ/NAME)},checks=checks,
        device_quality_pending=True,device_performance_pending=True,binary_sha256=row['binary_sha256'],
        lever='S1 dense-scales (packet177 PLAN section 5): Q6_K dense lanes read the retained fp16 d + int8 sub-scales (18 B/256 weights) instead of FP32 words (64 B/256)',
        admission='metadata smoke first (12 x 64 + incident64, exact); bracket A/B/A/B/A requires that smoke and 13/13 exact per view with identical draft proposals',
        win_path='chain/p183_win.py (prepared, NOT armed; chain/ARMING.md): lane-A confirmation bracket only on a lane-B chain-rule win',
        last_packet_write=True)
    ready.write_text(json.dumps(marker,indent=2)+'\n')
    try:
        g=pin_guard();assert g['cross_packet_mutable_pins']==0 and g['ready_in_closure'],g
    except BaseException as e:
        withdrawn=EV/f'withdrawn-ready-{int(time.time())}.json';ready.rename(withdrawn)
        (EV/'final-pin-guard.json').write_text(json.dumps(dict(passed=False,error=repr(e)[:4000],withdrawn=rel(withdrawn)),indent=1)+'\n')
        sys.exit('READY withdrawn: '+repr(e)[:400])
    (EV/'final-pin-guard.json').write_text(json.dumps(dict(passed=True,device_executed=False,ready_sha256=sha(ready),**g),indent=1)+'\n')
    print('READY written; live pin guard PASS on both rows; collected pins',g['collected_pins'],'cross-packet mutable',g['cross_packet_mutable_pins'],g['classes'])

if __name__=='__main__':main()
