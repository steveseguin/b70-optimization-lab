"""Sequential CPU campaign with exact gates, bounded resources and atomic receipts."""
import argparse,fcntl,gzip,hashlib,importlib.util,json,os,resource,re,shutil,signal,struct,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from retention import load_teardown,retain_teardown
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
INPUTS=ROOT/'experiments/own-xpu-runtime/stage2/long-inputs-20261012'
SUITE=HERE.parent/'arithmetic-v2-detmath-20261012-suite128'
SEALED=HERE.parent/'arithmetic-v2-detmath-20261011'
PREFIX=['nice','-n','19','ionice','-c','3']
ENV={**os.environ,'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'}
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=module('suite_base',SUITE/'suite_run.py')
sha,read,save,check,utc,rows=base.sha,base.read,base.save,base.check,base.utc,base.rows

def disk_guard():
 report=subprocess.check_output(PREFIX+['df','-B1','/'],text=True)
 check(int(report.splitlines()[-1].split()[3])>=8_000_000_000,'STOP: root filesystem below 8 GB free')
 scratch=sum(p.stat().st_size for d in HERE.glob('.*.partial*') for p in d.rglob('*') if p.is_file())
 scratch+=sum(p.stat().st_size for p in (HERE/'build').rglob('*') if p.is_file())
 check(scratch<2_000_000_000,'STOP: scratch reached 2 GB')
 return int(report.splitlines()[-1].split()[3]),scratch

def preflight():
 check(os.getpriority(os.PRIO_PROCESS,0)==19,'nice 19')
 check(os.environ.get('OMP_NUM_THREADS')=='2','two numerical threads')
 check('idle' in subprocess.check_output(PREFIX+['ionice','-p',str(os.getpid())],text=True),'idle IO')
 affinity=sorted(os.sched_getaffinity(0));check(not set(affinity)&{0,1,2,3,16,17,18,19},'reserved cores')
 check(affinity==read(HERE/'host-contract.json')['affinity'],'inherited affinity changed')
 build=read(HERE/'build-receipt.json');check(build['passed'],'build passed')
 snapshot=read(HERE/'campaign-source-snapshot.json')
 for name,digest in snapshot['sources'].items():check(sha(HERE/name)==digest,'campaign source changed: '+name)
 check(sha(HERE/'build/oracle')==build['binary_sha256'] and sha(HERE/'oracle_long.cpp')==build['source_sha256'],'build identity')
 for name,h in build['arithmetic']['arithmetic_sources'].items():check(sha(ROOT/name)==h,'frozen arithmetic changed: '+name)
 deps=subprocess.check_output(PREFIX+['readelf','-d',str(HERE/'build/oracle')],text=True)
 check(not any(s in deps for s in ('libsycl','libze_loader','libOpenCL','libcuda')),'CPU dependencies')
 check(not any(Path(p['args'][0].decode())==HERE/'build/oracle' for p in base.oracle_processes()),'live oracle already exists')
 disk_guard();return build

def compress_one(path):
 disk_guard();digest=sha(path);size=path.stat().st_size;tmp=path.with_name(path.name+'.gz.tmp')
 with path.open('rb') as src,tmp.open('wb') as raw:
  with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as dst:shutil.copyfileobj(src,dst,1024*1024)
 with gzip.open(tmp,'rb') as f:check(hashlib.file_digest(f,'sha256').hexdigest()==digest,'compressed bytes')
 dest=path.with_name(path.name+'.gz');tmp.replace(dest);path.unlink()
 return dict(sha256=digest,bytes=size,compressed_sha256=sha(dest))

def archived_logs(d,finished=False):
 ledger=d/'log-retention.json';records=read(ledger) if ledger.exists() else {}
 names=[p for p in d.iterdir() if p.is_file() and ('.segment-' in p.name or '.interrupted-' in p.name) and not p.name.endswith(('.gz','.tmp'))]
 if finished:
  for p in (d/'progress.jsonl',d/'timings.jsonl'):
   if p.exists():
    unique=p.with_name(p.name+'.segment-final-'+str(time.time_ns()));p.rename(unique);names.append(unique)
 for p in sorted(names):
  info=compress_one(p);match=re.match(r'(?:progress|timings)\.jsonl\.segment-(\d+)-',p.name)
  info['end_position']=int(match[1]) if match else read(d/'result.json')['next_position']
  info['recorded_utc']=utc();records[p.name]=info;save(ledger,records)
 return records

