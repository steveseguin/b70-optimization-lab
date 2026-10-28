#!/usr/bin/env python3
"""Target-only GPU route candidate: seven diagnostic-state gates then twelve cold generations."""
import argparse,gzip,hashlib,importlib.util,json,shutil,struct,subprocess,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('gpu_tie_seven',HERE.parent/'remaining-regressions/run.py');H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
C,BASE,ROOT=H.C,H.BASE,H.ROOT
REPO=ROOT.parents[1]
MATRIX=HERE.parents[2]/'realistic-matrix-registration.json'
REFERENCE=HERE.parent/'historical-seven-r1-evidence'

def suite():
 data=json.loads(MATRIX.read_text());rows=next(x['inputs']for x in data['matrix']if x['case']=='short-realistic-decode');result=[]
 BASE.require(len(rows)==12 and len({x['id']for x in rows})==12,'complete frozen twelve-task matrix')
 for row in rows:
  p=REPO/row['path'];BASE.require(BASE.digest(p)==row['sha256'],'frozen suite prompt source')
  tokens=json.loads(p.read_text());BASE.require(type(tokens)is list and len(tokens)==row['tokens'] and all(type(x)is int and 0<=x<248320 for x in tokens),'exact suite prompt IDs')
  result.append(dict(id=row['id'],path=str(p),sha256=row['sha256'],prompt=tokens,max_new=512))
 return result

def registration(config):
 path=Path(config['gpu_candidate_registration']).resolve()
 BASE.require(path.parent==HERE and path.name.startswith('registration-')and path.suffix=='.json','explicit local candidate registration')
 reg=json.loads(path.read_text());BASE.require(reg['schema']=='ownrt.gpu-route-candidate-registration.v1','candidate registration schema')
 receipt=Path(config['build_receipt']).resolve();BASE.require(BASE.digest(receipt)==reg['build_receipt_sha256'],'candidate exact compiled receipt')
 build=json.loads(receipt.read_text());BASE.require(build['binary_sha256']==reg['binary_sha256'],'candidate compiled binary')
 gate=Path(reg['route_kernel_gate']).resolve();BASE.require(BASE.digest(gate)==reg['route_kernel_gate_sha256'],'registered actual route kernel gate')
 actual=json.loads(gate.read_text());BASE.require(actual.get('schema')=='ownrt.reference-route-device-gate.v1'and actual.get('passed')is True,'actual route kernel gate must pass before model planning')
 # Root registration binds exact tested/applied files, not merely a boolean.
 sources=reg['gated_sources'];BASE.require(type(sources)is dict and bool(sources),'explicit gated/applied source authority')
 for name,digest in sources.items():
  p=Path(name).resolve();BASE.require(p.is_relative_to(ROOT/'engine/src')and BASE.digest(p)==digest,'applied source equals registered gated source')
 BASE.require(actual.get('source_sha256')==sources and actual.get('mode_counts',{}).get('off',0)>0 and actual.get('mode_counts',{}).get('on',0)>0,'actual gate binds exact sources and both modes')
 return path,reg,gate

def phase_b_enabled(config):
 value=config.get("phase_b_generation",True)
 BASE.require(type(value)is bool,"phase_b_generation strict boolean")
 return value

