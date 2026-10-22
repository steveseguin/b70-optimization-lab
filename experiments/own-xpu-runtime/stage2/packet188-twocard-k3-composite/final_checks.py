#!/usr/bin/env python3
"""Packet188 final checks; --ready writes READY-FOR-DEVICE.json last, then re-runs the pin guard.

Default (verification only):
  * the CPU seal verifies and every sealed gate receipt passed with unchanged sources;
  * packet188 receipts carry their required results: rebuilt entry TUs (8 compiler runs, 0 warnings,
    78 parent objects pinned), production-shape gate (V3 record-selection capture and census identity with
    packet186; the k3 storage in every start order with identical captures; layer-26 kernels = rank 1's;
    image capture unchanged; census delta +1,129,070,858 / 0 B), k3 state gate (engine: every trim
    combination byte-identical; two-rank miniature brackets), admission, the s188 rule tested on real
    packet186/packet187 device data;
  * package-rows/check-queue-rows receipts passed; the proposal file equals its sealed mirror;
  * drain-fix scan: every UNFIXED copy is a vendored historical v4-lanes file under lineage-inputs,
    and an import trace of the real bracket entry (plan mode) loads only the packet's FIXED drain code.
--ready: all of the above, then READY-FOR-DEVICE.json (with a `checks` path->sha256 map so the pin
  guard walks every receipt), then the live pin guard (check_job on every proposal row) and a direct
  classification of every pin in the closure; any cross-packet mutable pin withdraws READY.
Writes v5/evidence/final-checks.json and, with --ready, v5/evidence/final-pin-guard.json.
"""
import argparse,datetime,hashlib,importlib.util,json,os,re,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];V5=HERE/'v5';EV=V5/'evidence'
LQ=HERE.parents[1]/'ops/lane-queue';NAME='proposed-p188-two-card-B.txt'
SEALED=('build','full-shape','k3-state','admission','analysis','controller','safety','exec-limits','loader')
READY_GATES=('entry-gate','launch-limits','worker-gate','report-gate','queue-plan','pin-guard')
EXTRA=('package-rows','check-queue-rows')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name):return json.loads((EV/(name+'.json')).read_text())
def rel(p):return str(Path(p).relative_to(ROOT))

