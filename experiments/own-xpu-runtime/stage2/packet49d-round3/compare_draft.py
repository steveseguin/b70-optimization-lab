"""Full-vocabulary per-position distances to packet31 captured reference samples."""
import json,sys,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;Q=P.parent/'packet31-mtp-acceptance'
sys.path.insert(0,str(Q))
import torch,numpy as np
import draft_reference
from draft_reference import SafeStore,Bindings,BF
torch.set_num_threads(1);torch.set_num_interop_threads(1)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
@torch.inference_mode()
def main(name):
 run=json.loads((P/('capture-run-'+name+'.json')).read_text());assert run['passed'];out=Path(run['output'])
 rows=[json.loads(s) for s in (out/'draft-capture.jsonl').read_text().splitlines()]
 source=Q/'build'/name
 reference_build=Q/'build'
 if not source.exists():source=P/'build/reference31/build'/name;reference_build=source.parent;draft_reference.P=reference_build.parent
 reference=[json.loads(s) for s in (reference_build/(name+'-draft.jsonl')).read_text().splitlines()]
 bindings=Bindings(SafeStore());report=[]
 for ref in reference:
  pos=ref['draft_position'];raw=(out/f'row-{pos}/logits.bf16').read_bytes();logits=(np.frombuffer(raw,dtype='<u2').astype(np.uint32)<<16).view(np.float32)
  token=int(np.argmax(logits));assert token==rows[pos]['token'];record=dict(position=pos,generated_index=ref['generated_index'],target_token=ref['target_token'],draft_token=token,hit=token==ref['target_token'],logits_sha256=hashlib.sha256(raw).hexdigest(),references={})
  for variant in ('mtp_fp8_iq3','mtp_int8_iq3'):
   path=source/f"sample-{ref['generated_index']}-{variant}.bf16";sample=torch.frombuffer(bytearray(path.read_bytes()),dtype=BF).reshape(1,2560)
   expected=bindings.logits(sample).numpy();delta=logits.astype(np.float64)-expected.astype(np.float64)
   expected_token=int(np.argmax(expected));assert expected_token==ref['sources'][variant]['draft_token']
   record['references'][variant]=dict(token=expected_token,agrees=token==expected_token,hit=expected_token==ref['target_token'],logit_max_abs=float(np.max(np.abs(delta))),logit_rms=float(np.sqrt(np.mean(delta*delta))),logit_l2=float(np.linalg.norm(delta)),sample_sha256=sha(path))
  report.append(record);print(name,record['generated_index'],token,record['hit'],flush=True)
 total=len(report);assert total==64
 result=dict(passed=True,device_executed=False,prompt=name,positions=total,binary_sha256=run['binary_sha256'],target_acceptance=sum(r['hit'] for r in report)/total,rows=report)
 result['references']={v:dict(acceptance=sum(r['references'][v]['hit'] for r in report)/total,token_agreement=sum(r['references'][v]['agrees'] for r in report)/total) for v in ('mtp_fp8_iq3','mtp_int8_iq3')}
 (P/('agreement-'+name+'.json')).write_text(json.dumps(result,indent=2)+'\n');bindings.iq.close()
if __name__=='__main__':main(sys.argv[1])
