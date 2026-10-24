"""Fixed verified-prefix and recovered-storage admission; no device operations."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent;CANDIDATE=P.parent;L=CANDIDATE.parent;R=L.parents[2]
PRIOR=CANDIDATE/'operating/evidence/partial-independent-a/review.json'
PRIOR_SHA='663fb5e463b6e9ee6b45f6e55562394522f1f30f593ef5003991ba51c2e887cf'
BINARY_SHA='e83469b3a2c1781d6be6241f4c1cd0967379f15ca410c6aed55baf0831b8ac68'
STORAGE=L/'storage/evidence/complete.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,m):
 if not v:raise ValueError(m)
def verify_materialization():
 p=json.loads((P/'preparation.json').read_text());require(sha(P/'prepare.py')==p['recipe_sha256'] and sha(P/'overlay.patch')==p['patch_sha256'],'completion recipe')
 for n,h in {**p['source_sha256'],**p['generated_sha256']}.items():require(sha(n)==h,'completion source '+n)
def prerequisites(binary):
 verify_materialization();require(binary==BINARY_SHA and sha(PRIOR)==PRIOR_SHA,'exact candidate binary and partial audit')
 r=json.loads(PRIOR.read_text());require(r['audit_passed'] and not r['passed'] and r['incomplete'] and r['verified_prior_arms']==14 and r['verified_prompt_indices']==list(range(7)),'verified prefix only')
 require(r['native_binary_sha256']==binary and r['children_exited_and_physical_drain_attested'] and not r['new_classified_gpu_fault'],'prefix binary/drain/fault identity')
 expected={f'prompt-{i:02d}-{mode}' for i in range(7) for mode in ('none','mtp')}
 require({a['name'] for a in r['arms']}==expected and all(a['baseline_tokens_exact'] and a['baseline_state_exact'] for a in r['arms']),'prefix exact arms')
 manifest=json.loads((P/'manifest.json').read_text());require(manifest['prompt_indices']==list(range(7,12)) and manifest['requests']==12 and manifest['state_dumps']==13,'fixed completion subset')
 require(manifest['partial_review_sha256']==PRIOR_SHA and manifest['candidate_binary_sha256']==binary and sha(STORAGE)==manifest['storage_complete_sha256'],'completion authority')
 original=L/'baseline/manifest.json';require(sha(original)==manifest['baseline_manifest_sha256'],'original corpus manifest')
 baseline=json.loads(original.read_text());require(manifest['prompts']==[{'index':i,**baseline['prompts'][i]} for i in range(7,12)] and manifest['warmup']==baseline['warmup'],'unaltered selected prompts/order/warmups')
 storage=json.loads(STORAGE.read_text());require(storage['passed'] and len(storage['batches'])==27 and sum(b['removed_files'] for b in storage['batches'])==57045,'observed released file records')
 require(manifest['forecast_bin_files']==13*2113 and manifest['forecast_bin_files']+manifest['metadata_file_allowance']<57045,'bounded file-count forecast')
 return r
