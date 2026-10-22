"""Apply the packet180 entry-TU native delta and harness edits (idempotent, fail-closed).

Native delta: start from packet179's patched main.cpp (path-normalized to packet165's tree,
exactly the form packet179's adapt wrote and its native-delta.json pins), apply the packet180
edits (append, restore-then-save, tokenizer identity, one manifest source of truth, shared
sibling lock, inspect modes) and install the packet-root checkpoint.hpp v2 beside it. Kernel
arithmetic untouched: build_checkpoint.py relinks every kernel object byte-identical from
packet165, exactly as packet179 did. Harness edits: worker/measurement/screen/entry lifecycle
kind, native-help-flags, budget; new lifecycle.json, tokenizer-identity.tsv and
reference-p179-row-a.json (derived from the in-packet packet179 receipt copies).
"""
import difflib,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
OLD179=P.parent/'packet179-session-swap'
OLD165=P.parent/'packet165-warm-prefill'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def sha_text(t):return hashlib.sha256(t.encode()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')

NAT='native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native'
MAIN=P/'one-card'/NAT/'main.cpp'

def replace_once(text,old,new,what):
 assert text.count(old)==1,('anchor',what,text.count(old))
 return text.replace(old,new,1)

def native_edits(text):
 # 1. Options fields.
 text=replace_once(text,'  fs::path checkpoint_save, checkpoint_restore; std::string checkpoint_id;\n',
  '  fs::path checkpoint_save, checkpoint_restore, tokenizer_identity; std::string checkpoint_id, checkpoint_save_id;\n','options')
 # 2. --help (alphabetical).
 text=replace_once(text,'--checked --checkpoint-delete --checkpoint-id --checkpoint-inspect --checkpoint-restore --checkpoint-save --context',
  '--checked --checkpoint-delete --checkpoint-id --checkpoint-inspect --checkpoint-inspect-metadata --checkpoint-restore --checkpoint-save --checkpoint-save-id --context','help1')
 text=replace_once(text,'--timing --tokens --wait-seconds','--timing --tokenizer-identity --tokens --wait-seconds','help2')
 # 3. Parser branches.
 anchor='    else if (k == "--checkpoint-id") a.checkpoint_id=value();\n'
 text=replace_once(text,anchor,anchor+
  '    else if (k == "--checkpoint-save-id") a.checkpoint_save_id=value();\n'
  '    else if (k == "--tokenizer-identity") a.tokenizer_identity=value();\n','parser')
 # 4. Guards: save and restore now combine (restore-then-save); tokenizer identity required.
 old_guards=r'''  require(a.checkpoint_save.empty()||a.checkpoint_restore.empty(),"checkpoint save and restore are exclusive");
  require((a.checkpoint_save.empty()&&a.checkpoint_restore.empty())||a.suite_inputs.empty(),"checkpoint modes are single-request only");
  require(a.checkpoint_id.empty()||(!a.checkpoint_save.empty()||!a.checkpoint_restore.empty()),"--checkpoint-id requires a checkpoint mode");
  if(!a.checkpoint_save.empty()||!a.checkpoint_restore.empty())
    require(!a.checkpoint_id.empty()&&a.checkpoint_id.size()<=64&&
            a.checkpoint_id.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")==std::string::npos,
            "checkpoint id must be nonempty and filename-safe");
'''
 new_guards=r'''  {
    // packet180: save and restore combine (restore-then-save writes a NEW id and never
    // overwrites); every checkpoint operation carries the tokenizer/template identity.
    const bool ckpt_save=!a.checkpoint_save.empty(),ckpt_restore=!a.checkpoint_restore.empty();
    auto valid_id=[](const std::string& id){
      auto alnum=[](char c){return (c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9');};
      return !id.empty()&&id.size()<=64&&alnum(id[0])&&!id.ends_with(".lock")&&
             id.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")==std::string::npos;};
    require((!ckpt_save&&!ckpt_restore)||a.suite_inputs.empty(),"checkpoint modes are single-request only");
    require((!ckpt_save&&!ckpt_restore)||(!a.first&&a.bracket_inputs.empty()),"checkpoint modes require a plain decode request");
    require(a.checkpoint_id.empty()||ckpt_save||ckpt_restore,"--checkpoint-id requires a checkpoint mode");
    require(a.checkpoint_save_id.empty()||(ckpt_save&&ckpt_restore),"--checkpoint-save-id names the new checkpoint of restore-then-save; it requires --checkpoint-restore and --checkpoint-save");
    require(a.tokenizer_identity.empty()||ckpt_save||ckpt_restore,"--tokenizer-identity requires a checkpoint mode");
    if(ckpt_save||ckpt_restore) {
      require(valid_id(a.checkpoint_id),"checkpoint id must be 1..64 filename-safe characters starting with a letter or digit, not ending in .lock");
      require(!a.tokenizer_identity.empty(),"--tokenizer-identity FILE is required for every checkpoint operation");
    }
    if(ckpt_save&&ckpt_restore) {
      require(valid_id(a.checkpoint_save_id),"restore-then-save requires --checkpoint-save-id ID2 (1..64 filename-safe characters starting with a letter or digit)");
      require(fs::weakly_canonical(a.checkpoint_save)/a.checkpoint_save_id!=fs::weakly_canonical(a.checkpoint_restore)/a.checkpoint_id,
              "restore-then-save must write a new checkpoint; it never overwrites the restored one");
    }
  }
'''
 text=replace_once(text,old_guards,new_guards,'guards')
 # 5. Device-free host tools: inspect (full), inspect-metadata, delete.
 text=replace_once(text,'  if(argc==3&&(std::string(argv[1])=="--checkpoint-inspect"||std::string(argv[1])=="--checkpoint-delete")) {\n',
  '  if(argc==3&&(std::string(argv[1])=="--checkpoint-inspect"||std::string(argv[1])=="--checkpoint-inspect-metadata"||std::string(argv[1])=="--checkpoint-delete")) {\n','host tools')
 # 6. Cheap refusals before any model load; full validation runs later under the lock.
 anchor='    a = parse(argc, argv);\n'
 text=replace_once(text,anchor,anchor+r'''    if(!a.checkpoint_save.empty()){const auto sid=a.checkpoint_restore.empty()?a.checkpoint_id:a.checkpoint_save_id;
      require(!fs::exists(fs::symlink_status(a.checkpoint_save/sid)),"checkpoint save refused: never overwrite: "+(a.checkpoint_save/sid).string()+" already exists");}
    // Before any model load: tokenizer identity for every checkpoint mode; for a restore, the same
    // manifest/tokens/tokenizer/--input classification checks restore repeats under its lock.
    if(!a.checkpoint_save.empty()&&a.checkpoint_restore.empty())pipeline::checkpoint_tokenizer_identity(a.tokenizer_identity,"save");
    if(!a.checkpoint_restore.empty())
      pipeline::checkpoint_precheck(a.checkpoint_restore,a.checkpoint_id,a.inputs,a.tokens,!a.checkpoint_save.empty(),a.tokenizer_identity,a.mini);
''','early refusals')
 # 7. Restore integration: same-generation resume or append through the normal prefill path.
 old_restore=r'''    int next=-1;auto prefill_start=std::chrono::steady_clock::now();
    // Restore runs AFTER p58_reset_request (its zeroing makes sliced-KV byte-exact
    // and its reset.json receipt stays a hard gate); the prefill loop is skipped and
    // token_index starts at N so step()/admit_position match the uninterrupted run.
    pipeline::RestoredCheckpoint restored;const bool restoring=!a.checkpoint_restore.empty();double checkpoint_restore_ms=0;
    if(restoring){auto restore_start=std::chrono::steady_clock::now();
      restored=pipeline::checkpoint_restore(*e,a.checkpoint_restore,a.checkpoint_id,input);
      checkpoint_restore_ms=Engine::ms(restore_start);next=restored.next_token;token_index=size_t(restored.position);}
    else for(size_t i=0;i<input.size();++i)next=step(input[i],i+1==input.size()?1:0);
    prefill_ms=restoring?0:Engine::ms(prefill_start);first_token_ms=first_generated_ms;
'''
 new_restore=r'''    int next=-1;auto prefill_start=std::chrono::steady_clock::now();
    // packet180: restore runs AFTER p58_reset_request (its zeroing keeps sliced-KV restore
    // byte-exact and reset.json stays a hard gate) and token_index starts at the saved
    // position N. Same-generation resume steps the saved pending token as the first decode
    // step. Append steps input[N..] (the pending token first, then the delta) through the
    // unchanged prefill path, exactly as a fresh run of the same --input does at those
    // positions; the last input token's argmax is the first generated token.
    pipeline::RestoredCheckpoint restored;const bool restoring=!a.checkpoint_restore.empty();bool appending=false;
    double checkpoint_restore_ms=0,append_prefill_ms=0;
    if(restoring){auto restore_start=std::chrono::steady_clock::now();
      restored=pipeline::checkpoint_restore(*e,a.checkpoint_restore,a.checkpoint_id,input,a.tokenizer_identity,a.tokens,!a.checkpoint_save.empty());
      checkpoint_restore_ms=Engine::ms(restore_start);token_index=size_t(restored.position);appending=restored.operation=="append";
      if(appending){auto append_start=std::chrono::steady_clock::now();
        for(size_t i=size_t(restored.position);i<input.size();++i)next=step(input[i],i+1==input.size()?1:0);
        append_prefill_ms=Engine::ms(append_start);}
      else next=restored.next_token;}
    else for(size_t i=0;i<input.size();++i)next=step(input[i],i+1==input.size()?1:0);
    prefill_ms=restoring?append_prefill_ms:Engine::ms(prefill_start);first_token_ms=first_generated_ms;
'''
 text=replace_once(text,old_restore,new_restore,'restore')
 # 8. Only the same-generation resume uses packet179's pending-token decode loop.
 text=replace_once(text,'    if(!a.first&&restoring)for(int i=0;i<a.tokens;++i){\n      next=step(next,i+2);\n',
  '    if(!a.first&&restoring&&!appending)for(int i=0;i<a.tokens;++i){\n'
  '      {auto resume_step=std::chrono::steady_clock::now();next=step(next,i+2);if(i==0)first_token_ms=Engine::ms(resume_step);}\n','resume loop')
 # 8c: decode time excludes the checkpoint save I/O
 text=replace_once(text,'    decode_ms=Engine::ms(decode_start);\n','','decode_ms')
 # 9. Save hook (plain save or restore-then-save) at the decode boundary.
 old_save='    if(!a.checkpoint_save.empty())pipeline::checkpoint_save(*e,a.checkpoint_save,a.checkpoint_id,input,generated);\n'
 new_save=r'''    decode_ms=Engine::ms(decode_start);  // packet180: measured before the checkpoint save I/O
    pipeline::SavedCheckpoint saved;const bool saving=!a.checkpoint_save.empty();
    if(saving){
      // packet180: the saved history is every token the model processed in this session.
      // Same-generation resume continues the restored history (its pending token was
      // stepped first); fresh runs and appends processed exactly --input. The last
      // generated token is the new pending token.
      require(!generated.empty(),"checkpoint save requires at least one generated token");
      std::vector<int> processed;
      if(restoring&&!appending){processed=restored.tokens;processed.push_back(restored.next_token);}
      else processed=input;
      processed.insert(processed.end(),generated.begin(),generated.end()-1);
      pipeline::CheckpointParent parent;
      if(restoring){parent.checkpoint_id=restored.checkpoint_id;parent.manifest_sha256=restored.manifest_sha256;parent.present=true;}
      saved=pipeline::checkpoint_save(*e,a.checkpoint_save,restoring?a.checkpoint_save_id:a.checkpoint_id,input,processed,generated.back(),a.tokenizer_identity,parent);
    }
    const std::string checkpoint_json=pipeline::checkpoint_result_json(restoring?&restored:nullptr,checkpoint_restore_ms,append_prefill_ms,saving?&saved:nullptr);
'''
 text=replace_once(text,old_save,new_save,'save')
 # 10. result.json: additive "checkpoint" object.
 anchor=r'''<<",\"checkpoint_restore_ms\":"<<restore_ms_json'''
 text=replace_once(text,anchor,anchor+r'''<<",\"checkpoint\":"<<checkpoint_json''','result')
 return text

# ---------------------------------------------------------------- harness blocks
WORKER_CONSTANTS_OLD="""CHECKPOINT_PROMPT='incident-retrospective'
CHECKPOINT_K=256
CHECKPOINT_M=128
"""
WORKER_CONSTANTS_NEW="""LIFECYCLE=read(HERE/'lifecycle.json')
INSPECT_TOOL_TIMEOUT_SECONDS=600  # worker-local bound on each device-free host tool (inspect/delete); not a native or window deadline
"""
WORKER_FUNCTIONS=r'''def native_single_command(output,input_path,max_new,checkpoint_args):
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
 results={};receipts=[]
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
 check=measurement.lifecycle_check(results,manifests,tools,L,prompt,turn,p179,oracle)
 save(output/'lifecycle-receipt.json',dict(check,prompt_id=L['prompt_id'],prompt_tokens=len(prompt),turn_tokens=len(turn),
  new_input_tokens=len(prompt)+L['K']+len(turn),K=L['K'],M1=L['M1'],M2=L['M2'],
  manifests={cid:dict(sha256=m['sha256'],fields_sha256=m['fields_sha256'],semantics=m['semantics'],
   token_state=m['manifest']['token_state'],lineage=m['manifest']['lineage'],measurements=m['manifest']['measurements'],
   blob_count=len(m['manifest']['blobs'])) for cid,m in manifests.items()},
  tools={k:{kk:vv for kk,vv in v.items() if kk!='stdout_object'}|dict(ok=(v.get('stdout_object') or {}).get('ok')) for k,v in tools.items()},
  reset_sha256={leg:results[leg]['request_reset_sha256'] for leg in results},
  s2b_note='S2b blobs are deleted by the delete-tool gate after the full inspect verified them and their sha256 equal S2; its manifest.json and fields.tsv are kept in s2b-manifest-copy/',
  scope='experimental session checkpoint lifecycle: append, restore-then-save, chain resume and repeat determinism versus a one-shot fresh reference of the same input; oracle cap 128 on the save leg; not a performance claim'))
 require(check['passed'],'lifecycle gate FAILED: '+', '.join(check['problems'])+' (run/lifecycle-receipt.json holds the first divergent index and both streams)')

def p179_identity_gate(output,observed):
 """Row a: every request's full output must equal packet179 row a (relinked binary, unchanged arithmetic)."""
 check=measurement.p179_identity(observed,read(HERE/'reference-p179-row-a.json'))
 save(output/'p179-identity.json',check)
 require(check['passed'],'packet180 row a output differs from packet179 row a (run/p179-identity.json)')
 return check

'''
WORKER_MAIN_OLD_START='def main():\n'
WORKER_MAIN_NEW=r'''def main():
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
'''

MEASUREMENT_APPEND=r'''
# ---------------------------------------------------------------- packet180 comparators
LIFECYCLE_CONTRACT='v1.2+p180'
LIFECYCLE_OPERATIONS=['same-generation-resume','append','restore-then-save']

def first_divergence(actual,expected):
 """First index where two token streams differ (a length difference counts), else None."""
 actual=list(actual);expected=list(expected);n=min(len(actual),len(expected))
 for i in range(n):
  if actual[i]!=expected[i]:return dict(index=i,actual=actual[i],expected=expected[i],actual_length=len(actual),expected_length=len(expected))
 if len(actual)!=len(expected):
  return dict(index=n,actual=actual[n] if n<len(actual) else None,expected=expected[n] if n<len(expected) else None,
   actual_length=len(actual),expected_length=len(expected))
 return None

def compare_streams(label,actual,expected):
 """Exact equality; the record keeps the first divergent index and BOTH streams."""
 d=first_divergence(actual,expected)
 return dict(label=label,passed=d is None,compared=min(len(actual),len(expected)),first_divergence=d,
  actual_tokens=list(actual),expected_tokens=list(expected))

def lifecycle_turn(spec,here):
 """The appended turn T: a fixed EOS-free slice of a suite input, re-derived from its source file."""
 turn=spec['turn'];source=list(map(int,(Path(here)/turn['source']).read_text().split()))
 tokens=source[turn['start']:turn['stop']]
 require(tokens==turn['tokens'],'lifecycle turn differs from its recorded source slice')
 require(len(tokens)>=64 and not any(t in EOS for t in tokens),'lifecycle turn must be at least 64 EOS-free tokens')
 return tokens

def lifecycle_input(prompt,generated,turn,spec):
 """NEW = P + gen[0:K] + T: the saved history P + gen[0:K-1], the pending token gen[K-1], then T."""
 require(len(generated)==spec['K'] and not any(t in EOS for t in generated),'save leg must produce K EOS-free tokens')
 new=list(prompt)+list(generated)+list(turn)
 require(len(new)+spec['M1']+spec['M2']<=spec['context'],'lifecycle input plus decode exceeds the context allocation')
 return new

def manifest_semantics(manifest,tokens,small_blobs=None):
 """Python mirror of the engine's token-state cross-checks; reads packet179 v1 and packet180 manifests."""
 import struct
 ts=manifest['token_state'];N=ts['position'];eos=manifest['geometry']['eos'];problems=[]
 if ts['length']!=N:problems.append('length != position')
 if len(tokens)!=N:problems.append('tokens.bin length != position')
 if not 1<=ts['prompt_length']<=N:problems.append('prompt_length outside the processed prefix')
 history=[tokens[N-2] if N>=2 else eos,tokens[N-1]] if len(tokens)==N and N>=1 else None
 if list(ts['token_history'])!=history:problems.append('token_history != last two processed tokens')
 for name,want in (('position',N),('next_token',ts['next_token']),('token',history[1] if history else None),('error',0)):
  if small_blobs and name in small_blobs and struct.unpack('<i',small_blobs[name])[0]!=want:problems.append(name+' blob disagrees')
 if small_blobs and 'token_history' in small_blobs and list(struct.unpack('<2q',small_blobs['token_history']))!=history:
  problems.append('token_history blob disagrees')
 if sum(b['bytes'] for b in manifest['blobs'])!=manifest['measurements']['save_bytes']:problems.append('save_bytes != sum of blob bytes')
 return dict(passed=not problems,problems=problems,position=N,pending_token=ts['next_token'],
  blobs_checked=sorted(small_blobs) if small_blobs else [])

def p179_identity(observed,reference):
 """Row a: every request's full output equals packet179 row a's (relinked binary, unchanged arithmetic)."""
 rows=[];ok=True
 for pid,ref in reference['prompts'].items():
  got=observed.get(pid)
  cmp=compare_streams(pid,got if got is not None else [],ref['tokens'])
  passed=got is not None and cmp['passed'] and digest(got)==ref['output_token_digest']
  ok&=passed
  rows.append(dict(prompt_id=pid,passed=passed,tokens=len(got or []),first_divergence=cmp['first_divergence'],
   actual_tokens=None if passed else cmp['actual_tokens'],expected_tokens=None if passed else cmp['expected_tokens']))
 extra=sorted(set(observed)-set(reference['prompts']))
 return dict(passed=bool(ok and not extra and len(rows)==13),compared_prompts=len(rows),unexpected_prompts=extra,rows=rows,
  reference_binary_sha256=reference['binary_sha256'],
  scope='full output streams of all 13 requests (12 suite prompts + prefill512) versus packet179 row a')

def lifecycle_check(results,manifests,tools,spec,prompt,turn,p179_tokens,oracle):
 """Row b gates. Returns a receipt and never raises on a gate failure, so both streams are kept."""
 K,M1,M2=spec['K'],spec['M1'],spec['M2'];ids=spec['checkpoint_ids']
 sv,x,y,r,x2=(results[k] for k in ('save-s1','append-s2','resume-s2','reference','append-s2b'))
 gates={};problems=[]
 def gate(name,ok,detail=None):
  gates[name]=dict(passed=bool(ok),detail=detail)
  if not ok:problems.append(name)
 for leg,res in results.items():
  try:stream_check(res);gate('stream '+leg,True)
  except (ValueError,KeyError,TypeError) as error:gate('stream '+leg,False,str(error))
 gate('save K tokens EOS-free',len(sv['tokens'])==K and not any(t in EOS for t in sv['tokens']))
 save_p179=compare_streams('save-s1 vs packet179 row-a '+spec['prompt_id']+' [0:K]',sv['tokens'],list(p179_tokens)[:K])
 gate('save == packet179 row a [0:K]',save_p179['passed'],save_p179['first_divergence'])
 try:
  oracle_check=stream_check(sv,oracle)
  gate('save oracle-128 prefix',oracle_check['tokens_compared']==min(len(sv['tokens']),len(oracle)))
 except (ValueError,KeyError,TypeError) as error:
  oracle_check=None;gate('save oracle-128 prefix',False,str(error))
 R=list(r['tokens'])
 append_cmp=compare_streams('append (2) vs one-shot reference (4) [0:M1]',x['tokens'],R[:M1])
 gate('append == reference [0:M1]',append_cmp['passed'],append_cmp['first_divergence'])
 if len(R)>M1:
  chain_cmp=compare_streams('resume of S2 (3) vs one-shot reference (4) [M1:M1+M2]',y['tokens'],R[M1:M1+M2])
  gate('restore-then-save chain == reference [M1:M1+M2]',chain_cmp['passed'],chain_cmp['first_divergence'])
 else:
  chain_cmp=None
  gate('restore-then-save chain == reference [M1:M1+M2]',False,'not evaluable: the reference stopped naturally after '+str(len(R))+' <= M1 tokens')
 repeat_cmp=compare_streams('append repeat (5) vs append (2)',x2['tokens'],x['tokens'])
 gate('append repeat identical',repeat_cmp['passed'],repeat_cmp['first_divergence'])
 N1=len(prompt)+K-1;L=len(prompt)+K+len(turn)
 def rec(res):return res.get('checkpoint') or {}
 s1=rec(sv).get('save') or {}
 gate('save record',rec(sv).get('restore') is None and s1.get('checkpoint_id')==ids['S1'] and s1.get('position')==N1
      and s1.get('pending_token')==sv['tokens'][-1],s1)
 for leg,res,sid in (('append-s2',x,ids['S2']),('append-s2b',x2,ids['S2b'])):
  rr=rec(res).get('restore') or {};ss=rec(res).get('save') or {}
  gate(leg+' restore record',rr.get('operation')=='append' and rr.get('checkpoint_id')==ids['S1'] and rr.get('saved_prefix_length')==N1
       and rr.get('appended_length')==len(turn) and rr.get('input_length')==L and rr.get('pending_token')==sv['tokens'][-1]
       and rr.get('manifest_sha256')==manifests[ids['S1']]['sha256']
       and isinstance(rr.get('restore_ms'),(int,float)) and isinstance(rr.get('append_prefill_ms'),(int,float)),rr)
  gate(leg+' save record',ss.get('checkpoint_id')==sid and ss.get('parent_checkpoint_id')==ids['S1']
       and ss.get('position')==L+len(res['tokens'])-1 and ss.get('pending_token')==res['tokens'][-1],ss)
 ry=rec(y).get('restore') or {}
 gate('resume restore record',ry.get('operation')=='same-generation-resume' and ry.get('checkpoint_id')==ids['S2']
      and ry.get('saved_prefix_length')==L+len(x['tokens'])-1 and ry.get('pending_token')==x['tokens'][-1]
      and ry.get('appended_length')==0 and ry.get('append_prefill_ms') is None and rec(y).get('save') is None,ry)
 gate('reference is a fresh run',rec(r).get('restore') is None and rec(r).get('save') is None)
 m1,m2,m2b=(manifests[ids[k]] for k in ('S1','S2','S2b'))
 for cid,m in ((ids['S1'],m1),(ids['S2'],m2),(ids['S2b'],m2b)):
  mm=m['manifest']
  gate('manifest identity '+cid,mm.get('format')=='ownrt.session-checkpoint.v1' and mm.get('label')=='experimental'
       and mm.get('contract')==LIFECYCLE_CONTRACT and mm.get('operations')==LIFECYCLE_OPERATIONS and mm.get('checkpoint_id')==cid)
  gate('manifest semantics '+cid,m['semantics']['passed'],m['semantics']['problems'])
 gate('S1 lineage save',m1['manifest']['lineage']=={'operation':'save','parent':None})
 gate('S1 position',m1['manifest']['token_state']['position']==N1 and m1['manifest']['token_state']['prompt_length']==len(prompt))
 for cid,m in ((ids['S2'],m2),(ids['S2b'],m2b)):
  gate('lineage '+cid,m['manifest']['lineage']=={'operation':'restore-then-save','parent':{'checkpoint_id':ids['S1'],'manifest_sha256':m1['sha256']}})
 gate('S2 position',m2['manifest']['token_state']['position']==L+len(x['tokens'])-1 and m2['manifest']['token_state']['prompt_length']==L)
 strip=lambda m:[(b['name'],b['bytes'],b['sha256'],b['slice']) for b in m['manifest']['blobs']]
 gate('S2 == S2b saved state (every blob sha256, token state)',strip(m2)==strip(m2b) and m2['manifest']['token_state']==m2b['manifest']['token_state'])
 for cid in (ids['S1'],ids['S2'],ids['S2b']):
  t=tools.get('metadata-'+cid,{});o=t.get('stdout_object') or {}
  gate('inspect-metadata '+cid,t.get('returncode')==0 and t.get('stdout_lines')==1 and t.get('stderr_json_lines') and o.get('ok') is True
       and o.get('mode')=='metadata' and o.get('manifest')==manifests[cid]['manifest'] and o.get('manifest_sha256')==manifests[cid]['sha256']
       and (o.get('verified') or {}).get('blobs_verified') is None,{k:o.get(k) for k in ('ok','mode','error')})
 for cid in (ids['S2'],ids['S2b']):
  t=tools.get('full-'+cid,{});o=t.get('stdout_object') or {};mm=manifests[cid]['manifest'];v=o.get('verified') or {}
  gate('inspect-full '+cid,t.get('returncode')==0 and t.get('stdout_lines')==1 and t.get('stderr_json_lines') and o.get('ok') is True
       and o.get('mode')=='full' and v.get('blobs_verified')==len(mm['blobs'])
       and v.get('blob_bytes_verified')==mm['measurements']['save_bytes']+4*mm['token_state']['position'],{k:o.get(k) for k in ('ok','mode','error','verified')})
 t=tools.get('delete-'+ids['S2b'],{});o=t.get('stdout_object') or {}
 gate('delete '+ids['S2b'],t.get('returncode')==0 and o.get('deleted') is True and t.get('directory_removed') is True and t.get('lock_removed') is True,
      {k:o.get(k) for k in ('ok','deleted','reason','error')})
 def ms(res,key):return (rec(res).get('restore') or {}).get(key)
 restore_path=None if ms(x,'restore_ms') is None or ms(x,'append_prefill_ms') is None else ms(x,'restore_ms')+ms(x,'append_prefill_ms')
 timing=dict(
  restore_ms={leg:ms(res,'restore_ms') for leg,res in (('append-s2',x),('resume-s2',y),('append-s2b',x2))},
  append_prefill_ms={leg:ms(res,'append_prefill_ms') for leg,res in (('append-s2',x),('append-s2b',x2))},
  restored_bytes={leg:ms(res,'restored_bytes') for leg,res in (('append-s2',x),('resume-s2',y),('append-s2b',x2))},
  save_seconds={cid:m['manifest']['measurements']['save_seconds'] for cid,m in manifests.items()},
  save_bytes={cid:m['manifest']['measurements']['save_bytes'] for cid,m in manifests.items()},
  save_leg_prefill_ms=sv.get('prefill_ms'),reference_prefill_ms=r.get('prefill_ms'),
  request_wall_ms={leg:1000*(res['request_end_monotonic']-res['request_start_monotonic']) for leg,res in results.items()},
  cold_vs_restore=dict(cold_prefill_ms=r.get('prefill_ms'),restore_plus_append_prefill_ms=restore_path,
   ratio=(r['prefill_ms']/restore_path) if restore_path and r.get('prefill_ms') else None,input_tokens=L,saved_prefix_tokens=N1,
   definition='cold: the one-shot reference process steps all L input tokens from a reset state (its prefill_ms, through the first generated token); restore path: the append process restores the N1-token checkpoint and steps the L-N1 remaining input tokens (restore_ms + append_prefill_ms); same binary, same input, each a fresh process with an empty expert cache'))
 return dict(passed=not problems,device_executed=False,problems=problems,gates=gates,
  comparisons=dict(save_vs_packet179=save_p179,append_vs_reference=append_cmp,chain_vs_reference=chain_cmp,append_repeat=repeat_cmp),
  reference_tokens=len(R),reference_natural_stop=len(R)<M1+M2,oracle_check=oracle_check,timing=timing,
  merged_reference_definition='reference (4) is a fresh process given NEW = P + gen[0:K] + T decoding M1+M2; (2) must equal its [0:M1], (3) its [M1:M1+M2]')
'''

SCREEN_REPORT_OLD="""def report_completed(output,record,identity,coordination):
 if identity.get('bracket',{}).get('kind')=='checkpoint':
  receipt=read(output/'run/checkpoint-receipt.json')
  require(receipt.get('passed') is True and receipt.get('device_executed') is False,'checkpoint gate receipt incomplete')
  result=dict(receipt)
  result.update(kind='checkpoint',lane=identity['lane'],
   scope=coordination.get('scope','report-rehearsal'),device_executed=bool(record.get('device_executed')),
   source_receipt_sha256=sha(output/'run/checkpoint-receipt.json'),report_after_device_release=True,
   strict512=False,submission_eligible=False,experimental_checkpoint=True)
  save(output/'summary.json',result);save(output/'bracket-summary.json',result)
  return result
"""
SCREEN_REPORT_NEW="""def report_completed(output,record,identity,coordination):
 if identity.get('bracket',{}).get('kind')=='lifecycle':
  receipt=read(output/'run/lifecycle-receipt.json')
  require(receipt.get('passed') is True and receipt.get('device_executed') is False,'lifecycle gate receipt incomplete')
  result=dict(receipt)
  result.update(kind='lifecycle',lane=identity['lane'],
   scope=coordination.get('scope','report-rehearsal'),device_executed=bool(record.get('device_executed')),
   source_receipt_sha256=sha(output/'run/lifecycle-receipt.json'),report_after_device_release=True,
   strict512=False,submission_eligible=False,experimental_checkpoint=True)
  save(output/'summary.json',result);save(output/'bracket-summary.json',result)
  return result
"""
SCREEN_IDENTITY_OLD=""" # Generic shared rehearsal intentionally supplies64/128 receipts: those stay strict512=false.
"""
SCREEN_IDENTITY_NEW=""" if record.get('device_executed'):
  # Device row a: the worker's packet179 identity gate must have passed before report-inputs.
  check=read(output/'run/p179-identity.json');require(check.get('passed') is True,'packet179 row-a identity missing or failed')
  result['packet179_row_a_identity']=dict(passed=True,compared_prompts=check['compared_prompts'],reference_binary_sha256=check['reference_binary_sha256'])
 # Generic shared rehearsal intentionally supplies64/128 receipts: those stay strict512=false.
"""
SCREEN_PLAN_OLD=""" if args.kind=='checkpoint':
  plan.update(model_loads=3,request_count=3,requested_max_new=None,prefill=None,
   checkpoint=dict(prompt=measurement.IDS[0],save_max_new=256,restore_max_new=128,restore_launches=2,experimental=True,
    gate='save K=256 then two independent restore M=128 continuations; merged stream must equal this packet\\'s full512 row-A reference at [0:384); repeat-restore determinism; oracle-128 prefix on the merged stream'))
"""
SCREEN_PLAN_NEW=""" plan['expected_seconds']=budget['expected_seconds_by_kind'][args.kind] if args.kind in budget['expected_seconds_by_kind'] else budget['expected_seconds']
 if args.kind=='lifecycle':
  require(args.reference is None,'the lifecycle row is self-contained; it takes no --reference')
  life=read(HERE/'lifecycle.json')
  plan.update(model_loads=5,request_count=5,requested_max_new=None,prefill=None,second_fresh_attempt=False,
   lifecycle=dict(prompt=life['prompt_id'],K=life['K'],M1=life['M1'],M2=life['M2'],turn_tokens=len(life['turn']['tokens']),
    legs=['save-s1','append-s2','resume-s2','reference','append-s2b'],experimental=True,
    host_tools=['--checkpoint-inspect-metadata s1,s2,s2b','--checkpoint-inspect s2,s2b','--checkpoint-delete s2b'],
    gate='append (2) == one-shot reference [0:M1]; resume of the restore-then-saved S2 (3) == reference [M1:M1+M2]; repeat append (5) == (2) and S2b blobs == S2 blobs; save leg == packet179 row a [0:K] and oracle-128; inspect/delete tools; a divergence fails with the first index and both streams'))
"""

def main():
 p=P/'one-card'
 parent_main=(OLD165/'one-card'/NAT/'main.cpp').read_text()
 p179_delta=json.loads((OLD179/'one-card/evidence/native-delta.json').read_text())
 p179_main=(OLD179/'one-card'/NAT/'main.cpp').read_text().replace(str(OLD179),str(OLD165))
 assert sha_text(parent_main)==p179_delta['parent_main_sha256'],'packet165 parent main.cpp drifted'
 assert sha_text(p179_main)==p179_delta['patched_main_sha256'],'packet179 patched main.cpp drifted'
 text=native_edits(p179_main)
 MAIN.write_text(text)   # packet165-path-normalized form; build_checkpoint.py relocates to this packet
 header=(P/'checkpoint.hpp').read_text()
 (MAIN.parent/'checkpoint.hpp').write_text(header)
 p179_header=(OLD179/'one-card'/NAT/'checkpoint.hpp').read_text()
 lineage=p/'lineage'
 (lineage/'packet180-native-delta.patch').write_text(''.join(difflib.unified_diff(
  parent_main.splitlines(True),text.splitlines(True),fromfile='packet165/'+NAT+'/main.cpp',tofile='packet180/'+NAT+'/main.cpp')))
 (lineage/'packet180-vs-packet179-main.patch').write_text(''.join(difflib.unified_diff(
  p179_main.splitlines(True),text.splitlines(True),fromfile='packet179/'+NAT+'/main.cpp',tofile='packet180/'+NAT+'/main.cpp')))
 (lineage/'packet180-vs-packet179-checkpoint.patch').write_text(''.join(difflib.unified_diff(
  p179_header.splitlines(True),header.splitlines(True),fromfile='packet179/'+NAT+'/checkpoint.hpp',tofile='packet180/'+NAT+'/checkpoint.hpp')))

 # ---- harness edits (re-copied from packet179 first so reruns are idempotent)
 for leaf in ('worker.py','measurement.py','screen.py','entry.py','native-help-flags.json','budget.json'):
  src=(OLD179/'one-card'/leaf).read_text()
  if leaf.endswith('.py'):src=src.replace(OLD179.name,P.name)
  (p/leaf).write_text(src)
 worker=(p/'worker.py').read_text()
 worker=replace_once(worker,WORKER_CONSTANTS_OLD,WORKER_CONSTANTS_NEW,'worker constants')
 worker=replace_once(worker,'import argparse,copy,json,os,signal,subprocess,time\n','import argparse,copy,json,os,signal,struct,subprocess,time\n','worker imports')
 # Drop packet179's checkpoint_command (superseded by native_single_command); keep run_native
 # verbatim; replace packet179's checkpoint() gate with the packet180 lifecycle functions.
 start=worker.index('def checkpoint_command(');end=worker.index('def run_native(cmd,output):')
 worker=worker[:start]+worker[end:]
 start=worker.index('def checkpoint(output,reference):');end=worker.index('def prove_drain(receipts):')
 worker=worker[:start]+WORKER_FUNCTIONS+worker[end:]
 worker=worker[:worker.index(WORKER_MAIN_OLD_START)]+WORKER_MAIN_NEW
 worker=replace_once(worker,'"""One load; complete resets; in-run validation is stream format and exact prefix only."""',
  '"""One load; complete resets; in-run validation is stream format and exact prefix only.\n\npacket180: kind lifecycle is the experimental append / restore-then-save gate (row b).\n"""','worker doc')
 (p/'worker.py').write_text(worker)
 (p/'measurement.py').write_text((p/'measurement.py').read_text()+MEASUREMENT_APPEND)
 screen=(p/'screen.py').read_text()
 screen=replace_once(screen,"ap.add_argument('--kind',choices=('full512','smoke','bracket','checkpoint'),default='full512')",
  "ap.add_argument('--kind',choices=('full512','smoke','bracket','lifecycle'),default='full512')",'screen kind')
 screen=replace_once(screen,SCREEN_REPORT_OLD,SCREEN_REPORT_NEW,'screen report')
 screen=replace_once(screen,SCREEN_IDENTITY_OLD,SCREEN_IDENTITY_NEW,'screen identity')
 screen=replace_once(screen,SCREEN_PLAN_OLD,SCREEN_PLAN_NEW,'screen plan')
 screen=replace_once(screen," require(args.kind in('full512','checkpoint'),'short synthetic report modes cannot launch devices')",
  " require(args.kind in('full512','lifecycle'),'short synthetic report modes cannot launch devices')",'screen launch kinds')
 (p/'screen.py').write_text(screen)
 entry=(p/'entry.py').read_text()
 entry=replace_once(entry,"ap.add_argument('--kind',choices=('full512','smoke','bracket','checkpoint'),default='full512',help='smoke/bracket accepted only by offline report compatibility tests; checkpoint is the experimental session save/restore gate')",
  "ap.add_argument('--kind',choices=('full512','smoke','bracket','lifecycle'),default='full512',help='smoke/bracket accepted only by offline report compatibility tests; lifecycle is the experimental append/restore-then-save gate')",'entry kind')
 (p/'entry.py').write_text(entry)
 flags=json.loads((p/'native-help-flags.json').read_text())
 for after,flag in (('--checkpoint-inspect','--checkpoint-inspect-metadata'),('--checkpoint-save','--checkpoint-save-id'),('--timing','--tokenizer-identity')):
  assert flag not in flags;flags.insert(flags.index(after)+1,flag)
 save(p/'native-help-flags.json',flags)
 budget=json.loads((p/'budget.json').read_text())
 for k in ('checkpoint_planned_blob_bytes','checkpoint_note','checkpoint_extra_model_loads'):budget.pop(k)
 budget['planned_write_bytes']=400_000_000
 budget['lifecycle_planned_blob_bytes']=230_000_000
 budget['lifecycle_note']=('row b writes S1 (~69 MB at N=342), S2 and S2b (~76 MB each at N=596) plus five native output folders; '
  'S2b blobs are deleted by the delete-tool gate; 400 MB planned writes cover both rows; floors unchanged')
 budget['lifecycle_model_loads']=5
 budget['expected_seconds']=[450,2400]
 budget['expected_seconds_by_kind']={'full512':[450,900],'lifecycle':[1100,2400]}
 budget['expected_seconds_note']=('informational estimates from packet179 receipts (row a 499 s; row b legs 218-251 s each, model load ~210 s); '
  'no runner enforces them; the enforced bound is the 7200 s screen supervision of the worker child (screen.py)')
 save(p/'budget.json',budget)

 # ---- new packet files
 meta=[json.loads(f.read_text()) for f in sorted((p/'lineage/input-metadata').glob('*/input.json'))]
 pins={(m['header_sha256'],m['tokenizer_source_sha256'],m['files']['vocab.bin']) for m in meta}
 assert len(meta)==12 and len(pins)==1,pins
 header_sha,source_sha,vocab_sha=pins.pop()
 (p/'tokenizer-identity.tsv').write_text(
  '# packet180 tokenizer/template identity. Every value is a pin the harness already holds:\n'
  '#   gguf_header_sha256: shard 00001-of-00003 GGUF header bytes (tokenizer.ggml.* vocabulary/merges and\n'
  '#     tokenizer.chat_template), pinned by experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/admission-receipt.json\n'
  '#     and by every suite input.json (lineage/input-metadata/*/input.json header_sha256);\n'
  '#   tokenizer_source_sha256: packet2-cpu-oracle/tokenizer.py, which produced every suite tokens.txt;\n'
  '#   vocab_bin_sha256: the decoded vocabulary table written by that tokenizer (suite input bundles).\n'
  '# The engine records this file\'s sha256 and the three hashes at save and refuses a restore whose file differs.\n'
  'format\townrt.tokenizer-identity.v1\n'
  'model\tunsloth Qwen3.8-Flash-Next-GGUF 766911a6 UD-IQ3_XXS\n'
  'gguf_header_sha256\t'+header_sha+'\n'
  'tokenizer_source_sha256\t'+source_sha+'\n'
  'vocab_bin_sha256\t'+vocab_sha+'\n'
  'template\tChatML <|im_start|>/<|im_end|> with an empty <think></think> block, as embedded in the GGUF header (covered by gguf_header_sha256)\n')
 source=list(map(int,(p/'inputs/prefill512/tokens.txt').read_text().split()))
 turn=source[0:126]
 assert len(turn)==126 and not any(t in (248044,248046) for t in turn)
 save(p/'lifecycle.json',dict(schema='packet180.lifecycle.v1',prompt_id='incident-retrospective',K=256,M1=128,M2=64,context=4096,
  checkpoint_ids=dict(S1='s1',S2='s2',S2b='s2b'),
  turn=dict(source='inputs/prefill512/tokens.txt',start=0,stop=126,tokens=turn,eos_free=True,
   text='the first 126 tokens of the suite prefill512 document excerpt ("## 0. Operating Principles ... The weakest work came from: - comparing runs with different model"), ending mid list item; contains neither 248044 nor 248046'),
  legs=['save-s1: P, K=256, save S1 (N=P+K-1=342, pending gen[255])',
        'append-s2: restore S1, --input NEW=P+gen[0:256]+T (469), decode M1=128, save S2 (restore-then-save)',
        'resume-s2: restore S2 (same-generation resume, --input NEW), decode M2=64',
        'reference: fresh process, --input NEW, decode M1+M2=192',
        'append-s2b: repeat of append-s2 into S2b']))
 rows=json.loads((p/'lineage/packet179-receipts/COPY-MANIFEST.json').read_text())['entries']
 prompts={}
 for row in rows:
  leaf=row['copy_relative']
  if leaf.startswith('lineage/packet179-receipts/row-a/run/native/') and leaf.endswith('/result.json'):
   pid=leaf.split('/')[-2];tokens=json.loads((p/leaf).read_text())['tokens']
   prompts[pid]=dict(output_tokens=len(tokens),output_token_digest=hashlib.sha256(json.dumps(tokens,separators=(',',':')).encode()).hexdigest(),tokens=tokens)
 assert len(prompts)==13
 save(p/'reference-p179-row-a.json',dict(schema='packet180.p179-row-a-reference.v1',binary_sha256='8d18538475e00200032846d51dce11e0d38392dc9962778ffd01b03dd75394a7',
  source='lineage/packet179-receipts/row-a/run/native (byte-identical copies; COPY-MANIFEST.json)',prompts=dict(sorted(prompts.items())),
  digest_definition='measurement.digest: sha256 of the compact JSON token list'))

 save(p/'evidence/native-delta.json',dict(passed=True,device_executed=False,
  entry_tu_only=True,patched=[NAT+'/main.cpp',NAT+'/checkpoint.hpp'],added=[],
  parent_main_sha256=sha_text(parent_main),packet179_main_sha256=sha_text(p179_main),
  patched_main_sha256=sha_text(text),checkpoint_hpp_sha256=sha(MAIN.parent/'checkpoint.hpp'),
  packet179_checkpoint_hpp_sha256=sha_text(p179_header),
  patch_sha256=sha(lineage/'packet180-native-delta.patch'),
  incremental_main_patch_sha256=sha(lineage/'packet180-vs-packet179-main.patch'),
  incremental_checkpoint_patch_sha256=sha(lineage/'packet180-vs-packet179-checkpoint.patch'),
  harness_files=['worker.py','measurement.py','screen.py','entry.py','native-help-flags.json','budget.json'],
  new_files=['tokenizer-identity.tsv','lifecycle.json','reference-p179-row-a.json'],
  kernel_arithmetic='unchanged by construction: only the entry TU textual closure changed; kernel objects relinked byte-identical from packet165 by build_checkpoint.py',
  scope='experimental session checkpoint v2 (SESSION-SWAP-DESIGN.md v1.2 section 10 item 0): append, restore-then-save, tokenizer identity, one manifest source of truth, shared sibling lock, inspect modes; device qualification pending'))
 print('packet180 native delta + harness edits applied')

if __name__=='__main__':main()
