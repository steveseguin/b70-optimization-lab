import copy,hashlib,importlib.util,json,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('iq4_closed_audit',P/'audit.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
class Audit(unittest.TestCase):
 def records(self):
  m=json.loads((P.parent/'manifest.json').read_text());rows=[]
  for i,e in enumerate(m['schedule']):
   c=m['cases'][e['case']];r=dict(warmup=e['warmup'],cycle=e['cycle'],layer=0,label='blk.0.expsdown',order=''.join(e['order']),exact=True)
   for k in ('A_sha256','B_sha256','expected_sha256'):r[k]=c['fixtures']['expected']['sha256']
   for k in ('A_status_sha256','B_status_sha256','expected_status_sha256'):r[k]=c['fixtures']['status']['sha256']
   for j,arm in enumerate(e['order']):r[arm+'_start_ns']=i*10+j*3+1;r[arm+'_end_ns']=i*10+j*3+3
   rows.append(r)
  return rows,m
 def test_all_pairs_and_unfiltered_orders(self):
  rows,m=self.records();self.assertEqual(len(a.samples_check(rows,m)),24);self.assertEqual(a.aggregate(rows)['B_over_A_sum'],1)
  for change in ('missing','status','output','order','time'):
   bad=copy.deepcopy(rows)
   if change=='missing':bad.pop()
   elif change=='status':bad[5]['B_status_sha256']='0'*64
   elif change=='output':bad[7]['B_sha256']='0'*64
   elif change=='order':bad[8]['order']='BA' if bad[8]['order']=='AB' else 'AB'
   else:bad[9]['A_end_ns']=bad[9]['A_start_ns']
   with self.subTest(change=change),self.assertRaises(ValueError):a.samples_check(bad,m)
 def challenge(self):
  ready=b'GSQ_NATIVE_BACKEND_READY_V1 42 100 '+b'a'*32+b'\n';h=dict(pid=42,node='renderD1');c=dict(native_identity=[42,100],ready_sha256=hashlib.sha256(ready).hexdigest(),native_holders=[h],snapshot=dict(holders={'42':dict(start_ticks=100)},inventory=dict(holders=[h]),drm={'renderD1':dict(bdf='0000:23:00.0')}));return ready,c
 def test_ack_identity_nonce_and_positive_contact(self):
  ready,c=self.challenge();self.assertTrue(a.ack_join(ready,ready,c,[42,100]))
  for field in ('ack','pid','ticks','contact','bdf','digest'):
   bad=copy.deepcopy(c);ack=ready;native=[42,100]
   if field=='ack':ack=ready.replace(b'a',b'b')
   elif field=='pid':native=[43,100]
   elif field=='ticks':bad['snapshot']['holders']['42']['start_ticks']=101
   elif field=='contact':bad['native_holders']=[]
   elif field=='bdf':bad['snapshot']['drm']['renderD1']['bdf']='0000:47:00.0'
   else:bad['ready_sha256']='0'*64
   with self.subTest(field=field),self.assertRaises(ValueError):a.ack_join(ready,ack,bad,native)
 def test_warmups_not_measured(self):
  rows,m=self.records();rows[0]['A_end_ns']=rows[0]['A_start_ns']+1
  measured=a.samples_check(rows,m);self.assertEqual(a.aggregate(measured)['B_over_A_sum'],1);self.assertNotEqual(a.aggregate(rows)['B_over_A_sum'],1)
 def test_import_cannot_run_audit(self):
  self.assertEqual(a.index,{})
  source=(P/'audit.py').read_text();self.assertIn("p.add_argument('--run',action='store_true',required=True)",source)
if __name__=='__main__':unittest.main(verbosity=2)
