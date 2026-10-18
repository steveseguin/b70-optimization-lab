"""Pin packet-local sources and completed CPU evidence, never parent orchestration."""
import json
from build_engine import P,ROOT,sha,save,limits
def main():
 limits()
 for mode in ('gnu-host','intel-host','device'):
  r=json.loads((P/'evidence'/('build-'+mode+'.json')).read_text());assert r['passed'] and not r['device_executed']
  for group,base in [('sources',ROOT),('objects',ROOT),('artifacts',P)]:
   for n,h in r[group].items():assert sha(base/n)==h,n
 leaf=json.loads((P/'evidence/cpu-leaf.json').read_text());assert leaf['qsa_passed'] and not leaf['gdn_passed']
 assert json.loads((P/'evidence/cpu-layers.json').read_text())['passed']
 files={}
 for f in P.rglob('*'):
  n=f.relative_to(P)
  if not f.is_file() or n.parts[0] in ('build','__pycache__','.git') or n.name=='seal.json':continue
  if n.parts[0]=='evidence' and (len(n.parts)>1 and n.parts[1].startswith(('micro-B-','plan','queue-plan','qualification','seal'))):continue
  files[str(n)]=sha(f)
 save(P/'seal.json',dict(schema='packet107.cpu-preparation.v1',passed=True,device_executed=False,admitted_layers=[3],closed_layers={'4':'Intel NaN-payload mismatch'},files=files,runtime_inputs={str((P.parent/'packet34-replay-bench/directory.tsv').relative_to(ROOT)):sha(P.parent/'packet34-replay-bench/directory.tsv')}))
 print('sealed',len(files),'files; QSA only')
if __name__=='__main__':main()
