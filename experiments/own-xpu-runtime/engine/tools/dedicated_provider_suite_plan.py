"""Explicit suite extension of the existing dedicated planner, default untouched."""
from hashlib import sha256
import json
from pathlib import Path
import struct
import argparse
import dedicated_provider_driver as single
import dedicated_reset_suite as runtime
base=single.base

def make_plan(config_path, *, prepare_authority=False):
 config=json.loads(Path(config_path).read_text())
 base.require(config.get('dedicated_reset_protocol')=='ownrt.dedicated-reset-request.v2','explicit versioned suite request')
 plan=single.make_plan(config_path)
 base.require(plan.get('dedicated_bulk_prefill')is True and plan['max_new']==512,'actual authenticated bulk/512 suite')
 source=Path(config['dedicated_request_suite']).resolve();suite=json.loads(source.read_text())
 base.require(set(suite)=={'schema','model_identity_sha256','activation_dtype','eos_token_ids','prompts'} and suite['schema']=='ownrt.persistent-rolling-inputs.v1','runtime-only existing suite schema')
 base.require(suite['model_identity_sha256']==plan['model_identity_sha256'] and suite['activation_dtype']=='F32' and suite['eos_token_ids']==plan['eos_token_ids'],'suite actual arithmetic/model/EOS')
 rows=suite['prompts'];base.require(isinstance(rows,list)and len(rows)==12,'exact twelve requests')
 authority=Path(config['dedicated_suite_authority']).resolve();payloads={}
 route='1'if plan['reference_route_tie_sort']else'0'
 policy='ownrt.dedicated-reset-policy.v2\nF32\n'+plan['check_policy']+'\n'+str(plan['context'])+'\n'+str(plan['speculative_depth'])+'\n'+str(plan['prefill_rows'])+'\n'+str(plan['dedicated_prefill_slots'])+'\nreference_route_tie_sort='+route+'\n'
 manifest=dict(schema='ownrt.dedicated-prompt-suite.v1',requests=12,context=plan['context'],max_new=512,model_identity_sha256=plan['model_identity_sha256'],policy_sha256=sha256(policy.encode()).hexdigest())
 names=set()
 for i,row in enumerate(rows):
  base.require(set(row)=={'id','prompt_tokens','max_new'}and isinstance(row['id'],str)and row['id']not in names and row['max_new']==512,'no oracle/duplicate suite request')
  names.add(row['id']);tokens=row['prompt_tokens']
  base.require(isinstance(tokens,list)and 3<=len(tokens)<=plan['context']-512 and all(type(t)is int and 0<=t<plan['vocab']for t in tokens),'actual suite token geometry')
  data=struct.pack('<'+'i'*len(tokens),*tokens);p=authority/f'prompt-{i:02d}.i32';payloads[p.name]=data
  manifest.update({f'prompt_{i}_path':str(p),f'prompt_{i}_tokens':len(tokens),f'prompt_{i}_sha256':sha256(data).hexdigest()});plan['pins'][str(p)]=sha256(data).hexdigest()
 base.require(rows[0]['prompt_tokens']==plan['prompt_tokens'],'actual first prompt matches base planner')
 path=authority/'manifest.json'
 payloads[path.name]=(json.dumps(manifest,indent=2)+'\n').encode()
 if prepare_authority:
  base.require(not authority.exists() and not authority.is_symlink(),'fresh immutable suite authority directory')
  authority.mkdir(mode=0o700)
  for name,data in payloads.items():
   with (authority/name).open('xb')as f:f.write(data)
   (authority/name).chmod(0o400)
 else:
  base.require(authority.is_dir()and not authority.is_symlink()and {p.name for p in authority.iterdir()}==set(payloads),'prepared immutable authority exact inventory')
  for name,data in payloads.items():
   p=authority/name
   base.require(not p.is_symlink()and p.is_file()and p.stat().st_size==len(data)and p.read_bytes()==data,'prepared immutable authority exact bytes')
 digest=sha256(payloads[path.name]).hexdigest()
 request=sha256(json.dumps(dict(original=plan['request_sha256'],suite=digest,policy=manifest['policy_sha256']),sort_keys=True).encode()).hexdigest()
 for owner in plan['stages']+[plan['provider']]:
  base.require(owner['environment']['OWNRT_REFERENCE_ROUTE_TIE_SORT']==route,'all-owner admitted target-route policy')
  owner['argv']=base.replace_options(owner['argv'],{'--pipeline-ring-request-sha256':request,'--provider-prefill-prompt':manifest['prompt_0_path'],'--provider-prefill-prompt-sha256':manifest['prompt_0_sha256']})
  owner['argv']+=['--dedicated-reset-suite',str(path),'--dedicated-reset-suite-sha256',digest]
 plan.update(dedicated_reset_protocol=config['dedicated_reset_protocol'],persistent_requests=True,dedicated_requests=rows,request_sha256=request,
  dedicated_prompt_manifest=str(path),dedicated_prompt_manifest_sha256=digest,verification_policy_sha256=manifest['policy_sha256'],
  dedicated_prefill_prompt=manifest['prompt_0_path'],dedicated_prefill_prompt_sha256=manifest['prompt_0_sha256'],
  dedicated_reset_payload_bounds=config['dedicated_reset_payload_bounds'],dedicated_reset_evidence_bytes=config['dedicated_reset_evidence_bytes'])
 plan['dedicated_request_indices']=config.get('dedicated_request_indices',list(range(12)))
 base.require(plan['dedicated_request_indices']in (list(range(12)),[0,1,0]),'full suite or bounded repeated-A gate')
 runtime.forecast(plan)
 files=[source,path,Path(__file__),Path(runtime.__file__),Path(runtime.reset_all.__file__),Path(runtime.reset_all.target_reset.__file__),Path(runtime.reader.__file__),Path(runtime.reset_all.target_reset.evidence.__file__),Path(runtime.reset_all.target_reset.rolling.__file__)]
 for p in files:plan['pins'][str(p.resolve())]=base.digest(p)
 return plan


