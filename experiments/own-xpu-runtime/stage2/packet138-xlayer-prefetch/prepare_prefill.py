"""Retain historical non-speculative packet55 prefill for cache initialization.

Never reuse rejected speculative decode visits. These are cache simulation inputs,
not new packet138 device captures or a one-card measured cache hit rate.
"""
import gzip,hashlib,importlib.util,json,resource
from pathlib import Path
from router_replay import P,ROOT,sha,save
S=P.parent/'packet55-feasibility/route';WINDOW=S/'evidence/cards23-a'

def main():
 from build_engine import limits
 limits();manifest=json.loads((P/'suite.snapshot.json').read_text());window=json.loads((WINDOW/'window.json').read_text())
 assert window['passed'] and window['device_executed']
 conversion_path=WINDOW/'routes.jsonl.gz.json';conversion=json.loads(conversion_path.read_text());assert conversion['passed']
 assert sha(WINDOW/'window.json')==conversion['window_sha256'] and sha(WINDOW/'calibration-manifest.json')==conversion['manifest_sha256']
 originals={e['prompt_id']:e for e in json.loads((WINDOW/'calibration-manifest.json').read_text())['prompts']}
 spec=importlib.util.spec_from_file_location('p138_p55convert',S/'convert.py');convert=importlib.util.module_from_spec(spec);spec.loader.exec_module(convert)
 pins={str(f.relative_to(ROOT)):sha(f) for f in (S/'convert.py',conversion_path,WINDOW/'window.json',WINDOW/'calibration-manifest.json')}
 prompts={}
 for e in manifest['prompts']:
  if not e['analysis_included']:continue
  old=originals[e['prompt_id']];assert old['tokens']==list(map(int,(ROOT/e['input_bundle']/'tokens.txt').read_text().split()))
  summary=next(x for x in conversion['requests'] if x['prompt_id']==e['prompt_id'])
  directory=WINDOW/'requests'/e['prompt_id'];assert sha(directory/'result.json')==summary['result_sha256']==e['reference_sha256']
  n=e['prompt_tokens']-1;positions=[[None]*48 for _ in range(n)]
  for rank in (0,1):
   binary=directory/f'rank{rank}/routes.p55bin';assert sha(binary)==summary['binary_sha256'][str(rank)];pins[str(binary.relative_to(ROOT))]=sha(binary)
   for row in convert.read_records(binary,rank,old):
    if row['role']!='target' or row['phase']!='prefill':continue
    assert not row['speculative'] and row['fixture']==0
    pos,layer=row['position'],row['layer'];assert 0<=pos<n and positions[pos][layer] is None
    positions[pos][layer]=row['ids']
  assert all(all(row is not None for row in token) for token in positions),'missing prefill layer'
  prompts[e['prompt_id']]=positions
 raw=json.dumps(dict(schema='packet138.historical-prefill.v1',passed=True,prompts=prompts,sources=pins,
  caveat='Prior two-card packet55 target prefill, no speculation; paired with exact saved target prefix. Cache proxy only.'),separators=(',',':')).encode()
 out=P/'evidence/prefill-inputs.json.gz';out.write_bytes(gzip.compress(raw,mtime=0))
 save(P/'evidence/prefill-binding.json',dict(passed=True,device_executed=False,source_capture='historical_packet55',
  prompts=len(prompts),positions=sum(map(len,prompts.values())),layers=48,sha256=sha(out),sources=pins))
 print('Historical prefill pinned:',len(prompts),'prompts;',sum(map(len,prompts.values())),'positions')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
