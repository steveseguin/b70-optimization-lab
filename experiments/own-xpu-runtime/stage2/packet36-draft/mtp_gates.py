"""CPU-only provider and target state isolation gates."""
import json,time,hashlib,sys
from pathlib import Path
from pipeline import P,parser,run,sha
from gates import fixture_hashes,states
B=P/'build'
def main(mode):
 binary=B/mode/'own-rt-iq3';root=B/('mtp-gates-'+mode+'-'+str(time.time_ns()));root.mkdir();rows=[]
 def invoke(name,draft='mtp',fault='none',extra=()):
  out=root/name;a=parser().parse_args(['--binary',str(binary),'--output',str(out),'--mini','--tokens','8','--draft',draft,'--draft-fault',fault,'--dump-state',*extra]);a.dispatch=P/'dispatch-all-new.json'
  r=run(a);return out,r
 base,ref=invoke('reference','none');fx=fixture_hashes(base);state=states(base)
 reference_cache=None
 for fault in ('none','wrong','suppress','garbage','error','late-error','stall'):
  out,r=invoke(fault,fault=fault);assert r['tokens']==ref['tokens'] and fixture_hashes(out)==fx and states(out)==state
  cache={f.name:sha(f) for f in (out/'rank1/draft-final-state').iterdir()}
  if fault=='none':reference_cache=cache
  if fault in ('wrong','suppress','garbage'):assert cache==reference_cache
  if fault!='none':assert r['diagnostic'] and r['decode_tok_s'] is None
  rows.append(dict(fault=fault,tokens=8,fixtures=len(fx),full_target_state_files=len(state),draft_cache=cache,stats=r['stats']))
 result=dict(passed=True,device_executed=False,binary_sha256=sha(binary),cases=len(rows),rows=rows,root=str(root))
 (P/('mtp-gates-'+mode+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'gnu-host')
