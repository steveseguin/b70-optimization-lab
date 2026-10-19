#!/usr/bin/env python3
"""Durable, CPU-only split32 oracle campaign and hash-bound completion admission."""
import argparse,concurrent.futures,datetime,gzip,hashlib,importlib.util,json,os,shutil,struct,subprocess,sys,time,threading
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[4]
EXTERNAL=Path('/home/steve/own-xpu-runtime-results/packet49-integrate/oracle')
RESULTS=P/'results';OLD_MANIFEST=ROOT/'experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json'
MODEL='/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS'
IDENTITY='iq3-p49-split32-v1'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp-'+str(os.getpid()));tmp.write_text(json.dumps(x,indent=2)+'\n');tmp.replace(p)
def check(x,msg):
 if not x:raise RuntimeError(msg)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def checker():
 spec=importlib.util.spec_from_file_location('p49_checker',P/'suite_check.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def source_bindings():
 build=read(P/'build-receipt.json');check(build['passed'],'oracle build failed')
 check(sha(P/'arithmetic.json')==build['arithmetic_sha256'],'arithmetic identity changed')
 check(sha(EXTERNAL/'build/oracle')==build['binary_sha256'],'oracle binary changed')
 for n,h in build['sources'].items():check(sha(ROOT/n)==h,'oracle source changed: '+n)
 for n,h in build['frozen_sources'].items():check(sha(ROOT/n)==h,'oracle input source changed: '+n)
 identity=read(P/'arithmetic.json')
 for n,h in identity['arithmetic_sources'].items():check(sha(ROOT/n)==h,'frozen arithmetic source changed: '+n)
 for n,h in build['generated_sources'].items():check(sha(EXTERNAL/'build/src'/n)==h,'generated source changed: '+n)
 return build
def validate(directory,entry):
 ck=checker();result=read(directory/'result.json');tokens=ck.token_record(directory)
 check(result['device_executed'] is False,'device result forbidden')
 fixture_hashes=ck.fixture_inventory(directory,len(tokens))
 inp=read(ROOT/entry['input_bundle']/'input.json')
 check(read(directory/'input.json')==inp,'input differs')
 positions=[json.loads(x) for x in (directory/'positions.jsonl').read_text().splitlines()]
 consumed=inp['tokens']+tokens[:-1]
 check([r['position'] for r in positions]==list(range(len(consumed))),'position coverage')
 check([r['input_token'] for r in positions]==consumed,'consumed tokens differ')
 rows=[json.loads(x) for x in (directory/'tokens.jsonl').read_text().splitlines()]
 check(rows==result['steps'] and [r['token_id'] for r in rows]==tokens,'token log differs')
 teardown=read(directory/'teardown.json');check(len(teardown)==1 and teardown[0]['safe_to_exit'] and teardown[0]['live_bytes']==teardown[0]['in_flight']==0,'unsafe teardown')
 return dict(passed=True,fixture_hashes=fixture_hashes,generated_tokens=len(tokens),prompt_tokens=len(inp['tokens']),positions=len(positions),mean_seconds_per_position=sum(r['seconds'] for r in positions)/len(positions))
def run_one(entry,build,name=None):
 source_bindings();name=name or entry['prompt_id'];out=RESULTS/name
 check(not out.exists(),'refusing duplicate oracle job '+name)
 bundle=ROOT/entry['input_bundle'];inp=read(bundle/'input.json')
 check(inp['model_dir']==MODEL,'unadmitted model path')
 for n,h in entry['input_bundle_hashes'].items():check(sha(bundle/n)==h,'input changed '+n)
 check(shutil.disk_usage(EXTERNAL).free>=8_000_000_000,'free-space floor')
 cmd=[str(EXTERNAL/'build/oracle'),str(bundle),str(out),'10800','128']
 launch=dict(schema='packet49.oracle-launch.v1',device_executed=False,name=name,command=cmd,started_utc=utc(),binary_sha256=build['binary_sha256'])
 log=RESULTS/(name+'.log')
 with log.open('w') as stream:
  child=subprocess.Popen(cmd,stdout=stream,stderr=subprocess.STDOUT,env={**os.environ,'IQ3_MODEL_DIR':MODEL,'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1',**({'P49_CAPTURE':'1'} if entry['prompt_id']=='incident-retrospective' else {})})
  launch['pid']=child.pid;save(RESULTS/(name+'-launch.json'),launch);code=child.wait()
 launch.update(completed_utc=utc(),returncode=code);save(RESULTS/(name+'-launch.json'),launch)
 check(code==0,'CPU oracle failed; no retry: '+name)
 validation=validate(out,entry);save(out/'validation.json',validation)
 shutil.copyfile(P/'arithmetic.json',out/'arithmetic.json')
 result=read(out/'result.json');vocab=[]
 with (bundle/'vocab.bin').open('rb') as f:
  while h:=f.read(4):vocab.append(f.read(struct.unpack('<I',h)[0]))
 result['text']=b''.join(vocab[t] for t in result['tokens']).decode('utf-8',errors='replace');result['id']=entry['prompt_id'];result['prompt_tokens']=len(inp['tokens']);save(out/'result.json',result)
 receipt=dict(schema='packet49.cpu-oracle.prompt.v1',verified=True,device_executed=False,arithmetic=IDENTITY,binary_sha256=build['binary_sha256'],input_sha256=sha(bundle/'input.json'),result_sha256=sha(out/'result.json'),validation_sha256=sha(out/'validation.json'),launch_sha256=sha(RESULTS/(name+'-launch.json')),arithmetic_sha256=sha(P/'arithmetic.json'),generated_tokens=len(result['tokens']))
 receipt['compressed_logs']={}
 for n in ('progress.jsonl','timings.jsonl'):
  source=out/n
  if source.exists():
   digest=sha(source);receipt['compressed_logs'][n]=dict(sha256=digest,bytes=source.stat().st_size)
   with source.open('rb') as src,(out/(n+'.gz')).open('wb') as raw:
    with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as dest:shutil.copyfileobj(src,dest)
   with gzip.open(out/(n+'.gz'),'rb') as src:check(hashlib.file_digest(src,'sha256').hexdigest()==digest,'log archive mismatch')
   source.unlink()
 save(out/'receipt.json',receipt)
 return dict(entry,oracle_directory=str((P/'results'/name).relative_to(ROOT)),oracle_receipt_sha256=sha(out/'receipt.json'),generated_tokens=len(result['tokens']),first_8_token_ids=result['tokens'][:8],last_8_token_ids=result['tokens'][-8:],ended_early=len(result['tokens'])<128,termination=result['status'],context=4096,fixture_steps=[i for i in range(1,len(result['tokens'])+1) if i<=8 or 97<=i<=104],mean_seconds_per_position=validation['mean_seconds_per_position'])
def capture_draft_input(entry):
 directory=ROOT/entry['oracle_directory'];inp=read(directory/'input.json');result=read(directory/'result.json')
 # Preserve packet45's 87+63 position draft-capture coverage, including full
 # prefill history; target streams now belong to the split32 oracle identity.
 check(len(result['tokens'])>=64,'KD requires 64 generated oracle tokens')
 confirmed=inp['tokens']+result['tokens'];count=len(inp['tokens'])+63
 lines=[];streams={}
 for position in range(count):
  source=directory/'capture-streams'/f'streams-{position}.bf16'
  check(source.stat().st_size==20480,'KD stream extent')
  streams[str(source.resolve())]=sha(source)
  lines.append(f"{position} {confirmed[position+1]} {int(position>=len(inp['tokens'])-2)} {source.resolve()}\n")
 table=RESULTS/'capture-incident-retrospective.tsv';table.write_text(''.join(lines))
 save(RESULTS/'kd-capture.json',dict(passed=True,schema='packet49.oracle-draft-input.v1',arithmetic=IDENTITY,device_executed=False,prompt_id=entry['prompt_id'],rows=count,table=str(table.resolve()),table_sha256=sha(table),streams=streams,oracle_receipt_sha256=sha(directory/'receipt.json'),input_sha256=sha(directory/'input.json')))

def informational_diff(entries):
 rows=[]
 for old,new in zip(read(OLD_MANIFEST)['prompts'],entries):
  a=read(ROOT/old['oracle_directory']/'result.json')['tokens'];b=read(ROOT/new['oracle_directory']/'result.json')['tokens'];n=max(len(a),len(b));diff=[i+1 for i in range(n) if i>=len(a) or i>=len(b) or a[i]!=b[i]]
  rows.append(dict(prompt_id=new['prompt_id'],old_result_sha256=sha(ROOT/old['oracle_directory']/'result.json'),new_result_sha256=sha(ROOT/new['oracle_directory']/'result.json'),first_difference=diff[0] if diff else None,differing_positions=diff,old_tokens=a,new_tokens=b))
 save(RESULTS/'old-v-new.json',dict(informational_only=True,quality_or_speed_gate=False,old_arithmetic='iq3-p17-detmath-v2',new_arithmetic=IDENTITY,prompts=rows))
def run():
 check(os.getpriority(os.PRIO_PROCESS,0)==19,'nice 19 required');check(set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32)),'reserved cores forbidden')
 check(os.environ.get('OMP_NUM_THREADS')=='2','two threads required')
 check(RESULTS.is_symlink() and RESULTS.resolve()==EXTERNAL/'results','external output symlink required')
 build=source_bindings();manifest=read(OLD_MANIFEST);check(manifest['complete'] and len(manifest['prompts'])==12 and manifest['token_cap']==128,'frozen suite scope')
 RESULTS.mkdir(parents=True,exist_ok=True);check(not (RESULTS/'campaign.json').exists(),'campaign already exists; no automatic retry')
 campaign=dict(schema='packet49.cpu-oracle.campaign.v1',status='running',started_utc=utc(),device_executed=False,workers=2,threads_per_worker=2,cpu_affinity=sorted(os.sched_getaffinity(0)),nice=19,model_path=MODEL,oracle_build_receipt_sha256=sha(P/'build-receipt.json'),input_manifest_sha256=sha(OLD_MANIFEST),expected_prompts=12,token_cap=128,repeat_prompts=['incident-retrospective'],estimate_hours=[6,12])
 save(RESULTS/'campaign.json',campaign)
 try:
  # Two workers total, one compiler and one composite arithmetic mode. Each
  # prompt is a fresh host-only process; scheduling never splits row arithmetic.
  abort=threading.Event()
  def guarded(entry):
   check(not abort.is_set(),'earlier job failed; no new model launch')
   try:return run_one(entry,build)
   except BaseException:
    abort.set();raise
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   futures=[pool.submit(guarded,e) for e in manifest['prompts']]
   entries=[f.result() for f in futures]
  repeated=run_one(manifest['prompts'][0],build,'incident-retrospective-repeat')
  ck=checker();first=ROOT/entries[0]['oracle_directory'];second=ROOT/repeated['oracle_directory']
  check(ck.token_record(first)==ck.token_record(second),'fresh-process token repeat failed')
  check(ck.fixture_inventory(first,len(ck.token_record(first)))==ck.fixture_inventory(second,len(ck.token_record(second))),'fresh-process fixture repeat failed')
  repeat=dict(passed=True,prompt_id='incident-retrospective',tokens=len(ck.token_record(first)),fixtures=len(ck.fixture_inventory(first,len(ck.token_record(first)))),first_receipt_sha256=sha(first/'receipt.json'),repeat_receipt_sha256=sha(second/'receipt.json'),scope='One complete prompt repeated in a fresh CPU process; all 12 require device fresh-server qualification')
  save(RESULTS/'determinism.json',repeat)
  new=dict(manifest,arithmetic=IDENTITY,context=4096,prompts=entries,complete=True);save(RESULTS/'suite-manifest.json',new)
  for e in entries:ck.check_prompt(ROOT/e['oracle_directory'],ROOT/e['oracle_directory'],e,ROOT)
  capture_draft_input(entries[0]);informational_diff(entries);source_bindings()
  completion=dict(schema='packet49.cpu-oracle.complete.v1',passed=True,device_executed=False,completed_utc=utc(),prompts=12,token_cap=128,arithmetic=IDENTITY,manifest_sha256=sha(RESULTS/'suite-manifest.json'),build_receipt_sha256=sha(P/'build-receipt.json'),arithmetic_sha256=sha(P/'arithmetic.json'),old_manifest_sha256=sha(OLD_MANIFEST),determinism_sha256=sha(RESULTS/'determinism.json'),old_v_new_sha256=sha(RESULTS/'old-v-new.json'),kd_capture_sha256=sha(RESULTS/'kd-capture.json'))
  save(RESULTS/'completion.json',completion);campaign.update(status='complete',completed_utc=utc());save(RESULTS/'campaign.json',campaign)
 except BaseException as e:
  campaign.update(status='failed',error=str(e),completed_utc=utc());save(RESULTS/'campaign.json',campaign);raise
