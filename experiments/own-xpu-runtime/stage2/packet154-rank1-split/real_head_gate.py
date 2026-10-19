"""Stream actual authenticated Unsloth prefix through Q4 and CPU head twice."""
import json,os,shlex,subprocess,resource
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits

def main():
 limits();base=P.parent/'suite-inputs-20261012/code-review';model=Path(json.loads((base/'input.json').read_text())['model_dir'])
 filename='Qwen3.8-Flash-Next-UD-IQ3_XXS-00002-of-00003.gguf';file=model/filename
 identity=next(line.split()[1:] for line in (base/'identity.tsv').read_text().splitlines() if line.startswith(filename+' '))
 def statcheck():
  st=file.stat();assert tuple(map(int,identity))==(st.st_size,st.st_dev,st.st_ino,st.st_mtime_ns,st.st_ctime_ns)
 statcheck()
 meta=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/metadata.json';m=json.loads(meta.read_text())
 # Metadata container shape is inspected explicitly; no inferred payload offset.
 entries=m['shards'];entry=next(r for r in entries if r['shard'].endswith(filename));offset=entry['data_start']
 import hashlib,sys
 sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/stage1/packet1b'))
 from loaders.headers import gguf_header
 with file.open('rb') as stream:header=gguf_header(stream,file.stat().st_size)
 assert header['data_start']==offset
 with file.open('rb') as f:assert hashlib.sha256(f.read(header['header_bytes_read'])).hexdigest()==entry['header_sha256']
 dest=B/'real-head';dest.mkdir(exist_ok=True);runs=[];sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'real_head_gate.py',P/'p83_cpu.cpp',meta,base/'identity.tsv')}
 for name,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=dest/name;dep=dest/(name+'.d');cmd=[cxx,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-MMD','-MF',str(dep),str(P/'p83_cpu.cpp'),'-o',str(binary),'-lcrypto']
  with (dest/(name+'-compile.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
  for n in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):sources[str(Path(n).resolve().relative_to(ROOT))]=sha(n)
  for repeat in (1,2):
   command=['ionice','-c','3',str(binary),str(file),str(offset)];r=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
   row=json.loads(r.stdout);assert row['passed'] and row['rows']==91392 and row['expected_sha256']==row['actual_sha256'];runs.append(dict(compiler=name,repeat=repeat,command=command,**row));save(dest/f'{name}-{repeat}.json',row);print(name,repeat,'full real prefix PASS',flush=True)
 statcheck();assert len({r['quantized_sha256'] for r in runs})==1 and len({r['actual_sha256'] for r in runs})==1
 save(P/'evidence/real-head.json',dict(passed=True,device_executed=False,runs=runs,sources=sources,model_file=str(file),identity=identity,source_offset=offset,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':main()
