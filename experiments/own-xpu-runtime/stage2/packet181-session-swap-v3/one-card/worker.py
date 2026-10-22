"""One load; complete resets; in-run validation is stream format and exact prefix only.

packet180: kind lifecycle is the append / restore-then-save gate (row b).
packet181: the same row; manifests carry label qualified-one-card (contract v1.2+p181), every leg
records its prompt path, and the append prefill cost is reported against the cold reference.
"""
import argparse,copy,json,os,signal,struct,subprocess,time
from pathlib import Path
from common import HERE,D,read,save,require,sha
import measurement
import exec_limits

LIFECYCLE=read(HERE/'lifecycle.json')
INSPECT_TOOL_TIMEOUT_SECONDS=600  # worker-local bound on each device-free host tool (inspect/delete); not a native or window deadline


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
 return ['/usr/bin/ionice','-c3',*cmd]

def run_native(cmd,output):
 """One fresh native process with the same polling/stop discipline as one()."""
 child=None;stop=[]
 def signal_stop(sig,frame):
  stop.append(sig)
  if child is not None and child.poll()is None:child.send_signal(signal.SIGTERM)
 handlers={s:signal.signal(s,signal_stop)for s in(signal.SIGINT,signal.SIGTERM)}
 try:
  with(output/'native.log').open('w')as log:
   exec_limits.check();child=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
   while child.poll()is None:
    require(not stop,'coordinator stop');time.sleep(.25)
  require(child.returncode==0 and not stop,'native failed; no retry')
 finally:
  for s,h in handlers.items():signal.signal(s,h)

def native_single_command(output,input_path,max_new,checkpoint_args):
 """Single-request native argv for one lifecycle leg: the parent argv minus --suite-inputs,
 plus checkpoint flags; every checkpoint leg carries the packet tokenizer identity."""
 cmd=read(HERE/'parent-native-argv.json')
 require(cmd.count('--suite-inputs')==1,'native flag --suite-inputs')
 at=cmd.index('--suite-inputs');del cmd[at:at+2]
 def replace(k,v):require(cmd.count(k)==1,'native flag '+k);cmd[cmd.index(k)+1]=str(v)
 cmd[0]=str(HERE/'build/device/own-rt-iq3')
 for k,v in [('--max-new',max_new),('--seconds',7200),('--wait-seconds',600),('--output',output),
  ('--input',input_path),('--plan',HERE/'inputs/plan.tsv'),
  ('--identity',HERE/'inputs/identity.tsv'),('--selection',HERE/'selection.json'),('--selection-sha256',sha(HERE/'selection.json')),('--dispatch',HERE/'dispatch.json')]:replace(k,v)
 extra=[str(x) for x in checkpoint_args]
 if extra:extra+=['--tokenizer-identity',str(HERE/'tokenizer-identity.tsv')]
 return ['/usr/bin/ionice','-c3',*cmd,*extra]

def lifecycle_legs(root,prompt_path,new_path):
 L=LIFECYCLE;ids=L['checkpoint_ids']
 return [
  dict(leg='save-s1',input=prompt_path,max_new=L['K'],operation='save',
   args=['--checkpoint-save',root,'--checkpoint-id',ids['S1']]),
  dict(leg='append-s2',input=new_path,max_new=L['M1'],operation='append + restore-then-save',
   args=['--checkpoint-restore',root,'--checkpoint-id',ids['S1'],'--checkpoint-save',root,'--checkpoint-save-id',ids['S2']]),
  dict(leg='resume-s2',input=new_path,max_new=L['M2'],operation='same-generation resume',
   args=['--checkpoint-restore',root,'--checkpoint-id',ids['S2']]),
  dict(leg='reference',input=new_path,max_new=L['M1']+L['M2'],operation='fresh one-shot reference',args=[]),
  dict(leg='append-s2b',input=new_path,max_new=L['M1'],operation='append + restore-then-save (repeat)',
   args=['--checkpoint-restore',root,'--checkpoint-id',ids['S1'],'--checkpoint-save',root,'--checkpoint-save-id',ids['S2b']]),
 ]

