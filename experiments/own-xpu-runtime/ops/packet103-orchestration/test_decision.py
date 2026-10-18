import copy,json,unittest
from pathlib import Path
from decision import DEFAULTS,select,check_winner
from source_adapter import record_lane_veto
O=Path(__file__).resolve().parent
class DecisionTests(unittest.TestCase):
 def setUp(self):self.s=json.loads((O/'screens-current.json').read_text())
 def test_live_read(self):
  control,candidate,confirmed=select(self.s)
  self.assertEqual(control,DEFAULTS)
  self.assertIn('101',confirmed);self.assertEqual(candidate['draft_attention'],'split32')
  self.assertEqual(candidate['head'],'production')
 def test_one_lane_qualifies(self):check_winner(self.s['101'])
 def test_bad_quality_refused(self):
  r=copy.deepcopy(self.s['101']);next(iter(r['lanes'].values()))[1]['exact']=False
  with self.assertRaises(AssertionError):check_winner(r)
 def test_acceptance_refused(self):
  r=copy.deepcopy(self.s['101']);next(iter(r['lanes'].values()))[1]['acceptance_counts']=[]
  with self.assertRaises(AssertionError):check_winner(r)
 def test_tie_refused(self):
  r=copy.deepcopy(self.s['101']);rows=next(iter(r['lanes'].values()));rows[1]['rate']=max(rows[0]['rate'],rows[-1]['rate'])
  with self.assertRaises(AssertionError):check_winner(r)
 def test_a_loss_veto(self):
  r=copy.deepcopy(self.s['101']);rows=next(iter(r['lanes'].values()));rows[1]['rate']=min(rows[0]['rate'],rows[-1]['rate'])
  veto=record_lane_veto('draft_attention',[dict(kind='confirmation',rows=rows)])
  self.assertIsNotNone(veto)
  r['record_lane_veto']=veto
  with self.assertRaises(AssertionError):check_winner(r)
 def test_pending_down_omitted(self):
  self.s['100']={'status':'pending'}
  self.assertEqual(select(self.s)[1]['down'],'production')
 def test_failed_not_hidden(self):
  self.s['100']={'status':'failed','reason':'bad bytes'}
  with self.assertRaisesRegex(ValueError,'bad bytes'):select(self.s)
 def test_unknown_winner_refused(self):
  r=self.s['101'];old=r['winner'];r['winner']='unregistered'
  for rows in r['lanes'].values():
   for x in rows:
    if x['choice']==old:x['choice']=r['winner']
  with self.assertRaises(AssertionError):select(self.s)
if __name__=='__main__':unittest.main()
