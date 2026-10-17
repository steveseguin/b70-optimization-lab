#!/usr/bin/env python3
"""Coordinator-only sealed K0/KD/paired WS diagnostic; --plan is CPU only."""
import argparse,datetime,fcntl,json,os,signal,subprocess,time
from pathlib import Path
from types import SimpleNamespace
import pipeline as pp
from storage import digest,admit,projected_write_bytes
from window_safety import environment_gate,memory_snapshot
from window import Watch,foreign_engines,run_fixtures,live_owner_pids,compress_evidence,FAULT
from p57_seal import parent_proof,verify,require
P=Path(__file__).resolve().parent;B=P/'build'
CORES={0,1,2,3,16,17,18,19}
STAGES=('K0','KD','W57-control','W57-attribution')
EXPECTED={'K0':60,'KD':1800,'W57-control':1200,'W57-attribution':1200}
BUDGET={'K0':600,'KD':10800,'W57-control':7200,'W57-attribution':7200}
GAPS={'K0':90,'KD':305,'W57-control':305,'W57-attribution':305}

def plan(out):
 return dict(schema='packet57.window-plan.v1',device_executed=False,diagnostic=True,qualifying=False,
  cards=[0,1],stages=[dict(name=n,expected_work_seconds=EXPECTED[n],watchdog_seconds=BUDGET[n],cooldown_seconds=GAPS[n],output=str(out/n)) for n in STAGES],
  expected_total_seconds=sum(EXPECTED.values())+sum(GAPS.values()),outer_watchdog_seconds=28800,
  request_scope='12 fixed oracle49 prompts x 128 output tokens per arm, independent cold requests',
  timing_modes=['token','attribution'],gpu_event_sample='generated target/draft indices9–16 only',
  inherited_operator_proof=str(P/'parent-device-proof.json'),no_device_contact=True)

def unit_gate():
 from queue_runner import user_unit_gate
 cgroup=Path('/proc/self/cgroup').read_text();user_unit_gate(cgroup)
 unit=next(line.rsplit('/',1)[-1] for line in cgroup.splitlines() if '/user@' in line and line.endswith('.service'))
 result=subprocess.run(['systemctl','--user','show',unit,'-p','SendSIGKILL','-p','KillSignal','-p','KillMode'],capture_output=True,text=True,check=True,timeout=10)
 props=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
 require(props.get('SendSIGKILL')=='no' and props.get('KillSignal') in ('15','SIGTERM') and props.get('KillMode')=='control-group','unit needs SIGTERM, control-group, SendSIGKILL=no')
 return {'unit':unit,'properties':props}