def host_tool(flag,target,folder):
 """One device-free checkpoint host tool of this packet's binary; stdout must be ONE JSON object."""
 cmd=[str(HERE/'build/device/own-rt-iq3'),flag,str(target)]
 folder.mkdir(parents=True,exist_ok=True);stem=flag.lstrip('-')+'-'+Path(target).name
 cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=INSPECT_TOOL_TIMEOUT_SECONDS)
 (folder/(stem+'.stdout.json')).write_text(cp.stdout);(folder/(stem+'.stderr.jsonl')).write_text(cp.stderr)
 row=dict(argv=cmd,returncode=cp.returncode,stdout_object=None,stdout_lines=len(cp.stdout.splitlines()),stderr_json_lines=True)
 try:
  value=json.loads(cp.stdout)
  row['stdout_object']=value if isinstance(value,dict) else None
 except ValueError as error:row['stdout_parse_error']=str(error)
 for line in cp.stderr.splitlines():
  try:json.loads(line)
  except ValueError:row['stderr_json_lines']=False
 return row

def lifecycle(output):
 """Row b: five fresh processes of this binary (save S1; restore S1 + append T + save S2;
 resume S2; one-shot reference of the same input; repeat append into S2b), then the
 device-free host tools, then the comparisons. A divergence is a recorded FAILURE with the
 first divergent index and both streams; it is never tolerated."""
 L=LIFECYCLE
 require(measurement.IDS[0]==L['prompt_id'],'lifecycle prompt is the first registered suite prompt')
 prompt_path=HERE/'inputs'/L['prompt_id']/'tokens.txt'
 prompt=list(map(int,prompt_path.read_text().split()))
 turn=measurement.lifecycle_turn(L,HERE)
 oracle=read(HERE/'lineage/oracle128'/(L['prompt_id']+'.json'))['tokens']
 p179=read(HERE/'reference-p179-row-a.json')['prompts'][L['prompt_id']]['tokens']
 root=output/'checkpoints';inputs=output/'inputs';inputs.mkdir(parents=True)
 new_path=inputs/'new.txt'
 results={};receipts=[];prefill={}
 try:
  for spec in lifecycle_legs(root,prompt_path,new_path):
   if spec['leg']=='append-s2':
    new=measurement.lifecycle_input(prompt,results['save-s1']['tokens'],turn,L)
    new_path.write_text(' '.join(map(str,new))+'\n')
    save(inputs/'new.json',dict(tokens=len(new),prompt_tokens=len(prompt),saved_generation=L['K'],turn_tokens=len(turn),
     construction='P + gen(save-s1)[0:K] + T; gen[K-1] is the saved pending token; T from lifecycle.json'))
   legout=output/'run'/spec['leg'];legout.mkdir(parents=True);dest=legout/'native'
   cmd=native_single_command(dest,spec['input'],spec['max_new'],spec['args'])
   save(legout/'launch.json',dict(argv=cmd,operation=spec['operation']))
   run_native(cmd,legout)
   receipts.append(read(dest/'receipt.json'))
   require((dest/'lookup-request-complete.json').is_file(),'completion marker missing: '+spec['leg'])
   reset=read(dest/'reset.json')
   require(reset.get('passed')is True and reset.get('cached_tokens')==0 and reset.get('allocation_ids_preserved')is True,'cold request reset missing: '+spec['leg'])
   streams={'timings.jsonl':measurement.check_file_stream(dest/'timings.jsonl')}
   if spec['leg']!='resume-s2':streams['prefill-timings.jsonl']=measurement.check_file_stream(dest/'prefill-timings.jsonl')
   prefill[spec['leg']]=measurement.prefill_rows(dest/'prefill-timings.jsonl')  # packet181: per-position prompt-step rows
   save(dest/'stream-proof.json',dict(passed=True,streams=streams,scope='presence/format only; the same-generation resume leg has an empty prefill stream by construction'))
   results[spec['leg']]=read(dest/'result.json');results[spec['leg']]['request_reset_sha256']=[sha(dest/'reset.json')]
 except BaseException as error:
  save(output/'lifecycle-receipt.json',dict(passed=False,device_executed=False,stage='native legs',error=str(error),completed_legs=list(results),
   results={k:dict(tokens=v.get('tokens'),checkpoint=v.get('checkpoint')) for k,v in results.items()}))
  if receipts:save(output/'teardown-partial.json',dict(receipts=len(receipts),scope='legs completed before the failure'))
  raise
 save(output/'teardown.json',prove_drain(receipts))
 ids=L['checkpoint_ids'];manifests={}
 for key in ('S1','S2','S2b'):
  cid=ids[key];folder=root/cid;manifest=read(folder/'manifest.json')
  tokens=list(struct.unpack('<%di'%(manifest['token_state']['position']),(folder/'tokens.bin').read_bytes()))
  small={n:(folder/(n+'.bin')).read_bytes() for n in ('position','next_token','token','error','token_history') if (folder/(n+'.bin')).is_file()}
  manifests[cid]=dict(manifest=manifest,sha256=sha(folder/'manifest.json'),fields_sha256=sha(folder/'fields.tsv'),
   semantics=measurement.manifest_semantics(manifest,tokens,small))
 tools={}
 for key in ('S1','S2','S2b'):tools['metadata-'+ids[key]]=host_tool('--checkpoint-inspect-metadata',root/ids[key],output/'tools')
 for key in ('S2','S2b'):tools['full-'+ids[key]]=host_tool('--checkpoint-inspect',root/ids[key],output/'tools')
 keep=output/'s2b-manifest-copy';keep.mkdir()
 for leaf in ('manifest.json','fields.tsv'):(keep/leaf).write_bytes((root/ids['S2b']/leaf).read_bytes())
 tools['delete-'+ids['S2b']]=host_tool('--checkpoint-delete',root/ids['S2b'],output/'tools')
 tools['delete-'+ids['S2b']].update(directory_removed=not (root/ids['S2b']).exists(),lock_removed=not (root/(ids['S2b']+'.lock')).exists())
 check=measurement.lifecycle_check_v3(results,manifests,tools,L,prompt,turn,p179,oracle,prefill)
 save(output/'lifecycle-receipt.json',dict(check,prompt_id=L['prompt_id'],prompt_tokens=len(prompt),turn_tokens=len(turn),
  new_input_tokens=len(prompt)+L['K']+len(turn),K=L['K'],M1=L['M1'],M2=L['M2'],
  manifests={cid:dict(sha256=m['sha256'],fields_sha256=m['fields_sha256'],semantics=m['semantics'],
   token_state=m['manifest']['token_state'],lineage=m['manifest']['lineage'],measurements=m['manifest']['measurements'],
   blob_count=len(m['manifest']['blobs'])) for cid,m in manifests.items()},
  tools={k:{kk:vv for kk,vv in v.items() if kk!='stdout_object'}|dict(ok=(v.get('stdout_object') or {}).get('ok')) for k,v in tools.items()},
  reset_sha256={leg:results[leg]['request_reset_sha256'] for leg in results},
  s2b_note='S2b blobs are deleted by the delete-tool gate after the full inspect verified them and their sha256 equal S2; its manifest.json and fields.tsv are kept in s2b-manifest-copy/',
  scope='session checkpoint lifecycle (manifest label qualified-one-card, contract v1.2+p181): append, restore-then-save, chain resume and repeat determinism versus a one-shot fresh reference of the same input; every leg records its prompt path; oracle cap 128 on the save leg; the append prefill timing is a reported observation, not a gate and not a performance claim; one card only, TP2 checkpoints not implemented, no ctxkeeper adapter'))
 require(check['passed'],'lifecycle gate FAILED: '+', '.join(check['problems'])+' (run/lifecycle-receipt.json holds the first divergent index and both streams)')

