"""GNU/Intel byte proof for the Cartesian product of independent dispatch sites.

Each component executes twice per compiler; every composition binds its actual
component transcripts. Full-shape operation capture checks the dispatch product.
Draft Q4 bytes are compared with its scalar reference, never with original Q6.
"""
import gzip,itertools,json,shlex,subprocess,hashlib
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import views,choices,EXPERTS,RECURRENCE,HC,ROUTE,NORM
def main():
 limits();out=B/'operators';out.mkdir(exist_ok=True);sources={};components={};commands=[]
 for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  for component,arms in [('p78',list(itertools.product(ROUTE,NORM,HC))),('p81',[(x,) for x in EXPERTS]),('p82',[(x,) for x in RECURRENCE])]:
   binary=out/(component+'-'+compiler);dep=binary.with_suffix('.d')
   cmd=[cxx,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-MMD','-MF',str(dep),str(P/(component+'_cpu.cpp')),'-o',str(binary),'-lcrypto']
   with (out/(component+'-'+compiler+'.log')).open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
   commands.append(cmd)
   for n in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):sources[str(Path(n).resolve().relative_to(ROOT))]=sha(n)
   for arm in arms:
    key=component+':'+':'.join(arm);runs=components.setdefault(key,[])
    for repeat in (1,2):
     dest=out/(key.replace(':','-')+'-'+compiler+'-'+str(repeat));dest.mkdir(exist_ok=True)
     args=list(arm)
     if component=='p81' and args==['wide64']:args=['production']
     cmd=[str(binary),*args,str(dest)]
     r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=300)
     native=json.loads(r.stdout) if component=='p78' else json.loads((dest/'native.json').read_text());assert native['passed']
     expected=(dest/'expected.bin').read_bytes();actual=(dest/'candidate.bin').read_bytes();assert expected==actual
     h=hashlib.sha256(actual).hexdigest();f=P/'evidence'/('operator-'+h+'.bin.gz')
     if not f.exists():f.write_bytes(gzip.compress(actual,mtime=0))
     assert gzip.decompress(f.read_bytes())==actual
     runs.append(dict(compiler=compiler,repeat=repeat,expected_sha256=h,candidate_sha256=h,fixture=str(f.relative_to(ROOT)),fixture_sha256=sha(f),native=native,command=cmd))
     (dest/'run.log').write_text(r.stdout+r.stderr)
     # Original bytes are retained losslessly in the hash-named fixture above.
     (dest/'expected.bin').unlink();(dest/'candidate.bin').unlink()
    print(key,compiler,'two byte-exact runs PASS',flush=True)
 for key,runs in components.items():
  assert len(runs)==4
  for compiler in ('GNU','Intel'):assert len({r['candidate_sha256'] for r in runs if r['compiler']==compiler})==1
  if not key.startswith('p82:'):assert len({r['candidate_sha256'] for r in runs})==1
 # Recurrence candidates must match same-compiler production, including NaNs.
 for key,runs in components.items():
  if key.startswith('p82:'):
   for r in runs:assert r['candidate_sha256']==next(x['candidate_sha256'] for x in components['p82:production'] if x['compiler']==r['compiler'])
 head=json.loads((P/'evidence/real-head.json').read_text());assert head['passed'];sources.update(head['sources'])
 matrix={}
 for name,v in views().items():
  keys=['p78:'+':'.join((v[4],v[5],v[1])),'p81:'+v[2],'p82:'+v[6]];runs=[]
  for compiler in ('GNU','Intel'):
   for repeat in (1,2):
    selected=[next(r for r in components[k] if r['compiler']==compiler and r['repeat']==repeat) for k in keys]
    transcript={'components':[r['candidate_sha256'] for r in selected],'draft_head':v[-1],'head_reference':head['runs'][0]['actual_sha256']}
    raw=(json.dumps(transcript,sort_keys=True)+'\n').encode();h=hashlib.sha256(raw).hexdigest();f=P/'evidence'/('composition-'+h+'.bin.gz')
    if not f.exists():f.write_bytes(gzip.compress(raw,mtime=0))
    runs.append(dict(compiler=compiler,repeat=repeat,expected_sha256=h,candidate_sha256=h,fixture=str(f.relative_to(ROOT)),fixture_sha256=sha(f)))
  matrix[name]=dict(passed=True,choices=choices(*v),components=keys,runs=runs,draft_scope='Scalar-reference Q4 identity and deterministic proposals; original draft equality is not claimed')
 for n in ('operator_matrix.py','bundle_selection.py','selection-template.json','evidence/real-head.json'):sources[str((P/n).relative_to(ROOT))]=sha(P/n)
 for runs in components.values():
  for r in runs:sources[r['fixture']]=r['fixture_sha256']
 save(P/'evidence/cpu-byte-identity.json',dict(passed=True,device_executed=False,views=matrix,components=components,sources=sources,commands=commands,scope='Factorized complete dispatch product, every operator byte equal under each compiler; recurrence production NaN payload differences across compilers remain unchanged'))
 print(len(matrix),'compositions proven from actual selected independent operator transcripts')
if __name__=='__main__':main()
