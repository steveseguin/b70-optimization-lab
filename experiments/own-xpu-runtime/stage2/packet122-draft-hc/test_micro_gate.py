import copy,unittest
from micro_gate import analyze,CLASSES
def rows(ratio=.75):
 out=[]
 for context in (128,4096):
  for iteration in range(50):
   for view in ('production','p122'):
    ns=1000 if view=='production' else int(1000*ratio);classes={k:ns for k in CLASSES}
    out.append(dict(context=context,iteration=iteration,view=view,warmup=iteration<10,order=int((view=='p122')^(iteration&1)),gpu_ns=ns*3,submissions=3,classes_ns=classes,events=[dict(class_=k) for k in []]))
    out[-1]['events']=[{'class':k,'start_ns':100,'end_ns':100+ns} for k in CLASSES]
 return out
class GateTests(unittest.TestCase):
 def test_pass(self):self.assertEqual(analyze(rows())['qualified'],['p122'])
 def test_threshold(self):self.assertEqual(analyze(rows(.8))['qualified'],['p122']);self.assertEqual(analyze(rows(.801))['qualified'],[])
 def test_missing(self):
  with self.assertRaises(ValueError):analyze(rows()[:-1])
 def test_duplicate(self):
  r=rows();r[-1]=r[0]
  with self.assertRaises(ValueError):analyze(r)
 def test_lost_class(self):
  r=rows();del r[0]['classes_ns'][CLASSES[0]]
  with self.assertRaises(ValueError):analyze(r)
 def test_misreported_event(self):
  r=rows();r[0]['events'][0]['end_ns']+=1
  with self.assertRaises(ValueError):analyze(r)
 def test_one_slow_class_cannot_hide_in_sum(self):
  r=rows(.1)
  for row in r:
   if row['view']=='p122':
    row['classes_ns'][CLASSES[0]]=900;row['gpu_ns']=1100;row['events'][0]['end_ns']=1000
  self.assertEqual(analyze(r)['qualified'],[])
 def test_one_context_fails(self):
  r=rows()+[]
  for row in r:
   if row['view']=='p122' and row['context']==4096:
    row['classes_ns']={k:900 for k in CLASSES};row['gpu_ns']=2700
    for e in row['events']:e['end_ns']=1000
  self.assertEqual(analyze(r)['qualified'],[])
 def test_one_order_fails(self):
  r=rows(.1)
  for row in r:
   if row['view']=='p122' and row['iteration']%2:
    row['classes_ns']={k:900 for k in CLASSES};row['gpu_ns']=2700
    for e in row['events']:e['end_ns']=1000
  self.assertEqual(analyze(r)['qualified'],[])
 def test_wrong_order(self):
  r=rows();r[0]['order']=1
  with self.assertRaises(ValueError):analyze(r)
if __name__=='__main__':unittest.main()
