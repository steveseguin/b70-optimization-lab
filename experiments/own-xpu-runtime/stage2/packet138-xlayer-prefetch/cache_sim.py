"""CPU event model: global LRU, 58v's lag, one copy transaction, bounded windows.

No GPU mechanism is implemented here. Candidate assumes safe pointer publication
at layer boundaries, with explicit added predictor/publication/planning costs.
"""
from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass
import heapq,math

class Arena:
 def __init__(self,sizes,capacity=18_000_000_000):
  self.sizes=sizes;self.capacity=capacity;self.free=[(0,capacity)];self.entries={};self.recent={};self.clock=0;self.heap=[]
 def clone(self):
  x=Arena(self.sizes,self.capacity);x.free=self.free.copy();x.entries=self.entries.copy();x.recent=self.recent.copy();x.clock=self.clock;x.heap=self.heap.copy();return x
 def touch(self,keys):
  for key in keys:
   self.clock+=1;self.recent[key]=self.clock
   if key in self.entries:heapq.heappush(self.heap,(self.clock,key))
  if len(self.heap)>max(64,4*len(self.entries)):
   self.heap=[(self.recent[k],k) for k in self.entries];heapq.heapify(self.heap)
 def release(self,off,n):
  at=bisect_left(self.free,(off,n));self.free.insert(at,(off,n))
  if at and sum(self.free[at-1])==off:
   x,m=self.free[at-1];self.free[at-1:at+1]=[(x,m+n)];at-=1
  if at+1<len(self.free) and sum(self.free[at])==self.free[at+1][0]:
   x,m=self.free[at];self.free[at:at+2]=[(x,m+self.free[at+1][1])]
 def prepare(self,keys,protected=frozenset()):
  staged=self.clone();staged.touch(keys);fills=[];evicted=[]
  for key in keys:
   if key in staged.entries:continue
   size=staged.sizes[key//512];allocated=(size+255)&~255
   if allocated>self.capacity:continue
   def fit():return next((i for i,(_,n) in enumerate(staged.free) if n>=allocated),None)
   at=fit()
   while at is None:
    deferred=[];victim=None
    while staged.heap:
     tick,k=heapq.heappop(staged.heap)
     if k not in staged.entries or staged.recent[k]!=tick:continue
     if k in protected:deferred.append((tick,k));continue
     victim=k;break
    for row in deferred:heapq.heappush(staged.heap,row)
    if victim is None:return None  # no safe admission; no traffic submitted
    off,n=staged.entries.pop(victim);staged.release(off,n);evicted.append(victim);at=fit()
   off,n=staged.free[at]
   if n==allocated:staged.free.pop(at)
   else:staged.free[at]=(off+allocated,n-allocated)
   staged.entries[key]=(off,allocated);heapq.heappush(staged.heap,(staged.recent[key],key))
   fills.append((key,off,size))
  return staged,fills,evicted

def keys(route):return [layer*512+expert for layer,ids in enumerate(route) for expert in ids]

@dataclass(frozen=True)
class Scenario:
 name:str
 layer_ms:float
 pre_router_fraction:float
 dma_bytes_per_ms:float
 predictor_ms:float
 publication_ms:float
 plan_extra_ms:float
 fill_submit_ms:float
 transfer_window_fraction:float
 control_anchor_ms:float
 remote_ms_per_byte:float
 per_layer_windows_measured:bool=False
 special_remote_ms_per_byte:float|None=None

class Simulator:
 def __init__(self,sizes,scenario,capacity=18_000_000_000):
  self.cache=Arena(sizes,capacity);self.s=scenario;self.pending=None;self.previous=[];self.time=0.;self.stats=Counter();self.token_rows=[]
 def visible(self):
  if self.pending and self.pending['state']=='filling':return self.pending['visible']
  return self.cache.entries
 def commit(self,now,boundary=False):
  p=self.pending
  if p and p['state']=='filling' and now>=p['done'] and (p['kind']=='prefetch' or boundary):
   self.cache=p['staged'];self.pending=None;return True
  return False
 def submit(self,plan,kind,now,deadline=None):
  assert self.pending is None
  staged,fills,evicted=plan
  if not fills:
   self.cache=staged;return None
  n=sum(r[2] for r in fills);duration=n/self.s.dma_bytes_per_ms+len(fills)*self.s.fill_submit_ms
  done=now+duration
  visible={k for k in self.cache.entries if k in staged.entries and k not in {r[0] for r in fills}}
  self.pending=dict(state='filling',kind=kind,staged=staged,fills=fills,visible=visible,done=done)
  self.stats[kind+'_bytes']+=n;self.stats[kind+'_fills']+=len(fills);self.stats['evictions']+=len(evicted)
  if kind=='prefetch':
   self.stats['prefetch_batches']+=1
   self.stats['prefetch_late_batches']+=done>deadline
   self.stats['prefetch_window_overflow_bytes']+=max(0,n-max(0,deadline-now-len(fills)*self.s.fill_submit_ms)*self.s.dma_bytes_per_ms)
  return self.pending
 def boundary(self):
  self.commit(self.time,True)
  if self.pending and self.pending['state']=='planned':
   p=self.pending;self.pending=None;self.submit(p['plan'],'demand',self.time)
 def token(self,routes,predictions=None,predictor='router_input',record=True):
  before=self.stats.copy();self.boundary();start=self.time;miss=0;calls=0
  for layer,actual in enumerate(routes):
   begin=start+layer*self.s.layer_ms
   demand=begin+self.s.pre_router_fraction*self.s.layer_ms
   self.commit(demand)
   visible=self.visible();missing=[layer*512+i for i in actual if layer*512+i not in visible]
   missing_bytes=sum(self.cache.sizes[k//512] for k in missing)
   miss+=missing_bytes;self.stats['zero_copy_bytes_layer'+str(layer)]+=missing_bytes
   if predictions is not None and layer+1<len(routes):
    calls+=1
    available=demand if predictor=='router_input' else begin+self.s.layer_ms
    self.commit(available)
    if self.pending is not None:
     self.stats['prefetch_blocked_transaction']+=1;continue
    predicted=[(layer+1)*512+i for i in predictions[layer+1]]
    # No look-ahead truth in admission: only current layer ownership is protected.
    protected={k for k in self.cache.entries if k//512==layer}
    plan=self.cache.prepare(predicted,protected)
    if plan is None:
     self.stats['prefetch_blocked_readers']+=1;continue
    deadline=start+(layer+1+self.s.pre_router_fraction)*self.s.layer_ms
    # Fraction reserves unmeasured head/host/PCIe contention instead of treating
    # the whole averaged layer span as hideable DMA. Copies are never free.
    deadline=available+(deadline-available)*self.s.transfer_window_fraction
    if plan[1]:
     p=self.submit(plan,'prefetch',available+self.s.predictor_ms+self.s.publication_ms,deadline)
     truth={(layer+1)*512+i for i in routes[layer+1]}
     self.stats['prefetch_wrong_bytes']+=sum(n for k,_,n in plan[1] if k not in truth)
     self.stats['prefetch_right_bytes']+=sum(n for k,_,n in plan[1] if k in truth)
    else:self.cache=plan[0]
  self.time=start+len(routes)*self.s.layer_ms;self.commit(self.time)
  # Same lag as 58v: plan previous routes while this position owns the old
  # table, revoke/fill at NEXT position, publish only after completion.
  # Candidate planning is placed after its layer copies and charged separately.
  if self.pending is None and self.previous:
   plan=self.cache.prepare(self.previous)
   if plan[1]:self.pending=dict(state='planned',kind='demand',plan=plan,staged=plan[0])
   else:self.cache=plan[0]
  current=keys(routes)
  self.cache.touch(current)
  if self.pending:self.pending['staged'].touch(current)
  self.previous=current
  self.stats['zero_copy_bytes']+=miss;self.stats['tokens']+=1;self.stats['predictor_calls']+=calls
  self.stats['predictor_cost_ms']+=calls*(self.s.predictor_ms+self.s.publication_ms)
  if calls:self.stats['candidate_plan_cost_ms']+=self.s.plan_extra_ms
  if record:
   row={k:self.stats[k]-before[k] for k in self.stats};self.token_rows.append(row)
  return miss
 def reset_request(self):
  # Existing caches persist across requests. Pending DMA must drain before reset;
  # this is a quiescent boundary cost, not hidden inside decode token rates.
  if self.pending and self.pending['state']=='planned':
   p=self.pending;self.pending=None;self.submit(p['plan'],'demand',self.time)
  if self.pending:
   self.stats['request_drain_ms']+=max(0,self.pending['done']-self.time)
   self.time=max(self.time,self.pending['done']);self.commit(self.time,True)
  self.previous=[]
 def summary(self):
  totals=Counter()
  for row in self.token_rows:totals.update(row)
  n=len(self.token_rows);assert n
  return dict(tokens=n,totals=dict(totals),per_token={k:v/n for k,v in totals.items()},cache_resident_bytes=sum(n for _,n in self.cache.entries.values()),request_drain_ms=self.stats['request_drain_ms'])

def projection(control,candidate,s):
 a=control['per_token'];b=candidate['per_token']
 diff=b.get('zero_copy_bytes',0)-a.get('zero_copy_bytes',0)
 special=b.get('zero_copy_bytes_layer2',0)-a.get('zero_copy_bytes_layer2',0)
 delta=(diff-special)*s.remote_ms_per_byte+special*(s.special_remote_ms_per_byte or s.remote_ms_per_byte)
 delta+=b.get('predictor_cost_ms',0)+b.get('candidate_plan_cost_ms',0)
 # The side queue cannot make overflowing traffic disappear. Charge all modeled
 # excess serially even though late reads also remain zero-copy (conservative).
 delta+=b.get('prefetch_window_overflow_bytes',0)/s.dma_bytes_per_ms
 assert s.control_anchor_ms+delta>0
 return dict(projected_not_measured=True,control_tok_s=1000/s.control_anchor_ms,candidate_tok_s=1000/(s.control_anchor_ms+delta),
  delta_ms=delta,gain_percent=(s.control_anchor_ms/(s.control_anchor_ms+delta)-1)*100,
  traffic_fits_assumed_windows=b.get('prefetch_late_batches',0)==0,per_layer_windows_measured=s.per_layer_windows_measured)
