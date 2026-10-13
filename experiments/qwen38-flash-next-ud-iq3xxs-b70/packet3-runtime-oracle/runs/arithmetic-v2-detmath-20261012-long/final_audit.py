"""Audit final long-oracle evidence without starting a numerical process."""
import gzip,hashlib,json
from pathlib import Path
import long_run as m
H,I=m.HERE,m.INPUTS

def main():
 build=m.preflight();manifest=m.read(I/'suite-manifest.json')
 assert manifest['complete'] and manifest['context']==4096 and manifest['token_cap']==32
 assert manifest['cpu_accounting_complete']
 assert m.base.equality(H/'capacity-incident')==m.read(H/'capacity-incident/equality-proof.json')
 proof=m.read(H/'resume-equality-proof.json');assert proof['passed'] and proof['tokens']==8 and proof['generated_tokens_after_decode_resume']==4
 for label,key in (('capacity-incident','uninterrupted_receipt_sha256'),('resume-incident','resumed_receipt_sha256')):
  assert m.sha(H/label/'receipt.json')==proof[key]
  r=m.read(H/label/'receipt.json');assert r['binary_sha256']==build['binary_sha256'] and r['result_sha256']==m.sha(H/label/'result.json')
 for name,digest in proof['fixture_hashes'].items():
  assert m.sha(H/'capacity-incident'/name)==m.sha(H/'resume-incident'/name)==digest
 for name,digest in proof['midprompt_hashes'].items():
  assert m.sha(H/'capacity-incident'/name)==m.sha(H/'resume-incident'/name)==digest
 tests=m.read(H/'checker-tests.json');reports=[]
 checker=m.module('final_checker',H/'suite_check.py')
 for e in manifest['prompts']:
  label=e['prompt_id'];d=H/label;bundle=I/label;r=m.read(d/'receipt.json')
  assert e['oracle_receipt_sha256']==m.sha(d/'receipt.json')
  assert r['binary_sha256']==build['binary_sha256'] and r['result_sha256']==m.sha(d/'result.json')
  assert r['validation_sha256']==m.sha(d/'validation.json')
  assert r['log_retention_sha256']==m.sha(d/'log-retention.json')
  assert m.validate(d,bundle,32)==m.read(d/'validation.json')
  assert checker.check_prompt(d,d,e)==(32,384)
  assert len(tests[label])==7 and all(t['passed'] for t in tests[label])
  for name,digest in e['input_bundle_hashes'].items():assert m.sha(bundle/name)==digest
  segments=[];a=r
  while a:
   assert a['binary_sha256']==build['binary_sha256'] and a['nice']==19 and a['ionice']=='idle' and a['OMP_NUM_THREADS']==2
   assert a['affinity']==m.read(H/'host-contract.json')['affinity']
   assert m.timing_complete(a) and a['returncode']==0
   snapshot=H/'runner-snapshots'/(a['campaign_sources_sha256']+'.json')
   assert snapshot.exists() and m.sha(snapshot)==a['campaign_sources_sha256']
   segments.append(a);a=a.get('prior_attempt')
  assert len(segments)==e['execution_segments']
  restored=0;files=0
  ledgers=[m.read(d/'log-retention.json'),m.read(d/'resume-archives.json')]
  for ledger in ledgers:
   for name,meta in ledger.items():
    if 'compressed_sha256' in meta:
     p=d/(name+'.gz');assert m.sha(p)==meta['compressed_sha256']
     with gzip.open(p,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==meta['sha256']
     restored+=meta['bytes'];files+=1
    else:assert m.sha(d/name)==meta['sha256']
  meta=m.read(d/'teardown-retention.json');assert m.sha(d/'teardown.json.gz')==meta['compressed_sha256']
  with gzip.open(d/'teardown.json.gz','rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==meta['sha256']
  reports.append(dict(prompt_id=label,receipt_sha256=m.sha(d/'receipt.json'),generated_tokens=32,fixtures=384,midprompt_positions=e['midprompt_positions'],segments=len(segments),peak_anonymous_bytes=max(a['peak_anonymous_bytes'] for a in segments),compressed_files_verified=files+1,restored_bytes_verified=restored+meta['bytes'],elapsed_seconds=e['elapsed_seconds'],cpu_seconds=e['cpu_seconds']))
 out=dict(passed=True,checked_utc=m.utc(),numerical_oracle_executed=False,binary_sha256=build['binary_sha256'],manifest_sha256=m.sha(I/'suite-manifest.json'),capacity_gate=True,prefill_and_decode_resume_gate=True,corruption_tests=12,self_comparisons=2,cpu_accounting_complete=True,runs=reports,remaining_own_oracle_processes=[p['pid'] for p in m.base.oracle_processes() if Path(p['args'][0].decode())==H/'build/oracle'])
 assert not out['remaining_own_oracle_processes'];m.save(H/'final-audit.json',out);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
