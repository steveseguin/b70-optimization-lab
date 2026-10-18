"""Authenticate official MTP files against packet1 before making a load manifest."""
import hashlib,json,os
from pathlib import Path
P=Path(__file__).resolve().parent
MODEL=Path('/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(4*1024*1024):h.update(b)
 return h.hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 contract=P.parent/'packet1/tensor-contract.json';c=json.loads(contract.read_text())
 ts=[t for t in c['tensors'] if t['name'].startswith('mtp.')]
 assert len(ts)==3101
 names={t['shard'] for t in ts};files={}
 for r in c['shards']:
  if r['name'] not in names:continue
  f=MODEL/r['name'];before=f.stat();h=sha(f);after=f.stat()
  assert before==after and h==r['publisher_sha256'],str(f)
  files[r['name']]={'sha256':h,'bytes':after.st_size,'dev':after.st_dev,'ino':after.st_ino,'mtime_ns':after.st_mtime_ns,'ctime_ns':after.st_ctime_ns}
  print('authenticated',r['name'],flush=True)
 out=[];receipts={}
 for t in ts:
  f=MODEL/t['shard']
  with f.open('rb') as fd:fd.seek(t['file_offset']);raw=fd.read(t['bytes'])
  assert len(raw)==t['bytes'];h=hashlib.sha256(raw).hexdigest()
  r=files[t['shard']];shape=t['shape'];rows=shape[0];cols=shape[1] if len(shape)==2 else 1
  out.append(' '.join(map(str,[t['name'],t['shard'],t['file_offset'],t['bytes'],t['dtype'],rows,cols,h,r['bytes'],r['dev'],r['ino'],r['mtime_ns'],r['ctime_ns']])))
  receipts[t['name']]={**t,'sha256':h}
 (P/'mtp-manifest.tsv').write_text('\n'.join(out)+'\n')
 (P/'official-tensors.json').write_text(json.dumps({'revision':'bcd9f01ddc9cff2316eb84281bebcd5b058bddce','contract_sha256':sha(contract),'files':files,'tensors':receipts},indent=2)+'\n')
 print('tensors',len(ts),flush=True)
if __name__=='__main__':main()