def status(required):
 p=RESULTS/'completion.json'
 if not p.exists():
  state=read(RESULTS/'campaign.json') if (RESULTS/'campaign.json').exists() else {'status':'not-started'}
  print(json.dumps(dict(ready=False,**state)));return 1 if required else 0
 c=read(p);source_bindings();check(c['passed'] and c['arithmetic']==IDENTITY,'invalid completion')
 for key,path in [('manifest_sha256',RESULTS/'suite-manifest.json'),('build_receipt_sha256',P/'build-receipt.json'),('arithmetic_sha256',P/'arithmetic.json'),('old_manifest_sha256',OLD_MANIFEST),('determinism_sha256',RESULTS/'determinism.json'),('old_v_new_sha256',RESULTS/'old-v-new.json'),('kd_capture_sha256',RESULTS/'kd-capture.json')]:check(c[key]==sha(path),'completion binding changed '+key)
 manifest=read(RESULTS/'suite-manifest.json');check(manifest['complete'] and len(manifest['prompts'])==12 and manifest['token_cap']==128,'incomplete manifest')
 ck=checker()
 for e in manifest['prompts']:ck.check_prompt(ROOT/e['oracle_directory'],ROOT/e['oracle_directory'],e,ROOT)
 capture=read(RESULTS/'kd-capture.json');check(sha(Path(capture['table']))==capture['table_sha256'],'KD table changed')
 for n,h in capture['streams'].items():check(sha(RESULTS/n)==h,'KD stream changed '+n)
 print(json.dumps(dict(ready=True,completion=c)));return 0
def main():
 a=argparse.ArgumentParser();a.add_argument('action',choices=['run','status']);a.add_argument('--require-complete',action='store_true');args=a.parse_args()
 if args.action=='run':run();return 0
 return status(args.require_complete)
if __name__=='__main__':sys.exit(main())
