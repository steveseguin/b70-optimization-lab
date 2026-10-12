"""Read exact site logs; separate QSA work from other CPU-oracle overhead."""
import argparse,gzip,hashlib,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def summarize(d):
 receipt=json.loads((d/'receipt.json').read_text());result=json.loads((d/'result.json').read_text())
 assert receipt['verified'] and sha(d/'result.json')==receipt['result_sha256']
 assert not receipt['resumed'],'Per-position attribution for interrupted attempts is intentionally not inferred.'
 ledger=json.loads((d/'log-retention.json').read_text());positions=[json.loads(s) for s in (d/'positions.jsonl').read_text().splitlines()]
 files=[]
 for name,info in ledger.items():
  if not name.startswith('timings.jsonl'):continue
  p=d/(name+'.gz');assert sha(p)==info['compressed_sha256']
  match=re.match(r'timings\.jsonl\.segment-(\d+)-',name)
  end=int(match[1]) if match else result['next_position']
  assert match or '.segment-final-' in name
  files.append((end,name,info))
 records=[];raw_hashes={}
 for end,name,info in sorted(files):
  segment=[];current=None;digest=hashlib.sha256();size=0
  with gzip.open(d/(name+'.gz'),'rb') as f:
   for line in f:
    digest.update(line);size+=len(line);row=json.loads(line);label=row['label']
    if label=='begin.0':
     if current is not None:segment.append(current)
     current=dict(site_seconds=0.,qsa_pool_seconds=0.,qsa_select_seconds=0.,qsa_attention_seconds=0.,qsa_sites=0)
    assert current is not None
    seconds=row['wall_ms']/1000;current['site_seconds']+=seconds
    for suffix,key in (('.qsa.pool','qsa_pool_seconds'),('.qsa.select','qsa_select_seconds'),('.qsa.attention','qsa_attention_seconds')):
     if label.endswith(suffix):current[key]+=seconds;current['qsa_sites']+=1
  if current is not None:segment.append(current)
  assert digest.hexdigest()==info['sha256'] and size==info['bytes']
  start=end-len(segment);assert start==len(records)
  for index,row in enumerate(segment,start):
   assert row['qsa_sites']==36
   records.append(dict(position=index,**row,position_seconds=positions[index]['seconds']))
  raw_hashes[name]=info['sha256']
 assert len(records)==len(positions)
 bins=[]
 for lo,hi in ((0,100),(100,256),(256,512),(512,1024),(1024,1536),(1536,2048),(2048,2300),(2300,4096)):
  selected=[r for r in records if lo<=r['position']<hi]
  if selected:bins.append(dict(first_position=lo,last_position=min(hi-1,len(records)-1),positions=len(selected),**{k:sum(r[k] for r in selected)/len(selected) for k in ('position_seconds','site_seconds','qsa_pool_seconds','qsa_select_seconds','qsa_attention_seconds')}))
 result=dict(schema='iq3-long.site-cost-summary.v1',passed=True,oracle_receipt_sha256=sha(d/'receipt.json'),raw_log_hashes=raw_hashes,positions=len(records),bins=bins,
  caveat='Site wall time includes host dispatch/lookup overhead. Full position time also includes layer staging, capture and release; checkpoint writes are outside it. These are CPU oracle costs, not serving speed.')
 tmp=d/'site-cost-summary.json.tmp';tmp.write_text(json.dumps(result,indent=2)+'\n');assert json.loads(tmp.read_text())==result;tmp.rename(d/'site-cost-summary.json')
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();print(json.dumps(summarize(a.directory),indent=2))
