"""CPU-only pre-admission: real allocation calls, payload/address-token mocks.
Only the generated fixture admits split25; runtime sources remain unmodified.
"""
import json,subprocess,shutil,gzip,collections
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from compile_turn import turn
import full_shape

def main():
 limits()
 from kernel_gate import mirror
 mapping=mirror();generated=full_shape.generate();S=full_shape.S
 # This first census cannot authorize a native launch. Extend only generated
 # fixture guards so the existing boundary algorithm can count layer24.
 for path in (S/'main.cpp',mapping[P/'rank.hpp']):
  text=path.read_text().replace('a.target_split==0','(a.target_split==0||a.target_split==25)').replace('target_split==0||target_split==23','target_split==0||target_split==25||target_split==23')
  path.write_text(text)
 cmds=json.loads((P/'engine-commands.json').read_text())
 base=next(r['command'] for r in cmds if r['name']=='gnu-host-entry-main');base=base[:base.index('-o')]
 base=[x for x in base if not x.startswith('-O')]+['-O0','-I'+str(P)]
 compile=[*base,'-c',str(S/'entry.cpp'),'-o',str(S/'entry.o')]
 link=next(r['command'] for r in cmds if r['name']=='gnu-host-link')
 link=[x for x in link if not x.endswith('/entry-main.o') and not x.endswith('own-rt-iq3-entry.cpp.o')];link.insert(link.index('-o'),str(S/'entry.o'));link[link.index('-o')+1]=str(S/'fixture')
 for label,cmd in [('compile',compile),('link',link)]:
  with turn(),(S/(label+'.log')).open('w') as out:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=600)
 from bundle_selection import views,selection
 v=next(v for v in views().values() if v[14]=='80128');target=S/'selected.json';save(target,selection(v))
 rows=[]
 for placement,split in [('1',0),('25-23',25)]:
  for rank in (0,1):
   dest=S/f'{placement}-rank{rank}';dest.mkdir(exist_ok=True)
   cmd=[str(S/'fixture'),str(target),sha(target),str(rank),str(dest),'positive','1',str(split)]
   result=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
   assert result.returncode==0,result.stderr
   census=json.loads((dest/'census.json').read_text());alloc=[x for x in census['allocations'] if x['live'] and x['memory']=='device'];total=sum(x['bytes'] for x in alloc)
   assert total==census['totals']['device']
   categories=collections.Counter()
   for x in alloc:categories[x['category']]+=x['bytes']
   artifact=P/'evidence'/f'census-first-{placement}-rank{rank}.json.gz';artifact.write_bytes(gzip.compress((dest/'census.json').read_bytes(),mtime=0))
   rows.append(dict(placement=placement,rank=rank,device_bytes=total,arena_headroom_bytes=30*1024**3-total,capacity_bytes=34242297856,capacity_headroom_bytes=34242297856-total,categories=dict(categories),census=str(artifact.relative_to(ROOT)),sha256=sha(artifact),command=cmd))
   print(placement,rank,total,'arena headroom',30*1024**3-total,flush=True)
 save(P/'evidence/census-first.json',dict(passed=all(r['arena_headroom_bytes']>=512*1024**2 for r in rows),device_executed=False,model_payload_read=False,driver_residency_measured=False,rows=rows,commands=[compile,link],sources={str(p.relative_to(ROOT)):sha(p) for p in [P/'census_first.py',P/'full_shape.py',P/'main.cpp',P/'rank.hpp',*generated,mapping[P/'rank.hpp']]}))
if __name__=='__main__':main()
