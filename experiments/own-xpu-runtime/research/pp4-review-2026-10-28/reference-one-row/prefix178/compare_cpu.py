"""Completed prefix178 comparison only; no model/device execution.
CPU receipt must authenticate the new178 OFF/ON run and every retained array.
No244-row authority or assumed expected argmax is accepted.
"""
import argparse,hashlib,importlib.util,json,math,pathlib,struct
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sealed',HERE.parents[1]/'dedicated-gate/bounded-live-count-candidate/compare_completed.py')
# HERE.parents[1] is pp4-review root.
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
need,raw,read,sha=C.need,C.raw,C.read,C.sha
INPUT_SHA='6ae63f3cf088aa2c613d9e3c6fac6a4736d3fcd7ce7bc3bd5e2346c421487628'
PACKED_SHA='a6217b30f370018ed5a46eee4defbb1030e16d729ce8b48f8c32359b632810be'
def metrics(a,b):
 need(len(a)==len(b)>0 and len(a)%4==0,'equal F32 extent')
 av=struct.unpack('<%df'%(len(a)//4),a);bv=struct.unpack('<%df'%(len(b)//4),b)
 need(all(math.isfinite(x)for x in av+bv),'finite F32 arrays')
 delta=[x-y for x,y in zip(av,bv)];rms=math.sqrt(sum(x*x for x in delta)/len(delta));ref=math.sqrt(sum(x*x for x in bv)/len(bv))
 return dict(unequal_words=sum(a[i:i+4]!=b[i:i+4]for i in range(0,len(a),4)),max_abs=max(map(abs,delta)),rms=rms,reference_rms=ref,relative_rms=None if not ref else rms/ref)
def cpu_arrays(receipt):
 need(receipt['schema']=='ownrt.prefix178.cpu-capture-receipt.v1' and receipt['passed'] is True,'new CPU observer authority')
 need(receipt['input_json_sha256']==INPUT_SHA and receipt['packed_prompt_sha256']==PACKED_SHA and receipt['position']==177 and receipt['tokens']==178,'exact178 input/row authority')
 need(receipt['process_returncode']==0 and receipt['full_logits_bitwise_equal'] is True,'successful neutral OFF/ON observer')
 files=receipt['files'];result={}
 expected={'off/logits-177.f32':248320*4,'on/logits-177.f32':248320*4}
 for i in range(48):
  expected[f'on/layer-{i:02d}.f32']=40960
  for name,width in [('input',2560),('logits',512),('probabilities',512),('weights',10),('ids',10)]:expected[f'on/layer-{i:02d}-{name}.{"i32"if name=="ids"else"f32"}']=width*4
 need(set(expected)<=set(files),'complete48layer+240router arrays')
 root=pathlib.Path(receipt['root'])
 need(receipt['off']==str(root/'off')and receipt['on']==str(root/'on'),'actualOFF/ONpaths')
 need(sha(raw(root/'run.json'))==receipt['run_sha256'],'actual CPU run/source identity')
 neutral=read(root/'neutrality.json');need(neutral==receipt['neutrality'] and neutral['tokens']==178 and neutral['position']==177 and neutral['logit_words']==248320 and neutral['single_model_load']is True and neutral['independent_contexts']is True and neutral['full_logits_bitwise_equal']is True,'actual neutral fresh contexts')
 for name,n in expected.items():
  b=raw(root/name);entry=files[name];need(len(b)==entry['bytes']==n and sha(b)==entry['sha256'],'actual CPU array authority '+name);result[name]=b
 need(result['off/logits-177.f32']==result['on/logits-177.f32'],'full actual OFF/ON logits equal')
 for name in ['on/router-layouts.jsonl','off/rows.jsonl','on/rows.jsonl']:
  b=raw(root/name);need(sha(b)==files[name]['sha256']and len(b)==files[name]['bytes'],'CPU row/layout metadata authority')
 for mode in ['off','on']:
  rows=[json.loads(l)for l in raw(root/(mode+'/rows.jsonl')).splitlines()];need(len(rows)==1 and rows[0]['position']==177,'CPU scored row177 only')
 need(receipt['capture_counts']=={'layers':48,'router_arrays':240,'router_nodes':192},'actual observer inventory')
 return result
def run(native_root,cpu_receipt,result,router_evidence=False):
 result.update(schema='ownrt.prefix178.native-CPU-comparison.v1',passed=False,scope='One fixed teacher-forced178tokenprefix/row177. Argmax agreement alone does not resolve independentCPUquality; layer differences localize, not establish cause.')
 arrays=cpu_arrays(read(cpu_receipt));plan=read(native_root/'plan.json');inp=read(HERE/'input.json');need(sha(raw(HERE/'input.json'))==INPUT_SHA,'pinned178inputsource')
 need(plan['prompt_tokens']==inp['tokens'] and len(plan['prompt_tokens'])==178 and sha(struct.pack('<178i',*plan['prompt_tokens']))==PACKED_SHA,'actual native178prompt')
 res=read(native_root/'output/result.json');need(res['passed']is True and not res['error']and not res['live_pids']and set(res['returncodes'].values())=={0},'completed native owners')
 trace=res['rank_trace']
 for rank in [0,1]:
  rows=[x for x in trace if x['rank']==rank and x['op']==1];need([x['position']for x in rows]==list(range(178))and all(x['speculative']is False for x in rows),'actual178serial HALF trace')
 layers=[]
 for i in range(48):
  captures=[x for x in res['layer_captures']if pathlib.Path(x['path']).name==f'layer-{i:02d}.bf16'];need(len(captures)==1,'one native layer');e=captures[0];b=raw(e['path']);need(len(b)==e['bytes']==40960 and e['dtype']=='F32 little-endian' and sha(b)==e['sha256'],'native F32 layer authority');layers.append(dict(layer=i,native_sha256=sha(b),cpu_sha256=sha(arrays[f'on/layer-{i:02d}.f32']),metrics=metrics(b,arrays[f'on/layer-{i:02d}.f32'])))
 result['layers']=layers
 if router_evidence:
  routing=[];state_cache={}
  def selected(stage,name):
   dump=pathlib.Path(res['full_state_paths'][stage]);need(dump.name=='state-178','router dump178')
   if stage not in state_cache:state_cache[stage]=C.sealed(dump,True)
   ent=state_cache[stage]['entries'][name];need(res['verified_full_state_sources'][str(stage)][name]==ent['sha256'],'router source receipt')
   with(dump/'state.bundle').open('rb')as f:f.seek(ent['offset']);data=f.read(ent['bytes'])
   need(sha(data)==ent['sha256'],'router actual entry hash');return data
  for i in range(48):
   owners=[s['id']for s in plan['stages']if s['begin']<=i<s['end']];need(len(owners)==1,'unique actual native layerowner');stage=owners[0]
   log=selected(stage,f'blk.{i}.router.bin');ids=selected(stage,f'blk.{i}.ids.bin');mix=selected(stage,f'blk.{i}.hc.f.mix.bin');weights=selected(stage,f'blk.{i}.prob.bin')
   ci=struct.unpack('<10i',arrays[f'on/layer-{i:02d}-ids.i32']);ni=struct.unpack('<10I',ids)
   routing.append(dict(layer=i,native_ids=list(ni),cpu_ids=list(ci),ids_equal=ni==ci,router_logits=metrics(log,arrays[f'on/layer-{i:02d}-logits.f32']),router_input=metrics(mix,arrays[f'on/layer-{i:02d}-input.f32']),selected_weights=metrics(weights,arrays[f'on/layer-{i:02d}-weights.f32'])))
  result['router_evidence']=routing;result['first_different_router_ID_layer']=next((x['layer']for x in routing if not x['ids_equal']),None)
  result['router_scope']='Actual sealed native lastrow177 vs newCPU177, different incoming histories; no equal-input tie/causal claim.'
 # Exact full native seal/payload authority, including logits. No historic244fallback.
 final=pathlib.Path(res['full_state_paths'][-1]);need(final.name=='state-178','actual native dump178');sealed=C.sealed(final,True);entry=sealed['entries']['logits.bin'];need(entry['bytes']==248320*4 and res['verified_full_state_sources']['1']['logits.bin']==entry['sha256'],'actual native full logits authority')
 with(final/'state.bundle').open('rb')as f:f.seek(entry['offset']);b=f.read(entry['bytes'])
 need(sha(b)==entry['sha256'],'actual selected logits hash');cpu=arrays['on/logits-177.f32'];nv=struct.unpack('<248320f',b);cv=struct.unpack('<248320f',cpu);ni=max(range(len(nv)),key=nv.__getitem__);ci=max(range(len(cv)),key=cv.__getitem__);need(res['actual_output_ids']==[ni],'native output argmax')
 # Fixed reporting thresholds, not pass/fail tolerance or equivalence waiver.
 result.update(passed=True,native_argmax=ni,cpu_argmax=ci,argmax_matches=ni==ci,logits=metrics(b,cpu),first_bitwise_different_layer=next((x['layer']for x in layers if x['metrics']['unequal_words']),None),first_layer_rms_ge_1e_6=next((x['layer']for x in layers if x['metrics']['rms']>=1e-6),None),first_layer_rms_ge_1e_4=next((x['layer']for x in layers if x['metrics']['rms']>=1e-4),None),threshold_scope='Descriptive fixed localization markers, not fidelity tolerance.',cpu_receipt_sha256=sha(raw(cpu_receipt)),native_result_sha256=sha(raw(native_root/'output/result.json')))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('native_root',type=pathlib.Path);p.add_argument('--cpu-receipt',required=True,type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path);p.add_argument('--router-evidence',action='store_true');a=p.parse_args();need(not a.out.exists(),'exclusive output');result={}
 try:run(a.native_root,a.cpu_receipt,result,a.router_evidence)
 except Exception as e:result.update(passed=False,error={'type':type(e).__name__,'message':str(e)})
 with a.out.open('x')as f:json.dump(result,f,indent=2);f.write('\n')
 raise SystemExit(0 if result['passed']else 1)
