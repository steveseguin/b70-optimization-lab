"""GNU/Intel actual snapshot bytes, forced miss and fallback classes; CPU only."""
import gzip,json,os,subprocess,shutil,resource
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits,compiler_turn
def main():
 limits();os.environ['OMP_NUM_THREADS']='1';out=B/'miss-bytes-v3';out.mkdir(exist_ok=True)
 from mini_selection import prepare
 control,candidate=prepare();prior=json.loads((P/'engine-commands.json').read_text())
 base=next(r['command'] for r in prior if r['name']=='gnu-host-entry-main');base=base[:base.index('-o')]
 base=[x for x in base[1:] if not x.startswith('-O')]+['-O1','-I'+str(P/'native-src')]
 runs=[];compilers=[]
 for name,compiler in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  obj=out/(name+'.o');binary=out/('fixture-'+name)
  cmd=[compiler,*base,'-c',str(P/'native/miss_bytes.cpp'),'-o',str(obj)]
  link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'))
  link=[str(obj) if a.endswith('/entry-main.o') else a for a in link if not a.endswith('own-rt-iq3-entry.cpp.o')]
  link[link.index('-o')+1]=str(binary)
  log=out/(name+'-compile.log')
  with compiler_turn(),log.open('w') as stream:
   subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=300)
   subprocess.run(link,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=180)
  compilers.append(dict(compiler=name,binary=str(binary.relative_to(ROOT)),binary_sha256=sha(binary),commands=[cmd,link],compile_log=str(log.relative_to(ROOT)),compile_log_sha256=sha(log)))
  for repeat in (1,2):
   pair=[]
   for label,path in [('control',control),('candidate',candidate)]:
    dest=out/f'{name}-{repeat}-{label}';dest.mkdir()
    cmd=[str(binary),str(path),sha(path),str(dest),label]
    log=P/'evidence'/f'miss3-{name}-{repeat}-{label}.log'
    with log.open('w') as stream:result=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=900)
    if result.returncode:raise RuntimeError('miss byte gate refused '+str(log))
    row=json.loads((dest/'result.json').read_text());raw=dest/'cases.txt'
    archive=P/'evidence'/f'miss-{name}-{repeat}-{label}.txt.gz';archive.write_bytes(gzip.compress(raw.read_bytes(),mtime=0))
    row.update(compiler=name,repeat=repeat,view=label,command=cmd,raw_evidence=str(archive.relative_to(ROOT)),raw_evidence_sha256=sha(archive),log_path=str(log.relative_to(ROOT)),log_sha256=sha(log))
    pair.append(row);shutil.rmtree(dest)
   assert pair[0]['canonical_sha256']==pair[1]['canonical_sha256'],'control/candidate canonical bytes differ'
   assert pair[1]['restore_submissions']*2==pair[0]['restore_submissions'],'restore must remove exactly one upload per restore'
   runs.extend(pair);print(name,repeat,'canonical state and all miss classes PASS',flush=True)
 assert len({r['canonical_sha256'] for r in runs})==1,'cross compiler/repeat canonical bytes differ'
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'miss_gate.py',P/'native/miss_bytes.cpp',P/'mini_selection.py',P.parent/'p121_reverse.hpp',P.parent/'strict_snapshot.hpp',*P.glob('native-src/*')] if f.is_file()}
 save(P.parent/'evidence/cpu-byte-identity.json',dict(schema='packet121.cpu-byte-identity.v1',passed=True,device_executed=False,runs=runs,compilers=compilers,sources=sources,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,scope='Actual compiled snapshot/restore and miniature target state; unchanged arithmetic objects inherited from packet118. No full model device equality claim.'))
 limits()
if __name__=='__main__':main()
