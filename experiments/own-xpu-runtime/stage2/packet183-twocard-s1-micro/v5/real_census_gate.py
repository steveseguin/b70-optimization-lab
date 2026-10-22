"""Packet183 real-weight S1 census: every expanded Q6_K tensor of the model, CPU only.

Lean real-model gate (~3.3 GB of Q6_K payload read once, bounded 8 MiB chunks,
page cache dropped per chunk, single thread). GGUF directories come from the
lab's own header parser (vendored byte-for-byte as gguf_headers.py from
stage1/packet1b/loaders/headers.py); the model directory is the one the suite
input bundles admit. Selected: every Q6_K tensor except token_embd.weight (a
bounded-row lookup the engine never expands). The native tool
(native/real_census.cpp) proves on the real bytes what the device arm relies
on: every fp16 d is finite and every stored FP32 scale word equals the
recomputed metadata product; sampled real rows give bit-identical S1 and
production lanes. Writes evidence/real-census.json.
"""
import json,os,resource,subprocess,tempfile
from pathlib import Path
from p183_v5_build_engine import P,LOCAL,ROOT,B,CHECKED,sha,save,run,limits
from gguf_headers import gguf_header,gguf_shards

ADMITTED=Path('/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS')
S1_CLASSES={'attn_qkv.weight':'gdn.qkv p33.dense.segment','attn_gate.weight':'gdn.z p33.dense.segment','attn_q.weight':'qsa.qgate p33.dense.segment',
 'ssm_out.weight':'attention p49c attention_combine','attn_output.weight':'attention p49c attention_combine',
 'ffn_gate_shexp.weight':'small.ffn.q6 p49d','ffn_up_shexp.weight':'small.ffn.q6 p49d',
 'output.weight':'logits p33.dense.segment (rank1 prefix 202240 rows + draft prefix); rank0 suffix stays expanded',
 'attn_k.weight':'qsa.k p28.dense.rows4 (not S1)','attn_v.weight':'qsa.v p28.dense.rows4 (not S1)'}

def model_dir():
 from common import D,ROOT as R
 entry=D.oracle_inputs()['prompts'][0];model=Path(json.loads((R/entry['input_bundle']/'input.json').read_text())['model_dir']).resolve()
 assert model==ADMITTED.resolve(),'unadmitted model path'
 return model

def main():
 limits();model=model_dir();shards=sorted(model.glob('*.gguf'));assert len(shards)==3,shards
 parsed=[]
 for path in shards:
  with path.open('rb') as f:parsed.append(gguf_header(f,path.stat().st_size))
 gguf_shards(parsed)
 rows=[]
 for path,p in zip(shards,parsed):
  for name,t in p['tensors'].items():
   if t['type']!='Q6_K' or name=='token_embd.weight':continue
   K=t['dimensions'][0];n=t['bytes']//(K//256*210);assert n*(K//256*210)==t['bytes']
   rows.append((name,str(path),t['file_offsets'][0],K,n))
 rows.sort()
 assert len(rows)==249 and all(K in (2560,6144) for _,_,_,K,_ in rows),(len(rows),{r[3] for r in rows})
 out=B/'real-census';out.mkdir(exist_ok=True);binary=out/'real-census'
 prior=json.loads((P/'engine-commands.json').read_text())
 args=list(next(r['command'] for r in prior if r['name']=='gnu-host-entry-main'));args=args[1:args.index('-o')];i=args.index('-c');del args[i:i+2]
 run(['/usr/bin/g++',*[a for a in args if a!='-fopenmp'],P/'native/real_census.cpp','-o',binary],'real-census-compile')
 table=out/'tensors.tsv';table.write_text(''.join('\t'.join(map(str,r))+'\n' for r in rows))
 cp=subprocess.run(['nice','-n','19','ionice','-c','3',str(binary),str(table)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=3600)
 assert cp.returncode in (0,3),cp.stderr[-4000:]
 result=json.loads(cp.stdout);assert result['passed'] and result['nonfinite_d']==0 and result['word_mismatches']==0,result
 assert result['tensors']==len(rows) and result['lane_checks']>0
 by_class={}
 for t in result['per_tensor']:
  key=next((k for k in S1_CLASSES if t['name'].endswith(k)),'other');c=by_class.setdefault(key,dict(route=S1_CLASSES.get(key,'unmapped'),tensors=0,rows=0,groups=0));c['tensors']+=1;c['rows']+=t['rows'];c['groups']+=t['groups']
 assert 'other' not in by_class,by_class.get('other')
 provenance=[dict(name='gguf_headers.py',parent_relpath='experiments/own-xpu-runtime/stage1/packet1b/loaders/headers.py',parent_digest=sha(ROOT/'experiments/own-xpu-runtime/stage1/packet1b/loaders/headers.py'),copy_equal=sha(P/'gguf_headers.py')==sha(ROOT/'experiments/own-xpu-runtime/stage1/packet1b/loaders/headers.py'))]
 shard_ids=[dict(name=s.name,bytes=s.stat().st_size) for s in shards]
 save(P/'evidence/real-census.json',dict(passed=True,device_executed=False,model_read=True,model_payload_read='Q6_K tensors only (expanded set), once, page cache dropped per chunk',
   model_dir=str(model),model_shards=shard_ids,tensor_count=len(rows),excluded=['token_embd.weight (bounded-row lookup, never expanded)'],
   census={k:result[k] for k in ('rows','blocks','groups','nonfinite_d','word_mismatches','packed_bytes_read','sampled_rows','lane_checks')},
   by_class=by_class,binary_sha256=sha(binary),table_sha256=sha(table),per_tensor_count=len(result['per_tensor']),provenance=provenance,
   sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'real_census_gate.py',P/'native/real_census.cpp',P/'gguf_headers.py',CHECKED/'s1_lanes.hpp')}))
 (out/'per-tensor.json').write_text(json.dumps(result['per_tensor'],indent=1)+'\n')
 print('real census:',result['tensors'],'tensors',result['groups'],'groups, 0 non-finite d, 0 word mismatches,',result['lane_checks'],'real-row lane checks')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
