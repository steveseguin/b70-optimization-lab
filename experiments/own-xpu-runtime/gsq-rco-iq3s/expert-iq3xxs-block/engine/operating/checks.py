"""Immutable baseline authority and per-arm exact gate; no runtime imports."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;CANDIDATE=P.parent;L=P.parents[2];R=L.parents[2]
ATTENTION=L/'attention-q8-p33';QKV=L/'qkv-q6-p33'
REVIEW=L/'baseline/evidence/independent-a/review.json'
REVIEW_SHA='f662fcecf93c92f90006c09c05d4a4c02e71e84ae9d8c82dbff3fdfc39ebb5bb'
REFERENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a/resident-suite.json')
REFERENCE_SHA=json.loads(REVIEW.read_text())['full_result_sha256'] if hashlib.sha256(REVIEW.read_bytes()).hexdigest()==REVIEW_SHA else None
REFERENCES={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,msg):
 if not v:raise ValueError(msg)
def read(p):
 p=Path(p);require(p.is_file() and not p.is_symlink() and p.stat().st_size<64*1024**2,'bounded regular JSON');return json.loads(p.read_text())
def verify_materialization():
 prep=read(P/'preparation.json');require(sha(P/'prepare.py')==prep['recipe_sha256'] and sha(P/'overlay.patch')==prep['patch_sha256'],'materialization recipe/patch')
 for name,h in {**prep['source_sha256'],**prep['generated_sha256']}.items():require(sha(R/name)==h,'materialized source '+name)
 ledger=read(P/'candidate-ledger.json');require(ledger['parent_sha256']==sha(L/'memory/engine-accounting.json'),'ledger authority')
 old=read(L/'memory/engine-accounting.json')['scenarios']['split24-24_mtp-rank0']['ranks'];new=ledger['scenarios']['split24-24_mtp-rank0']['ranks']
 require(len(new)==2 and ledger['initial_mem_available_delta_bytes']==382730240,'candidate ledger ranks/delta')
 for a,b,q6 in zip(old,new,(183500800,104857600)):
  require(b['device_logical_bytes']==a['device_logical_bytes']+47185920+q6 and b['expanded_q8_delta_bytes']==47185920 and b['expanded_q6_delta_bytes']==q6,'exact allocation delta')
 for name,h in read(P/'authority.json').items():require(sha(name)==h,'combined frozen authority '+name)
def baseline():
 require(sha(REVIEW)==REVIEW_SHA and REFERENCE_SHA is not None,'independent baseline review changed');r=read(REVIEW)
 require(r['passed'] and r['all12_exact'] and r['requests']==26 and r['kernel_fault_baseline_unchanged'] and r['source_and_binary_pins_verified'],'complete audited baseline')
 require(sha(REFERENCE)==REFERENCE_SHA,'baseline full result changed');f=read(REFERENCE)
 require(f['passed'] and len(f['prompts'])==12,'baseline complete corpus');refs={}
 for p,audited in zip(f['prompts'],r['prompts']):
  require(p['prompt_id']==audited['prompt_id'] and p['exact_tokens'] and p['exact_final_target_state'],'baseline pair')
  for arm in p['arms']:
   ar=next(x for x in audited['arms'] if x['mode']==arm['mode']);require(ar['tokens']==arm['result']['tokens'],'audited tokens');require(arm['measured'] and arm['requested_max_new']==128,'baseline arm')
   require(arm['name'] not in refs,'duplicate arm');refs[arm['name']]=arm
 require(len(refs)==24,'baseline24 arms');return refs
def prerequisites(binary_sha):
 verify_materialization();baseline()
 build=CANDIDATE/'evidence/native-build.json';b=read(build)
 require(b['passed'] is True and b['mode']=='native' and b['binary_sha256']==binary_sha and sha(b['binary'])==binary_sha,'candidate native build')
 # Root's independent source/build review is a concrete prerequisite, never a
 # boolean supplied by the launch plan. Every bound source must remain exact.
 review=P/'evidence/independent-review.json';v=read(review);require(v['passed'] is True and v.get('source_sha256'),'independent candidate operation review')
 for name,h in v['source_sha256'].items():require(sha(R/name)==h,'review source '+name)
 cpu=CANDIDATE/'evidence/cpu-proof.json';c=read(cpu);require(c['passed'] is True and c.get('source_sha256'),'candidate CPU arithmetic proof')
 for name,h in c['source_sha256'].items():require(sha(R/name)==h,'CPU proof source '+name)
 scale_authority();qkv_authority()
 return REVIEW
def scale_authority():
 scale=read(ATTENTION/'evidence/scale-census.json')
 require(scale['passed'] is True and scale['all_scales_finite'] is True and len(scale['tensors'])==48,'actual48 scale census')
 expected={f'blk.{i}.'+('attn_output.weight' if i%4==3 else 'ssm_out.weight') for i in range(48)}
 require({x['weight'] for x in scale['tensors']}==expected and scale['totals']['infinity']==scale['totals']['nan']==0,'selected finite scale census')
 require(scale['preparation_sha256']==sha(ATTENTION/'preparation.json'),'scale preparation')
 require(sha(ATTENTION/'scale_census.py')==scale['source_sha256'],'scale source')
 return scale
def qkv_authority():
 cpu=read(QKV/'evidence/cpu-proof.json');micro=read(QKV/'micro/evidence/device-a/review.json')
 require(cpu['passed'] is True and micro['passed'] is True and micro['exact_pairs']==84 and micro['safe_native_teardown'] and micro['physical_drain'],'Q6 arithmetic and actual micro')
 return micro
def bind_references(plan):
 global REFERENCES
 require(plan['baseline_review_sha256']==REVIEW_SHA and plan['baseline_result_sha256']==REFERENCE_SHA,'plan baseline authority')
 REFERENCES=baseline()
def check_arm(row):
 require(row['name'] in REFERENCES,'unexpected candidate arm');ref=REFERENCES[row['name']]
 require(row['mode']==ref['mode'] and row['prompt_tokens']==ref['prompt_tokens'] and row['requested_max_new']==128,'candidate request identity')
 require(row['result']['tokens']==ref['result']['tokens'],'candidate tokens differ from baseline: '+row['name'])
 require(row['state_sha256']==ref['state_sha256'],'candidate target state differs from baseline: '+row['name'])

def bundle_and_micro_authority():
 bundle=read(L/'state-bundle/evidence/device-a/review.json')
 require(bundle['passed'] is True,'qualified current bundle prerequisite')
 micro=read(CANDIDATE.parent/'micro/evidence/device-a/review.json')
 require(micro['audit_passed'] and micro['native_kernel_result_passed'] and micro['exact_pairs']==84 and micro['kernel_submissions']==168,'micro numerical evidence')
 require(not micro['qualification_complete'] and not micro['coordinator_passed'] and micro['observed_contact_samples']==0,'retain micro physical-attestation failure')
 return micro

def capture_stamp(destination):
 out={}
 for rank in (0,1):
  path=Path(destination)/f'rank{rank}/state-2147483647'
  require(path.is_dir() and not path.is_symlink(),'capture directory')
  rows={}
  for f in sorted(path.iterdir()):
   require(f.is_file() and not f.is_symlink(),'regular closed capture member')
   s=f.stat();rows[f.name]=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
  require(set(rows)=={'state.bundle','state-index.tsv','state-seal.txt','state.json'},'exact bundle inventory')
  out[str(rank)]=rows
 return out

def verify_capture_stamps(root,expected):
 for name,stamp in expected.items():require(capture_stamp(Path(root)/name)==stamp,'sealed capture changed after RESET/FINISH: '+name)
