import importlib.util,json,unittest
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parent
s=importlib.util.spec_from_file_location('hc_source_prepare',P/'prepare.py');M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
class Source(unittest.TestCase):
 def test_generated_candidate_and_arithmetic_identity(self):
  old,new=M.derive();self.assertEqual(new,(P/'one_sg.hpp').read_text())
  def span(text,a,b):return text[text.index(a):text.index(b,text.index(a))]
  self.assertEqual(span(old,'template<Type T,unsigned SG> inline float dot','template<unsigned SG> float dispatch_dot'),span(new,'template<Type T,unsigned SG> inline float dot','template<unsigned SG> float dispatch_dot'))
  self.assertEqual(span(old,'          // Explicit adjacent-pair tree.','        }));'),span(new,'          // Explicit adjacent-pair tree.','        }));'))
  for a,b in [('void check(', 'void geometry('),('ownrt::Event finish(', '\n}\n}')]:self.assertEqual(span(old,a,b),span(new,a,b))
  self.assertIn('constexpr size_t rows_per_group=1;',new);self.assertIn('(mul(count,span)+rows_per_group-1)/rows_per_group',new)
  self.assertIn('it.barrier(sycl::access::fence_space::local_space);',new);self.assertIn('sycl::local_accessor<uint8_t,1> storage(stride*rows_per_group,h);',new)
  self.assertIn('return run<Type::BF16,32>(q,p,deps);',new);self.assertNotIn('ownrt::Event routed_gemv(',new)
  self.assertIn('policy(t,rows,k,a,o,sg,fp32);',new);self.assertIn('{t,w,x,y,rows,k,a,o,fp32},1,1,rows)',new)
 def test_exact_census_and_fixed_unique_writers(self):
  g=json.loads((L/'graph/new-plan.json').read_text());c=json.loads((L/'metadata/new-census.json').read_text());sel=json.loads((P/'selection.json').read_text());chosen=[]
  for x in g['launches']:
   if any(x['label'].endswith(s) for s in ['hc.a.low','hc.f.low','hc.a.inject','hc.f.inject']):
    t=c['tensors'][x['weights'][0]];n=4 if x['label'].endswith('inject') else 320;self.assertEqual(x['shape'],[1,n,10240]);self.assertEqual(t['type_id'],30);self.assertEqual(t['bytes'],n*20480)
    chosen.append(dict(label=x['label'],weight=x['weights'][0],shape=x['shape'],type_id=30,weight_bytes=t['bytes'],inputs=x['inputs'],outputs=x['outputs']))
  self.assertEqual(sel['sites'],chosen);self.assertEqual(len(chosen),192)
  plan=json.loads((P/'micro/extraction-plan.json').read_text())
  for case in plan['cases']:
   for item in case['ranges'].values():self.assertEqual([x['label'] for x in g['launches'] if item['name'] in x['outputs']],[item['unique_writer']])
 def test_actual_ack_parent_and_balanced_schedule(self):
  parent=L/'iq4nl-down-direct/micro';self.assertEqual((P/'micro/startup.hpp').read_bytes(),(parent/'startup.hpp').read_bytes());self.assertEqual((P/'micro/handshake.py').read_bytes(),(parent/'handshake.py').read_bytes())
  runner=(P/'micro/runner.cpp').read_text();self.assertLess(runner.index('await_backend_ack(out)'),runner.index('Harness h(*d'))
  for cycles in [4,24]:
   counts={}
   for cycle in range(cycles):
    for pos in range(2):
     key=(((cycle//2)+pos)%2,cycle%2,pos);counts[key]=counts.get(key,0)+1
   self.assertEqual(set(counts.values()),{cycles//4});self.assertEqual(len(counts),8)
  self.assertIn('pairs==56&&submissions==112',runner);self.assertIn('allocated==6677776&&transfers==6712768',runner)
if __name__=='__main__':unittest.main(verbosity=2)
