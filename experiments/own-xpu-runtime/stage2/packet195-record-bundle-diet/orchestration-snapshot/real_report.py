"""Read-only report replay on packet190's real record-chain windows (the 62.345282 tok/s chain, read in place under its
git-ignored build/) and packet194's two lane-B rows (s194 recomputation). packet136's chain output was archived off the
root disk on 2026-10-22 (stage2/DISK-CLEANUP-20261022.md), so packet195 replays the current record chain instead."""
import json,math,os,resource,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet'
sys.path.insert(0,str(P))
def main():
 def audit(event,args):
  if event=='open' and isinstance(args[0],(str,bytes)):
   path=Path(os.fsdecode(args[0])).absolute()
   if str(path).startswith('/dev/dri/'):raise PermissionError('device open forbidden')
   if (args[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and path!=Path('/dev/null'):raise PermissionError('report writes forbidden')
  if event in ('subprocess.Popen','os.system','os.exec','os.kill','os.killpg','os.posix_spawn'):raise PermissionError('report execution forbidden')
 sys.addaudithook(audit)
 import window,suite,suite_metrics
 from stream_gate195 import check
 from bracket_gate import verify
 from reuse_build import sha
 chain=P.with_name('packet190-record-bundle-k3x')/'build/device-cards01-p190-a';rows=[];pins={}
 assert (chain/'WS128/run/summary.json').exists(),'packet190 record chain output is not on disk: '+str(chain)
 for name in ('WS','WSs','WS128x','WS128'):
  path=chain/name/'run/summary.json';old=json.loads(path.read_text());new=suite.summarize(old['rows'],old['complete'])
  assert new['passed'] and new['complete'] and new['observed_prompts']==12
  key='class_balanced_tok_s_1_100_intervals_after_ttft';assert new[key]==old[key],name+' report metric changed'
  for r in old['rows']:
   receipt=chain/name/'run'/r['receipt'];result=json.loads(receipt.read_text());check(result)
   oracle=P/'oracle/results'/r['prompt_id']/'result.json';tokens=json.loads(oracle.read_text())['tokens'];assert result['tokens']==tokens[:len(result['tokens'])]
   pins[str(receipt.relative_to(ROOT))]=sha(receipt)
  pins[str(path.relative_to(ROOT))]=sha(path)
  rows.append(dict(window=name,passed=True,exact=12,rate=new[key]['median']))
 assert abs(next(r['rate'] for r in rows if r['window']=='WS128')-62.345281904743764)<1e-12,'packet190 WS128 replay does not reproduce the record 62.345281904743764'
 bracket=verify()
 print(json.dumps(dict(passed=True,device_executed=False,model_read=False,real_evidence=True,chain=rows,chain_source=str(chain.relative_to(ROOT)),record_reproduced=62.345281904743764,bracket=bracket,evidence=pins,strict512=False)))
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
