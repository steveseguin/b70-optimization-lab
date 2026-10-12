"""Run compiled CPU draft on immutable copies of packet31 confirmed inputs."""
import json,sys,subprocess,time,shutil,hashlib,os
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build';Q=P.parent/'packet31-mtp-acceptance'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare(name,retained=64):
 source=Q/'build'/name
 dest=B/('captured-'+name)
 if not source.exists() and dest.exists():
  receipt=json.loads((P/('capture-input-'+name+'.json')).read_text())
  table=B/('capture-'+name+'.tsv')
  assert sha(table)==receipt['table_sha256']
  assert sha(dest/'target-rows.json')==receipt['target_rows_sha256']
  assert all(sha(dest/f)==h for f,h in receipt['streams'].items())
  return table
 if not source.exists():source=B/'reference31/build'/name
 rows=[json.loads(s) for s in (source/'predictions.jsonl').read_text().splitlines()]
 input_path=Q/'build'/('input-'+name)/'input.json'
 if not input_path.exists():input_path=B/'reference31/build'/('input-'+name)/'input.json'
 inp=json.loads(input_path.read_text());n=len(inp['tokens']);assert len(rows)>=n+retained
 dest=B/('captured-'+name);dest.mkdir(exist_ok=True);table=[];hashes={}
 for j in range(n+retained-1):
  f=dest/f'streams-{j}.bf16';raw=(source/f.name).read_bytes();assert len(raw)==20480
  if f.exists():assert f.read_bytes()==raw
  else:f.write_bytes(raw)
  hashes[f.name]=sha(f);table.append(f"{j} {rows[j+1]['input_token']} {int(j>=n-2)} {f.resolve()}")
 tablefile=B/('capture-'+name+'.tsv');tablefile.write_text('\n'.join(table)+'\n')
 (dest/'target-rows.json').write_text(json.dumps(rows[:n+retained],indent=2)+'\n')
 (dest/'input.json').write_text(json.dumps(inp,indent=2)+'\n')
 (P/('capture-input-'+name+'.json')).write_text(json.dumps(dict(source=str(source),streams=hashes,table_sha256=sha(tablefile),target_rows_sha256=sha(dest/'target-rows.json')),indent=2)+'\n')
 return tablefile

def main(name):
 from storage import admit
 admit(120_000_000)
 import fcntl
 lock=(B/'cpu-mtp.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
 table=prepare(name);out=B/('draft-cpu-'+name+'-'+str(time.time_ns()));inp=json.loads((B/'input/input.json').read_text());binary=B/'gnu-host/own-rt-iq3'
 cmd=[str(binary),'--draft-capture',str(table),'--rank','1','--context','256','--plan',str(B/'input/plan.tsv'),'--identity',str(B/'input/identity.tsv'),'--model-dir',inp['model_dir'],'--output',str(out),'--dispatch',str(P/'dispatch-all-new.json')]
 with (B/('capture-'+name+'.log')).open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
 previous=P/('capture-run-'+name+'.json')
 old=json.loads(previous.read_text()) if previous.exists() else json.loads((P.parent/'packet36-draft'/previous.name).read_text())
 receipt=dict(previous=old,passed=r.returncode==0,binary_sha256=sha(binary),output=str(out),table_sha256=sha(table),device_executed=False)
 (P/('capture-run-'+name+'.json')).write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True);assert r.returncode==0
if __name__=='__main__':main(sys.argv[1])
