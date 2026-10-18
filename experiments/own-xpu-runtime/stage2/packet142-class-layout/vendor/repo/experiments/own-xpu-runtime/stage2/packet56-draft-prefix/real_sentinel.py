#!/usr/bin/env python3
"""One fresh 4096/dr0 CPU real-model sentinel for the fixture-only delta."""
import json,os,fcntl,resource
from cpu_merged_gate import Campaign,P,B,ROOT,hash_file
from storage import discard
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 resource.setrlimit(resource.RLIMIT_AS,(8_000_000_000,8_000_000_000))
 manifest=P.parent/'suite-inputs-20261012-cap128/suite-manifest.json';entry=json.loads(manifest.read_text())['prompts'][0]
 bundle=ROOT/entry['input_bundle'];oracle=ROOT/entry['oracle_directory']
 for n,h in entry['input_bundle_hashes'].items():assert hash_file(bundle/n)==h
 assert hash_file(oracle/'receipt.json')==entry['oracle_receipt_sha256']
 expected=json.loads((oracle/'result.json').read_text())['tokens'][:8]
 with (B/'cpu-merged-gate.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  c=Campaign(B/'gnu-host/own-rt-iq3',P/'dispatch-p45.json',P/'cpu-real-sentinel.json',anonymous_limit=9_000_000_000)
  try:
   out,row=c.case('real-c4096-r0-native',4096,0,'native',real=dict(input=bundle))
   signature=row['signature'];assert signature['tokens']==expected
   assert len(signature['fixtures'])==384 and all(h==hash_file(oracle/n) for n,h in signature['fixtures'].items())
   row.update(oracle_subset_tokens=8,oracle_layer_fixtures=384,prompt_id=entry['prompt_id'],manifest_sha256=hash_file(manifest),oracle_receipt_sha256=hash_file(oracle/'receipt.json'),oracle_result_sha256=hash_file(oracle/'result.json'))
   c.retain(out,row);c.completed=True;result=c.seal();assert result['passed'] and result['cases']==1
   result['runner_sha256']=hash_file(P/'real_sentinel.py');(P/'cpu-real-sentinel.json').write_text(json.dumps(result,indent=2)+'\n');discard(c.root)
   print(json.dumps(dict(passed=True,cases=1,token_matches=8,layer_matches=384)),flush=True)
  except BaseException as error:
   c.campaign_error=str(error);c.seal();raise
if __name__=='__main__':main()
