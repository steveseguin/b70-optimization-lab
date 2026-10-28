"""Root-release-only composition of existing sealed reader and exact comparator.
No launches, writes to native evidence, tolerance, or source exclusions.
"""
import argparse,hashlib,json,sys
from pathlib import Path
from common import CONTROL,CANDIDATE,need,read,sha,stamp,finished,first_a
HERE=Path(__file__).resolve().parent;RUNTIME=HERE.parents[2]
sys.path.insert(0,str(RUNTIME/'engine/tools'))
import dedicated_reset_suite as existing
reader=existing.reader

def identity(control,candidate):
 plans=[];checks=[];hashed={}
 for root,depth in [(control,3),(candidate,2)]:
  config=read(root/'config.json');plan=read(root/'plan.json');need(config['speculative_depth']==plan['speculative_depth']==depth,'expected fixed depth')
  need(plan['boundaries']==[0,17,33,48] and plan['context']==65536 and plan['max_new']==512,'registered exact geometry')
  need(plan['reference_route_tie_sort'] is True and plan['draft_route_policy']=='unchanged-bf16'and plan['reference_route_scope']=='f32-target-only','registered arithmetic/routing scope')
  build=read(config['build_receipt']);need(build['binary_sha256']=='e60f7427d5737bee1e4e521ffbad1c77f4ea687fbb86bd542f05fb495eb9e378','actual registered reset binary')
  admission=read(root/'admission.json');need(admission['plan_sha256']==sha(root/'plan.json'),'actual admitted plan digest')
  for source,expected in plan['pins'].items():
   if source not in hashed:hashed[source]=sha(source)
   need(hashed[source]==expected,'actual immutable source pin '+source)
  manifest=read(plan['dedicated_prompt_manifest']);need(sha(plan['dedicated_prompt_manifest'])==plan['dedicated_prompt_manifest_sha256'],'actual immutable prompt authority')
  route='1'if plan['reference_route_tie_sort']else'0'
  policy='ownrt.dedicated-reset-policy.v2\nF32\n'+plan['check_policy']+'\n'+str(plan['context'])+'\n'+str(depth)+'\n'+str(plan['prefill_rows'])+'\n'+str(plan['dedicated_prefill_slots'])+'\nreference_route_tie_sort='+route+'\n'
  need(hashlib.sha256(policy.encode()).hexdigest()==manifest['policy_sha256']==plan['verification_policy_sha256'],'actual depth-specific reset policy')
  markers={plan['request_sha256']:'<DERIVED_REQUEST>',plan['verification_policy_sha256']:'<DERIVED_DEPTH_POLICY>',plan['dedicated_prompt_manifest_sha256']:'<DERIVED_MANIFEST>'}
  def norm(value):
   if isinstance(value,dict):
    result={}
    for k,v in value.items():
     key=norm(k)
     if k=='speculative_depth':v='<DEPTH>'
     elif k=='pins':
      v={norm(name):('<DERIVED_CONFIG>'if name==str(root/'config.json')else '<DERIVED_MANIFEST>'if name==plan['dedicated_prompt_manifest']else h)for name,h in v.items()}
     result[key]=norm(v)
    return result
   if isinstance(value,list):
    output=[norm(v)for v in value]
    for flag in ['--pipeline-ring-depth','--channel','--stop-fd']:
     if flag in output:
      i=output.index(flag);output[i+1]='<DEPTH>'if flag=='--pipeline-ring-depth'else'<EPHEMERAL_FD>'
    return output
   if isinstance(value,str):return markers.get(value,value.replace(str(root),'<RUN>'))
   return value
  actual={}
  for spec in plan['stages']+[plan['provider']]:
   owner=str(spec['id']);launch=read(root/f'output/stage{owner}/launch.json')
   need(norm(launch['argv'])==norm(spec['argv']),'actual native argv versus admitted plan '+owner)
   need(norm(launch['environment'])==norm(spec['environment']),'actual native environment versus admitted plan '+owner)
   argv=launch['argv'];need(argv[argv.index('--pipeline-ring-depth')+1]==str(depth),'actual native selected depth')
   actual[owner]=dict(argv=norm(argv),environment=norm(launch['environment']))
   if owner!='provider':
    stage=read(root/f'output/stage{owner}/native/pipeline-stage.json');need(stage['ring_capacity']==stage['depth']==depth,'actual native ring capacity witness')
  plans.append(dict(config=norm(config),plan=norm(plan),manifest=norm(manifest),actual_native=actual))
  checks.append(dict(root=str(root),depth=depth,plan_sha256=sha(root/'plan.json'),source_pins=len(plan['pins']),request_sha256=plan['request_sha256'],verification_policy_sha256=plan['verification_policy_sha256']))
 need(plans[0]==plans[1],'unexpected cross-depth config/plan/model/precision/topology/env/argv difference')
 return checks

