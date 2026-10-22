"""Synthetic wiring tests supplement (never replace) the real packet136 replay."""
import ast,base64,copy,gzip,json,resource,sys,unittest
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet190-record-bundle-k3x'
sys.path.insert(1,str(P));sys.path.insert(1,str(ROOT/'scripts'))
import submission_evidence as p

def fixture():
 # Execute just the unchanged fixture builders; pytest's test runner is not a
 # runtime dependency. Nothing in these functions launches or writes files.
 ns=dict(p=p,P=P,ROOT=ROOT,Path=Path,base64=base64,json=json,gzip=gzip,copy=copy)
 for path,names in [(ROOT/'scripts/tests/test_packet49_submission.py',{'put','fixture'}),(O/'lineage-p190-scaffolding/submission_fixture.py',{'prefix_fixture'})]:
  tree=ast.parse(path.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
  assert len(nodes)==len(names);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
 return ns['prefix_fixture'](),ns['put']
class Submission(unittest.TestCase):
 def test_k3x_notes_disclosure_and_cap(self):
  text=p.submission_notes(json.loads((P/'bundle-selection.json').read_text()))
  self.assertLessEqual(len(text),2000)
  for term in ('k3x','snapshot_host=static','layers 24-26','VERIFIED token','rank 1 starts at QSA layer 27','248,320','60.659520','strict512 false','Packet189','not the submitted measurement','cmvjvabyv040jrf01dricuz8s','kernel_io=kernel','rank0_prepare=async','boundary_export=copy'):self.assertIn(term,text)
  self.assertLessEqual(len(p.submission_notes(json.loads((P/'bundle-selection.json').read_text()),resumed=True)),2000)
 def test_equal_and_lower_floor_refuse(self):
  for rate in (60.659520,60.65951991975228,58.798109):
   with self.assertRaises(ValueError):p.require_new_record(rate)
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);unittest.main()
