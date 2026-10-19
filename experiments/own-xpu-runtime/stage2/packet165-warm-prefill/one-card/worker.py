"""One load; complete resets; in-run validation is stream format and exact prefix only."""
import argparse,copy,json,os,signal,subprocess,time
from pathlib import Path
from common import HERE,D,read,save,require,sha
import measurement
import exec_limits


def entries():
 manifest=read(HERE/'lineage/oracle128/suite-manifest.json')
 # The first registered prompt is the distinct warm-up, run ONCE.
 result=[manifest['prompts'][0],dict(prompt_id='prefill512',prompt_tokens=512),*manifest['prompts'][1:]]
 for row in result:
  row['tokens']=list(map(int,(HERE/'inputs'/row['prompt_id']/'tokens.txt').read_text().split()))
  require(len(row['tokens'])==row['prompt_tokens'],'input length')
 require(len({tuple(e['tokens']) for e in result})==13,'all prompts must be distinct; no warm-up reuse')
 return result

def expected(entry):
 if entry['prompt_id']=='prefill512':return None
 return read(HERE/'lineage/oracle128'/ (entry['prompt_id']+'.json'))['tokens']

def record_request(dest,entry,result,observed):
 result.update(requested_max_new=512,prompt_tokens=len(entry['tokens']))
 # Do not change cache counts; they come from reset/engine evidence.
 check=measurement.stream_check(result,expected(entry))
 result.update(prompt_id=entry['prompt_id'],oracle_check=check)
 if entry['prompt_id']=='prefill512':
  warm_id=measurement.IDS[0]
  require(list(observed)==[warm_id],'prefill must be second, after exactly one distinct request')
  warm=read(observed[warm_id]['path'])
  warm_tokens=entries()[0]['tokens']
  require(warm_tokens!=entry['tokens'] and warm.get('cached_tokens')==0,'distinct uncached warm-up required')
  require(warm['request_end_monotonic']<=result['request_start_monotonic'],'warm-up must finish before prefill')
  result['warmup']=dict(prompt_id=warm_id,prompt_token_sha256=measurement.digest(warm_tokens),
    receipt_sha256=sha(Path(observed[warm_id]['path'])),output_tokens=len(warm['tokens']),
    completed_before_prefill=True,request_count_before_prefill=1,suite_prompt_used_once=True,
    state_reset_before_prefill=True,reset_sha256=result['request_reset_sha256'],cached_tokens=0)

 save(dest/'receipt.json',result)
 return dict(path=str(dest/'receipt.json'),prompt_id=entry['prompt_id'])

def native_command(output,table):
 cmd=read(HERE/'parent-native-argv.json')
 def replace(k,v):require(cmd.count(k)==1,'native flag '+k);cmd[cmd.index(k)+1]=str(v)
 cmd[0]=str(HERE/'build/device/own-rt-iq3')
 for k,v in [('--max-new',512),('--seconds',7200),('--wait-seconds',600),('--output',output/'native'),
  ('--suite-inputs',table),('--input',HERE/'inputs/prefill512/tokens.txt'),('--plan',HERE/'inputs/plan.tsv'),
  ('--identity',HERE/'inputs/identity.tsv'),('--selection',HERE/'selection.json'),('--selection-sha256',sha(HERE/'selection.json')),('--dispatch',HERE/'dispatch.json')]:replace(k,v)
 return cmd

def prove_drain(receipts):
 for row in receipts:
  require(row.get('passed')is True and row.get('device_executed')is True,'native owner failed')
  owners=row.get('teardown',[]);require(len(owners)==1,'one teardown per native owner')
  o=owners[0];require(o.get('safe_to_exit')is True and o.get('idle_marker_complete')is True and all(type(o.get(k))is int and o[k]==0 for k in ('live_bytes','in_flight','exit_code')),'native drain incomplete')
 return dict(drained=True,owner_count=len(receipts),safe_to_exit=True)

def one(output,items):
 table=output/'suite-inputs.tsv';table.write_text(''.join(e['prompt_id']+' '+str(HERE/'inputs'/e['prompt_id']/'tokens.txt')+'\n'for e in items))
 cmd=native_command(output,table);save(output/'launch.json',dict(argv=cmd))
 child=None;stop=[];observed={}
 def signal_stop(sig,frame):
  stop.append(sig)
  if child is not None and child.poll()is None:child.send_signal(signal.SIGTERM)
 handlers={s:signal.signal(s,signal_stop)for s in(signal.SIGINT,signal.SIGTERM)}
 def inspect_completed():
  for entry in items:
   if entry['prompt_id']in observed:continue
   dest=output/'native'/entry['prompt_id'];path=dest/'result.json'
   if not path.exists():continue
   # Native publishes this completion marker after its result and streams.
   if not(dest/'lookup-request-complete.json').exists():continue
   result=read(path);reset=read(dest/'reset.json')
   require(reset.get('passed')is True and reset.get('cached_tokens')==0 and reset.get('allocation_ids_preserved')is True,'cold request reset missing')
   result['request_reset_sha256']=[sha(dest/'reset.json')]
   result['request_start_boundary']='before native reset (TTFT includes reset)'
   streams={name:measurement.check_file_stream(dest/name)for name in('timings.jsonl','prefill-timings.jsonl')}
   observed[entry['prompt_id']]=record_request(dest,entry,result,observed)
   save(dest/'stream-proof.json',dict(passed=True,streams=streams,scope='presence/format and oracle prefix only'))
 try:
  with(output/'native.log').open('w')as log:
   exec_limits.check();child=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
   while child.poll()is None:
    require(not stop,'coordinator stop');inspect_completed();time.sleep(.25)
  require(child.returncode==0 and not stop,'native failed; no retry')
  inspect_completed();require(len(observed)==13,'all13 request streams required')
  from composition import check_lookups,check_census
  receipt=read(output/'native/receipt.json');check_lookups(receipt);check_census(read(output/'native/census.json'))
  save(output/'teardown.json',prove_drain([receipt]))
  return observed
 except BaseException:
  if child is not None and child.poll()is None:
   child.send_signal(signal.SIGTERM)
   # The outer admitted unit retains ownership. Never detach or hard-kill.
   child.wait()
  if child is not None and child.returncode==0:
   save(output/'teardown.json',prove_drain([read(output/'native/receipt.json')]))
  raise
 finally:
  for s,h in handlers.items():signal.signal(s,h)

