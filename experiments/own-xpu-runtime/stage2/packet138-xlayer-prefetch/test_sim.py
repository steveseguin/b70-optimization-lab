"""Exact LRU comparison to frozen 58v; causal scheduling and byte-accounting tests."""
from array import array
import ctypes,random,unittest
from cache_sim import Arena,Scenario,Simulator,projection
from router_replay import library

class LRU(unittest.TestCase):
 def test_production_offsets_bytes_and_evictions(self):
  lib=library();ptr=ctypes.c_void_p
  lib.p138_cache_create.argtypes=[ptr,ctypes.c_uint64];lib.p138_cache_create.restype=ptr
  lib.p138_cache_free.argtypes=[ptr]
  lib.p138_cache_step.argtypes=[ptr,ptr,ctypes.c_uint,ptr,ptr,ptr]
  lib.p138_cache_observe.argtypes=[ptr,ptr,ctypes.c_uint]
  sizes=[1024]*48;sizes[2]=1280;native=array('Q',sizes);capacity=6912
  handle=lib.p138_cache_create(native.buffer_info()[0],capacity);self.assertTrue(handle)
  arena=Arena(sizes,capacity);rng=random.Random(138)
  try:
   for _ in range(150):
    selected=[rng.randrange(4)*512+rng.randrange(4) for _ in range(4)]
    keys=array('I',selected);ids=array('I',[0])*4;offsets=array('Q',[0])*4;metrics=array('Q',[0])*4
    self.assertEqual(lib.p138_cache_step(handle,keys.buffer_info()[0],4,ids.buffer_info()[0],offsets.buffer_info()[0],metrics.buffer_info()[0]),0)
    arena,fills,evicted=arena.prepare(selected)
    self.assertEqual(list(ids[:metrics[0]]),[k for k,_,_ in fills])
    self.assertEqual(list(offsets[:metrics[0]]),[off for _,off,_ in fills])
    self.assertEqual(list(metrics[1:]),[sum(n for _,_,n in fills),len(evicted),sum(n for _,n in arena.entries.values())])
    observed=array('I',[rng.randrange(4)*512+rng.randrange(4) for _ in range(3)])
    arena.touch(observed);self.assertEqual(lib.p138_cache_observe(handle,observed.buffer_info()[0],3),0)
  finally:lib.p138_cache_free(handle)
 def test_reader_protection(self):
  arena=Arena([1024]*48,2048);arena,_,_=arena.prepare([0,1])
  self.assertIsNone(arena.prepare([512],{0,1}))
  staged,fills,evicted=arena.prepare([512],{1})
  self.assertEqual(evicted,[0]);self.assertIn(1,staged.entries)
 def test_oversized_keeps_host(self):
  arena=Arena([2048]*48,1024);staged,fills,evicted=arena.prepare([0]);self.assertFalse(fills);self.assertFalse(staged.entries)

S=Scenario('test',1,.5,1000000,0,0,0,0,1,40,0.00001)
class Timing(unittest.TestCase):
 def test_position_lag(self):
  sim=Simulator([1024]*48,S,10000)
  route=[[0],[0]]
  self.assertEqual([sim.token(route) for _ in range(4)],[2048,2048,2048,0])
 def test_prefetch_useful_and_wrong_charged(self):
  sim=Simulator([1024]*48,S,10000)
  sim.token([[0],[0]],predictions=[[],[0,1]])
  self.assertEqual(sim.stats['prefetch_bytes'],2048)
  self.assertEqual(sim.stats['prefetch_wrong_bytes'],1024)
  self.assertEqual(sim.stats['prefetch_right_bytes'],1024)
  self.assertEqual(sim.stats['zero_copy_bytes'],1024)
 def test_late_copy_is_not_free_or_visible(self):
  slow=Scenario('slow',1,.5,100,0,0,0,0,1,40,0.00001)
  sim=Simulator([1024]*48,slow,10000)
  sim.token([[0],[0]],predictions=[[],[0]])
  self.assertEqual(sim.stats['zero_copy_bytes'],2048)
  self.assertEqual(sim.stats['prefetch_bytes'],1024)
  self.assertEqual(sim.stats['prefetch_late_batches'],1)
  self.assertNotIn(512,sim.visible())
 def test_demand_pending_blocks_prefetch(self):
  sim=Simulator([1024]*48,S,10000);r=[[0],[0]]
  sim.token(r);sim.token(r)
  self.assertEqual(sim.pending['state'],'planned')
  sim.token(r,predictions=[[],[1]])
  self.assertEqual(sim.stats['prefetch_blocked_transaction'],1)
  self.assertEqual(sim.stats['prefetch_bytes'],0)
 def test_residual_has_shorter_window(self):
  s=Scenario('window',1,.5,1500,0,0,0,0,1,40,0.00001)
  early=Simulator([1024]*48,s,10000);late=Simulator([1024]*48,s,10000)
  early.token([[0],[0]],predictions=[[],[0]],predictor='router_input')
  late.token([[0],[0]],predictions=[[],[0]],predictor='residual_stream0')
  self.assertEqual(early.stats['prefetch_late_batches'],0);self.assertEqual(late.stats['prefetch_late_batches'],1)
 def test_no_traffic_no_free_gain(self):
  a=dict(per_token={'zero_copy_bytes':1000});b=dict(per_token={'zero_copy_bytes':1000,'predictor_cost_ms':1})
  r=projection(a,b,S);self.assertLess(r['gain_percent'],0)
if __name__=='__main__':unittest.main()
