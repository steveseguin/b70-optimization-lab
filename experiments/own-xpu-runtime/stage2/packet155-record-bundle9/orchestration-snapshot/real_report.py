"""Read-only report replay on real packet136 windows and packet153 bracket."""
import json,math,os,resource,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet155-record-bundle9'
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
 from stream_gate155 import check
 from bracket_gate import verify
 from reuse_build import sha
 chain=P.with_name('packet136-record-bundle')/'build/device-cards01-a';rows=[];pins={}
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
 bracket=verify()
 print(json.dumps(dict(passed=True,device_executed=False,model_read=False,real_evidence=True,chain=rows,bracket=bracket,evidence=pins,strict512=False)))
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
