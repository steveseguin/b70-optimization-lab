from pathlib import Path
import json,hashlib,io,importlib.util,struct
repo=Path('/home/steve/llm-optimizations');own=repo/'experiments/own-xpu-runtime';base=own/'research/pp4-review-2026-10-28';census=json.loads((own/'gsq-rco-iq3s/metadata/new-census.json').read_text());sh=census['shards'][0];path=Path(sh['path']);before=path.stat();raw=path.open('rb').read(sh['header_bytes_read']);assert hashlib.sha256(raw).hexdigest()==sh['header_sha256'];assert before==path.stat()
parser=own/'stage1/packet1b/loaders/headers.py';s=importlib.util.spec_from_file_location('lookup_header',parser);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);r=m.Reader(io.BytesIO(raw),len(raw));assert r.read(4)==b'GGUF'and r.number('I')==3;nt,nm=r.number('Q'),r.number('Q');meta={}
for _ in range(nm):
 key=r.string();kind=r.number('I');assert key not in meta;meta[key]=m._metadata(r,kind)
mul=meta['qwen4exp.ple.layer_multipliers'];sizes=meta['qwen4exp.ple.head_vocab_sizes'];offsets=meta['qwen4exp.ple.head_offsets'];eos=meta['tokenizer.ggml.eos_token_id'];assert len(mul)==3 and len(sizes)==len(offsets)==16
matrix=json.loads((base/'realistic-matrix-registration.json').read_text());suite=next(x for x in matrix['matrix']if x['case']=='short-realistic-decode')['inputs'];longpath=Path('/dev/shm/sc117-reference-route-long512-plans-20261028-r1/control-plan.json');cases=[('long121854',json.loads(longpath.read_text())['prompt_tokens'],str(longpath))]+[(x['id'],json.loads((repo/x['path']).read_text()),x['path'])for x in suite];allids=set();allple=set();rows=[]
def count(tokens):
 ids=set(tokens);ple=set();h0=h1=eos
 for token in tokens:
  old0=eos if h1==eos else h0
  for n in (2,3):
   bits=((token*mul[0])&((1<<64)-1))^((h1*mul[1])&((1<<64)-1))
   if n==3:bits^=(old0*mul[2])&((1<<64)-1)
   v=bits-(1<<64)if bits>=(1<<63)else bits
   for h in range(8):
    i=(n-2)*8+h;ple.add(v%sizes[i]+offsets[i])
  h0,h1=h1,token
 return ids,ple
for name,tokens,source in cases:
 ids,ple=count(tokens);allids|=ids;allple|=ple;payload=len(ids)*1360+len(ple)*90;rows.append(dict(id=name,source=source,tokens=len(tokens),packed_prompt_sha256=hashlib.sha256(struct.pack('<'+'i'*len(tokens),*tokens)).hexdigest(),unique_token_ids=len(ids),unique_PLE_ids=len(ple),embedding_packed_bytes=len(ids)*1360,PLE_packed_bytes=len(ple)*90,prompt_packed_staging_bytes=payload,prompt_plus_max512_decode_upper_bytes=payload+512*(1360+16*90),decode_assumption='Each new target input consumes <=one embedding row +16 new PLE rows; pessimistically no reuse. This bound excludes rejected speculative target inputs; see note.'))
d=dict(schema='ownrt.sparse-lookup-source-screen.v1',tested=False,model_header_sha256=sh['header_sha256'],model_payload_bytes_read=0,metadata=dict(multipliers=mul,sizes=sizes,offsets=offsets,eos=eos),table_bytes=29137853440,embedding_row_bytes=1360,PLE_row_bytes=90,F32_decoded_upload_bytes_per_target_token=20480,cases=rows,union=dict(unique_token_ids=len(allids),unique_PLE_ids=len(allple),packed_prompt_bytes=len(allids)*1360+len(allple)*90),scope='Counts from frozen prompts and exact native unsigned64 bitpattern/signed64 modulo hash; no source weight payload read, kernel or model run.')
(base/'lookup-sparse-staging-screen.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d,indent=2))
