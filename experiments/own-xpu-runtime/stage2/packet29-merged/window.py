#!/usr/bin/env python3
"""Packet29 admitted device windows. This file is prepared only; CPU tests use fake children."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import struct
import subprocess
import time
from window_safety import environment_gate, memory_snapshot, memory_admission
from k2_summary import summarize
from merge_dispatch import validate as validate_dispatch, covered_by_k1, REGISTRY, SECTIONS
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
spec=importlib.util.spec_from_file_location('packet2_window',HERE.parent/'packet2/tests/device_window.py')
p2=importlib.util.module_from_spec(spec);spec.loader.exec_module(p2)
def helper_command(command):
 return ['nice','-n','19','ionice','-c','3']+list(map(str,command))

def sha(path):
 return subprocess.check_output(helper_command(['sha256sum','--',path]),text=True,timeout=120).split()[0]

def journal(cursor=None):
 args=['journalctl','-k','--no-pager','--show-cursor']
 args+=['--after-cursor',cursor] if cursor else ['-n','200']
 result=subprocess.run(helper_command(args),capture_output=True,text=True,timeout=2)
 if result.returncode or result.stderr.strip():raise RuntimeError('kernel journal unavailable: '+result.stderr)
 lines=result.stdout.splitlines();cursors=[s[len('-- cursor: '):] for s in lines if s.startswith('-- cursor: ')]
 if not cursors and not cursor:raise RuntimeError('missing journal boundary')
 return '\n'.join(s for s in lines if not s.startswith('-- cursor: '))+'\n',cursors[-1] if cursors else cursor

def priority_gate(requested):
 actual=os.getpriority(os.PRIO_PROCESS,0)
 require(0<=requested<=19 and actual==requested,'wrapper nice must equal requested --native-nice (default 19)')
 require(os.environ.get('OMP_NUM_THREADS')=='2','OMP_NUM_THREADS=2 required')
 return dict(wrapper_nice=actual,native_nice=requested,helper_nice=19)

AUTHORITY='iq3-p17-detmath-v2'
SCHEMA='own-runtime.iq3.packet29.window.v1'
CONFIG={
 'K0':dict(cards=2,kind='jit'),
 'K1a':dict(cards=1,kind='fixtures'),
 'K1b':dict(cards=1,kind='fixtures'),
 'K2':dict(cards=1,kind='profile'),
 'W0':dict(cards=2,kind='canary'),
 'W1':dict(cards=1,kind='model',memory='layer-streaming',count=8,steps=8,stage='first-token',gemv='r5',timing='token',context=256),
 'W2':dict(cards=2,kind='model',memory='resident',count=64,steps=8,stage='decode',gemv='r5',timing='token',context=256),
 'W2m':dict(cards=2,kind='model',memory='resident',count=64,steps=8,stage='decode',gemv='r5',timing='token',context=256),
 'W2x':dict(cards=2,kind='model',memory='resident',count=64,steps=8,stage='decode',gemv='r5',timing='token',context=256),
 'W2c':dict(cards=2,kind='model',memory='resident',count=64,steps=8,stage='decode',gemv='r5',timing='class',context=256),
}
EXPECTED_SECONDS={'K0':30.,'K1a':1800.,'K1b':1800.,'K2':1800.,'W0':30.,'W1':1900.,'W2':1900.,'W2m':1900.,'W2c':1900.,'W2x':1900.}
JIT_SECONDS=17.

def deadline_record(window,seconds):
 expected=EXPECTED_SECONDS[window]+JIT_SECONDS
 return dict(expected_work_seconds=EXPECTED_SECONDS[window],first_jit_estimate_seconds=JIT_SECONDS,
  expected_total_seconds=expected,expectation_enforced=False,watchdog_seconds=seconds,
  watchdog_estimate_ratio=seconds/expected,submission_budget_seconds=None if window=='K0' else .1 if window=='W0' else 4.,
  submission_budget_measured=window in ('K1a','K1b','K2','W0','W2c'),
  driver_job_timeout_seconds=5.,cooperative_drain_seconds=60.)

def watchdog_seconds(window,seconds=None):
 lower=max(300,math.ceil(4*(EXPECTED_SECONDS[window]+JIT_SECONDS)))
 value=(600 if window in ('K0','W0') else 10800) if seconds is None else seconds
 require(lower<=value<= (1800 if window in ('K0','W0') else 10800),f'{window} watchdog must be {lower}..'+str(1800 if window in ('K0','W0') else 10800)+' seconds')
 return value
def read(path):
    return json.loads(path.read_text())

def require(test, reason):
    if not test:
        raise ValueError(reason)

def safe_teardown(run, cards):
    rows = run.get('teardown', [])
    coverage = len(rows) == cards or (len(rows) == 1 and run.get('owner_cards') == cards)
    return coverage and all(r.get('safe_to_exit') is True and
        r.get('live_bytes') == 0 and r.get('in_flight') == 0 for r in rows)

def fixtures(root, steps):
    hashes = {}
    for step in range(1, steps + 1):
        for layer in range(48):
            rel = f'step{step}/layer-{layer:02}.bf16'
            path = root / rel
            require(path.is_file() and path.stat().st_size == 20480, 'fixture missing/wrong size: ' + str(path))
            hashes[rel] = sha(path)
    return hashes

def oracle_gate(path, input_tokens, steps, count):
    require(path is not None, 'every window requires --oracle v2 CPU prompt root')
    meta = read(path / 'arithmetic.json')
    require(meta.get('arithmetic') == AUTHORITY, 'oracle arithmetic identity mismatch')
    require(meta == read(HERE.parent / 'packet17-detmath/arithmetic.json'), 'oracle differs from v2 arithmetic authority')
    for name, digest in meta.get('arithmetic_sources', {}).items():
        require(sha(ROOT / name) == digest, 'oracle arithmetic source changed: ' + name)
    require(read(path / 'input.json').get('tokens') == input_tokens, 'oracle prompt mismatch')
    tokens = read(path / 'result.json').get('tokens', [])
    require(len(tokens) >= count, 'oracle token coverage missing')
    return fixtures(path, steps), tokens[:count]

def supervise(child, seconds, cursor, kernel, latch_fault, persist, requested,
              journal=journal, now=time.monotonic, sleep=time.sleep, drain_seconds=60):
    """Every poll/drain has a deadline; only one SIGTERM, never hard-kill."""
    start = now()
    sent = None
    while True:
        try:
            fresh, cursor = journal(cursor)
            kernel.write(fresh)
            kernel.flush()
            if p2.FAULT.search(fresh):
                requested.append('new GPU fault signature')
        except Exception as error:
            requested.append('kernel journal unavailable: ' + str(error))
        if now() - start >= seconds:
            requested.append('window deadline')
        if requested and sent is None:
            latch_fault(requested[0])
            if child.poll() is None:
                child.send_signal(signal.SIGTERM)
            sent = now()
            persist()
        if child.poll() is not None:
            break
        if sent is not None and now() - sent >= drain_seconds:
            requested.append('cooperative drain deadline; child retained for coordinator')
            latch_fault(requested[-1])
            return dict(returncode=None, child_still_running=True, elapsed_seconds=now()-start, sigterm_sent=True)
        sleep(.25)
    # Five seconds of postflight, including journal subprocess time (2s bound).
    deadline = now() + 5
    while now() < deadline:
        sleep(min(.25, deadline - now()))
        try:
            fresh, cursor = journal(cursor)
            kernel.write(fresh)
            if p2.FAULT.search(fresh):
                requested.append('postflight GPU fault signature')
        except Exception as error:
            requested.append('postflight journal unavailable: ' + str(error))
    if requested:
        latch_fault(requested[0])
    return dict(returncode=child.returncode, child_still_running=False, elapsed_seconds=now()-start, sigterm_sent=sent is not None)

def value_statistics(actual, expected):
    """Interpret little-endian BF16 bytes without loading any device library."""
    if not actual.is_file() or not expected.is_file():
        return {'missing_actual': not actual.is_file(), 'missing_oracle': not expected.is_file()}
    a, b = actual.read_bytes(), expected.read_bytes()
    if len(a) % 2 or len(b) % 2:
        return dict(actual_bytes=len(a), oracle_bytes=len(b), malformed_bf16=True)
    av = [x[0] for x in struct.iter_unpack('<H', a)]
    bv = [x[0] for x in struct.iter_unpack('<H', b)]
    f = lambda x: struct.unpack('<f', struct.pack('<I', x << 16))[0]
    differences = [(i, x, y) for i, (x, y) in enumerate(zip(av, bv)) if x != y]
    finite = [abs(f(x)-f(y)) for _, x, y in differences if math.isfinite(f(x)) and math.isfinite(f(y))]
    first = differences[0] if differences else None
    return dict(actual_values=len(av), oracle_values=len(bv), unequal_values=len(differences)+abs(len(av)-len(bv)),
                finite_max_abs_difference=max(finite, default=0), finite_mean_abs_difference=sum(finite)/len(finite) if finite else 0,
                nonfinite_pairs=sum(not math.isfinite(f(x)) or not math.isfinite(f(y)) for _, x, y in differences),
                first_value_index=first[0] if first else None,
                first_actual_bf16=f'0x{first[1]:04x}' if first else None,
                first_oracle_bf16=f'0x{first[2]:04x}' if first else None)

def compare_layers(actual_root, oracle_root, expected_hashes):
    rows = []
    first = None
    actual = {}
    for name, digest in expected_hashes.items():
        path = actual_root / name
        observed = sha(path) if path.is_file() else None
        actual[name] = observed
        row = dict(fixture=name, step=int(name.split('/')[0][4:]), layer=int(name.split('-')[1][:2]),
                   exact=observed == digest, sha256=observed, oracle_sha256=digest)
        rows.append(row)
        if not row['exact'] and first is None:
            first = dict(row, site='layer_output', site_localization='earliest retained layer boundary; inner site not retained',
                         value_statistics=value_statistics(path, oracle_root / name) if oracle_root else {'oracle_path_unavailable': True})
    return dict(layers=rows, layer_matches=sum(row['exact'] for row in rows), layer_total=len(rows),
                first_differing_layer=first, layer_hashes=actual)

def ldd_preflight(binary, runner=subprocess.run):
    # Loader inspection only: never invoke the device program or discovery.
    result = runner(helper_command(['ldd', str(binary)]), capture_output=True, text=True, timeout=10)
    require(result.returncode == 0 and 'not found' not in result.stdout + result.stderr,
            'ldd dependency preflight failed: ' + result.stdout + result.stderr)
    return dict(argv=helper_command(['ldd', str(binary)]), returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)

def token_diagnostics(observed, expected):
    first = next((i + 1 for i in range(max(len(observed), len(expected)))
                  if i >= len(observed) or i >= len(expected) or observed[i] != expected[i]), None)
    return dict(tokens=observed, token_matches=sum(a == b for a, b in zip(observed, expected)),
                token_total=len(expected), first_differing_token=first)

def canary_receipt_gate(run):
    require(run.get('schema') == 'own-runtime.iq3.packet18.canary.v2' and
            run.get('passed') is True and run.get('device_executed') is True and
            run.get('round_trips') == 100 and run.get('kernels_per_card') == 1000 and
            run.get('token_sequence') is True and safe_teardown(run, 2),
            'W0 canary coverage/teardown incomplete')
    require(0 < run.get('owned_device_bytes', 0) < 16*1024**2 and
            run.get('submission_budget_passed') is True and
            0 < run.get('max_submission_ns', 0) < 100000000,
            'W0 canary memory/submission bounds failed')
    for field in ('wall_ms', 'startup_jit_ms', 'device_work_ms', 'work_wall_ms', 'teardown_ms'):
        value = run.get(field)
        require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                'W0 invalid timing: ' + field)


def cpu_gate(path,build):
 require(sha(path)==build.get('cpu_tests_sha256'),'CPU receipt changed since build')
 row=read(path)
 require(row.get('passed') is True and row.get('device_executed') is False and row.get('binary_sha256')==build.get('artifacts_sha256',{}).get('host/own-rt-iq3'),'CPU gate/binary identity failed')
 real=row.get('real_model',{}).get('all_new',{})
 require(real.get('passed') is True and real.get('layer_matches')==384 and real.get('layer_total')==384 and real.get('token_matches',0)>=8 and len(real.get('tokens',[]))>=8,'CPU all-new 384-layer/eight-token oracle gate incomplete')
 fresh=path.parent/'real-eight.json'
 require(sha(fresh)==row.get('extra_eight_token_oracle_sha256') and read(fresh).get('binary_sha256')==row.get('binary_sha256') and read(fresh).get('passed') is True,'fresh all-new CPU oracle receipt mismatch')


def prerequisite(path,name,identity):
 require(path is not None,'missing --'+name.lower()+' receipt')
 row=read(path)
 require(row.get('schema')==SCHEMA and row.get('window')==name and row.get('passed') is True,'prerequisite failed: '+name)
 for key in ('boot_id','artifacts_sha256','environment'):
  require(row.get(key)==identity.get(key),'prerequisite '+name+' '+key+' changed')
 native=path.parent/'run/receipt.json'
 require(sha(native)==row.get('native_receipt_sha256') and read(native).get('passed') is True,'prerequisite native receipt changed: '+name)
 return row


def k0_gate(path,identity,cfg):
 row=prerequisite(path,'K0',identity)
 require(set(range(cfg['card'],cfg['card']+cfg['cards']))<=set(range(row['card'],row['card']+row['cards'])),'K0 missing admitted card')
 return row


def sequential_teardown(row,count):
 rows=row.get('teardown',[])
 return row.get('owner_cards')==1 and len(rows)==count and all(r.get('safe_to_exit') is True and r.get('live_bytes')==0 and r.get('in_flight')==0 for r in rows)


def fixture_receipt_gate(root,build):
 row=read(root/'receipt.json')
 require(row.get('schema')=='packet26.fixtures.v1' and row.get('passed') is True and row.get('device_executed') is True and row.get('reference_exact') is True and row.get('packet18_exact') is True,'K1 exactness incomplete')
 require(row.get('fixtures',0)>=72 and all(type(row.get(k)) is int and row[k]>0 for k in ('odd_lengths','ties','nan_routes')),'K1 fixture/edge coverage incomplete')
 require(sequential_teardown(row,4),'K1 unsafe/missing sequential-owner teardown')
 require(type(row.get('max_submission_ns')) in (int,float) and 0<row['max_submission_ns']<4e9,'K1 submission budget failed')
 output=root/'output.bin'
 require(sha(output)==row.get('output_sha256')==build.get('nongemv_fixture_host_sha256'),'K1 bytes differ from host fixtures')
 return row


def k1_gate(first,second,identity,build):
 a=prerequisite(first,'K1a',identity);b=prerequisite(second,'K1b',identity)
 require(a['card']==b['card'],'K1 card changed')
 require(a.get('candidate_dispatch_sha256')==b.get('candidate_dispatch_sha256'),'K1 candidate dispatch changed')
 require(a.get('pid') and b.get('pid') and a['pid']!=b['pid'],'K1 requires two fresh owner processes')
 require(b.get('k1a_sha256')==sha(first),'K1b not linked to K1a')
 fixture_receipt_gate(first.parent/'run',build);fixture_receipt_gate(second.parent/'run',build)
 return a,b


def k2_gate(path,identity,dispatch):
 row=prerequisite(path,'K2',identity)
 require(dispatch is not None and sha(dispatch)==row.get('dispatch_sha256'),'measured dispatch changed or missing')
 require(sha(path.parent/'run/events.jsonl')==row.get('events_sha256'),'K2 events changed')
 require(sha(path.parent/'run/summary.json')==row.get('summary_sha256'),'K2 summary changed')
 return row


def native_command(binary,cfg,input_root,model_dir,oracle,out,seconds,dispatch=None,native_nice=19):
 cmd=[str(binary),'--authorized-device-window','--native-nice',str(native_nice),'--card',str(cfg['card']),'--cards',str(cfg['cards']),
  '--timing',cfg['timing'],'--memory',cfg['memory'],'--stage',cfg['stage'],'--nongemv','parallel','--gemv',cfg['gemv'],
  '--prompt-tokens',str((input_root/'tokens.txt').resolve()),'--max-new',str(cfg['count']),'--context',str(cfg['context']),
  '--plan',str((input_root/'plan.tsv').resolve()),'--identity',str((input_root/'identity.tsv').resolve()),'--model-dir',model_dir,
  '--oracle',str(oracle.resolve()),'--output',str(out/'run'),'--seconds',str(seconds),'--wait-seconds','60']
 if dispatch is not None:cmd+=['--dispatch',str(dispatch.resolve())]
 return cmd


def compare_run(out,cfg,expected_hashes,expected_tokens,oracle_root,diagnostics):
 row=read(out/'run/receipt.json')
 if 'native_nice' in diagnostics:require(row.get('native_nice')==row.get('observed_nice')==diagnostics['native_nice'],'native priority receipt differs from wrapper')
 require(row.get('schema')=='own-runtime.iq3.packet26.run.v1' and row.get('device_executed') is True and row.get('arithmetic')==AUTHORITY and row.get('owner_cards')==cfg['cards'] and row.get('context')==cfg['context'] and row.get('timing')==cfg['timing'] and row.get('nongemv')=='parallel' and row.get('gemv')==cfg['gemv'] and row.get('memory_mode')==cfg['memory'],'native run identity mismatch')
 diagnostics.update(compare_layers(out/'run',oracle_root,expected_hashes));diagnostics.update(token_diagnostics(row.get('tokens',[]),expected_tokens))
 require(diagnostics['first_differing_layer'] is None,'layer oracle mismatch')
 require(row.get('tokens')==expected_tokens,'token oracle mismatch')
 require(row.get('passed') is True and safe_teardown(row,cfg['cards']),'native failure or unsafe teardown')
 rows=[json.loads(s) for s in (out/'run/timings.jsonl').read_text().splitlines() if s.strip()]
 require(len(rows)==cfg['count'],'timing row coverage mismatch')
 for i,r in enumerate(rows):
  require(r.get('kind')=='generated_token' and r.get('generated_index')==i+1 and r.get('token_id')==expected_tokens[i],'timing rows reordered')
  for key in ('wall_ms','prepare_ms','enqueue_loop_ms','wait_ms','kernel_submissions','host_waits'):
   require(type(r.get(key)) in (int,float) and math.isfinite(r[key]) and r[key]>=0,'missing/invalid token phase: '+key)
 require(row.get('decode_tokens')==cfg['count']-1,'decode numerator differs from tokens 2..N')
 duration,rate=row.get('decode_wall_ms'),row.get('decode_tok_s')
 require(type(duration) in (int,float) and type(rate) in (int,float) and duration>0 and rate>0 and math.isfinite(duration) and math.isfinite(rate) and math.isclose(rate,(cfg['count']-1)*1000/duration,rel_tol=2e-5),'decode rate mismatch')
 diagnostics.update(token_rows=rows,oracle_exact=True,decode_wall_ms=duration,decode_tok_s=rate if cfg['timing']=='token' else None)
 if cfg['timing']=='class':
  require(row.get('submission_budget_measured') is True and row.get('submission_budget_ns')==4000000000 and type(row.get('max_submission_ns')) in (int,float) and 0<row['max_submission_ns']<=4e9,'profiled submission budget failed')
  profile=read(out/'run/class-times.json')
  require(profile.get('profiling') is True and profile.get('tokens')==cfg['count']-1 and bool(profile.get('classes')),'class profile coverage missing')
  diagnostics['class_times_sha256']=sha(out/'run/class-times.json')
 return row


def run_child(command,record,out,latch,seconds,environment,bindings,check):
 out.mkdir(parents=True)
 requested=[]
 def persist():
  if requested:record['stop_reason']=requested[0]
  (out/'window.json').write_text(json.dumps(record,indent=2)+'\n')
 def fault(reason):
  latch.write_text(json.dumps(dict(boot_id=record['boot_id'],window=str(out),reason=reason,pid=record.get('pid')))+'\n')
 for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda s,f:requested.append('watcher signal '+str(s)))
 record.update(command=command,passed=False,device_executed=False)
 persist()
 try:
  pre,cursor=journal();(out/'preflight-kernel.txt').write_text(pre)
  with (out/'stdout.txt').open('w') as log,(out/'kernel-window.txt').open('w') as kernel:
   require(not requested,'stopped before launch')
   child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=environment['native'])
   record.update(pid=child.pid,device_executed=True);persist()
   record.update(supervise(child,seconds,cursor,kernel,fault,persist,requested))
  require(record['returncode']==0 and not requested,'native child failed/stopped')
  for path,digest in bindings.items():require(sha(path)==digest,'binding changed: '+str(path))
  check(record)
  record.update(passed=True,native_receipt_sha256=sha(out/'run/receipt.json'))
 except (OSError,ValueError,KeyError,TypeError) as error:
  requested.append(str(error));persist();fault(requested[0])
 persist()
 return 0 if record['passed'] else 1


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--authorized-device-window',action='store_true',required=True)
 parser.add_argument('--window',choices=CONFIG,required=True)
 parser.add_argument('--card',type=int,required=True)
 parser.add_argument('--native-nice',type=int,default=19,choices=range(0,20))
 parser.add_argument('--seconds',type=int)
 for key in ('input','output','oracle','k0','k1a','k1b','k2','w0','w1','dispatch'):
  parser.add_argument('--'+key,type=Path,required=key=='output')
 a=parser.parse_args();environment=environment_gate()
 priorities=priority_gate(a.native_nice)
 require('idle' in subprocess.check_output(helper_command(['ionice','-p',str(os.getpid())]),text=True,timeout=2),'wrapper ionice -c3 required')
 seconds=watchdog_seconds(a.window,a.seconds);cfg=dict(CONFIG[a.window],card=a.card)
 require(0<=a.card and a.card+cfg['cards']<=4,'card indexes outside 0..3')
 build=(HERE/'build').resolve();out=a.output.resolve();boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();latch=build/'FAULT.json'
 require(not latch.exists() or read(latch).get('boot_id')!=boot,'boot fault latch: coordinator recovery required')
 require(build in out.parents and not out.exists(),'new output directory beneath packet29 build required')
 receipt=read(HERE/'build-receipt.json');require(receipt.get('passed') is True,'build gate failed')
 cpu_gate(HERE/'cpu-tests.json',receipt)
 artifacts=receipt['artifacts_sha256'];native_hashes={k:v for k,v in artifacts.items() if k.startswith('device/')}
 bindings={ROOT/name:digest for name,digest in receipt['sources'].items()}
 bindings.update({HERE/'build-receipt.json':sha(HERE/'build-receipt.json'),HERE/'cpu-tests.json':receipt['cpu_tests_sha256']})
 for name,digest in native_hashes.items():bindings[build/name]=digest
 for path,digest in bindings.items():require(sha(path)==digest,'source/binary changed: '+str(path))
 identity=dict(schema=SCHEMA,window=a.window,boot_id=boot,artifacts_sha256=native_hashes,environment=environment,**cfg)
 record=dict(identity,binary_sha256=artifacts['device/own-rt-iq3'],deadlines=deadline_record(a.window,seconds),**priorities,
  profiling=a.window in ('K2','W2c'),evidence_label='profiling; not model decode speed' if a.window in ('K2','W2c') else 'correctness window')
 if a.window!='K0':k0_gate(a.k0,identity,cfg);bindings[a.k0]=sha(a.k0)
 if a.dispatch is not None:validate_dispatch(read(a.dispatch))
 if a.window in ('K1a','K1b','K2'):
  record['candidate_dispatch_sha256']=sha(a.dispatch) if a.dispatch else None
  if a.dispatch is not None:bindings[a.dispatch]=sha(a.dispatch)
 if a.window=='K1b':
  first=prerequisite(a.k1a,'K1a',identity);fixture_receipt_gate(a.k1a.parent/'run',receipt)
  require(first['card']==a.card,'K1 card changed');require(first.get('candidate_dispatch_sha256')==record.get('candidate_dispatch_sha256'),'K1 candidate dispatch changed');bindings[a.k1a]=sha(a.k1a);record['k1a_sha256']=sha(a.k1a)
 if a.window in ('K2','W2m','W2c','W2x'):
  k1a,k1b=k1_gate(a.k1a,a.k1b,identity,receipt)
  if a.window=='K2':require(k1a.get('candidate_dispatch_sha256')==record.get('candidate_dispatch_sha256'),'K2 candidate differs from K1')
  for path in (a.k1a,a.k1b):bindings[path]=sha(path)
  record.update(k1a_sha256=sha(a.k1a),k1b_sha256=sha(a.k1b))
 if a.window in ('W2','W2m','W2c','W2x'):
  canary=prerequisite(a.w0,'W0',identity);require(canary['card']==a.card and canary['cards']==2,'W0 topology changed')
  canary_receipt_gate(read(a.w0.parent/'run/receipt.json'));bindings[a.w0]=sha(a.w0)
 if a.window in ('W2m','W2c'):
  measured=k2_gate(a.k2,identity,a.dispatch)
  require(measured.get('k1a_sha256')==sha(a.k1a) and measured.get('k1b_sha256')==sha(a.k1b),'K2 fixture gates changed')
  require(measured.get('candidate_dispatch_sha256')==read(a.k1a).get('candidate_dispatch_sha256'),'K2/K1 candidate dispatch identity changed')
  bindings[a.k2]=sha(a.k2);bindings[a.dispatch]=sha(a.dispatch);record['dispatch_sha256']=sha(a.dispatch)
 elif a.window=='W2x':
  require(a.dispatch is not None,'W2x requires explicit --dispatch')
  selected=validate_dispatch(read(a.dispatch))
  for admission in (k1a,k1b):
   require(admission.get('kernel_registry_sha256')==sha(HERE/'kernel-registry.json'),'K1 kernel registry changed')
   covered_by_k1(selected,admission.get('kernel_coverage',{}))
  bindings[a.dispatch]=sha(a.dispatch);record['dispatch_sha256']=sha(a.dispatch)
 elif a.window not in ('K1a','K1b','K2'):require(a.dispatch is None,'custom dispatch allowed only in K1/K2/W2m/W2c/W2x')
 binary=build/'device/own-rt-iq3'
 if a.window=='K0':
  binary=build/'device/jit-smoke'
  command=[str(binary),'--authorized-device-window','--card',str(a.card),'--cards',str(cfg['cards']),'--output',str(out/'run')]
  def check(r):
   n=read(out/'run/receipt.json');require(n.get('passed') is True and n.get('kernel_execution') is False and n.get('explicit_allocations')==0 and n.get('cards')==cfg['cards'] and n.get('kernels_per_device',0)>0,'K0 compile smoke incomplete')
 elif a.window in ('K1a','K1b'):
  binary=build/'device/nongemv-fixtures'
  command=[str(binary),'--authorized-device-window','--card',str(a.card),'--output',str(out/'run')]
  def check(r):
   fixture_receipt_gate(out/'run',receipt)
   r.update(kernel_registry_sha256=sha(HERE/'kernel-registry.json'),kernel_coverage={s:REGISTRY[s] for s in SECTIONS})
   if a.window=='K1b':require(r['pid']!=read(a.k1a)['pid'],'K1 owners not fresh')
 elif a.window=='K2':
  binary=build/'device/k2-fixtures'
  command=[str(binary),'--authorized-device-window','--card',str(a.card),'--repetitions','200','--output',str(out/'run')]
  def check(r):
   n=read(out/'run/receipt.json')
   require(n.get('schema')=='packet26.k2.v1' and n.get('passed') is True and n.get('device_executed') is True and n.get('diagnostic') is True and n.get('repetitions')==200 and n.get('owner_cards')==1 and sequential_teardown(n,4),'K2 native coverage/teardown incomplete')
   summary=summarize(out/'run',identity)
   require(type(n.get('max_submission_ns')) in (int,float) and 0<n['max_submission_ns']<=4e9,'K2 submission budget failed')
   require(summary['passed'],'K2 timing/exactness gate failed')
   r.update(class_rows=len(summary['classes']),dispatch_sha256=sha(out/'run/dispatch-measured.json'),events_sha256=sha(out/'run/events.jsonl'),summary_sha256=sha(out/'run/summary.json'))
 elif a.window=='W0':
  command=[str(binary),'--authorized-device-window','--canary','--cards','2','--card',str(a.card),'--timing','token','--memory','resident','--seconds',str(seconds),'--output',str(out/'run')]
  def check(r):canary_receipt_gate(read(out/'run/receipt.json'))
 else:
  require(a.input is not None and a.oracle is not None,'model windows require --input and --oracle')
  manifest=a.input/'input.json';require(sha(manifest)==receipt['input_sha256'],'model input manifest changed')
  inp=read(manifest);bindings[manifest]=sha(manifest)
  for name,digest in inp['files'].items():bindings[a.input/name]=digest
  expected_hashes,expected_tokens=oracle_gate(a.oracle,inp['tokens'],cfg['steps'],cfg['count'])
  for name in ('arithmetic.json','input.json','result.json'):bindings[a.oracle/name]=sha(a.oracle/name)
  for name,digest in expected_hashes.items():bindings[a.oracle/name]=digest
  if cfg['cards']==2:
   require(sha(HERE/'census.json')==receipt['census_sha256'],'memory census changed')
   bindings[HERE/'census.json']=receipt['census_sha256'];record['memory_admission']=memory_admission(read(HERE/'census.json'),cfg['gemv'])
  if a.w1 is not None:
   w1=prerequisite(a.w1,'W1',identity)
   require(w1.get('oracle_exact') is True and w1.get('tokens')==expected_tokens[:8],'optional W1 oracle mismatch');bindings[a.w1]=sha(a.w1)
  record.update(arithmetic=AUTHORITY,expected_tokens=expected_tokens,oracle_hashes=expected_hashes,input_sha256=sha(a.input/'tokens.txt'),oracle_path=str(a.oracle.resolve()))
  command=native_command(binary,cfg,a.input,inp['model_dir'],a.oracle,out,seconds,a.dispatch,a.native_nice)
  def check(r):compare_run(out,cfg,expected_hashes,expected_tokens,a.oracle,r)
 for path,digest in bindings.items():require(sha(path)==digest,'admission binding changed: '+str(path))
 if a.dispatch is not None and a.window in ('K1a','K1b','K2'):command+=['--dispatch',str(a.dispatch.resolve())]
 record['ldd_preflight']=ldd_preflight(binary)
 record['bindings']={str(k):v for k,v in bindings.items()}
 command=['ionice','-c','3']+command
 return run_child(command,record,out,latch,seconds,environment,bindings,check)

if __name__=='__main__':
 try:raise SystemExit(main())
 except (OSError,ValueError,KeyError,TypeError) as error:raise SystemExit(str(error))
