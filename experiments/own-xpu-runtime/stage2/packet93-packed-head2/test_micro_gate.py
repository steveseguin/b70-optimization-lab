import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import micro_gate
from micro_gate import analyze,CANDIDATES
def samples(ratio=.84):
 rows=[]
 for name in CANDIDATES:
  rows.append(dict(kind='correctness',view=name,rows=248320,columns=2560,fp32_exact=True,bf16_exact=True,argmax_exact=True))
  for rep in range(40):
   for pos in (0,1):
    candidate=bool(pos^(rep&1));rows.append(dict(kind='sample',pair=name,view=name if candidate else 'production',repeat=rep,position=pos,event_ns=1000*ratio if candidate else 1000,rows=248320,columns=2560,sg=32,wg=32,diagnostic_only=True))
 rows.append(dict(kind='summary',passed=True,drained=True,rows=248320,columns=2560,diagnostic_only=True));return rows
class Gate(unittest.TestCase):
 def test_reseal_requires_fresh_b2_and_rejects_changed_seal(self):
  with tempfile.TemporaryDirectory() as tmp:
   packet=Path(tmp);old=packet/'evidence/micro-B';old.mkdir(parents=True)
   (old/'qualification.json').write_text(json.dumps(dict(qualified=['head-transpose'])))
   historical=(old/'qualification.json').read_bytes()
   with self.assertRaisesRegex(ValueError,'micro-B2 qualification pending'):micro_gate.require_qualified(packet)
   directory=packet/micro_gate.MICRO_DIRECTORY;directory.mkdir()
   (packet/'build').mkdir();(packet/'build/microbench').write_bytes(b'test binary')
   (packet/'build-device-receipt.json').write_text('{}')
   (packet/'screen-jobs-seal.json').write_text('{}')
   (packet/'micro_gate.py').write_text('test gate identity')
   sample_path=directory/'samples.jsonl';sample_path.write_text(''.join(json.dumps(r)+'\n' for r in samples()))
   build=packet/'evidence/microbench-build.json'
   build.write_text(json.dumps(dict(passed=True,device_executed=False,sources={},artifacts={'build/microbench':micro_gate.sha(packet/'build/microbench')})))
   (directory/'window.json').write_text(json.dumps(dict(passed=True,device_executed=True,drained=True,lease_released=True,binary_sha256=micro_gate.sha(packet/'build/microbench'),build_receipt_sha256=micro_gate.sha(build),samples_sha256=micro_gate.sha(sample_path))))
   micro_gate.evaluate(packet)
   self.assertEqual(micro_gate.require_qualified(packet),CANDIDATES)
   import screen_jobs
   with patch.object(screen_jobs,'P',packet):self.assertEqual(screen_jobs.qualified_candidates(),CANDIDATES)
   (packet/'screen-jobs-seal.json').write_text('{"changed":true}')
   with self.assertRaisesRegex(ValueError,'stale or altered'):micro_gate.require_qualified(packet)
   self.assertEqual((old/'qualification.json').read_bytes(),historical)
 def test_threshold(self):
  self.assertEqual(analyze(samples(.85))['qualified'],list(CANDIDATES))
  self.assertEqual(analyze(samples(.850001))['qualified'],[])
 def test_refusals(self):
  for kind in ('missing','duplicate','order','short','nan','negative','bad-exact','incomplete','geometry'):
   rows=samples();sample=next(r for r in rows if r['kind']=='sample')
   if kind=='missing':rows.pop(3)
   if kind=='duplicate':rows.insert(3,copy.deepcopy(rows[3]))
   if kind=='order':sample['position']=1
   if kind=='short':sample['rows']=10240
   if kind=='nan':sample['event_ns']=float('nan')
   if kind=='negative':sample['event_ns']=-1
   if kind=='bad-exact':rows[0]['fp32_exact']=False
   if kind=='incomplete':rows[-1]['passed']=False
   if kind=='geometry':sample['wg']=256
   with self.subTest(kind=kind),self.assertRaises(ValueError):analyze(rows)
 def test_order_bias_does_not_pass(self):
  rows=samples(.7)
  for row in rows:
   if row['kind']=='sample' and row['view']!='production' and row['repeat']%2:row['event_ns']=900
  self.assertEqual(analyze(rows)['qualified'],[])
if __name__=='__main__':unittest.main()
