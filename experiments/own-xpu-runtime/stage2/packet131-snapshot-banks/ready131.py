"""Admit only the completed CPU packet; never execute or authorize a device."""
import json
from build131 import P,ROOT,sha,save,cpu_main,limits
def main():
 sources={}
 reports=['census131.json','state131.json','mini131.json','recurrence131.json','reset-regression.json','startup131.json','python131.json','extended-queue131.json','inherited-gate131.json','oracle131.json','arguments131.json','launch-limits.json','queue131.json']
 for name in reports:
  f=P/'evidence'/name;r=json.loads(f.read_text());assert r['passed'] and not r.get('device_executed',False),name
  sources[str(f.relative_to(ROOT))]=sha(f)
  for path,h in r['sources'].items():
   assert sha(ROOT/path)==h,'stale gate: '+path
   sources[path]=h
 from bootstrap import install
 install()
 from common import sealed
 from types import SimpleNamespace
 for label in ('control','candidate'):
  v=P/'selections'/label
  sealed(SimpleNamespace(lineage=v,seal=v/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='1'))
  for leaf in ('screen-seal.json','build-receipt.json','byte-fixture.json','selection.json'):
   sources[str((v/leaf).relative_to(ROOT))]=sha(v/leaf)
 for f in P.glob('*.py'):sources[str(f.relative_to(ROOT))]=sha(f)
 limits()
 save(P/'evidence/ready131.json',dict(passed=True,device_executed=False,device_results_pending=True,sources=sources,reports=reports))
 print('CPU gates and two seals verified; device smoke/grid remain pending')
if __name__=='__main__':cpu_main();main()
