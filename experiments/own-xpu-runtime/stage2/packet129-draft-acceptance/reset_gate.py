"""Three requests in one host-only rank pair: shadow/reset isolation."""
import json,time,shutil
from build_engine import P,B,ROOT,limits,save,sha
import pipeline,suite
def main():
 limits();suite.storage.admit=lambda *a,**k:limits()
 adapter=B/'mini-adapter';pipeline.P=adapter
 out=B/('cpu-shadow-reset-'+str(time.time_ns()));out.mkdir()
 args=pipeline.parser().parse_args(['--binary',str(B/'gnu-host/own-rt-iq3'),'--output',str(out),'--mini','--context','256','--tokens','24','--seconds','180','--wait-seconds','120','--native-nice','19','--draft','mtp','--draft-rank','1','--target-split','0','--controller','native','--timing','token','--retain-steps','1-24'])
 args.acceptance_shadow=True;args.host_memory='resident';args.selection_sha256=None
 ranks=out/'ranks';ranks.mkdir();transport=pipeline.Transport.__new__(pipeline.Transport);passed=False
 try:
  pipeline.Transport.__init__(transport,args,ranks);rows=[];expected=None
  for i in range(3):
   dest=out/f'request-{i}';suite.reset(transport,dest)
   result=suite.run_request(transport,args,[2,5,3,7,1],24)
   shadow=[json.loads(s) for s in (dest/'rank1/shadow-rows.jsonl').read_text().splitlines()]
   assert result['passed'] and len(shadow)==24
   assert all(s['restored_exact'] and s['production']==s['candidate'] for s in shadow)
   identity=dict(tokens=result['tokens'],shadow=shadow)
   if expected is None:expected=identity
   assert expected==identity
   rows.append(dict(request=i,tokens=24,shadow_proposals=len(shadow),output_sha256=result['output_token_sha256']))
  suite.reset(transport,out/'after');transport.close(True);passed=True
  save(P/'evidence/reset-gate.json',dict(passed=True,device_executed=False,model_lifetimes=1,requests=rows,sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('reset_gate.py','mtp.hpp','pipeline.py','suite.py')},binary_sha256=sha(B/'gnu-host/own-rt-iq3')))
  print('Three requests in one load: exact tokens, shadow proposals and reset state PASS')
 finally:
  if not passed and hasattr(transport,'stop_write') and not transport.closed:transport.stop('CPU reset gate failed');transport.close(False)
if __name__=='__main__':main()
