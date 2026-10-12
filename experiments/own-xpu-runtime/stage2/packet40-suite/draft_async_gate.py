#!/usr/bin/env python3
"""Actual CPU Engine: native asynchronous draft vs synchronous target oracle."""
import argparse,json,time
from pathlib import Path
from pipeline import P,parser,sha,Transport,Controller,NativeController,Draft
import suite
from storage import admit,discard

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--binary',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 admit(150_000_000);root=P/'build'/('draft-async-'+str(time.time_ns()));root.mkdir();rows=[]
 def target_state(dest):
  files=suite.retained_state(dest);state={}
  for name,row in files.items():
   if '/state-2147483647/' in name:state[name]=row['sha256']
   elif name.endswith('/request-state-inventory.json'):
    inventory=json.loads(row['text']);inventory.pop('logical_event',None)
    state[name]=inventory
  assert state,'no full target state evidence'
  return state
 def invoke(name,controller='native',draft='mtp',fault='none',retention='none'):
  dest=root/name;dest.mkdir();args=parser().parse_args(['--binary',str(a.binary.resolve()),'--output',str(dest),'--mini','--tokens','8','--draft',draft,'--draft-fault',fault,'--controller',controller,'--retain-steps',retention,'--native-nice','19'])
  args.dispatch=P/'dispatch-p38.json';transport=None
  try:
   transport=Transport(args,dest)
   cls=NativeController if controller=='native' else Controller
   result=cls(transport,Draft(draft),True,False).run([2,5,3,7,1],8,())
   suite.reset(transport,dest/'after')
   transport.close(True);transport=None
   return dest,result
  finally:
   if transport is not None:transport.stop('draft gate exception');transport.close(False)
 try:
  baseline,reference=invoke('reference',draft='none');expected=target_state(baseline);discard(baseline)
  for controller in ('python','native'):
   for fault in ('none','wrong','suppress','garbage','error','late-error','stall'):
    for retention in ('none','1-8'):
     dest,result=invoke(controller+'-'+fault+'-'+retention,controller,fault=fault,retention=retention)
     actual=target_state(dest);assert result['tokens']==reference['tokens'],(controller,fault,retention,'tokens')
     assert actual==expected,(controller,fault,retention,'state')
     choices=json.loads((dest/'rank1/draft-kernel-choices.json').read_text());assert choices['target_mutable_aliases']==0
     rows.append(dict(controller=controller,fault=fault,retain_steps=retention,target_state_files=len(actual),tokens=len(result['tokens']),stats=result['stats']))
     discard(dest)
  receipt=dict(passed=True,device_executed=False,cases=len(rows),binary_sha256=sha(a.binary),rows=rows,comparison=['every emitted token','both ranks complete target state hashes including alternate banks','standalone target mutable allocations (logical launch counter excluded)','draft mutable allocation isolation'],python_mode='synchronous reference',native_mode='asynchronous publication')
  a.output.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
 finally:discard(root)
if __name__=='__main__':main()