def metadata(directory,expected):
 directory=Path(directory);stamps={n:stamp(directory/n)for n in ['state-index.tsv','state.json','state-seal.txt']}
 fields=(directory/'state-seal.txt').read_text().splitlines();need(len(fields)==5 and fields[0]=='GSQ_STATE_SEAL_V1','state seal schema')
 need(sha(directory/'state-index.tsv')==fields[3] and sha(directory/'state.json')==fields[4],'metadata seal hashes')
 obj=read(directory/'state.json');sources={reader.logical_name(k):v for k,v in obj['buffers'].items()};sources['state.json']=fields[4]
 need(sources==expected,'actual state metadata versus completed repeated-A proof')
 lines=(directory/'state-index.tsv').read_text().splitlines();need(lines[0]=='GSQ_STATE_BUNDLE_V1','state index schema')
 layout=[];offset=0
 for line in lines[1:]:
  name,start,length,h=line.split('\t');need(int(start)==offset and sources[name]==h,'contiguous actual layout/hash');layout.append([name,int(start),int(length)]);offset+=int(length)
 need(offset==int(fields[1])and len(layout)==len(sources)-1,'complete actual indexed payload')
 need(all(stamp(directory/n)==old for n,old in stamps.items()),'stable state metadata')
 return dict(layout=layout,sources=sources,bytes=int(fields[1]),payload_sha256=fields[2])

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--control-root',type=Path,default=CONTROL);parser.add_argument('--candidate-root',type=Path,default=CANDIDATE);parser.add_argument('--restored-control',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
 need(not a.output.exists(),'fresh exclusive comparison receipt')
 result=dict(schema='ownrt.fixed-depth2-vs3-full-first-A.v1',passed=False,exclusions=[],tolerance=False,stage='finished-owner-admission')
 try:
  result['finished']={str(root):finished(root)for root in [a.control_root,a.candidate_root]}
  result['stage']='identity';result['identities']=identity(a.control_root,a.candidate_root)
  result['stage']='actual-three-request-prompt-output'
  left=read(a.control_root/'output/driver-result.json')['request_results'];right=read(a.candidate_root/'output/driver-result.json')['request_results'];need(len(left)==len(right)==3,'actual A/B/A length')
  result['outputs']=[]
  for i,(x,y)in enumerate(zip(left,right)):
   need(x['id']==y['id']and x['authority']['prompt_index']==y['authority']['prompt_index']and x['authority']['prompt_sha256']==y['authority']['prompt_sha256']and x['authority']['prompt_tokens']==y['authority']['prompt_tokens'],'actual prompt identity')
   need(x['result']['output_ids']==y['result']['output_ids']and len(x['result']['output_ids'])==512,'all actual512 output IDs')
   result['outputs'].append(dict(ordinal=i,id=x['id'],tokens=512,prompt_sha256=x['authority']['prompt_sha256']))
  restored=read(a.restored_control/'restoration.json');need(restored['passed']and restored['archive_receipt_sha256']==sha(a.control_root/'state-archive.json'),'exact restored archive authority')
  lstate=first_a(a.control_root);rstate=first_a(a.candidate_root);need(set(lstate)==set(rstate)=={'0','1','2','provider'},'complete four-owner state')
  result['stage']='complete-source-layout-maps';result['owners']={};differences=[];canonical=set();inactive=0
  for owner in ['0','1','2','provider']:
   lp=a.restored_control/owner;rp=Path(rstate[owner]['path']);l=metadata(lp,lstate[owner]['sources']);r=metadata(rp,rstate[owner]['sources'])
   changed=[n for n in sorted(set(l['sources'])|set(r['sources']))if l['sources'].get(n)!=r['sources'].get(n)]
   if owner=='provider':need(len(l['sources'])-1==73,'complete first-A provider inventory')
   else:
    inactive+=sum(n.startswith('alternate-')for n in l['sources'])
    for n,h in l['sources'].items():
     if n=='state.json'or n.startswith('alternate-'):continue # counting only; all sources are compared below
     canonical.add(n) # Inventory only: postrequest scratch differs between ranks.
   row=dict(control=str(lp),candidate=str(rp),control_bytes=l['bytes'],candidate_bytes=r['bytes'],source_count=len(l['sources'])-1,layout_equal=l['layout']==r['layout'],changed_sources=changed)
   result['owners'][owner]=row
   if l['layout']!=r['layout']or changed:differences.append(dict(owner=owner,layout_equal=row['layout_equal'],changed_sources=changed,control_layout=l['layout']if not row['layout_equal']else None,candidate_layout=r['layout']if not row['layout_equal']else None))
  need(len(canonical)==2065 and inactive==27,'complete first-A target/inactive inventories');result['inventory_counts']=dict(target_canonical=2065,inactive=27,provider=73)
  result['source_layout_differences']=differences;need(not differences,'actual full source/layout difference; no exclusions permitted')
  result['stage']='sealed-reader-and-exact-full-bytes';total=0
  for owner,row in result['owners'].items():
   lp=Path(row['control']);rp=Path(row['candidate']);lm=reader.read_state(lp);rm=reader.read_state(rp)
   need(lm==lstate[owner]['sources']and rm==rstate[owner]['sources']and lm==rm,'complete sealed raw source maps')
   n=existing.exact(lp/'state.bundle',rp/'state.bundle',lambda:None);row['full_bytes_compared']=n;total+=n
  result.update(passed=True,stage='complete',full_payload_bytes_compared=total,scope='All first-A target3+provider physical payload bytes, every source/layout map and state metadata, no exclusion/tolerance; all3 actual prompt/outputs match. Not full12 suite speed or independent CPU state equality.')
 except Exception as e:result['error']=repr(e)
 a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print(json.dumps({k:result.get(k)for k in ['passed','stage','full_payload_bytes_compared','error']}));raise SystemExit(0 if result['passed']else 1)
if __name__=='__main__':main()
