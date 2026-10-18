import copy,math,unittest
from verify_ready import choose,qualify_bracket

def fixture(gain=.006,drift=0):
 controls=[100.,100.+100*drift,100.];candidate=max(controls)*(1+gain)
 views=[dict(index=i,choice='candidate' if i%2 else 'control',lane='B',all_13_exact=True,exact_count=13,rate=candidate if i%2 else controls[i//2],acceptance_counts=[{'prompt_id':'synthetic','hits':2,'guesses':3}],draft_proposals={'synthetic':'identical'}) for i in range(5)]
 return dict(result=dict(passed=True,kind='bracket',model_lifetimes=1,views=views),window_sha256='a'*64,summary_sha256='b'*64,selection_sha256='c'*64,evidence_path='synthetic-only',coordination_sha256='d'*64)
class Rules(unittest.TestCase):
 def test_strict_best_control(self):
  row=fixture(.005,.01);self.assertAlmostEqual(qualify_bracket(row)['strict_ratio'],1.005)
 def test_weak_repeat(self):
  row=fixture();row['result']['views'][3]['rate']=100.49
  with self.assertRaises(ValueError):qualify_bracket(row)
 def test_drift(self):
  with self.assertRaises(ValueError):qualify_bracket(fixture(.1,.010001))
 def test_quality_and_shape_refusals(self):
  changes=[('all_13_exact',False),('exact_count',12),('lane','A'),('rate',float('nan')),('rate',float('inf')),('rate',0),('rate',True),('acceptance_counts',[]),('draft_proposals',{}),('choice','control'),('index',9)]
  for field,value in changes:
   with self.subTest(field=field,value=value):
    row=fixture();row['result']['views'][1][field]=value
    with self.assertRaises(ValueError):qualify_bracket(row)
 def test_one_load(self):
  row=fixture();row['result']['model_lifetimes']=5
  with self.assertRaises(ValueError):qualify_bracket(row)
 def test_select_only_winners(self):
  row=choose(lambda d:fixture(.006 if d=='hc_layout' else .004))
  self.assertEqual(row['selection'],dict(attention_layout='production',expert_gate_up_layout='production',hc_layout='order600',token_input='original'))
  self.assertEqual(list(row['winners']),['hc_layout'])
 def test_all_products(self):
  row=choose(lambda d:fixture(.005));self.assertAlmostEqual(row['combined_ratio'],1.005**4);self.assertGreaterEqual(row['combined_ratio'],1.02)
 def test_three_not_enough(self):
  row=choose(lambda d:fixture(.005 if d!='token_input' else .004));self.assertLess(row['combined_ratio'],1.02)
 def test_no_winners(self):
  row=choose(lambda d:fixture(.004));self.assertFalse(row['winners']);self.assertEqual(row['combined_ratio'],1)
 def test_missing_evidence(self):
  def missing(d):raise FileNotFoundError('pending '+d)
  row=choose(missing);self.assertFalse(row['winners']);self.assertEqual(len(row['rejected']),4)
if __name__=='__main__':unittest.main()
