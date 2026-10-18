"""Compile the actual snapshot/target fixture with GNU and Intel; CPU only."""
import gzip,json,subprocess,shutil,resource
from build131 import P,ROOT,B,sha,save,cpu_main,limits,run
def main():
 prior=json.loads((P/'engine-commands.json').read_text());base=next(r['command'] for r in prior if r['name']=='gnu-host-entry-main');base=base[:base.index('-c')]
 base=[a for a in base[1:] if not a.startswith('-O')]+['-O1']
 out=B/'state131';out.mkdir(exist_ok=True);runs=[];commands=[]
 # Include the exact checked Engine source, rather than bypassing the mirror.
 source=out/'state.cpp';source.write_text((P/'state131.cpp').read_text().replace('#include "main.cpp"','#include '+json.dumps(str(B/'checked'/P.relative_to(ROOT)/'main.cpp'))))
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  obj=out/(compiler+'.o');binary=out/('fixture-'+compiler)
  commands.append(run([cxx,*base,'-c',source,'-o',obj],'state-'+compiler+'-compile'))
  link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'));link=[str(obj) if a.endswith('/entry-main.o') else a for a in link if not a.endswith('own-rt-iq3-entry.cpp.o')];link[link.index('-o')+1]=str(binary)
  commands.append(run(link,'state-'+compiler+'-link'))
  for repeat in (1,2):
   for view in ('control','candidate'):
    selection=P/'selections'/view/'mini.json';row=json.loads((selection.parent/'selection.json').read_text())
    # Production-only kernels reject the synthetic miniature geometry.
    for key in ('route','recurrence','hc','experts','hc_gate','hc_norm','head','other_fusion'):row['choices'][key]='production'
    # Selection parser retains packet56 arithmetic identity for admission.
    row['choices']['route']='route-exp32-rank4';row['choices']['recurrence']='rows4-shared'
    save(selection,row)
    dest=out/f'{compiler}-{repeat}-{view}';dest.mkdir()
    cmd=[str(binary),str(selection),sha(selection),str(dest),view]
    log=P/'evidence'/f'state-{compiler}-{repeat}-{view}.log'
    with log.open('w') as stream:cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=1200)
    assert cp.returncode==0,str(log)
    result=json.loads((dest/'result.json').read_text());raw=dest/'cases.txt';archive=P/'evidence'/f'state-{compiler}-{repeat}-{view}.txt.gz';archive.write_bytes(gzip.compress(raw.read_bytes(),mtime=0))
    result.update(compiler=compiler,repeat=repeat,view=view,command=cmd,artifact=str(archive.relative_to(ROOT)),artifact_sha256=sha(archive),snapshot=json.loads((dest/'speculative-snapshot.json').read_text()))
    runs.append(result);shutil.rmtree(dest);print(compiler,repeat,view,'state PASS',flush=True)
 assert len({r['canonical_sha256'] for r in runs})==1,'cross view/compiler/repeat bytes differ'
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'state131.cpp',P/'state131.py',P/'strict_snapshot.hpp',P/'rank.hpp',P/'main.cpp',P/'request_reset.hpp',*(P/'selections'/v/n for v in ('control','candidate') for n in ('selection.json','mini.json'))]}
 save(P/'evidence/state131.json',dict(passed=True,device_executed=False,runs=runs,sources=sources,commands=commands,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 limits()
if __name__=='__main__':cpu_main();main()
