"""Bounded real mini-engine token/state comparisons, never a CPU model run."""
import hashlib,json,os,resource
from pathlib import Path
import pipeline
P=Path(__file__).resolve().parent
BASE=P.with_name('packet64-record-bundle')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 root=P/'fixture';root.mkdir(exist_ok=True)
 reports=[]
 def args(binary,out,depth=False,mode='none',script=None,force='none',tokens=8):
  argv=['--output',str(out),'--binary',str(binary),'--mini','--context','64','--tokens',str(tokens),'--controller','native','--draft',mode,'--draft-rank','1','--retain-steps','none','--seconds','120','--wait-seconds','120']
  if depth:argv+=['--depth2','--depth2-force',force]
  if script:argv+=['--script',str(script)]
  a=pipeline.parser().parse_args(argv);a.host_memory='resident';a.mini_prompt=([2,5,3,7,1] if tokens==8 else [6,1,4,2] if tokens==11 else [1,9,5]);return a
 # Each process handles only a four-layer tiny synthetic plan (h=16), <=11 tokens.
 for index,count in enumerate((8,11,32)):
  dest=root/f'fixture{index}'
  dest.mkdir(exist_ok=True)
  control=dest/'packet64';pipeline.run(args(BASE/'build/gnu-host/own-rt-iq3',control,tokens=count))
  reference=json.loads((control/'receipt.json').read_text());assert reference['passed']
  script=dest/'oracle-guesses.txt';script.write_text(' '.join(map(str,reference['tokens']))+'\n')
  for force in ('none','first','second'):
   out=dest/force;pipeline.run(args(P/'build/gnu-host/own-rt-iq3',out,True,'script',script,force,count))
   actual=json.loads((out/'receipt.json').read_text());assert actual['passed'] and actual['tokens']==reference['tokens']
   rowlog=[json.loads(x) for x in (out/'rank0/depth2-rows.jsonl').read_text().splitlines()]
   assert any(x.get('accepted_prefix')=={'none':2,'first':0,'second':1}[force] for x in rowlog)
   comparisons=0
   for rank in (0,1):
    left=control/f'rank{rank}/state-2147483647';right=out/f'rank{rank}/state-2147483647'
    for source in left.glob('*.bin'):
     assert source.read_bytes()==(right/source.name).read_bytes(),(index,force,rank,source.name)
     comparisons+=1
   reports.append(dict(fixture=index,tokens=count,forced=force,token_sha256=hashlib.sha256(bytes(actual['tokens'])).hexdigest(),state_byte_comparisons=comparisons,passed=True))
 # Exercise the actual recursive draft with private snapshot/restore, independently
 # of oracle scripting. Emitted tokens must still equal the target-only parent.
 out=root/'mtp';pipeline.run(args(P/'build/gnu-host/own-rt-iq3',out,True,'mtp',tokens=8))
 actual=json.loads((out/'receipt.json').read_text());ref=json.loads((root/'fixture0/packet64/receipt.json').read_text());assert actual['passed'] and actual['tokens']==ref['tokens']
 receipt=dict(schema='packet71.cpu-state-gate.v1',passed=True,device_executed=False,full_model_executed=False,arithmetic='iq3-p49-split32-v1',cases=reports,recursive_draft_tokens_exact=True,parent_binary_sha256=sha(BASE/'build/gnu-host/own-rt-iq3'),candidate_binary_sha256=sha(P/'build/gnu-host/own-rt-iq3'))
 (root/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
