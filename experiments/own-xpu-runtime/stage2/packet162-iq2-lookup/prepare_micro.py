"""Bounded CPU extraction; never read GGUF alongside a packet58 unit."""
import hashlib,json,subprocess,os,shutil
from pathlib import Path
from analyze import limits
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
LANE=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1'

def quiet():
 text=subprocess.check_output(['systemctl','--user','list-units','--state=active,activating','--no-legend','--plain','screen-packet58*','packet58*'],text=True)
 if text.strip():raise RuntimeError('packet58 active: no GGUF reads permitted')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 limits();assert shutil.disk_usage('/').free >= 27_000_000_000, 'CPU preparation floor';quiet();out=P/'build/micro-inputs';out.mkdir(exist_ok=False)
 admission=json.loads((LANE/'admission-receipt.json').read_text());assert admission['passed']
 census=json.loads((LANE/'tensor-census.json').read_text())['tensors']
 records=[]
 for layer in (0,24):
  ids=list(range(10)) if layer==0 else [(37*i+19)%512 for i in range(10)]
  path=out/f'layer{layer}.bin';sources=[]
  with path.open('xb') as dst:
   for kind in ('gate','up'):
    t=next(t for t in census if t['name']==f'blk.{layer}.ffn_{kind}_exps.weight')
    assert t['type_id']==22 and t['dimensions']==[2560,640,512]
    src=Path(admission['model_dir'])/Path(t['shard']).name
    item=next(v for v in admission['files'] if Path(v['path']).name==src.name)
    stat=src.stat();sig=dict(bytes=stat.st_size,ctime_ns=stat.st_ctime_ns,device=stat.st_dev,inode=stat.st_ino,mtime_ns=stat.st_mtime_ns)
    assert sig==item['after'],'admitted GGUF changed'
    with src.open('rb') as f:
     for expert in ids:
      quiet();offset=t['file_offsets'][0]+expert*640*820;f.seek(offset);raw=f.read(640*820);assert len(raw)==640*820;dst.write(raw)
      sources.append(dict(tensor=t['name'],shard=src.name,expert=expert,offset=offset,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
  records.append(dict(shape=f'layer{layer}',path=str(path.relative_to(ROOT)),sha256=sha(path),expert_ids=ids,rows=640,columns=2560,streams=2,source_rows=sources))
 (P/'evidence/micro-prep/inputs.json').write_text(json.dumps(dict(passed=True,device_executed=False,representative_fixed_experts=True,slot_remap='original selected IDs -> compact slots 0..9; arithmetic unchanged',admission_sha256=sha(LANE/'admission-receipt.json'),census_sha256=sha(LANE/'tensor-census.json'),records=records),indent=2)+'\n')
 print('prepared two real gate/up shapes; 20,992,000 GGUF bytes; no device')
if __name__=='__main__':main()
