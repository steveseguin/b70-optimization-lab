import sys,json,copy,struct,importlib.util
from pathlib import Path
root=Path('/home/steve/llm-optimizations');h=root/'experiments/own-xpu-runtime/research/continuation-2026-10-25';scratch=Path('/dev/shm/ownrt-provider-role-support');sh=scratch/h.relative_to(root);st=scratch/'experiments/own-xpu-runtime/engine/tools'
sys.path[:0]=[str(sh),str(st),str(h),str(root/'experiments/own-xpu-runtime/engine/tools')]
# Reuse the one retained-trace focused check; import resolves only changed scratch auditor.
exec(Path('/dev/shm/check_capture_audit.py').read_text().replace("sys.path.insert(0,str(h))","sys.path.insert(0,str(h));sys.path.insert(0,str(sh))"))
sp=importlib.util.spec_from_file_location('scratch_pipeline',st/'compare_pipeline_state.py');pipeline=importlib.util.module_from_spec(sp);sp.loader.exec_module(pipeline)
spec=dict(provider_stage=1,stages=[{}, {}, {}, {}]);metadata=dict(provider_stage=1,provider_present=True,first=False)
assert pipeline.provider_owner(spec,metadata,dict(id=1)) is True
for m in [dict(metadata,provider_present=False),dict(metadata,provider_stage=0),dict(first=False)]:
 try:pipeline.provider_owner(spec,m,dict(id=1))
 except ValueError:pass
 else:raise AssertionError('bad native role accepted')
# Bind a remote provider reservation/capture against the real stage0 seed prefix.
original=lines('commands.jsonl');i=next(i for i,e in enumerate(original) if e['event']=='issued' and e['op']==27)
e=copy.deepcopy(original[i]);n=1;prefix=copy.deepcopy(original[:i]);done=[x for x in prefix if x['stage']==n and x['event']=='completed'];last=done[-1];ack=last['ack'];assert ack['pending']==0
seq=last['sequence']+1;e.update(stage=n,sequence=seq,target_physical=ack['physical'],target_committed=ack['committed'],pending_target_rows=[])
packet=list(a.base.REQUEST.unpack(bytes.fromhex(e['request_hex'])));packet[5]=seq;packet[6]=n;e['request_hex']=a.base.REQUEST.pack(*packet).hex()
meta=list(a.wire.ROW_META.unpack(bytes.fromhex(e['metadata_hex'])));meta[10]=n;meta[14]=e['row_ticket'];e['metadata_hex']=a.wire.ROW_META.pack(*meta).hex()
seed_meta=list(meta);seed_meta[10]=0
journal=struct.pack('<4IQ2i',0x52534331,1,256,0,e['accepted_seed_sequence'],original[i]['target_physical'],original[i]['target_committed'])+a.wire.ROW_META.pack(*seed_meta)
e['seed_journal_hex']=journal.hex();e['seed_journal_sha256']=a.sha(journal)
b=next(x for x in original[i:] if x['event']=='completed' and x['op']==27)['provider'];r=e['row']
cap=dict(e,event='parent-captured',reply_hex=a.base.REPLY.pack(2,-1,0,128,seq,1,n,0,0.,0,0,0).hex(),metadata_hex=struct.pack('<QII6Q32s32s',0x315950414352574f,1,128,r['epoch'],seq,r['id'],r['parent'],b['final_commit'],e['provider_serial'],bytes.fromhex(r['request']),bytes.fromhex(e['parent_record_sha256'])).hex())
remote=prefix+[e,cap]
def remote_check(commands):
 return a.audit_controller(commands,lines('final-records.jsonl'),lines('provider-batches.jsonl'),plan['prompt_tokens'],result['output_ids'],result['request_sha256'],len(plan['stages']),extent,plan['vocab'],plan['context'],epoch=result['epoch'],initial_sequences=result['initial_sequences'],check_policy=plan['check_policy'],max_new=plan['max_new'],provider_stage=1)
try:remote_check(remote)
except ValueError as error:assert 'terminal owners not fully drained' in str(error),str(error)
else:raise AssertionError('partial trace passed')
bad=copy.deepcopy(remote);bad[-1]['reply_hex']=a.base.REPLY.pack(2,-1,0,128,seq,0,0,0,0.,0,0,0).hex()
try:remote_check(bad)
except ValueError as error:assert 'capture raw nonterminal header' in str(error),str(error)
else:raise AssertionError('wrong remote rank/stage accepted')
print('remote provider reservation/capture accepted until expected incomplete-prefix refusal; wrong rank/stage and metadata-role mutations refused')

for kind in ('hash','accepted','rowticket'):
 bad=copy.deepcopy(remote)
 if kind=='hash':bad[-2]['seed_journal_sha256']='0'*64
 else:
  raw=bytearray(bytes.fromhex(bad[-2]['seed_journal_hex']))
  offset=16 if kind=='accepted' else 32+4*16+4*4
  raw[offset]^=1
  bad[-2]['seed_journal_hex']=raw.hex();bad[-2]['seed_journal_sha256']=a.sha(raw)
 try:remote_check(bad)
 except ValueError:pass
 else:raise AssertionError('bad seed journal accepted')
print('remote seed-journal hash/ACCEPT/row-byte mutations refused')
sp=importlib.util.spec_from_file_location('scratch_policy',st/'persistent_ring_policy.py');policy=importlib.util.module_from_spec(sp);sp.loader.exec_module(policy)
att0=json.loads((Path(result['reset_receipts'][0]['native_output'])/'state-2000000000.ring-state.json').read_text())
att1=json.loads((Path(result['reset_receipts'][1]['native_output'])/'state-2000000000.ring-state.json').read_text())
assert policy.validate_policy(att0,policy='qualification',first=False,provider=True)
assert policy.validate_policy(att1,policy='qualification',first=True,provider=False)
import persistent_rolling_reset_audit as reset
reset_plan=json.loads((p.parent/'plan.json').read_text());reset_plan['provider_stage']=1
reset_result=copy.deepcopy(result);reset_log=copy.deepcopy(lines('reset-commands.jsonl'));rawfiles={}
keys=['draft_position','provider_serial','draft_context_extent','provider_cold_host_sha256','provider_cold_sequence_sha256']
completed={e['stage_id']:e for e in reset_log if e['event']=='completed'}
for key in keys:completed[0]['receipt'][key],completed[1]['receipt'][key]=completed[1]['receipt'][key],completed[0]['receipt'][key]
for e in completed.values():
 rawfiles[e['descriptor_path']]=Path(e['descriptor_path']).read_bytes()
 rb=json.dumps(e['receipt']).encode();rawfiles[e['receipt_path']]=rb;e['receipt_sha256']=reset.sha(rb)
 reset_result['reset_receipts'][e['stage_id']]={k:v for k,v in e.items() if k!='event'}
checked=reset.audit_reset(reset_plan,{'id':result['id'],'prompt_tokens':plan['prompt_tokens'],'max_new':plan['max_new']},reset_result,reset_log,previous_request=json.loads((p.parent/'plan.json').read_text())['request_sha256'],previous_sequences=[0]*len(plan['stages']),previous_target_position=0,prior_inventories=None,read_raw=lambda p:rawfiles[str(p)])
assert checked['passed']
print('provider/target-first policy split and remote all-owner cold RESET receipt checks passed')
