import copy,importlib.util,json,unittest
from pathlib import Path
O=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('dense_closed_audit',O/'evidence/device-a/audit.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
s=importlib.util.spec_from_file_location('dense_manifest_source',O/'prepare.py');M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
class Audit(unittest.TestCase):
 def fixture(self):
  extraction=json.loads((O.parent/'evidence/extraction.json').read_text());cases,schedule=M.cases_schedule(extraction);manifest=dict(cases=cases,schedule=schedule);rows=[];clock=1
  for e in schedule:
   c=cases[e['case']];r=dict(warmup=e['warmup'],cycle=e['cycle'],layer=c['layer'],label=c['label'],order=''.join(e['order']),exact=True,A_sha256=c['fixtures']['expected']['sha256'],B_sha256=c['fixtures']['expected']['sha256'],expected_sha256=c['fixtures']['expected']['sha256'])
   for arm in e['order']:r[arm+'_start_ns']=clock;r[arm+'_end_ns']=clock+2+e['case'];clock+=10
   rows.append(r)
  return rows,manifest
 def test_full_three_case_schedule_and_statistics(self):
  rows,m=self.fixture();measured=A.samples_check(rows,m);self.assertEqual(len(rows),84);self.assertEqual(len(measured),72);stats=A.per_case(measured);self.assertEqual(len(stats),3)
  for item in stats.values():self.assertEqual(item['all']['pairs'],24);self.assertEqual(item['all']['B_over_A_sum'],1);self.assertEqual([item['by_order'][k]['pairs'] for k in ('AB','BA')],[12,12])
 def test_wrong_fixed_identity_output_schedule_and_time_refuse(self):
  for bad in ('type','layer','extent','output','order','missing','overlap'):
   rows,m=self.fixture()
   if bad=='type':m['cases'][0]['type_id']=23
   elif bad=='layer':rows[0]['layer']=2
   elif bad=='extent':m['cases'][0]['fixtures']['expected']['bytes']-=2
   elif bad=='output':rows[18]['B_sha256']='0'*64
   elif bad=='order':rows[18]['order']='BA' if rows[18]['order']=='AB' else 'AB'
   elif bad=='missing':rows.pop()
   else:rows[18]['A_start_ns']=1
   with self.subTest(bad=bad),self.assertRaises(ValueError):A.samples_check(rows,m)
 def test_operational_bindings_and_ack_body(self):
  self.assertTrue(A.PLAN_SHA is None or len(A.PLAN_SHA)==64)
  import hashlib
  build=O.parent/'evidence/native-build.json';receipt=json.loads(build.read_text());self.assertEqual(hashlib.sha256(build.read_bytes()).hexdigest(),A.BUILD_SHA);self.assertEqual(receipt['binary_sha256'],A.BINARY_SHA)
  import ast
  old=A.PARENT.read_text();new=(O/'evidence/device-a/audit.py').read_text()
  def body(src,name):return ast.dump(next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
  for name in ('ack_join','digest','pins','aggregate'):self.assertEqual(body(old,name),body(new,name))
if __name__=='__main__':unittest.main(verbosity=2)
