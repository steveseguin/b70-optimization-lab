"""Fresh GNU/Intel operator bytes, then hash-bound complete selectable products.

Every component compares actual production/candidate raw bytes. The transcript
is a factorized composition proof; full-shape startup separately checks their
joint allocation and dispatch. Device model exactness remains a screen gate.
"""
import gzip,hashlib,json,shlex,shutil,subprocess
from build_engine import P,ROOT,B,sha,save,limits
from compile_turn import turn
from bundle_selection import views,choices
COMPONENTS={
 'route':('p78_cpu.cpp',[('production','production','hc-wide'),('fast','production','hc-wide')]),
 'recurrence':('p82_cpu.cpp',[('rec-parallel',),('rec-both-plus',)]),
 'head':('p93_cpu.cpp',[('production',),('head-transpose',)]),
 'hc_norm':('p94_cpu.cpp',[('production',),('hc-normfuse',)]),
 'experts':('p95_cpu.cpp',[(x,) for x in ('production','exp-grid-prefetch','exp-halfcache','exp-grid-prefetch+halfcache')]),
 'host':('reply_first_test.cpp',[()])}
def main():
 limits();dest=B/'cpu';dest.mkdir(exist_ok=True);sources={};components={};commands=[]
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  for cls,(leaf,arms) in COMPONENTS.items():
   binary=dest/(cls+'-'+compiler);dep=binary.with_suffix('.d')
   cmd=[cxx,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-MMD','-MF',str(dep),str(P/leaf),'-o',str(binary),'-lcrypto']
   with turn(),(dest/(cls+'-'+compiler+'.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
   commands.append(cmd)
   for n in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):sources[str(Path(n).resolve().relative_to(ROOT))]=sha(n)
   for arm in arms:
    key=cls+':'+':'.join(arm);runs=components.setdefault(key,[])
    for repeat in (1,2):
     scratch=dest/'scratch';scratch.mkdir();limits()
     try:
      args=("production",) if cls=="recurrence" and arm==("rec-parallel",) else arm
      cmd=[str(binary),*args,str(scratch)]
      r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=300)
      expected=(scratch/'expected.bin').read_bytes();actual=(scratch/'candidate.bin').read_bytes();assert expected==actual,key
      native=json.loads(r.stdout) if cls=='route' else json.loads((scratch/('result.json' if cls=='host' else 'native.json')).read_text());assert native['passed']
      digest=hashlib.sha256(actual).hexdigest();f=P/'evidence'/('operator-'+digest+'.bin.gz')
      if not f.exists():f.write_bytes(gzip.compress(actual,mtime=0))
      assert gzip.decompress(f.read_bytes())==actual
      cases=scratch/'cases.jsonl';case_art={}
      if cases.exists():
       retained=P/'evidence'/('cases-'+hashlib.sha256(cases.read_bytes()).hexdigest()+'.jsonl.gz');retained.write_bytes(gzip.compress(cases.read_bytes(),mtime=0));sources[str(retained.relative_to(ROOT))]=sha(retained);case_art={'cases_path':str(retained.relative_to(ROOT))}
      runs.append(dict(compiler=compiler,repeat=repeat,command=cmd,expected_sha256=digest,candidate_sha256=digest,fixture=str(f.relative_to(ROOT)),fixture_sha256=sha(f),native=native,**case_art))
     finally:shutil.rmtree(scratch)
    print(compiler,key,'two fresh byte repeats PASS',flush=True)
 for key,runs in components.items():
  assert len(runs)==4
  for compiler in ('GNU','Intel'):assert len({r['candidate_sha256'] for r in runs if r['compiler']==compiler})==1
  for r in runs:sources[r['fixture']]=r['fixture_sha256']
 matrix={}
 for label,v in views().items():
  c=choices(*v);keys=['route:'+v[4]+':production:hc-wide','recurrence:'+v[6],'head:'+v[8],'hc_norm:'+('hc-normfuse' if v[9]=='normfuse' else 'production'),'experts:'+('production' if v[2]=='wide64' else c['experts']),'host:'];runs=[]
  for compiler in ('GNU','Intel'):
   for repeat in (1,2):
    selected=[next(r for r in components[k] if r['compiler']==compiler and r['repeat']==repeat) for k in keys]
    raw=(json.dumps(dict(choices=c,components=[r['candidate_sha256'] for r in selected]),sort_keys=True)+'\n').encode();digest=hashlib.sha256(raw).hexdigest();f=P/'evidence'/('composition-'+digest+'.bin.gz');f.write_bytes(gzip.compress(raw,mtime=0))
    runs.append(dict(compiler=compiler,repeat=repeat,expected_sha256=digest,candidate_sha256=digest,fixture=str(f.relative_to(ROOT)),fixture_sha256=sha(f)))
  matrix[label]=dict(passed=True,choices=c,components=keys,runs=runs)
 for leaf in ('cpu_gate.py','compile_turn.py','bundle_selection.py'):sources[str((P/leaf).relative_to(ROOT))]=sha(P/leaf)
 save(P/'evidence/cpu-byte-identity.json',dict(passed=True,device_executed=False,views=matrix,components=components,sources=sources,commands=commands,scope=__doc__,cross_compiler='Exact per-compiler production oracle. Inherited production NaN payload differences across compilers are not candidate tolerances.'))
if __name__=='__main__':
 from pathlib import Path
 main()
