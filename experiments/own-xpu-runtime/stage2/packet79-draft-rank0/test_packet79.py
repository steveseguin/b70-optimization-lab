"""Actual placement/selection consumers, full census admission, closed worker import."""
import copy,json,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from bootstrap import P,ROOT,WRAPPER,install
placement=install()
from common import read,sha,sealed
from memory_gate import configuration,check
from screen_jobs import jobs,choose,verify

class Packet79(unittest.TestCase):
 def test_six_selections_real_placement(self):
  verify()
  for name,(dr,split,boundary) in placement.PLACEMENTS.items():
   for hc in ('production','hc-wide'):
    root=P/'selections'/(name+'--'+hc)
    identity=sealed(SimpleNamespace(lineage=root,seal=root/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement=name))
    v=identity['placement'];self.assertTrue(v['supported']);self.assertEqual((v['draft_rank'],v['target_split'],v['target_layers']),(dr,split,[boundary,48-boundary]))
    got,gate=placement.verify_identity(identity);self.assertEqual(got,v)
    wrong=dict(identity,selection_sha256='0'*64)
    with self.assertRaisesRegex(ValueError,'identity/placement changed'):placement.verify_identity(wrong)
    with self.assertRaisesRegex(ValueError,'placement differs'):sealed(SimpleNamespace(lineage=root,seal=root/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='0' if name!='0' else '1'))
 def test_worker_import_in_closed_environment(self):
  r=subprocess.run(['/usr/bin/python3','-B',str(P/'worker.py'),'--help'],env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
  self.assertEqual(r.returncode,0,r.stderr);self.assertIn('--identity',r.stdout)
 def test_full_census_and_negative_memory(self):
  ledger=read(P/'memory-plan.json');proof=read(P/'evidence/full-shape.json')
  for row in proof['runs']:
   c=read(ROOT/row['census']);args=dict(rank=row['rank'],mtp=True,context=4096,draft_rank=row['draft_rank'],target_split=row['target_split'])
   self.assertTrue(check(c,ledger,**args)['passed'])
   bad=copy.deepcopy(c);bad['totals']['device']+=1
   with self.assertRaisesRegex(ValueError,'live total differs'):check(bad,ledger,**args)
  with self.assertRaises(ValueError):configuration(ledger,32768,0,24)
  bad=copy.deepcopy(ledger);bad['arena_limit_bytes']+=1
  with self.assertRaisesRegex(ValueError,'cap changed'):configuration(bad,4096,0,24)
  bad=copy.deepcopy(ledger);bad['placements']['0-split24']['capacities']['4096']['ranks'][0]['draft_duplicate_head_bytes']=839321600
  with self.assertRaises(ValueError):configuration(bad,4096,0,24)
 def test_lane_A_order_B_selection_and_refusals(self):
  self.assertEqual([r['placement'] for r in jobs('A')],['1','0-split23','0','1'])
  rows=[dict(choice=r['choice'],rate=rate,exact=True) for r,rate in zip(jobs('A'),[50,54,51,50.5])]
  self.assertEqual(choose(rows)['choice'],'0-split23')
  self.assertEqual([r['placement'] for r in jobs('B',choose(rows)['choice'])],['1','0-split23','1'])
  bad=copy.deepcopy(rows);bad[1]['exact']=False
  with self.assertRaisesRegex(ValueError,'match packet49'):choose(bad)
  bad=copy.deepcopy(rows);bad[0]['rate']=60
  with self.assertRaisesRegex(ValueError,'beats both'):choose(bad)
  with self.assertRaisesRegex(ValueError,'complete ordered'):choose(rows[:-1])
  with self.assertRaisesRegex(ValueError,'candidate'):jobs('B','1')
 def test_native_selection_consumer_rejects_unknown_or_broken_fusion(self):
  for variant in ('unknown','broken-draft'):
   with tempfile.TemporaryDirectory(dir=P/'build') as t:
    root=Path(t);selection=read(P/'selection.json')
    if variant=='unknown':selection['choices']['unexpected']='must-reject'
    else:selection['draft']['hc_a_low']='production'
    path=root/'selection.json';path.write_text(json.dumps(selection))
    r=subprocess.run([str(P/'build/full-shape/fixture'),str(path),sha(path),'0',str(root/'out'),'positive','0','24'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
    self.assertNotEqual(r.returncode,0);self.assertTrue('selection' in r.stderr or 'requires' in r.stderr,r.stderr)
 def test_shared_wrapper_has_not_changed(self):
  from common import verify_map
  verify_map(ROOT,read(P/'dependency-pins.json'))
  self.assertEqual(sha(P/'memory_gate.py'),sha(P.parent/'packet56-draft-prefix/memory_gate.py'))
if __name__=='__main__':unittest.main()