def two(output,items):
 import pipeline,suite,storage
 adapter=output/'adapter';adapter.mkdir();(adapter/'build').mkdir()
 for leaf in ('selection.json','memory-plan.json'):(adapter/leaf).write_bytes((HERE/leaf).read_bytes())
 pipeline.P=adapter;storage.P=output
 args=pipeline.parser().parse_args(['--output',str(output),'--device','--binary',str(HERE/'build/device/own-rt-iq3'),
  '--dispatch',str(HERE/'dispatch.json'),'--controller','native','--draft','mtp','--draft-rank','1','--target-split','0',
  '--context','4096','--tokens','512','--retain-steps','none','--timing','token','--native-nice','0','--card','0',
  '--seconds','7200','--wait-seconds','1200'])
 args.selection_sha256=sha(HERE/'selection.json');args.input=HERE/'inputs'
 ranks=output/'ranks';ranks.mkdir();transport=pipeline.Transport.__new__(pipeline.Transport);stopped=[]
 handlers={s:signal.signal(s,lambda n,f:stopped.append(n))for s in(signal.SIGINT,signal.SIGTERM)}
 def check():require(not stopped,'coordinator stop')
 observed={};previous=None
 def completed_streams(dest):
  for rank in (0,1):measurement.check_file_stream(dest/f'rank{rank}/timings.jsonl')
 try:
  exec_limits.check();pipeline.Transport.__init__(transport,args,ranks,dict(os.environ),check)
  for entry in items:
   check();dest=output/'requests'/entry['prompt_id'];suite.reset(transport,dest)
   if previous is not None:completed_streams(previous)
   result=pipeline.NativeController(transport,pipeline.Draft('mtp'),True,False).run(entry['tokens'],512,(248044,248046))
   for rank in(0,1):
    reset=read(dest/f'rank{rank}/reset.json');require(reset.get('passed')is True and reset.get('allocation_ids_preserved')is True,'native complete reset required')
   result['request_reset_sha256']=[sha(dest/f'rank{rank}/reset.json')for rank in(0,1)]
   result['request_start_boundary']='after full reset (TTFT excludes reset)'
   result.update(passed=True,arithmetic='iq3-p49-split32-v1',cached_tokens=0,cache_zero_evidence='both native full-allocation reset receipts; no reuse path',
    request_start_monotonic=transport.work_start,request_end_monotonic=transport.work_end)
   observed[entry['prompt_id']]=record_request(dest,entry,result,observed);previous=dest
  suite.reset(transport,output/'after-suite');completed_streams(previous);transport.close(True)
  save(output/'teardown.json',prove_drain([read(ranks/f'rank{i}/receipt.json')for i in(0,1)]))
  return observed
 except BaseException as error:
  if hasattr(transport,'stop_write')and not transport.closed:
   transport.check=lambda:None
   try:transport.stop(error);transport.close(False)
   finally:
    while any(p.poll()is None for p in transport.children):time.sleep(.25)
  raise
 finally:
  for s,h in handlers.items():signal.signal(s,h)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--lane',choices=('A','B'),required=True);a=ap.parse_args()
 require((a.output.parent/'window.json').is_file(),'outer admitted window required')
 identity=read(a.output.parent/'identity.json');require(identity['lane']==a.lane,'lane binding')
 a.output.mkdir();items=entries()
 observed=one(a.output,items)if read(HERE/'identity.json')['gpu_count']==1 else two(a.output,items)
 # This process has released every device before doing metric aggregation.
 rows=[measurement.request(read(observed[e['prompt_id']]['path']),e['tokens'],e['prompt_id'],expected(e))for e in items]
 by_id={r['prompt_id']:r for r in rows}
 save(a.output/'report-inputs.json',dict(passed=True,requests=[by_id[i] for i in measurement.IDS],prefill=by_id['prefill512'],execution_order=[e['prompt_id'] for e in items],device_isolation=dict(passed=True,scope='outer whole-host admission and complete owner drain'),lane=a.lane))
 return 0
if __name__=='__main__':raise SystemExit(main())