def launch(label,bundle,cap,*,resume=False,extra=None):
 build=preflight();dest=HERE/label
 if dest.exists():
  r=read(dest/'receipt.json');check(r['verified'] and r['binary_sha256']==build['binary_sha256'],'existing oracle binary identity');check(r['result_sha256']==sha(dest/'result.json') and r['validation_sha256']==sha(dest/'validation.json'),'existing oracle receipt binding');return dest
 attempt=HERE/('.'+label+'.partial');attempt.mkdir(exist_ok=True);d=attempt/'native';inp=read(bundle/'input.json')
 check(1<=cap<=64 and len(inp['tokens'])+cap-1<=4096,'run bounds')
 for n,h in inp['files'].items():check(sha(bundle/n)==h,'input file '+n)
 check(list(map(int,(bundle/'tokens.txt').read_text().split()))==inp['tokens'],'input tokens')
 prior=read(attempt/'receipt.json') if (attempt/'receipt.json').exists() else None
 if prior and (d/'result.json').exists() and ((d/'teardown.json').exists() or (d/'teardown.json.gz').exists()) and read(d/'result.json')['status'] in ('token-cap','eos'):
  check(prior['binary_sha256']==build['binary_sha256'] and prior['input_sha256']==sha(bundle/'input.json'),'completed partial identity');return d
 if resume:
  check(prior and prior['binary_sha256']==build['binary_sha256'] and prior['input_sha256']==sha(bundle/'input.json'),'resume identity')
  check((d/'checkpoint.bin').exists(),'no checkpoint')
  current=read(d/'result.json')
  check(current['status'] in ('running','checkpoint-stopped') or (current['status']=='failed-or-stopped' and current['error'] in ('cooperative stop','cooperative deadline')),'numerical failure is not resumable')
  archives=read(d/'resume-archives.json') if (d/'resume-archives.json').exists() else {}
  for name in ('teardown.json','result.json'):
   if (d/name).exists():
    target=d/(name+'.attempt-'+str(time.time_ns()));disk_guard();shutil.copyfile(d/name,target)
    if name=='teardown.json':archives[target.name]=compress_one(target)
    else:archives[target.name]=dict(sha256=sha(target),bytes=target.stat().st_size)
  save(d/'resume-archives.json',archives)
 else:check(not d.exists(),'unfinished run exists; explicit --resume required')
 check(len(base.oracle_processes())<2,'at most two oracle processes')
 cmd=PREFIX+[str(HERE/'build/oracle'),str(bundle),str(d),'259200',str(cap)]+(['resume'] if resume else [])
 r=dict(schema='iq3-runtime-cpu-oracle.run.v1',status='running',verified=False,started_utc=utc(),command=cmd,
  arithmetic=build['arithmetic'],binary_sha256=build['binary_sha256'],source_hashes=build['arithmetic']['arithmetic_sources'],runner_sha256=sha(Path(__file__)),support_sha256=sha(HERE/'campaign_support.py'),checker_sha256=sha(HERE/'suite_check.py'),campaign_sources_sha256=sha(HERE/'campaign-source-snapshot.json'),
  model=read(SEALED/'receipt.json')['model'],prompt_id=label,prompt_sha256=inp['prompt_sha256'],prompt_tokens=len(inp['tokens']),requested_tokens=cap,context=4096,
  input_sha256=sha(bundle/'input.json'),device_executed=False,nice=19,ionice='idle',OMP_NUM_THREADS=2,affinity=sorted(os.sched_getaffinity(0)),
  oracle_environment_overrides=extra or {},checkpoint_interval=int((extra or {}).get('IQ3_CHECKPOINT_INTERVAL','100')),address_space_cap_bytes=38_000_000_000,anonymous_memory_guard_bytes=11_500_000_000,resumed=resume,prior_attempt=prior)
 save(attempt/'receipt.json',r);snapshot=HERE/'runner-snapshots'/(r['runner_sha256']+'.py');snapshot.parent.mkdir(exist_ok=True)
 if not snapshot.exists():shutil.copyfile(Path(__file__),snapshot)
 child=None;start=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN);peak=0;last_pos=-1;last_disk=0
 with (attempt/('stdout-resume-'+str(time.time_ns())+'.txt' if resume else 'stdout.txt')).open('w') as log:
  child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env={**ENV,'IQ3_MODEL_DIR':inp['model_dir'],**(extra or {})})
  r['pid']=child.pid;save(attempt/'receipt.json',r)
  def stop(sig,frame):
   if child.poll() is None:child.send_signal(sig)
  old={s:signal.signal(s,stop) for s in (signal.SIGTERM,signal.SIGINT)}
  try:
   while child.poll() is None:
    if time.monotonic()-last_disk>10:free,scratch=disk_guard();last_disk=time.monotonic();archived_logs(d) if d.exists() else None
    processes=base.oracle_processes();anon=sum(p['anon'] for p in processes)
    threads=0
    for process in processes:
     try:threads+=next(int(s.split()[1]) for s in Path(f"/proc/{process['pid']}/status").read_text().splitlines() if s.startswith('Threads:'))
     except (FileNotFoundError,ProcessLookupError):pass
    check(threads<=6,'STOP: oracle/helper compute-thread budget exceeds eight')
    own=next(int(s.split()[1])*1024 for s in Path('/proc/self/status').read_text().splitlines() if s.startswith('RssAnon:'))
    anon+=own;peak=max(peak,anon)
    check(anon<11_500_000_000,'STOP: combined oracle anonymous memory near 12 GB')
    check(len(processes)<=2,'STOP: more than two CPU oracles')
    check(time.monotonic()-start<259260,'CPU time budget')
    if (d/'positions.jsonl').exists():
     lines=(d/'positions.jsonl').read_text().splitlines()
     try:last=json.loads(lines[-1]) if lines else None
     except json.JSONDecodeError:last=None
     if last and last['position']!=last_pos:
      last_pos=last['position'];s=dict(status='running',prompt=label,completed_positions=last_pos+1,prompt_positions=len(inp['tokens']),last_position=last,
       elapsed_seconds=time.monotonic()-start,combined_oracle_anonymous_bytes=anon,peak_anonymous_bytes=peak,pid=child.pid,updated_utc=utc(),free_root_bytes=free,scratch_bytes=scratch)
      save(attempt/'status.json',s);save(HERE/'status.json',s)
    time.sleep(2)
  except BaseException as failure:
   if child.poll() is None:child.send_signal(signal.SIGTERM);child.wait(timeout=60)
   after=resource.getrusage(resource.RUSAGE_CHILDREN)
   r.update(status='supervisor-stopped',error=str(failure),returncode=child.returncode,elapsed_seconds=time.monotonic()-start,cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,peak_anonymous_bytes=peak,completed_utc=utc())
   save(attempt/'receipt.json',r)
   raise
  finally:
   for sig,handler in old.items():signal.signal(sig,handler)
 after=resource.getrusage(resource.RUSAGE_CHILDREN)
 r.update(status=read(d/'result.json')['status'],returncode=child.returncode,elapsed_seconds=time.monotonic()-start,cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,peak_anonymous_bytes=peak,completed_utc=utc())
 save(attempt/'receipt.json',r);archived_logs(d,True)
 check(child.returncode==0,'CPU oracle failed; no automatic retry')
 return d