def make_plan(config):
 config=Path(config).resolve();cfg=json.loads(config.read_text());regpath,reg,gate=registration(cfg)
 registered=H.cases();enabled=phase_b_enabled(cfg);tasks=suite()if enabled else []
 BASE.require(cfg['boundaries']==[0,23,48]and cfg['context']==4096 and cfg['max_new']==512 and cfg['prompt_tokens']==registered[0]['prompt'],'fixed target-only candidate request envelope')
 BASE.require(cfg.get('live_draft')is False and cfg.get('use_proposals')is False,'no draft or speculative proposals')
 p=C.base.make_plan(config);out=Path(p['output'])
 for stage in p['stages']:
  rank=stage['id'];argv=C.native_argv(stage['argv'],out,rank)
  argv=BASE.replace_options(argv,{'--context':4096,'--max-new':128,'--retain-steps':1},{'--draft-rank'})
  BASE.require(not any(x.startswith(('--draft','--provider','--pipeline','--oracle'))for x in argv),'target-only scalar no oracle argv')
  env=stage['environment'];BASE.require(not any(k in env for k in ['OWNRT_ROUTER_TIE_DIAGNOSTIC','OWNRT_REFERENCE_ROUTE_TIE_SORT','OWNRT_L4_RAW_HISTORY','OWNRT_L4_PREP_HISTORY','OWNRT_LOOKUP_VIEW']),'no inherited candidate/host diagnostic flags')
  env['OWNRT_REFERENCE_ROUTE_TIE_SORT']='1';stage['argv']=argv;stage['native_output']=str(out/f'native/rank{rank}')
 BASE.require(BASE.option(p['stages'][0]['argv'],'--reset-dump')=='none'and all(BASE.option(s['argv'],'--finish-dump')=='none'for s in p['stages']),'explicit bounded dumps only')
 proof=json.loads(H.CACHE_PROOF.read_text());main=ROOT/'engine/src/gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp';rank=ROOT/'engine/src/gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp'
 BASE.require(proof['admit_position_function']in main.read_text()and proof['half_callsite']in rank.read_text(),'unchanged actual pre-HALF retained-cache rebind proof')
 BASE.require(hashlib.sha256(proof['admit_position_function'].encode()).hexdigest()==proof['admit_position_function_sha256']and proof['allowed_inventory_fields']==['launch_extent','alternate_launch_extent'],'same narrow cold inventory authority')
 archive=json.loads((REFERENCE/'archive.json').read_text());BASE.require(archive['full_tar_bytes_compared']and archive['actual_payload_sha256_matches_all_seals']and archive['removal_completed'],'verified diagnostic archive authority')
 ref=json.loads(gzip.decompress((REFERENCE/'output-result.json.gz').read_bytes()));BASE.require(ref['passed']and len(ref['records'])==7,'completed seven diagnostic references')
 p.update(schema='ownrt.gpu-route-seven-plus-twelve.v1',requests=19 if enabled else 7,phase_A_requests=7,phase_B_requests=12 if enabled else 0,phase_b_generation=enabled,binary_sha256=reg['binary_sha256'],native_launch_max_new=128,native_request_max_new=512,mode='target-only-none',live_draft=False,use_proposals=False,expected_output_ids=None,eos_token_ids=[248044,248046],diagnostic_only=True,speed_claim=False,gpu_route_tie_sort=True,reference_host_diagnostic=False,evidence_forecast_bytes=5*1024**3,reference_archive_stat=list(H.reader.identity(Path(archive['archive']).stat())),reference_archive_receipt_sha256=BASE.digest(REFERENCE/'archive.json'),limits='PhaseA seven fixed-prefix outputs/layers/fullstate vs host diagnostic. Optional PhaseB all12 frozen genuine prompts, naturalEOS max512, cold reset each; phase_b_generation=false skips all generation after required PhaseA parity. No runtime output oracle; no free-running CPU fidelity claim until later independent comparison.')
 for path in [Path(__file__).resolve(),Path(H.__file__).resolve(),H.REG,H.CACHE_PROOF,H.READER,MATRIX,regpath,gate,REFERENCE/'archive.json',REFERENCE/'output-result.json.gz',main,rank]:p['pins'][str(path)]=BASE.digest(path)
 for name,digest in reg['gated_sources'].items():p['pins'][name]=digest
 for row in registered:
  for key in ['input','cpu_rows']:p['pins'][str(ROOT/row[key])]=BASE.digest(ROOT/row[key])
 for row in tasks:p['pins'][row['path']]=row['sha256']
 spec=importlib.util.spec_from_file_location('gpu_route_adapter_pins',C.ADAPTER);adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
 for path in [Path(C.__file__).resolve(),C.ADAPTER,Path(adapter.PARENT),Path(adapter.ENV_SOURCE)]:p['pins'][str(path)]=BASE.digest(path)
 for name,digest in adapter.source_pins().items():
  path=Path(name)if Path(name).is_absolute()else adapter.ROOT/name
  BASE.require(BASE.digest(path)==digest,'actual adapter dependency pin');p['pins'][str(path)]=digest
 return p

def drop_duplicate_cold(actual,baseline):
 BASE.require(actual['compared_to_first_actual_cold']is True,'cold duplicate requires completed canonical comparison')
 removed=[]
 for rank in ('0','1'):
  a,b=actual['state'][rank],baseline['state'][rank];p=Path(a['path'])/'state.bundle'
  BASE.require(p!=Path(b['path'])/'state.bundle'and a['sources']==b['sources']and a['bundle_sha256']==b['bundle_sha256'],'same verified cold sources and entire payload hash')
  BASE.require(actual['actual_canonical_bytes_compared'][rank]==p.stat().st_size,'actual complete cold bytes compared')
  BASE.require(not p.is_symlink(),'cold cleanup plain payload only');before=H.reader.identity(p.stat());removed.append(dict(path=str(p),bytes=p.stat().st_size,sha256=a['bundle_sha256'],duplicate_of=str(Path(b['path'])/'state.bundle'),identity=before))
 for row in removed:
  p=Path(row['path']);BASE.require(H.reader.identity(p.stat())==row['identity'],'cold duplicate identity unchanged');p.unlink()
 return dict(removed=removed,verified_duplicate=True,initial_cold_retained=True,removed_files_absent=all(not Path(x['path']).exists()for x in removed))