def drain_scan():
    r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/check_drain_fix.py'),str(HERE)],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
    rows=[l.split(None,1) for l in r.stdout.splitlines() if l.startswith(('FIXED','UNFIXED'))]
    unfixed=[p for k,p in rows if k=='UNFIXED']
    vendored=[p for p in unfixed if '/lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/screen/v4-lanes/' in p]
    assert unfixed==vendored,'UNFIXED drain copy outside the vendored historical v4-lanes tree: '+str(sorted(set(unfixed)-set(vendored)))
    code=('import sys,runpy,json,os\nsys.path.insert(0,%r)\nsys.argv=["bracket_job.py","--variant","v3k","--kind","bracket","--index","2","--lane","B","--output",%r,"--plan"]\n'
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
    b=load('build');assert b['rebuilt'] is True and b['compiler_runs']==8 and b['warning_lines']==0 and b['inherited_parent_objects']==78
    assert b['binary_sha256']==seal['binary_sha256']==sha(V5/'build/device/own-rt-iq3')
    shape=load('full-shape');assert shape['census_delta_bytes_per_rank']==[1129070858,0] and shape['draft_commands_identical']
    assert shape['v3_capture_identity_with_packet186'] is True and shape['v3_census_identity_with_packet186'] is True
    assert len(shape['startup_runs'])==12 and len(shape['runs'])==10 and {r['result']['native_refusals'] for r in shape['runs']}=={21}
    ic=shape['image_census'];assert len({(v['capture_bytes'],v['extents']) for v in ic.values()})==1
    L=shape['launches'];assert L['rank0_layer26_commands']>0 and L['rank0_k3_commands']==L['rank0_v3_commands']+L['rank0_layer26_commands'] and L['rank1_identical']
    st=load('k3-state');assert len(st['engine_runs'])==14 and all(r['negatives']==2 and r['cases']>=65 for r in st['engine_runs']) and st['pipeline']['requests']>=60
    assert st['pipeline']['hits']>0 and st['pipeline']['misses']>0 and st['pipeline']['no_guess']>0
    canon={r['selection']:r['canonical_sha256'] for r in st['engine_runs']}
    assert len({canon[m] for m in ('k3','k3kio','k3prep','k3trims')})==1 and canon['k3p']==canon['k3trimsp'],'trim byte identity'
    adm=load('admission');assert adm['census_delta_bytes_per_rank']==[1129070858,0] and adm['host_required_available_bytes']['k3']==108797048558
    ana=load('analysis');assert ana['boundary_scopes_mandatory_every_cycle'] and ana['staged_view_refuses_synchronous_token_history'] and len(ana['tests'])==3
    # Real inputs read in place (packet186/187 device evidence, packet49 oracle): the map lives outside the pin guard's
    # walk (no device row reads these files); its digest is sealed in analysis.json and every file is re-hashed here.
    inputs=json.loads((ROOT/ana['real_inputs_receipt']).read_text())['files']
    assert len(inputs)==ana['real_inputs_read_in_place'] and hashlib.sha256(json.dumps(inputs,sort_keys=True,separators=(',',':')).encode()).hexdigest()==ana['real_inputs_map_sha256']
    assert all(sha(ROOT/k)==v for k,v in inputs.items()),'a real analysis input changed where it is retained'
    ctl=load('controller');assert {r['test'] for r in ctl['rows']}=={'probe','v3'}
    live,mirror=LQ/NAME,HERE/'proposals'/NAME;assert sha(live)==sha(mirror)==load('package-rows')['proposal_sha256']
    assert load('queue-plan')['sha256']==sha(live)
    drain=drain_scan()
    pauses={p.name:sha(p) for p in sorted(LQ.glob('PAUSE-*'))};queues={p.name:sha(p) for p in sorted(LQ.glob('queue-*.txt'))}
    row=dict(passed=True,device_executed=False,queued=False,cpu_seal_sha256=sha(V5/'cpu-seal.json'),binary_sha256=seal['binary_sha256'],
             receipts=out,drain=drain,rebuilt=True,census_delta_bytes_per_rank=shape['census_delta_bytes_per_rank'],
             launches={k:v for k,v in shape['launches'].items() if not k.endswith('_sites')},
             lane_state_observed=dict(pause_files=sorted(pauses),queue_files=sorted(queues),note='observed only; never written by preparation'),
             proposal=rel(live),proposal_sha256=sha(live))
    (EV/'final-checks.json').write_text(json.dumps(row,indent=1)+'\n')
    return row

def pin_guard():
    spec=importlib.util.spec_from_file_location('p188_pin_guard_live',LQ/'pin_guard.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
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
    print('final checks PASS: seal',row['cpu_seal_sha256'][:16],'binary',row['binary_sha256'][:16],'(rebuilt entry TUs)')
    if not a.ready:return
    commit=subprocess.run(['git','-C',str(ROOT),'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()
    checks={rel(EV/(n+'.json')):sha(EV/(n+'.json')) for n in SEALED+READY_GATES+EXTRA+('final-checks',)}
    checks[rel(V5/'cpu-seal.json')]=sha(V5/'cpu-seal.json')
    marker=dict(schema='packet188.ready-for-device.v1',commit=commit,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        passed=True,ready_for_device=True,device_executed=False,queued=False,lane='B',arithmetic='iq3-p49-split32-v1',
        cpu_seal_sha256=sha(V5/'cpu-seal.json'),cpu_gate_sha256={n:sha(EV/(n+'.json')) for n in READY_GATES},
        proposal_sha256s={rel(LQ/NAME):sha(LQ/NAME)},checks=checks,
        device_quality_pending=True,device_performance_pending=True,binary_sha256=row['binary_sha256'],
        measurement=('k3+trims (GDN layer 26 joins the verified-token boundary on rank 0, rank 1 from QSA layer 27; kernel_io=kernel; '
                     'rank0_prepare=async) vs the V3 record line (packet187 selection fresh, and V3 views of the same k3 storage in-load)'),
        admission=('three rows on one lane, each depending on the previous: k3+trims smoke 12x64 exact with first-request data proof; '
                   'fresh-load V3 control (packet187 record selection); one-load V3/k3+trims/V3/k3+trims/V3 bracket'),
        decision=('s188_decision in row 2: screen winner iff min k3+trims >= 1.005 x every V3 view (fresh + 3 in-load), exact, identical '
                  'proposals, V3 drift <= 3%; chain rule iff also >= 1.02 x every V3 view AND >= 61.873 tok/s (1.02 x 60.659520); kill '
                  'rules recorded (k3 hit saving < 0.25 ms, Bd > D on > 5% of hits, trims remove < 0.105 ms of A)'),
        win_path=None,record_eligible=False,
        last_packet_write=True)
    ready.write_text(json.dumps(marker,indent=2)+'\n')
    try:
        g=pin_guard();assert g['cross_packet_mutable_pins']==0 and g['ready_in_closure'],g
    except BaseException as e:
        withdrawn=EV/f'withdrawn-ready-{int(time.time())}.json';ready.rename(withdrawn)
        (EV/'final-pin-guard.json').write_text(json.dumps(dict(passed=False,error=repr(e)[:4000],withdrawn=rel(withdrawn)),indent=1)+'\n')
        sys.exit('READY withdrawn: '+repr(e)[:400])
    (EV/'final-pin-guard.json').write_text(json.dumps(dict(passed=True,device_executed=False,ready_sha256=sha(ready),**g),indent=1)+'\n')
    print('READY written; live pin guard PASS on all three rows; collected pins',g['collected_pins'],'cross-packet mutable',g['cross_packet_mutable_pins'],g['classes'])

if __name__=='__main__':main()
