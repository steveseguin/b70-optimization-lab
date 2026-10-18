#!/usr/bin/env python3
"""Recheck archived cancellation standalone state without rerunning CPU models."""
import argparse,base64,gzip,hashlib,json
from pathlib import Path
from storage import digest,admit
P=Path(__file__).resolve().parent

def inventories(path):
 rows={};selected=None;data=bytearray()
 with gzip.open(path,'rt') as stream:
  assert json.loads(next(stream))=={'schema':'packet38.scratch-stream.v1'}
  for line in stream:
   row=json.loads(line)
   if row['kind']=='file':
    selected=row if row['path'].endswith('/request-state-inventory.json') else None
    data=bytearray()
   elif row['kind']=='chunk' and selected:data.extend(base64.b64decode(row['base64'],validate=True))
   elif row['kind']=='end' and selected:
    assert len(data)==selected['bytes'] and hashlib.sha256(data).hexdigest()==selected['sha256']
    rank=Path(selected['path']).parent.name;assert rank in ('rank0','rank1') and rank not in rows
    model=json.loads(data);event=model.pop('logical_event')
    rows[rank]=dict(model=model,logical_event=event,raw_sha256=selected['sha256'])
    selected=None
 assert set(rows)=={'rank0','rank1'}
 return rows

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--case',action='append',required=True,help='packet receipt name:archive prefix without -reference.jsonl.gz')
 ap.add_argument('--output',default='cancellation-inventory-gates.json')
 a=ap.parse_args();cases=[];errors=[]
 for spec in a.case:
  receipt_name,prefix=spec.split(':',1)
  assert Path(receipt_name).name==receipt_name and Path(prefix).name==prefix
  receipt=json.loads((P/receipt_name).read_text());assert receipt['passed']
  reference=P/'evidence'/(prefix+'-reference.jsonl.gz');baseline=inventories(reference)
  rows=[]
  for cut in receipt['rows']:
   archive=P/'evidence'/(prefix+'-cut-'+str(cut['launch_boundary'])+'.jsonl.gz')
   actual=inventories(archive)
   differences={rank:[key for key in sorted(baseline[rank]['model'].keys()|actual[rank]['model'].keys()) if baseline[rank]['model'].get(key)!=actual[rank]['model'].get(key)] for rank in baseline}
   differences={rank:keys for rank,keys in differences.items() if keys}
   if differences:errors.append(dict(case=receipt_name,cut=cut['launch_boundary'],differences=differences))
   rows.append(dict(launch_boundary=cut['launch_boundary'],passed=not differences,archive=str(archive.relative_to(P)),archive_sha256=digest(archive),raw_inventory={rank:{k:v for k,v in values.items() if k!='model'} for rank,values in actual.items()}))
  cases.append(dict(receipt=receipt_name,receipt_sha256=digest(P/receipt_name),binary_sha256=receipt['binary_sha256'],controller=receipt['controller'],real_model=receipt['real_model'],reference_archive=str(reference.relative_to(P)),reference_archive_sha256=digest(reference),reference_inventory=baseline,rows=rows))
 result=dict(passed=not errors,device_executed=False,cases=cases,errors=errors,gate_count=sum(len(case['rows']) for case in cases),normalization='Only logical_event excluded; raw inventory hashes and counters retained; every other standalone mutable and host-state field must match',source_sha256={Path(__file__).name:digest(Path(__file__))})
 admit(1000000);(P/a.output).write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(dict(passed=not errors,cases=len(cases),gates=result['gate_count'],errors=errors)),flush=True)
 raise SystemExit(bool(errors))
if __name__=='__main__':main()