def validate_run(plan_path,admission_path):
 plan_path,admission_path=Path(plan_path),Path(admission_path)
 plan=json.loads(plan_path.read_text());admission=json.loads(admission_path.read_text())
 base.require(admission.get('plan_sha256')==base.digest(plan_path),'admission plan hash')
 base.require(isinstance(plan.get('pins'),dict)and plan['pins'],'source pins required')
 for name,digest in plan['pins'].items():
  p=Path(name);base.require(p.is_absolute()and not p.is_symlink()and p.is_file()and base.digest(p)==digest,'immutable plan/source pin changed: '+name)
 base.require(plan==make_plan(plan['config']),'plan/source/runtime identity changed')
 return plan,admission

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--config',type=Path);parser.add_argument('--plan',type=Path)
 parser.add_argument('--prepare-authority',action='store_true');parser.add_argument('--run',action='store_true')
 parser.add_argument('--admission',type=Path);parser.add_argument('--unit')
 args=parser.parse_args()
 base.require(not(args.prepare_authority and args.run),'exclusive prepare/run modes')
 if args.prepare_authority:
  base.require(args.config is not None and args.plan is None,'authority preparation requires config only')
  plan=make_plan(args.config,prepare_authority=True)
  print(json.dumps(dict(authority=plan['dedicated_prompt_manifest'],sha256=plan['dedicated_prompt_manifest_sha256'],device_execution_requested=False)))
 elif args.run:
  base.require(args.plan is not None and args.admission is not None and args.unit,'explicit plan/admission/unit')
  plan,admission=validate_run(args.plan,args.admission)
  print(json.dumps(single.lifecycle.execute(plan,admission,args.unit)))
 else:
  base.require(args.config is not None and args.plan is not None,'config/plan required')
  plan=make_plan(args.config);base.save(args.plan,plan)
  print(json.dumps(dict(plan=str(args.plan),sha256=base.digest(args.plan),device_execution_requested=False)))
if __name__=='__main__':main()
