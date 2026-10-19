"""Actual production argv/parser and prepare path, CPU transport, no model/device grants."""
import importlib.util,json,os,resource,subprocess,sys,time
from pathlib import Path
from build_engine import P,ROOT,turn,limits,sha,save
name=sys.argv[1];p=P/name;sys.path.insert(0,str(p))
import worker,launch_env,native_env
sys.path.append(str(ROOT/"experiments/own-xpu-runtime/ops"))
spec=importlib.util.spec_from_file_location('shared_rehearsal',ROOT/'experiments/own-xpu-runtime/ops/rehearse_entry.py');R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
B=p/'build/preparation163';scratch=B/('run-'+str(time.time_ns()));scratch.mkdir(exist_ok=False)
commands=[]
if name=='one-card':
 table=scratch/'suite-inputs.tsv';table.write_text(''.join(e['prompt_id']+' '+str(p/'inputs'/e['prompt_id']/'tokens.txt')+'\n'for e in worker.entries()))
 commands=[worker.native_command(scratch,table)]
else:
 # Capture Transport's exact command builder. Popen is intercepted before exec;
 # receive stops before census/device processing. All descriptors are local IPC.
 import pipeline
 from unittest.mock import patch
 class Stop(Exception):pass
 class Child:
  pid=os.getpid()
  def poll(self):return 0
 def fake(argv,**kw):commands.append(argv[3:] if argv[:3]==['ionice','-c','3'] else argv);return Child()
 args=pipeline.parser().parse_args(['--output',str(scratch),'--device','--binary',str(p/'build/device/own-rt-iq3'),'--dispatch',str(p/'dispatch.json'),'--controller','native','--draft','mtp','--draft-rank','1','--target-split','0','--context','4096','--tokens','512','--retain-steps','none','--timing','token','--native-nice','0','--card','0','--seconds','7200','--wait-seconds','1200'])
 args.selection_sha256=sha(p/'selection.json');args.input=p/'inputs';pipeline.P=p
 out=scratch/'capture';out.mkdir();t=pipeline.Transport.__new__(pipeline.Transport)
 with patch.object(pipeline.subprocess,'Popen',side_effect=fake),patch.object(pipeline.Transport,'receive',side_effect=Stop):
  try:pipeline.Transport.__init__(t,args,out,native_env.environment("A"))
  except Stop:pass
 for f in t.logs:f.close()
 for s in t.sockets:s.close()
 t.mapping.close();os.close(t.stop_read);os.close(t.stop_write)
 assert len(commands)==2
metadata=[f for f in (p/'inputs').rglob('*')if f.is_file()]+[p/'selection.json',p/'dispatch.json',p/'memory-plan.json']
metadata += list((p/'native-source').rglob('*.bf16'))+list((p/'native-source').rglob('*manifest*.json'))
metadata += list(scratch.glob('*.tsv'))
env=native_env.environment("A");results=[]
with turn():
 limits()
 for rank,command in enumerate(commands):
  dest=scratch/f'probe{rank}';dest.mkdir();env['ENTRY_PREPARE_OUTPUT']=str(dest)
  (dest/'request').mkdir();(dest/'final-state').mkdir();(dest/'draft-final-state').mkdir()
  binary=B/'prepare-probe';argv=[str(binary),*command[1:]]
  help_run=subprocess.run([str(p/'build/device/own-rt-iq3'),'--help'],env=native_env.environment("A"),stdin=subprocess.DEVNULL,capture_output=True,text=True,preexec_fn=lambda:R.prepare_restrict(p/'build/device/own-rt-iq3',[],dest))
  assert help_run.returncode==0,help_run.stderr
  flags=[x for x in command[1:]if x.startswith('--')];assert set(flags)<=set(help_run.stdout.split()),set(flags)-set(help_run.stdout.split())
  with (dest/'stdout.log').open('w')as out,(dest/'stderr.log').open('w')as err:
   child=subprocess.Popen(argv,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,preexec_fn=lambda:R.prepare_restrict(binary,metadata,dest))
   peak=0
   while child.poll()is None:
    try:
     rss=next(int(x.split()[1])*1024 for x in Path(f'/proc/{child.pid}/status').read_text().splitlines()if x.startswith('VmRSS:'));peak=max(peak,rss)
     if rss>4*1024**3:child.terminate();child.wait();raise ValueError('CPU probe RSS exceeds4GB')
    except (FileNotFoundError,StopIteration):pass
    time.sleep(.05)
  assert child.returncode==0,(child.returncode,(dest/'stderr.log').read_text())
  assert 'PASS CPU device-branch'in(dest/'stdout.log').read_text()
  results.append(dict(passed=True,rank=rank,argv=argv,real_native_argv=command,all_flags_in_built_help=True,help=help_run.stdout,peak_rss_bytes=peak,binary_sha256=sha(binary),stdout=(dest/'stdout.log').read_text(),stderr=(dest/'stderr.log').read_text()))
 save(p/'evidence/preparation-probe.json',dict(passed=True,device_executed=False,model_reads=False,backend='CPU marker transport and synthetic/opaque weight payload; no arithmetic or driver validation',landlock='libraries and exact metadata only; no /dev/dri or model files granted',environment=native_env.environment("A"),probes=results))
 print(name,'preparation PASS',flush=True)