def compare_archive(records,reference,receipt,check=lambda:None):
 """One archive stream for all PhaseA payloads; no extraction or repeated HDD hash."""
 BASE.require(len(records)==len(reference['records'])==7,'all seven actual and diagnostic cases')
 wanted={};by_member={x['member']:x for x in receipt['members']};count=0
 for candidate,old in zip(records,reference['records']):
  BASE.require(candidate['id']==old['id']and candidate['actual_output_ids']==old['actual_output_ids'],'actual fixed-prefix output matches diagnostic')
  BASE.require({Path(x['path']).name:x['sha256']for x in candidate['layer_captures']}=={Path(x['path']).name:x['sha256']for x in old['layer_captures']},'all48 actual layers match diagnostic')
  for rank in ('0','1'):
   a,b=candidate['full_state'][rank],old['full_state'][rank];BASE.require(a['sources']==b['sources'],'complete canonical source maps match diagnostic')
   original=Path(b['path'])/'state.bundle';row=next(x for x in receipt['members']if x['path']==str(original));BASE.require(row['sha256']==a['bundle_sha256'],'entire candidate payload matches verified reference seal')
   wanted[row['member']]=(Path(a['path'])/'state.bundle',row)
 archive=Path(receipt['archive']);before=H.reader.identity(archive.stat());proc=subprocess.Popen(['zstd','-dc',str(archive)],stdout=subprocess.PIPE);verified=[]
 try:
  with tarfile.open(fileobj=proc.stdout,mode='r|')as tar:
   for member in tar:
    check();BASE.require(member.isfile()and member.name in by_member,'known plain archived state member')
    if member.name not in wanted:continue
    p,row=wanted.pop(member.name);BASE.require(member.size==row['bytes']==p.stat().st_size,'actual archived/candidate full extent');identity=H.reader.identity(p.stat());h=hashlib.sha256();compared=0
    with p.open('rb')as actual:
     f=tar.extractfile(member)
     for b in iter(lambda:f.read(1024**2),b''):
      check();BASE.require(actual.read(len(b))==b,'actual archive/candidate entire payload differs');h.update(b);compared+=len(b)
     BASE.require(not actual.read(1),'no extra candidate payload')
    BASE.require(h.hexdigest()==row['sha256']and H.reader.identity(p.stat())==identity,'reference archive actual SHA and candidate stable identity');verified.append(dict(member=member.name,actual_candidate=str(p),bytes=compared,sha256=h.hexdigest()));count+=compared
  BASE.require(not wanted,'every candidate final payload compared exactly once')
 finally:
  proc.stdout.close();rc=proc.wait()
 BASE.require(rc==0 and before==H.reader.identity(archive.stat()),'stable archive full stream completed')
 return dict(passed=True,bytes_compared=count,members=verified,scope='Actual selected whole bundles streamed against previously sealed/verified diagnostic archive; all14 final payloads compared, no exclusions or synthesized state.')

def validate_generation(result,prompt,eos):
 tokens=result['tokens'];BASE.require(1<=len(tokens)<=512 and all(type(x)is int and 0<=x<248320 for x in tokens),'actual bounded generated output IDs')
 BASE.require(len(tokens)==512 or tokens[-1]in eos,'short natural generation must end at EOS')
 BASE.require(not any(x in eos for x in tokens[:-1]),'no generation beyond firstEOS')
 BASE.require(result['stats']['guesses']==0 and all(x['speculative']is False for x in result['rank_trace']),'target-only no proposals/speculation')
 for rank in (0,1):BASE.require([x['position']for x in result['rank_trace']if x['rank']==rank and x['op']==1]==list(range(len(prompt)+len(tokens)-1)),'every actual prompt and generated continuation HALF position')

def run_native(a,t,prompt,count,eos):
 before=list(t.seq);result=a.NativeController(t,a.BASE.Draft('none'),False,False,prefill=0,start=0).run(prompt,count,eos)
 BASE.require(list(t.seq)==[x+1 for x in before]and not any(t.pending),'one completed actual native-controller outer command per rank')
 BASE.require(not any((t.request_output/f'rank{rank}/router-tie-diagnostic.jsonl').exists()for rank in (0,1)),'host diagnostic remains OFF throughout')
 return result