def mid_inventory(d,prompt_count):
 positions=sorted(set([prompt_count-1]+[p for p in (2040,2047,2048,2049,2050,2051,2100) if p<prompt_count]))
 check({int(p.name) for p in (d/'midprompt').iterdir()}==set(positions),'mid-prompt position coverage')
 expected_layers=[i for i in range(48) if i%4==3] # Verified against captured plan below; fail closed.
 inventory={};summaries=[]
 for position in positions:
  folder=d/'midprompt'/str(position);records=[read(p) for p in sorted(folder.glob('layer-*.json'))]
  check([r['layer'] for r in records]==expected_layers,'QSA layer coverage')
  for r in records:
   name=f"layer-{r['layer']:02}.ids.i32";raw=(folder/name).read_bytes();ids=list(struct.unpack('<2051i',raw));admitted=[i for i in ids if i>=0]
   count=min((position+1)//4,512)*4+(position+1)%4
   check(r['position']==position and r['prompt_ordinal']==position+1 and r['budget']==2048,'QSA metadata')
   check(ids==admitted+[-1]*(2051-len(admitted)) and r['ids']==admitted and len(admitted)==count,'QSA list layout')
   check(len(set(admitted))==count and all(0<=i<=position for i in admitted),'QSA ids range/unique')
   check(r['admitted']==count and r['dropped']==position+1-count and sha(folder/name)==r['selection_sha256'],'QSA digest/count')
   scores=[struct.unpack('<f',struct.pack('<I',b))[0] for b in r['pool_score_f32_bits']]
   check(len(scores)==(position+1)//4,'pool score count')
   rank=sorted(range(len(scores)),key=lambda j:(-scores[j],j))
   reference=[b*4+j for b in rank[:512] for j in range(4)]+list(range(len(scores)*4,position+1))
   check(reference==admitted,'stable pool-score ranking')
   ties=sum(scores[a]==scores[b] for a,b in zip(rank,rank[1:]));cutoff=len(rank)>512 and scores[rank[511]]==scores[rank[512]]
   check(ties==r['tied_adjacent_score_pairs'] and cutoff==r['cutoff_tie'],'tie summary')
  stream=read(folder/'stream.json');check(stream['position']==position and stream['layer']==47 and stream['shape']==[1,4,2560] and stream['dtype']=='BF16 little-endian','mid stream metadata')
  check((folder/'layer-47.bf16').stat().st_size==20480 and sha(folder/'layer-47.bf16')==stream['sha256'],'mid stream bytes')
  if position==prompt_count-1:check((folder/'layer-47.bf16').read_bytes()==(d/'step1/layer-47.bf16').read_bytes(),'last prompt/step1 equality')
  for p in sorted(folder.iterdir()):inventory[str(p.relative_to(d))]=sha(p)
  summaries.append(dict(position=position,prompt_ordinal=position+1,admitted=records[0]['admitted'],dropped=records[0]['dropped'],layers=len(records),layers_with_ties=sum(r['tied_adjacent_score_pairs']>0 for r in records),cutoff_tie_layers=[r['layer'] for r in records if r['cutoff_tie']]))
 return inventory,summaries

def validate(d,bundle,cap):
 result=read(d/'result.json');tokens=result['tokens'];check(result['status'] in ('token-cap','eos') and not result['error'],'complete result')
 check(result['arithmetic']=='iq3-p17-detmath-v2' and result['device_executed'] is False and result['context']==4096,'arithmetic')
 check(0<len(tokens)<=cap and (len(tokens)==cap or tokens[-1] in (248044,248046)),'token cap')
 check(not any(t in (248044,248046) for t in tokens[:-1]),'continued after EOS')
 check((result['status']=='eos')==(tokens[-1] in (248044,248046)),'EOS status')
 inp=read(bundle/'input.json');check((d/'input.json').read_bytes()==(bundle/'input.json').read_bytes(),'input identity')
 check(rows(d/'tokens.jsonl')==result['steps'] and [r['token_id'] for r in result['steps']]==tokens,'token records')
 check([r['step'] for r in result['steps']]==list(range(1,len(tokens)+1)),'token step order')
 positions=rows(d/'positions.jsonl');consumed=inp['tokens']+tokens[:-1]
 check([r['position'] for r in positions]==list(range(len(consumed))) and [r['input_token'] for r in positions]==consumed,'position/token coverage')
 checker=module('long_checker',HERE/'suite_check.py');fixtures=checker.fixture_inventory(d,len(tokens))
 mid,summaries=mid_inventory(d,len(inp['tokens']))
 teardown=load_teardown(d);check(len(teardown)==1 and teardown[0]['safe_to_exit'] and teardown[0]['live_bytes']==teardown[0]['in_flight']==0,'CPU teardown')
 return dict(passed=True,fixture_hashes=fixtures,midprompt_hashes=mid,selection_summary=summaries,generated_tokens=len(tokens),prompt_tokens=len(inp['tokens']),consumed_tokens_exact=True,positions=len(positions),mean_seconds_per_position=sum(r['seconds'] for r in positions)/len(positions))

def seal(label,bundle,cap):
 dest=HERE/label;attempt=HERE/('.'+label+'.partial');d=attempt/'native'
 if dest.exists():validate(dest,bundle,cap);return dest
 r=read(attempt/'receipt.json');result=read(d/'result.json');vocab=[]
 with (bundle/'vocab.bin').open('rb') as f:
  while h:=f.read(4):vocab.append(f.read(struct.unpack('<I',h)[0]))
 result.update(text=b''.join(vocab[t] for t in result['tokens']).decode('utf-8',errors='replace'),prompt_tokens=r['prompt_tokens'],id=label)
 save(d/'result.json',result);save(d/'arithmetic.json',r['arithmetic']);v=validate(d,bundle,cap);save(d/'validation.json',v)
 if label=='capacity-incident':save(d/'equality-proof.json',base.equality(d))
 r.update(status=result['status'],verified=True,result_sha256=sha(d/'result.json'),validation_sha256=sha(d/'validation.json'),coverage={k:v[k] for k in ('prompt_tokens','generated_tokens')},mean_seconds_per_position=v['mean_seconds_per_position'],seconds_per_position_sha256=sha(d/'positions.jsonl'),build_receipt_sha256=sha(HERE/'build-receipt.json'),log_retention_sha256=sha(d/'log-retention.json'))
 # Checkpoints are scratch, not unique evidence. Their byte hashes and full equality test are retained.
 if (d/'checkpoint.bin').exists():
  save(d/'checkpoint-retention.json',dict(sha256=sha(d/'checkpoint.bin'),bytes=(d/'checkpoint.bin').stat().st_size,state=read(d/'checkpoint.json'),disposition='regenerable scratch; removed only after verified complete run'))
  (d/'checkpoint.bin').unlink()
 r['teardown_retention']=retain_teardown(d,compress_one,save,sha)
 save(d/'receipt.json',r)
 for p in attempt.glob('stdout*.txt'):shutil.copyfile(p,d/p.name)
 d.rename(dest);return dest

def run_segmented(label,bundle,cap,allow_resume):
 # Preregistered segments, each executed once. Failure exits; it is never retried.
 if (HERE/label).exists():return launch(label,bundle,cap)
 d=HERE/('.'+label+'.partial/native');resuming=d.exists()
 check(not resuming or allow_resume,'existing partial requires explicit --resume')
 consumed_limit=len(read(bundle/'input.json')['tokens'])+cap-1
 while True:
  start=read(d/'checkpoint.json')['next_position'] if resuming else 0
  boundary=(start//100+1)*100
  check(start<=consumed_limit and boundary<=((consumed_limit+99)//100)*100+100,'segment bound')
  launch(label,bundle,cap,resume=resuming,extra={'IQ3_STOP_AT_CHECKPOINT':str(boundary)})
  result=read(d/'result.json')
  if result['status'] in ('eos','token-cap'):return
  check(result['status']=='checkpoint-stopped' and read(d/'checkpoint.json')['next_position']==boundary,'planned checkpoint stop required')
  resuming=True

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['all','capacity','resume-test','long','refresh'],required=True);ap.add_argument('--resume',action='store_true');ap.add_argument('--publish',action='store_true');a=ap.parse_args()
 if a.stage=='refresh':refresh();return
 with (HERE/'.runner.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  if a.stage in ('all','capacity'):
   bundle=ROOT/'experiments/own-xpu-runtime/stage2/suite-inputs-20261012/incident-retrospective'
   launch('capacity-incident',bundle,64,resume=a.resume);seal('capacity-incident',bundle,64)
   save(HERE/'status.json',dict(status='capacity-gate-passed',updated_utc=utc()))
  if a.stage in ('all','resume-test'):resume_test(a.resume)
  if a.stage in ('all','long'):
   check(read(HERE/'capacity-incident/equality-proof.json')['passed'],'capacity gate required');check(read(HERE/'resume-equality-proof.json')['passed'],'resume gate required')
   for label in ('LONG-A','LONG-B'):
    run_segmented(label,INPUTS/label,32,a.resume);seal(label,INPUTS/label,32);module('site_costs',HERE/'summarize_costs.py').summarize(HERE/label);refresh();checker_tests(label)
    if a.publish:publish(label)
   save(HERE/'status.json',dict(status='complete',updated_utc=utc()))
from campaign_support import install
install(sys.modules[__name__])
if __name__=='__main__':
 try:main()
 except BlockingIOError:raise
 except BaseException as e:save(HERE/'status.json',dict(status='stopped',error=str(e),updated_utc=utc()));raise
