import importlib.util,json,copy,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('hc_closed_audit',P/'device-a/audit.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
class Audit(unittest.TestCase):
 def fixture(self):
  m=json.loads((P.parent/'manifest.json').read_text());rows=[];clock=1
  for e in m['schedule']:
   case=m['cases'][e['case']];h=case['fixtures']['expected']['sha256'];r=dict(warmup=e['warmup'],cycle=e['cycle'],layer=0,label=case['label'],order=''.join(e['order']),exact=True,A_sha256=h,B_sha256=h,expected_sha256=h)
   duration={'A':100 if e['case']==0 else 10,'B':50 if e['case']==0 else 20}
   for arm in e['order']:r[arm+'_start_ns']=clock;clock+=(10000 if e['warmup'] else duration[arm]);r[arm+'_end_ns']=clock;clock+=1
   rows.append(r)
  return m,rows
 def test_fixed_schedule_per_case_warmup_exclusion(self):
  m,rows=self.fixture();v=A.samples_check(rows,m);summary=A.per_case(v);self.assertEqual(len(v),48)
  for label,ratio in [('blk.0.hc.a.low',.5),('blk.0.hc.a.inject',2.)]:
   self.assertEqual(summary[label]['all']['pairs'],24);self.assertEqual(summary[label]['all']['B_over_A_sum'],ratio)
   for order in ['AB','BA']:self.assertEqual(summary[label]['by_order'][order]['pairs'],12);self.assertEqual(summary[label]['by_order'][order]['B_over_A_sum'],ratio)
  self.assertEqual(summary['blk.0.hc.a.low']['all']['A_ns']['mean'],100)
 def test_full_output_order_count_and_geometry_refuse(self):
  for bad in ['digest','label','missing','order','geometry','reorder_manifest','event']:
   m,r=self.fixture()
   if bad=='digest':r[17]['B_sha256']='0'*64
   elif bad=='label':r[0]['label']='blk.0.hc.a.inject'
   elif bad=='missing':r.pop()
   elif bad=='order':r[0]['order']='BA'
   elif bad=='geometry':m['cases'][0]['rows']=4
   elif bad=='reorder_manifest':m['schedule'][0],m['schedule'][1]=m['schedule'][1],m['schedule'][0]
   else:r[1]['A_start_ns']=1
   with self.subTest(bad=bad),self.assertRaises(ValueError):A.samples_check(r,m)
 def test_actual_plan_manifest_identity(self):
  plan=P/'device-a/plan.json';self.assertEqual(A.digest(plan),A.PLAN_SHA);j=json.loads(plan.read_text());self.assertEqual(j['unit'],'gsq-hc-bf16-one-sg-micro-a');self.assertEqual(j['binary_sha256'],A.BINARY_SHA);self.assertEqual((j['pairs'],j['kernels'],j['device_bytes']),(56,112,6677776))
if __name__=='__main__':unittest.main(verbosity=2)
