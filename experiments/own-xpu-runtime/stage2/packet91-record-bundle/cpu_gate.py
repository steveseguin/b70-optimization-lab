"""Recheck frozen GNU/Intel proof; fresh recurrence bytes without recompilation."""
import gzip,hashlib,json,os,shutil,subprocess
from build_engine import P,ROOT,B,PARENTS,limits,sha,save,provenance
from bundle_selection import views,choices,name
from chain_seal import check_map

def main():
 limits();provenance();sources={};reports={};fresh=[]
 for rec,parent in PARENTS.items():
  f=parent/'evidence/cpu-byte-identity.json';r=json.loads(f.read_text())
  assert r['passed'] and not r['device_executed'];check_map(ROOT,r['sources']);sources.update(r['sources']);sources[str(f.relative_to(ROOT))]=sha(f);reports[rec]=r
 # The reused p82b fixtures cover every state/output byte, consecutive tokens,
 # both compilers and fresh repeats. Scratch is removed after every invocation.
 parent=PARENTS['rec-both-plus'];scratch=B/'cpu-current'
 for compiler in ('GNU','Intel'):
  binary=parent/'build/cpu'/('fixture-'+compiler);sources[str(binary.relative_to(ROOT))]=sha(binary)
  for choice in ('production','rec-both-plus'):
   old=next(r for r in reports['rec-both-plus']['views'][choice]['runs'] if r['compiler']==compiler and r['repeat']==1)
   for repeat in (1,2):
    limits();scratch.mkdir()
    try:
     command=[str(binary),choice,str(scratch)]
     result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=180,env={**os.environ,'OMP_NUM_THREADS':'2'})
     native=json.loads((scratch/'native.json').read_text());expected=sha(scratch/'expected.bin');candidate=sha(scratch/'candidate.bin')
     assert native['passed'] and expected==candidate==old['candidate_sha256']
     assert native['raw_bytes_compared'] and native['cases']==260 and native['tokens_checked']==416
     fresh.append(dict(compiler=compiler,repeat=repeat,choice=choice,command=command,expected_sha256=expected,candidate_sha256=candidate,**native))
     for leaf in ('expected.bin','candidate.bin','native.json','cases.jsonl'):
      if (scratch/leaf).exists():
       raw=(scratch/leaf).read_bytes();dest=P/'evidence'/f'cpu-{compiler}-{choice}-{repeat}-{leaf}.gz';dest.write_bytes(gzip.compress(raw,mtime=0));sources[str(dest.relative_to(ROOT))]=sha(dest)
    finally:shutil.rmtree(scratch)
   print(compiler,choice,'two fresh runs PASS',flush=True)
 rows={}
 for label,v in views().items():
  oldv=list(v);oldv[6]='rec-parallel';oldname=name(*oldv)
  base=reports['rec-parallel']['views'][oldname];assert base['passed'];runs=[]
  assert {(r['compiler'],r['repeat']) for r in base['runs']}=={(c,n) for c in ('GNU','Intel') for n in (1,2)}
  for run in base['runs']:
   f=ROOT/run['fixture'];raw=gzip.decompress(f.read_bytes())
   assert sha(f)==run['fixture_sha256'] and hashlib.sha256(raw).hexdigest()==run['expected_sha256']==run['candidate_sha256'];sources[str(f.relative_to(ROOT))]=sha(f)
   if v[6]=='rec-both-plus':
    added=next(r for r in fresh if r['compiler']==run['compiler'] and r['repeat']==run['repeat'] and r['choice']=='rec-both-plus')
    # Factorized operator transcript, not a claim that this is a model run.
    raw+=json.dumps(dict(recurrence_expected=added['expected_sha256'],recurrence_candidate=added['candidate_sha256']),sort_keys=True).encode()
   digest=hashlib.sha256(raw).hexdigest();dest=P/'evidence'/('composition-'+digest+'.bin.gz')
   if not dest.exists():dest.write_bytes(gzip.compress(raw,mtime=0))
   runs.append(dict(compiler=run['compiler'],repeat=run['repeat'],expected_sha256=digest,candidate_sha256=digest,fixture=str(dest.relative_to(ROOT)),fixture_sha256=sha(dest)))
  rows[label]=dict(passed=True,choices=choices(*v),runs=runs)
 sources[str((P/'cpu_gate.py').relative_to(ROOT))]=sha(P/'cpu_gate.py')
 save(P/'evidence/cpu-byte-identity.json',dict(passed=True,device_executed=False,views=rows,fresh_recurrence_runs=fresh,sources=sources,
      cross_compiler=reports['rec-both-plus']['cross_compiler'],scope='Frozen packet84 selected operator proof plus fresh p82b full-state recurrence equality, each GNU/Intel twice. Factorized independent dispatch sites, not full model output.'))
if __name__=='__main__':main()
