"""Freeze independent token inputs before any acceptance measurements."""
import hashlib,json,os,resource,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 rule=json.loads((P/'preregistration.json').read_text())
 sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/stage1/packet1b'))
 from loaders.headers import gguf_header
 sys.path.insert(0,str(ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle'))
 from tokenizer import Tokenizer
 authority=json.loads((P.parent/'packet49c-round2/build/input/input.json').read_text())
 model=Path(authority['model_dir']);shard=next(model.glob('*00001-of-00003.gguf'))
 with shard.open('rb') as f:header=gguf_header(f,shard.stat().st_size)
 with shard.open('rb') as f:assert sha(f.read(header['header_bytes_read']))==authority['header_sha256']
 tokenizer=Tokenizer(header['metadata']);prompts=[]
 for i,entry in enumerate(rule['sources']):
  raw=subprocess.check_output(['git','show',rule['source_commit']+':'+entry['path']],cwd=ROOT,stdin=subprocess.DEVNULL)
  assert sha(raw)==entry['sha256'] and len(raw)==entry['bytes']
  tokens=tokenizer.encode(raw.decode());assert tokenizer.decode(tokens)==raw.decode() and len(tokens)>=256
  for side,ids in [('first',tokens[:128]),('last',tokens[-128:])]:
   prompts.append(dict(prompt_id=f'independent-{i+1}-{side}',source=entry,side=side,tokens=ids,token_sha256=sha(json.dumps(ids,separators=(',',':')).encode()),output_cap=128))
 assert len({tuple(p['tokens']) for p in prompts})==10
 result=dict(schema='lab.packet129.independent-inputs.v1',preregistration_sha256=sha((P/'preregistration.json').read_bytes()),header_sha256=authority['header_sha256'],tokenizer_sha256=sha((ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/tokenizer.py').read_bytes()),prompts=prompts)
 dest=P/'calibration/inputs.json'
 if dest.exists():assert json.loads(dest.read_text())==result,'independent corpus cannot be retuned'
 else:dest.write_text(json.dumps(result,indent=2)+'\n')
 print('10 independent prompts frozen; benchmark suite unused')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
