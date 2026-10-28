"""Isolated all-owner OP11 barrier; uses existing persistent_rolling_suite transport.
Not enabled by any canonical driver. Native startup/provider runtime remain blockers.
"""
from hashlib import sha256
import json
from pathlib import Path
import re
import persistent_rolling_suite as target_reset
base=target_reset.base
PROTOCOL='ownrt.dedicated-reset-request.v2'
def require(ok,text):base.require(ok,text)
def authority(plan,index):
 require(plan.get('dedicated_reset_protocol')==PROTOCOL and type(index)is int and 0<=index<12,'explicit suite capability/index')
 path=Path(plan['dedicated_prompt_manifest']);raw=target_reset.evidence.read_bounded(path,8192)
 digest=sha256(raw).hexdigest();require(digest==plan['dedicated_prompt_manifest_sha256'],'startup manifest SHA')
 def unique(pairs):
  result={}
  for key,value in pairs:require(key not in result,'duplicate manifest key');result[key]=value
  return result
 m=json.loads(raw,object_pairs_hook=unique)
 require(len(m)==42 and m['schema']=='ownrt.dedicated-prompt-suite.v1'and m['requests']==12
  and m['max_new']==512 and m['context']==plan['context']
  and m['model_identity_sha256']==plan['model_identity_sha256']
  and m['policy_sha256']==plan['verification_policy_sha256'],'exact registered startup geometry/model/policy')
 path=Path(m[f'prompt_{index}_path']);data=target_reset.evidence.read_bounded(path,4*262144)
 require(len(data)==4*m[f'prompt_{index}_tokens']and sha256(data).hexdigest()==m[f'prompt_{index}_sha256'],'selected actual immutable prompt')
 return dict(suite_sha256=digest,prompt_sha256=m[f'prompt_{index}_sha256'],prompt_index=index,prompt_tokens=m[f'prompt_{index}_tokens'])
def transition(stages,provider,plan,guard,output,*,previous_epoch,previous_request,epoch,request,prompt_index,cold_verify):
 """Return only after ALL ACKs, publications and actual cold comparison pass.
 cold_verify is the future gate's pinned existing sealed-reader comparison, not a
 controller boolean assertion. No OP15/OP28 is issued by this function.
 """
 require(not plan.get('dedicated_reset_poisoned')and callable(cold_verify),'healthy dedicated transition/cold reader binding')
 selected=authority(plan,prompt_index);target_reset.quiescent(stages)
 require(provider.command_pending is None and not provider.transmit and not provider.received
  and not getattr(provider,'prefill_bulk_busy',False),'provider all-owner quiescence')
 require(epoch==previous_epoch+1 and all(re.fullmatch('[0-9a-f]{64}',x)for x in [previous_request,request])and previous_request!=request,'consecutive distinct request')
 owner=provider.owner;original=Path(owner.spec['native_output']);destination=original/f'request-{epoch}'
 sequence=provider.sequence+1;path=original/f'reset-{sequence}.json'
 require(original==original.resolve()and original.is_dir()and not path.exists()and not path.is_symlink()and not destination.exists()and not destination.is_symlink(),'fresh provider reset destination/descriptor')
 descriptor=dict(schema=PROTOCOL,role='provider',owner_index=0,global_sequence=sequence,
  previous_epoch=previous_epoch,next_epoch=epoch,previous_request_sha256=previous_request,
  next_request_sha256=request,destination=str(destination),oracle='',**selected)
 raw=(json.dumps(descriptor,sort_keys=True)+'\n').encode()
 require(len(raw)<=8192,'bounded actual provider descriptor')
 with path.open('xb')as out:out.write(raw)
 try:
  # Existing target reset reserves monotonic sequence before send; it retains
  # target ledgers until this complete all-owner transaction is accepted.
  targets=target_reset.reset(stages,plan,guard,output,previous_epoch=previous_epoch,
   previous_request=previous_request,epoch=epoch,request=request,dedicated=selected,defer_rebind=True)
  provider.reset_request(descriptor)
  for stage,record in zip(stages,targets):stage.dedicated_native_output=record['native_output']
  provider.dedicated_native_output=str(destination)
  receipt_path=destination/'provider-reset.json';receipt=target_reset.evidence.read_json(receipt_path)
  expected=dict(schema='ownrt.dedicated-provider-reset.v1',passed=True,global_sequence=sequence,
   next_epoch=epoch,next_request_sha256=request,prompt_sha256=selected['prompt_sha256'],
   suite_sha256=selected['suite_sha256'],prompt_index=prompt_index,
   metadata_sha256=sha256(raw).hexdigest(),provider_serial=0,bulk_closed=False,bulk_used=False)
  require(all(type(receipt.get(k))is type(v)and receipt.get(k)==v for k,v in expected.items()),'actual provider reset receipt')
  before=receipt.get('allocation_inventory_before_sha256');require(isinstance(before,str)and re.fullmatch('[0-9a-f]{64}',before)and before==receipt.get('allocation_inventory_after_sha256'),'provider retained allocation identity')
  # Must use actual canonical maps/bundles and real cold baseline, including
  # inactive banks; this callback has not yet been bound to a model harness.
  proof=cold_verify(stages,provider,output)
  require(proof['passed']is True and proof['target_canonical_sources']==2065
   and proof['provider_canonical_sources']==73 and proof['full_payload_bytes_compared']>0,
   'all-owner actual canonical cold proof')
  for stage in stages:
   require(not any(stage.shared[:])and not any(stage.prefill[:]),'target complete normal/bulk publication zero')
   extent,header=base.prefill_layout(plan['prefill_rows'],stage.stream_bytes,plan.get('dedicated_prefill_slots',2))
   require(len(stage.prefill)==extent,'retained bulk map exact extent')
   stage.prefill[:len(header)]=header
   require(bytes(stage.prefill[:len(header)])==header and not any(stage.prefill[len(header):]),'post-all-ACK bulk header only publication')
   stage.start_async();stage.sock.settimeout(.2)
   if hasattr(stage,'handoff'):del stage.handoff
  provider.start_async();provider.sock.settimeout(.2)
  target_reset.quiescent(stages)
  plan['dedicated_reset_ready']=(epoch,request,selected['prompt_sha256'])
  return dict(passed=True,targets=targets,provider_receipt=receipt,cold_proof=proof,authority=selected)
 except BaseException:
  plan['dedicated_reset_poisoned']=True;provider.plan['dedicated_reset_poisoned']=True
  for stage in stages:setattr(stage,'dedicated_reset_poisoned',True)
  raise