def p179_identity_gate(output,observed):
 """Row a: every request's full output must equal packet179 row a (relinked binary, unchanged arithmetic)."""
 check=measurement.p179_identity(observed,read(HERE/'reference-p179-row-a.json'))
 save(output/'p179-identity.json',check)
 require(check['passed'],'packet180 row a output differs from packet179 row a (run/p179-identity.json)')
 return check

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
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--lane',choices=('A','B'),required=True)
 ap.add_argument('--kind',choices=('full512','lifecycle'),default='full512');ap.add_argument('--reference',type=Path);a=ap.parse_args()
 require((a.output.parent/'window.json').is_file(),'outer admitted window required')
 identity=read(a.output.parent/'identity.json');require(identity['lane']==a.lane,'lane binding')
 a.output.mkdir()
 if a.kind=='lifecycle':
  require(a.reference is None,'the lifecycle row is self-contained; it takes no --reference')
  lifecycle(a.output);return 0
 items=entries()
 observed=one(a.output,items)if read(HERE/'identity.json')['gpu_count']==1 else two(a.output,items)
 # This process has released every device before doing metric aggregation.
 rows=[measurement.request(read(observed[e['prompt_id']]['path']),e['tokens'],e['prompt_id'],expected(e))for e in items]
 by_id={r['prompt_id']:r for r in rows}
 p179_identity_gate(a.output,{pid:r['tokens'] for pid,r in by_id.items()})
 save(a.output/'report-inputs.json',dict(passed=True,requests=[by_id[i] for i in measurement.IDS],prefill=by_id['prefill512'],execution_order=[e['prompt_id'] for e in items],device_isolation=dict(passed=True,scope='outer whole-host admission and complete owner drain'),lane=a.lane))
 return 0
if __name__=='__main__':raise SystemExit(main())
