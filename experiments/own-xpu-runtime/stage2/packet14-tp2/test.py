#!/usr/bin/env python3
import argparse,importlib.util,json,subprocess,sys,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('p13test',HERE.parent/'packet13-integrate/test.py');ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
def main():
 p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--control',type=Path,required=True);a=p.parse_args()
 for binary in [a.binary,a.control]:
  dynamic=subprocess.check_output(['readelf','-d',binary],text=True).lower()
  assert not any(x in dynamic for x in ['libsycl','libze_loader','libur_loader','libopencl'])
 scratch=HERE/'build/tests';scratch.mkdir(exist_ok=False)
 results=[]
 for count in [1,3,8]:
  token=scratch/'input.txt';token.write_text('2\n')
  baseline=None
  for mode,binary,cards in [('p13',a.control,1),('single',a.binary,1),('tp2',a.binary,2)]:
   out=scratch/f'{mode}-{count}'
   cmd=[str(binary),'--mini','--card','0','--cards',str(cards),'--memory','tp2-streaming' if cards==2 else 'layer-streaming','--tokens',str(count),'--input',str(token),'--output',str(out)]
   run=subprocess.run(cmd,text=True,capture_output=True,timeout=120)
   assert run.returncode==0,run.stderr
   actual=json.loads((out/'buffers.json').read_text())
   oracle=ref.Reference();oracle.step(2);tokens=[]
   for i in range(count):
    next=int(oracle.buffers['next_token'][0]);tokens.append(next)
    if next==15:break
    if i+1<count:oracle.step(next)
   expected={k:v.reshape(-1).view(ref.np.uint32).tolist() for k,v in oracle.buffers.items()}
   assert actual==expected,[k for k in expected if actual.get(k)!=expected[k]]
   if baseline is None:baseline=actual
   assert actual==baseline
   receipt=json.loads((out/'receipt.json').read_text());assert receipt['passed'] and receipt['tokens']==tokens and not receipt['device_executed']
   assert len(receipt['teardown'])==cards and all(t['safe_to_exit'] and not t['live_bytes'] and not t['in_flight'] for t in receipt['teardown'])
   results.append(dict(mode=mode,generated=count,buffers=len(actual),values=sum(map(len,actual.values())),exact=True))
 # Fresh process TP repeat.
 out=scratch/'repeat';cmd=[str(a.binary),'--mini','--card','0','--cards','2','--memory','tp2-streaming','--tokens','8','--input',str(token),'--output',str(out)]
 run=subprocess.run(cmd,capture_output=True,text=True);assert run.returncode==0,run.stderr
 assert (out/'buffers.json').read_bytes()==(scratch/'tp2-8/buffers.json').read_bytes()
 # Two KV heads, even GDN heads: compare all states at both pool boundaries.
 kv2_cases=[]
 for count in [1,4,8]:
  expected=None
  for mode,binary in [('control',a.control.parent/'kv2-control'),('single',a.binary),('tp2',a.binary)]:
   out=scratch/f'kv2-{mode}-{count}'
   args=['--mini'] if mode=='control' else ['--mini-kv2']
   args+=['--card','0','--tokens',str(count),'--input',str(token),'--output',str(out)]
   if mode=='tp2':args+=['--cards','2','--memory','tp2-streaming']
   run=subprocess.run([str(binary),*args],capture_output=True,text=True,timeout=120);assert run.returncode==0,run.stderr
   actual=json.loads((out/'buffers.json').read_text())
   if expected is None:expected=actual
   assert actual==expected,[k for k in expected if actual.get(k)!=expected[k]]
   kv2_cases.append(dict(mode=mode,generated=count,values=sum(map(len,actual.values())),exact=True))
 # Every mini tensor range is exhaustive and disjoint, or explicitly replicated.
 plan=json.loads((scratch/'tp2-8/plan.json').read_text())
 for tensor in plan['tensor_owners']:
  if tensor['placement'] in ('output-rows','expert-id'):
   left,right=tensor['ranges'];assert left['begin']==0 and left['end']==right['begin'] and right['end']>right['begin']
 for row in plan['request_buffers']:
  if row['name'].endswith('.state'):
   assert row['bytes']==(16 if row['card']==0 else 32)*2
 r=dict(passed=True,device_executed=False,integration_cases=results,kv2_cases=kv2_cases,fresh_process_repeat=True)
 (HERE/'cpu-tests.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