def reviewed_journal(boundary):
 stamp=datetime.datetime.fromisoformat(boundary.replace('Z','+00:00'))
 require(stamp.tzinfo is not None and stamp<=datetime.datetime.now(datetime.timezone.utc),'review boundary needs nonfuture timezone-aware UTC')
 result=subprocess.run(['journalctl','-k','--no-pager','--since',stamp.astimezone(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')],capture_output=True,text=True,check=True,timeout=10)
 require(not FAULT.search(result.stdout),'fault after reviewed boundary; coordinator recovery required')
 return {'reviewed_through_utc':stamp.isoformat(),'new_fault_lines':0}

def cooldown(watch,seconds,stop):
 until=time.monotonic()+seconds
 while time.monotonic()<until:
  require(not stop.exists(),'STOP requested, no next launch');watch.check();time.sleep(min(1,until-time.monotonic()))

def run(a):
 require(a.authorized_device_window,'explicit coordinator authorization required')
 require(os.getpriority(os.PRIO_PROCESS,0)==0 and set(os.sched_getaffinity(0))==CORES,'admitted nice0 unit on cores0-3,16-19 required')
 unit=unit_gate();env=environment_gate();require(env['native']['OMP_NUM_THREADS']=='2','OMP2 required')
 # All seal/source/parent checks happen before opening a device or output directory.
 build=verify();base,proof=parent_proof()
 from shared_oracle import completed_binding
 oracle=completed_binding()
 out=a.output.resolve();require(B.resolve()==Path('/home/steve/own-xpu-runtime-results/packet57-attribution/build'),'build root changed')
 require(out==B.resolve()/'device-cards01-a' and not out.exists(),'registered fresh output only; never retry/overwrite')
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 for latch in (B/'FAULT.json',P.parent/'packet56-draft-prefix/build/FAULT.json'):
  require(not latch.exists() or json.loads(latch.read_text()).get('boot_id')!=boot,'same-boot fault latch requires coordinator review')
 reviewed=reviewed_journal(a.faults_reviewed_through)
 foreign=foreign_engines();memory=memory_snapshot();require(memory['MemAvailable']>=97*1024**3,'97GiB required; wait for packet55 release')
 dispatch=Path(proof['dispatch']['path']);require(digest(dispatch)==proof['dispatch']['sha256'],'qualified dispatch changed')
 # Three state snapshots cannot coexist across stages: inherited WS retention
 # compresses each request before the next; reserve two suites plus KD/logs.
 storage=admit(3_000_000_000,build_extra=3_000_000_000)
 out.mkdir();record=dict(plan(out),passed=False,device_executed=False,no_device_contact=False,
  boot_id=boot,build_receipt_sha256=digest(P/'build-receipt.json'),unit=unit,environment=env,
  memory_admission=memory,storage_admission=storage,foreign_engine_admission=foreign,reviewed_journal=reviewed,
  shared_oracle=oracle,dispatch_sha256=digest(dispatch),completed=[],receipts={})
 pp.save(out/'window.json',record)
 with (out/'window.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  watch=Watch(out,boot,28800);overall_end=watch.end;stop=out/'STOP'
  old={s:signal.signal(s,lambda n,f:watch.cancelled.append(n)) for s in (signal.SIGTERM,signal.SIGINT)}
  try:
   for name in STAGES:
    require(not stop.exists(),'STOP requested');watch.check()
    require(not live_owner_pids(watch),'previous owners still present')
    foreign_engines();reviewed_journal(a.faults_reviewed_through)
    if name.startswith('W'):
     require(memory_snapshot()['MemAvailable']>=97*1024**3,'97GiB required before each fresh rank pair')
    dest=out/name;dest.mkdir();watch.end=min(overall_end,time.monotonic()+BUDGET[name])
    args=SimpleNamespace(window=name,card=0,context=4096,draft_rank=1,target_split=23,dispatch=dispatch,input=B/'input',seconds=BUDGET[name],cpu_rehearsal=False)
    before=len(watch.launched)
    if name=='K0':
     receipts=run_fixtures(args,dest,env['native'],watch)
     for rank in (0,1):
      r=json.loads((dest/f'run{rank}/receipt.json').read_text());require(r['passed'] and r['kernel_execution'] is False and r['explicit_allocations']==0 and r['kernels_per_device']>0,'new K0 readiness failed')
     result={'passed':True,'receipts':receipts}
    elif name=='KD':
     from draft_window import run as run_draft
     receipts,pids=run_draft(args,dest,env['native'],watch,build)
     result={'passed':True,'receipts':receipts,'pids':pids}
    else:
     require('KD' in record['completed'],'fresh packet57 KD required')
     args=pp.parser().parse_args(['--output',str(dest/'run')])
     args.binary=B/'device/own-rt-iq3';args.device=True;args.native_nice=0;args.mini=False
     args.card=0;args.context=4096;args.draft_rank=1;args.target_split=23;args.controller='native';args.prompt_overlap='on'
     args.seconds=BUDGET[name];args.wait_seconds=600;args.tokens=128;args.retain_steps='none';args.draft='mtp'
     args.dispatch=dispatch;args.selection_sha256=build['selection']['selection_sha256'];args.input=B/'input';args.oracle=None
     args.timing='token' if name=='W57-control' else 'attribution';args.suite_manifest=P/'oracle/results/suite-manifest.json';args.repeat=1
     result=pp.run(args,env['native'],watch.check,watch.latch,watch.mark_launched)
     require(result['passed'],'suite target oracle mismatch')
    watch.postflight();require(not live_owner_pids(watch),'owners retained after stage; no next launch')
    stage=dict(schema='packet57.diagnostic-stage.v1',passed=True,device_executed=True,diagnostic=True,qualifying=False,no_speed_claim=True,
       window=name,build_receipt_sha256=record['build_receipt_sha256'],dispatch_sha256=digest(dispatch),launched_pids=watch.launched[before:],result=result)
    pp.save(dest/'window.json',stage);record['completed'].append(name);record['receipts'][name+'/window.json']=digest(dest/'window.json')
    pp.save(out/'window.json',record);watch.end=overall_end;cooldown(watch,GAPS[name],stop)
   from p57_perturbation import summarize
   comparison=summarize(out/'W57-control/run',out/'W57-attribution/run')
   require(comparison['passed'],'paired attribution completeness failed')
   pp.save(out/'attribution-summary.json',comparison);record.update(passed=True,comparison_sha256=digest(out/'attribution-summary.json'))
  except Exception as error:
   record.update(error=str(error),passed=False)
   pp.failure_attempt('fault latch',lambda:watch.latch(error),record.setdefault('diagnostic_errors',[]))
  finally:
   # Passive kernel capture always runs after success, cancellation or deadline.
   # It never calls check(), which would immediately reject cancelled work.
   end=time.monotonic()+5;postflight_errors=[]
   while time.monotonic()<end:
    try:watch.last=0.;watch.poll_kernel()
    except Exception as error:postflight_errors.append(str(error))
    time.sleep(.25)
   record['passive_postflight']={'seconds':5,'errors':sorted(set(postflight_errors)),'new_gpu_fault':watch.new_gpu_fault}
   if postflight_errors:record['passed']=False
   for sig,handler in old.items():signal.signal(sig,handler)
   record.update(device_executed=bool(watch.launched),launched_pids=watch.launched,retained_owner_pids=live_owner_pids(watch))
   pp.save(out/'window.json',record)
 return 0 if record['passed'] else 1

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',action='store_true');p.add_argument('--authorized-device-window',action='store_true');p.add_argument('--faults-reviewed-through');p.add_argument('--output',type=Path,default=B/'device-cards01-a');a=p.parse_args()
 if a.plan:print(json.dumps(plan(a.output),indent=2));return 0
 require(a.faults_reviewed_through,'coordinator reviewed fault boundary required');return run(a)
if __name__=='__main__':raise SystemExit(main())