def request(a,t,plan,began):
 BASE.require(t.out==Path(plan['output'])/'native','existing metadata authority')
 BASE.require(shutil.disk_usage(t.out).free>=plan['evidence_floor_bytes']+plan['evidence_forecast_bytes'],'bounded fiveGiB evidence plus actual unchanged floor')
 H.install_sequence_audit(t,Path(plan['output'])/'outer-wire-sequences.jsonl');baseline=H.cold(a,t);BASE.save(Path(plan['output'])/'cold-initial.json',baseline)
 records=[];resets=[]
 def reset_cold(dest):
  maintenance=H.reset(a,t,dest);actual=H.cold(a,t,baseline);maintenance['cold_duplicate_cleanup']=drop_duplicate_cold(actual,baseline);BASE.save(dest/'cold-proof.json',actual);maintenance['cold_proof']=str(dest/'cold-proof.json');resets.append(maintenance)
  if len(resets)>1:
   for rank in ('0','1'):BASE.require(maintenance['receipts'][rank]['value']==resets[0]['receipts'][rank]['value'],'stable actual reset allocation receipt')
  return maintenance
 for i,row in enumerate(H.cases()):
  maintenance=reset_cold(t.out/f'phase-a-{i:02d}')if i else None
  result=run_native(a,t,row['prompt'],1,())
  H.validate_trace(result,len(row['prompt']),a);BASE.require(not any((t.request_output/f'rank{rank}/router-tie-diagnostic.jsonl').exists()for rank in (0,1)),'host tie diagnostic must stay OFF')
  record=dict(id=row['id'],actual_output_ids=result['tokens'],result=result,layer_captures=H.layers(t,plan),full_state=H.dump(a,t,len(row['prompt'])),reset=maintenance)
  records.append(record);BASE.save(Path(plan['output'])/f'phase-a-{i:02d}.json',record)
 receipt=json.loads((REFERENCE/'archive.json').read_text());BASE.require(list(H.reader.identity(Path(receipt['archive']).stat()))==plan['reference_archive_stat'],'registered immutable diagnostic archive stat')
 reference=json.loads(gzip.decompress((REFERENCE/'output-result.json.gz').read_bytes()))
 try:proof=compare_archive(records,reference,receipt,t.check)
 except BaseException as error:
  BASE.save(Path(plan['output'])/'phase-a-diagnostic-parity.json',dict(passed=False,error=repr(error),actual_records=len(records),phase_B_started=False));raise
 BASE.save(Path(plan['output'])/'phase-a-diagnostic-parity.json',proof)
 generated=[]
 BASE.require(proof.get("passed")is True,"PhaseA full archive parity required before optional PhaseB/finish")
 for i,row in enumerate(suite()if phase_b_enabled(plan)else []):
  maintenance=reset_cold(t.out/f'phase-b-{i:02d}');prompt=row['prompt']
  result=run_native(a,t,prompt,512,plan['eos_token_ids']);validate_generation(result,prompt,plan['eos_token_ids'])
  record=dict(id=row['id'],prompt_tokens=prompt,prompt_source=row['path'],prompt_source_sha256=row['sha256'],actual_output_ids=result['tokens'],max_new=512,eos_token_ids=plan['eos_token_ids'],cached_tokens=0,prompt_state_reused=False,cold_reset=maintenance,result=result,independent_cpu_teacherforce='pending actual generated-token continuation check; no runtime expected tokens')
  BASE.save(Path(plan['output'])/f'phase-b-{i:02d}.json',record);generated.append(record)
 return dict(schema='ownrt.gpu-route-seven-plus-twelve-result.v1',phase_A_records=records,phase_A_full_diagnostic_parity=proof,phase_B_records=generated,phase_B_skipped=not phase_b_enabled(plan),cold_resets=resets,phase_B_independent_cpu_fidelity='pending'if phase_b_enabled(plan)else 'not run',limits='One owner lifetime; no restart/retry. PhaseA compares actual frozen historical outputs/state; PhaseB fresh greedy generation for all12 fixed prompts when enabled; otherwise explicitly skipped. No runtime oracle or quality claim for generated continuations before independentCPU check.')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--run',action='store_true');ap.add_argument('--admission',type=Path);ap.add_argument('--unit');x=ap.parse_args()
 if not x.run:BASE.save(x.plan,make_plan(x.config));return
 p=json.loads(x.plan.read_text());BASE.require(p==make_plan(p['config']),'exact current candidate/source plan');ad=json.loads(x.admission.read_text());BASE.require(ad['plan_sha256']==BASE.digest(x.plan),'admission plan SHA');C.execute(p,ad,x.unit,request=request)
if __name__=='__main__':main()
