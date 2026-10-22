"""Synthetic wiring tests supplement (never replace) the real packet136 replay."""
import ast,base64,copy,gzip,json,resource,sys,unittest
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet187-record-bundle-v3'
sys.path.insert(1,str(P));sys.path.insert(1,str(ROOT/'scripts'))
import submission_evidence as p

def fixture():
 # Execute just the unchanged fixture builders; pytest's test runner is not a
 # runtime dependency. Nothing in these functions launches or writes files.
 ns=dict(p=p,P=P,ROOT=ROOT,Path=Path,base64=base64,json=json,gzip=gzip,copy=copy)
 for path,names in [(ROOT/'scripts/tests/test_packet49_submission.py',{'put','fixture'}),(O/'lineage-p187-scaffolding/submission_fixture.py',{'prefix_fixture'})]:
  tree=ast.parse(path.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
  assert len(nodes)==len(names);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
 return ns['prefix_fixture'](),ns['put']
class Submission(unittest.TestCase):
 def test_v3_notes_disclosure_and_cap(self):
  text=p.submission_notes(json.loads((P/'bundle-selection.json').read_text()))
  self.assertLessEqual(len(text),2000)
  for term in ('V3','snapshot_host=static','layers 24-25','VERIFIED token','rank 1 starts at layer 26','248,320','58.798109','strict512 false','Packet186','not the submitted measurement','cmve4dtir007wrf01k57sdf23'):self.assertIn(term,text)
  self.assertLessEqual(len(p.submission_notes(json.loads((P/'bundle-selection.json').read_text()),resumed=True)),2000)
 def test_equal_and_lower_floor_refuse(self):
  for rate in (58.798109,58.798108759182306):
   with self.assertRaises(ValueError):p.require_new_record(rate)
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);unittest.main()
