"""Admitted, one-load measurement window. Import and --plan never touch a GPU."""
import argparse,json,os,signal,shutil,subprocess,time
from pathlib import Path
from common import HERE,ROOT,D,S,SUPPORT,read,save,sha,require
from conditions import cpu_gate,lane_gate,LANES
from lane_admission import Reservation
from drain_gate import DrainPermit,screen_teardown_admit
import chain_devices
import launch_env
import fault_review
import measurement

DEVICE_FLOOR=25_000_000_000

def storage(path,planned_writes=0):
 free=shutil.disk_usage(path).free
 require(free-planned_writes>=DEVICE_FLOOR,'device storage floor 25 GB')
 return dict(free_bytes=free,planned_write_bytes=planned_writes,floor_bytes=DEVICE_FLOOR)

def parser():
 ap=argparse.ArgumentParser()
 ap.add_argument('--lane',choices=('A','B'),required=True)
 ap.add_argument('--kind',choices=('full512','smoke','bracket'),default='full512')
 ap.add_argument('--output',type=Path,required=True)
 ap.add_argument('--reference',type=Path)
 ap.add_argument('--fault-review',type=Path)
 ap.add_argument('--authorized-device-window',action='store_true')
 ap.add_argument('--plan',action='store_true')
 return ap

def unit_gate():
 cgroup=Path('/proc/self/cgroup').read_text()
 units=[line.rsplit('/',1)[-1] for line in cgroup.splitlines() if '/user@'in line and line.endswith('.service')]
 require(len(units)==1 and units[0].startswith('screen-'),'coordinator screen user unit required')
 keys=('Restart','SendSIGKILL','KillMode','ExitType','TimeoutStopUSec')
 cp=subprocess.run(['/usr/bin/systemctl','--user','show',units[0],*[s for k in keys for s in ('-p',k)]],env=dict(PATH='/usr/bin:/bin',XDG_RUNTIME_DIR='/run/user/'+str(os.getuid())),stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
 props=dict(line.split('=',1)for line in cp.stdout.splitlines()if'='in line)
 require(props==dict(Restart='no',SendSIGKILL='no',KillMode='process',ExitType='cgroup',TimeoutStopUSec='infinity'),'graceful nonrestarting unit required')
 return dict(unit=units[0],properties=props)

def memory(required):
 values={line.split(':',1)[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemAvailable:','SwapFree:'))}
 require(values['MemAvailable']>=required,'host memory admission')
 return values

def report_completed(output,record,identity,coordination):
 proof=read(output/'run/report-inputs.json')
 require(proof.get('passed') is True,'measurement worker incomplete')
 rows=proof['requests']
 reference=read(Path(identity['reference'])/'summary.json') if identity.get('reference') else None
 result=measurement.aggregate(rows,proof.get('prefill'),identity.get('measurement_identity'),reference)
 result.update(kind=identity.get('bracket',{}).get('kind','full512'),lane=identity['lane'],
  scope=coordination.get('scope','report-rehearsal'),device_executed=bool(record.get('device_executed')),
  source_report_sha256=sha(output/'run/report-inputs.json'),report_after_device_release=True)
 # Generic shared rehearsal intentionally supplies64/128 receipts: those stay strict512=false.
 if result.get('strict512'):
  require(proof.get('prefill') is not None and proof.get('device_isolation',{}).get('passed') is True,'full512 needs prefill and device isolation')
 save(output/'summary.json',result);save(output/'bracket-summary.json',result)
 return result

def screen_main(argv=None):
 args=parser().parse_args(argv)
 if args.plan:cpu_gate()
 else:lane_gate(args.lane)
 from cpu_seal import verify
 verify()
 identity=read(HERE/'identity.json');one=identity['gpu_count']==1
 require(not one or args.lane=='A','one-card measurement requires lane A whole host')
 args.output=args.output.resolve()
 require(args.output.parent==HERE/'evidence' and not args.output.exists(),'fresh private output required')
 if args.reference:
  args.reference=args.reference.resolve();require(args.reference.parent==HERE/'evidence' and args.reference!=args.output,'fresh same-packet reference required')
 budget=read(HERE/'budget.json')
 spec=dict(measurement_identity=identity,lane=args.lane,profile='onecard'if one else'tp2',bracket=dict(kind=args.kind),reference=str(args.reference)if args.reference else None)
 command=['/usr/bin/python3','-B',str(HERE/'worker.py'),'--output',str(args.output/'run'),'--lane',args.lane]
 plan=dict(passed=True,device_executed=False,model_loads=1,request_count=13,requested_max_new=512,prefill_input_tokens=512,oracle_exact_tokens=128,
  host_required_available_bytes=budget['host_required_available_bytes'],planned_write_bytes=budget['planned_write_bytes'],
  expected_seconds=budget['expected_seconds'],watchdog_seconds=7200,per_operation_wait_seconds=budget['wait_seconds'],
  reservation_scope='whole-host'if args.lane=='A'else'lane-B with other lane required idle',command=command,
  second_fresh_attempt=bool(args.reference),prefill=dict(users=1,cached_tokens=0),submission_eligible=False)
 if args.plan:
  print(json.dumps(plan));return 0
 require(args.kind=='full512','short synthetic report modes cannot launch devices')
 require(args.authorized_device_window and args.fault_review,'coordinator authorization and fault review required')
 from readiness import verify_ready
 verify_ready()
 D.oracle_inputs()
 if args.reference:
  prior=read(args.reference/'window.json');require(prior.get('passed')is True and prior.get('device_executed')is True and prior.get('child_still_running')is False,'first fresh attempt must complete')
  require(read(args.reference/'summary.json')['identity']==identity,'fresh repeat record identity')
 screen_teardown_admit(args.lane);unit=unit_gate();memory(budget['host_required_available_bytes']);storage(HERE,budget['planned_write_bytes'])
 reviewed,initial,fresh,cursor=fault_review.validate(args.fault_review)
 stop=[];child=None;record=dict(passed=False,device_executed=False,child_still_running=False,stop_reasons=stop,unit=unit,plan=plan)
 def check():
  nonlocal cursor
  require(not stop and not (HERE/'evidence/STOP').exists(),'coordinator stop')
  text,cursor=S.journal(cursor);require(not fault_review.fault_lines(text),'new GPU fault')
  storage(HERE)
  if args.lane=='B':require(not (chain_devices.Path('/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1')/'active-lane-A.json').exists(),'lane A entered during measurement')
 handlers={s:signal.signal(s,lambda n,f:stop.append('signal '+str(n)))for s in(signal.SIGTERM,signal.SIGINT)}
 lease=Reservation(args.lane,window='WS128',timing_claim=True,check=check)
 try:
  with lease:
   # Whole host empty before a first engine launch; B also requires A remain idle.
   chain_devices.admit_clients('whole-host');check()
   args.output.mkdir();save(args.output/'identity.json',spec)
   record.update(started_utc_ns=time.time_ns(),measurement_identity=identity,reservation=lease.record)
   def persist():save(args.output/'window.json',record)
   def latch(reason):save(args.output/'FAULT.json',dict(reason=reason,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip()))
   env=launch_env.environment()
   # Use exact record loader environment; mask the two-card pair before discovery.
   if not one:chain_devices.topology_admit(args.lane);env=chain_devices.mask_native(env,args.lane)
   env['HOME']=str(args.output/'driver-home');Path(env['HOME']).mkdir()
   record['environment']=env;persist()
   with DrainPermit(args.output,check=check,reservation=lease.record)as permit:
    with (args.output/'worker.log').open('w')as log,(args.output/'kernel-window.jsonl').open('w')as kernel:
     check();memory(budget['host_required_available_bytes']);storage(HERE,budget['planned_write_bytes'])
     child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env)
     record.update(device_executed=True,pid=child.pid,process_start_ticks=chain_devices.process_identity(child.pid));persist()
     # Resident copies are31GB; inherit the measured98.99GB host admission and monitor the full tree.
     S.ANONYMOUS_LIMIT_BYTES=budget['host_required_available_bytes']-8*1024**3
     S.ANONYMOUS_STOP_BYTES=S.ANONYMOUS_LIMIT_BYTES-256*1024**2
     def sensor(pid):
      sample=SUPPORT.process_tree_anon(pid)
      memory(8*1024**3);storage(HERE)
      if args.lane=='B':require(not (lease.root/'active-lane-A.json').exists(),'lane A entered during measurement')
      return sample
     record.update(S.supervise(child,7200,cursor,kernel,stop,latch,persist,memory_sensor=sensor,read_journal=S.journal,drain_seconds=120))
    persist()
    require(not record['child_still_running'],'live child retained; coordinator required')
    proof=read(args.output/'run/teardown.json');require(proof.get('drained')is True,'owner drain proof missing')
    chain_devices.admit_clients('whole-host');check();permit.complete();lease.complete(drained=True)
   coordination=dict(passed=True,released_before_report=True,scope=lease.scope,reservation=lease.record)
   save(args.output/'lane-coordination.json',coordination)
   require(child.returncode==0 and not stop,'measurement failed; no retry')
   report_completed(args.output,record,spec,coordination)
   record.update(passed=True,finished_utc_ns=time.time_ns());persist();return 0
 except Exception as error:
  record.update(error=str(error),child_still_running=child is not None and child.poll()is None)
  if child is not None and child.poll()is None:child.send_signal(signal.SIGTERM)
  if args.output.exists():save(args.output/'window.json',record)
  return 75 if record['child_still_running'] else 1
 finally:
  for s,h in handlers.items():signal.signal(s,h)

def main(argv=None):return screen_main(argv)
if __name__=='__main__':raise SystemExit(main())
