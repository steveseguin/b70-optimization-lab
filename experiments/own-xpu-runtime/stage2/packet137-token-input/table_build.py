"""CPU-only, bounded streaming table creation. No GPU imports or discovery."""
import argparse,hashlib,importlib.util,json,os,resource,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];BASE=P.with_name('packet124c-record-bundle');B=P/'build/table'
OUT=Path('/home/steve/own-xpu-runtime-results/packet137-token-input')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def admission():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=25_000_000_000
 assert sum(p.stat().st_size for p in (P/'build').rglob('*') if p.is_file() and not p.is_symlink())<300_000_000

def authenticate():
 inp=BASE/'build/input';meta=json.loads((inp/'input.json').read_text());root=Path(meta['model_dir'])
 for name in ('identity.tsv','plan.tsv'):assert sha(inp/name)==meta['files'][name]
 for line in (inp/'identity.tsv').read_text().splitlines():
  n,*v=line.split();s=(root/n).stat();assert list(map(int,v))==[s.st_size,s.st_dev,s.st_ino,s.st_mtime_ns,s.st_ctime_ns],n
 wanted={'mtp.pre_fc_norm_embedding.weight':'norm.bf16','mtp.fc_embedding.weight':'projection.bf16'};draft=Path('/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8');pins={}
 for line in (P/'mtp-manifest.tsv').read_text().splitlines():
  fields=line.split();name=fields[0]
  if name not in wanted:continue
  n,f,offset,size,dtype,rows,cols,digest,filebytes,dev,ino,mtime,ctime=fields
  path=draft/f;s=path.stat();assert [s.st_size,s.st_dev,s.st_ino,s.st_mtime_ns,s.st_ctime_ns]==list(map(int,[filebytes,dev,ino,mtime,ctime]))
  with path.open('rb') as stream:stream.seek(int(offset));data=stream.read(int(size))
  assert hashlib.sha256(data).hexdigest()==digest
  dest=B/wanted[name];dest.write_bytes(data);pins[name]=dict(path=str(path),offset=int(offset),bytes=int(size),sha256=digest)
 assert len(pins)==2
 return root,inp,pins

def main():
 a=argparse.ArgumentParser();a.add_argument('--rows',type=int,default=248320);a.add_argument('--compile-only',action='store_true');args=a.parse_args()
 admission();B.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
 from compile_turn import turn
 commands=[]
 for label,compiler in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  cmd=[compiler,'-std=c++20','-O3','-fno-fast-math','-ffp-contract=off','-fopenmp','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),str(P/'table_cpu.cpp'),str(P.parent/'packet2/loader/gguf.cpp'),'-o',str(B/label)]
  with turn(),(B/(label+'-build.log')).open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600)
  commands.append(cmd);print(label+' compiled',flush=True)
 if args.compile_only:return
 root,inp,pins=authenticate();table=OUT/('draft-embedding.bf16' if args.rows==248320 else 'pilot-'+str(args.rows)+'.bf16');assert not table.exists(),table
 partial=table.with_suffix('.partial');assert not partial.exists(),partial
 runs=[]
 for label,mode in [('GNU','generate'),('Intel','verify')]:
  admission();start=time.monotonic();cmd=[str(B/label),mode,str(root),str(inp/'identity.tsv'),str(inp/'plan.tsv'),str(B/'norm.bf16'),str(B/'projection.bf16'),str(partial),str(args.rows)]
  with (B/(label+'-'+str(args.rows)+'.log')).open('w') as f:
   subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=5400)
  runs.append(dict(compiler=label,command=cmd,seconds=time.monotonic()-start,binary_sha256=sha(B/label),log_sha256=sha(B/(label+'-'+str(args.rows)+'.log'))));print(label+' replay complete',flush=True)
 assert partial.stat().st_size==args.rows*5120
 os.chmod(partial,0o444);partial.rename(table)
 sources={str(p.relative_to(ROOT)):sha(p) for p in (P/'table_cpu.cpp',P/'table_build.py',P/'token_input.hpp',P/'kernels.hpp',P/'p28/dense.hpp',P/'mtp-manifest.tsv',inp/'identity.tsv',inp/'plan.tsv')}
 row=dict(passed=True,complete=args.rows==248320,device_executed=False,rows=args.rows,bytes=table.stat().st_size,path=str(table),sha256=sha(table),sources=sources,pins=pins,runs=runs,commands=commands,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
 save(P/'evidence'/('table.json' if row['complete'] else 'table-pilot.json'),row);print(json.dumps({k:row[k] for k in ('path','sha256','rows','max_rss_kib')}),flush=True)
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
