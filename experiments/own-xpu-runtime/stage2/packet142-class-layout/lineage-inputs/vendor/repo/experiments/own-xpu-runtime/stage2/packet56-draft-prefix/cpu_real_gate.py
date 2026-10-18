#!/usr/bin/env python3
"""Six sequential native CPU first-eight-token oracle checks; no speed claim."""
import fcntl,json,os,resource
from pathlib import Path
from cpu_merged_gate import Campaign,CONTEXTS,P,B,ROOT,hash_file
from storage import discard

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 resource.setrlimit(resource.RLIMIT_AS,(8_000_000_000,8_000_000_000))
 manifest=P.parent/'suite-inputs-20261012-cap128/suite-manifest.json'
 data=json.loads(manifest.read_text());entry=data['prompts'][0]
 assert entry['prompt_id']=='incident-retrospective'
 bundle=ROOT/entry['input_bundle'];oracle=ROOT/entry['oracle_directory']
 for name,digest in entry['input_bundle_hashes'].items():assert hash_file(bundle/name)==digest
 assert hash_file(oracle/'receipt.json')==entry['oracle_receipt_sha256']
 expected=json.loads((oracle/'result.json').read_text())['tokens'][:8]
 with (B/'cpu-merged-gate.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  c=Campaign(B/'gnu-host/own-rt-iq3',P/'dispatch-p45.json',P/'cpu-real-gates.json',anonymous_limit=9_000_000_000)
  try:
   for context in (32768,4096,256):
    for rank in (1,0):
     out,row=c.case(f'real-c{context}-r{rank}-native',context,rank,'native',real=dict(input=bundle))
     signature=row['signature'];assert signature['tokens']==expected,'real token oracle mismatch'
     assert len(signature['fixtures'])==384
     assert all(digest==hash_file(oracle/name) for name,digest in signature['fixtures'].items()),'real layer bytes differ'
     row.update(oracle_subset_tokens=8,oracle_layer_fixtures=384,prompt_id=entry['prompt_id'],
       manifest_sha256=hash_file(manifest),oracle_receipt_sha256=hash_file(oracle/'receipt.json'),
       oracle_result_sha256=hash_file(oracle/'result.json'),realistic_final_gate=dict(passed=False,reason='first eight tokens of one fixed suite prompt; correctness only'))
     c.retain(out,row)
  except BaseException as error:
   c.campaign_error=str(error)
   for scratch in list(c.root.iterdir()):
    if scratch.is_dir():c.retain(scratch,dict(name=scratch.name,passed=False,error=str(error)))
   c.seal();raise
  c.completed=True
  result=c.seal();assert result['passed'] and result['cases']==6
  discard(c.root);print(json.dumps(dict(passed=True,cases=6,token_matches=48,layer_matches=2304)),flush=True)
if __name__=='__main__':main()
