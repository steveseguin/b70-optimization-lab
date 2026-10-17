#!/usr/bin/env python3
"""Actual host-engine state/rollback tests; never executes a device binary."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
import pipeline
from prepare_selections import CHOICES
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build';E=P/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def state(out):
 files={str(f.relative_to(out)):f.read_bytes() for r in (0,1) for f in sorted((out/f'rank{r}/state-2147483647').glob('*.bin'))}
 metadata={str(r):json.loads((out/f'rank{r}/state-2147483647/state.json').read_text()) for r in (0,1)}
 inventories={str(r):json.loads((out/f'rank{r}/request-state-inventory.json').read_text()) for r in (0,1)}
 private={}
 for rank,inv in inventories.items():
  inv.pop('logical_event')
  for name,item in list(inv['standalone_target_mutable'].items()):
   if any(x in name for x in ('speculative-private-image','speculative-copy-table','speculative-reserve:')):
    assert item['sha256']==hashlib.sha256(bytes(item['bytes'])).hexdigest(),('nonzero private',name)
    private[rank+'/'+name]=item;del inv['standalone_target_mutable'][name]
 return files,metadata,inventories,private

def run(name,choice='control',binary=None,prompt=None,count=24,guesses=(),eos=(),cut=-1,controller='native',retain='1-24',after=None,reset_repeat=False):
 out=B/name;assert not out.exists(),out;out.mkdir();launch_out=out
 binary=binary or B/'gnu-host/own-rt-iq3'
 args=pipeline.parser().parse_args(['--binary',str(binary),'--output',str(out),'--mini','--context','256','--tokens',str(count),'--seconds','180','--wait-seconds','120','--native-nice','19','--draft','none','--draft-rank','1','--controller',controller,'--timing','token','--retain-steps',retain,'--cancel-launch',str(cut)])
 args.host_memory='resident'
 if choice is not None:args.cpu_selection=P/'selections'/choice/'selection.json'
 transport=pipeline.Transport.__new__(pipeline.Transport)
 try:
  transport.__init__(args,out)
  result=pipeline.request_run(transport,pipeline.Draft('script' if guesses else 'none',guesses),prompt or [2,5,3,7,1],count,eos,True,False)
  if after:after(transport,result)
  if reset_repeat:
   following=out/'after-reset';following.mkdir()
   for rank in (0,1):
    metadata=out/f'rank{rank}'/f'reset-{transport.seq[rank]+1}.txt'
    metadata.write_text(str(following/f'rank{rank}')+'\n\n')
    transport.call(rank,11)
   transport.mapping[:pipeline.SHARED]=bytes(pipeline.SHARED)
   result=pipeline.request_run(transport,pipeline.Draft('script' if guesses else 'none',guesses),prompt or [2,5,3,7,1],count,eos,True,False)
   out=following
  for rank in (0,1):transport.call(rank,pipeline.DUMP,position=2147483647)
  sig=state(out);slot=bytes(transport.mapping[:pipeline.SLOT])
  transport.close(True)
 except BaseException:
  if not getattr(transport,'closed',False):transport.stop('CPU gate failure');transport.close(False)
  raise
 fixtures={str(f.relative_to(out)):sha(f) for rank in ('rank0','rank1') for f in (out/rank).glob('step*/layer-*.bf16')}
 row=dict(name=name,choice=choice,passed=True,device_executed=False,tokens=result['tokens'],stats=result['stats'],fixtures=fixtures,
  snapshot=json.loads((out/'rank0/speculative-snapshot.json').read_text()),
  state_hashes={k:hashlib.sha256(v).hexdigest() for k,v in sig[0].items()},metadata=sig[1],inventory=sig[2],private=sig[3],shared_slot_sha256=hashlib.sha256(slot).hexdigest(),
  binary_sha256=sha(binary),selection_sha256=sha(args.cpu_selection) if choice else None,
  launch_files={f.name:sha(f) for f in launch_out.glob('rank*-launch.json')})
 save(E/(name+'.json'),row)
 return row,sig,slot,out

def equal(a,b):
 assert a[0]['tokens']==b[0]['tokens'],'tokens differ'
 for index,label in ((0,'buffer bytes'),(1,'state metadata'),(2,'inventory')):
  assert a[1][index]==b[1][index],(label,[k for k in a[1][index] if a[1][index][k]!=b[1][index].get(k)])
 assert a[2]==b[2],'shared stream bytes differ'

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert not list((P/'selections').glob('*/screen-seal.json'))
 libraries=subprocess.check_output(['readelf','-d',str(B/'gnu-host/own-rt-iq3')],text=True).lower()
 assert not any(x in libraries for x in ('libsycl','libze_loader','libur_loader','libopencl'))
 subprocess.run([str(B/'flat-fixture'),str(E)],check=True)
 parent=run('target-packet56',None,P.parent/'packet56-draft-prefix/build/gnu-host/own-rt-iq3')
 assert len(parent[0]['fixtures'])==96 and len(parent[0]['tokens'])==24
 rows=[];expected=bytearray();actual=bytearray()
 for choice in CHOICES:
  reference=run(choice+'-reference',choice)
  equal(reference,parent);assert reference[0]['fixtures']==parent[0]['fixtures']
  tokens=reference[0]['tokens']
  for kind,guesses in [('hits',tokens[:-1]),('misses',[(x+1)%16 for x in tokens[:-1]]),('mixed',[x if i%3 else (x+1)%16 for i,x in enumerate(tokens[:-1])])]:
   candidate=run(choice+'-'+kind,choice,guesses=guesses)
   equal(candidate,reference);assert candidate[0]['fixtures']==reference[0]['fixtures']
   for key,value in sorted(reference[1][0].items()):expected.extend(value);actual.extend(candidate[1][0][key])
   rows.append(candidate[0])
  # Cross a context-preparation bucket using a deterministic supplied prompt.
  prompt=([2,5,3,7,1]*7)[:31]
  boundary=run(choice+'-bucket-reference',choice,prompt=prompt,count=5,retain='none')
  mixed=run(choice+'-bucket-mixed',choice,prompt=prompt,count=5,retain='none',guesses=[x if i%2 else (x+1)%16 for i,x in enumerate(boundary[0]['tokens'][:-1])])
  equal(mixed,boundary);rows.append(mixed[0])
  # Terminal rollback from no writes, partial prefix, and completed half.
  terminal=run(choice+'-terminal-reference',choice,count=1,retain='none')
  timing=[json.loads(x) for x in (terminal[3]/'rank0/timings.jsonl').read_text().splitlines()]
  n=timing[-1]['launches_issued']
  for cut in (0,1,n//2,n,n+1):
   candidate=run(choice+'-terminal-'+str(cut),choice,count=2,guesses=[(tokens[0]+1)%16],eos=[tokens[0]],cut=cut,retain='none')
   equal(candidate,terminal);rows.append(candidate[0])
  # A confirmed redo can be abandoned. Fall back before any dump observes it.
  def abandoned(t,result):
   position=5+len(result['tokens'])-1;guess=(result['tokens'][-1]+1)%16
   t.call(0,pipeline.HALF,token=guess,position=position,fixture=len(result['tokens'])+1,speculative=1)
   t.call(0,pipeline.ROLLBACK,token=result['tokens'][-1],position=position,fixture=len(result['tokens'])+1,speculative=1)
  abandoned_run=run(choice+'-abandoned',choice,count=1,retain='none',cut=n+1,after=abandoned)
  equal(abandoned_run,terminal);assert abandoned_run[0]['snapshot']['redo_fallbacks']==1;rows.append(abandoned_run[0])
  reset=run(choice+'-reset',choice,guesses=tokens[:-1],reset_repeat=True)
  equal(reset,reference);assert reset[0]['fixtures']==reference[0]['fixtures'];rows.append(reset[0])
  for which in (0,1,2):
   def corrupt(t,result,which=which):
    position=5+len(result['tokens'])-1
    t.call(0,pipeline.HALF,token=(result['tokens'][-1]+1)%16,position=position,fixture=len(result['tokens'])+1,speculative=1)
    t.call(0,12,token=which);t.call(0,pipeline.ROLLBACK)
   negative=run(choice+'-negative-'+str(which),choice,count=1,retain='none',cut=n+1,after=corrupt)
   assert negative[1][:3]!=terminal[1][:3],('negative corruption hidden',choice,which)
   negative[0]['expected_state_mismatch']=True;negative[0]['corruption_kind']=which;rows.append(negative[0])
  print(choice,'PASS',flush=True)
 assert expected==actual and expected
 (E/'expected.bin').write_bytes(expected);(E/'actual.bin').write_bytes(actual)
 build=json.loads((P/'build-device-receipt.json').read_text())
 sources=dict(build['sources'])
 for leaf in ('cpu_gate.py','pipeline.py','prepare_selections.py','flat_fixture.cpp','evidence/flat-fixture.json'):
  sources[str((P/leaf).relative_to(ROOT))]=sha(P/leaf)
 save(E/'cpu-gates.json',dict(passed=True,device_executed=False,cases=len(rows),selections=list(CHOICES),rows=rows))
 sources[str((E/'cpu-gates.json').relative_to(ROOT))]=sha(E/'cpu-gates.json')
 save(E/'fixture.json',dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,
  changed_class='Speculative recurrent destination rotation, flat capture/restore transport and overlapped restore bookkeeping; actual engine hit/miss/cancel/terminal/abandoned-redo bytes',
  command=[sys.executable,'-B',str(P/'cpu_gate.py')],build_receipt_sha256=sha(P/'build-device-receipt.json'),sources=sources,
  expected=dict(path='evidence/expected.bin',sha256=sha(E/'expected.bin')),actual=dict(path='evidence/actual.bin',sha256=sha(E/'actual.bin')),bytes_compared=len(expected),
  target_fixture_count=96,target_tokens=24,selections=list(CHOICES),qualification='CPU synthetic state proof; production device packet49 oracle screen pending'))
 print('CPU gates PASS',len(rows),len(expected),'bytes',flush=True)
if __name__=='__main__':main()
