"""Production 24/24 allocation and snapshot census, payloads mocked, CPU only."""
import gzip,json,subprocess,shutil
from build131 import P,ROOT,B,sha,save,cpu_main,limits,run
def main():
 from kernel_gate import mirror
 mirror()
 import full_shape
 generated=full_shape.generate();s=full_shape.S
 f=s/'entry.cpp';t=f.read_text().replace('#undef main','#undef main\n#include '+json.dumps(str(P/'binding131.hpp'))).replace('{pipeline::SpeculativeImage image(*e);','binding131(*e);{pipeline::SpeculativeImage image(*e);').replace('const auto before_draft=p80_operations;', 'if(a.rank==0)for(int pos:{0,3,4,31,32,4095})image.census131(a.output/("snapshot-"+std::to_string(pos)+".json"),pos);const auto before_draft=p80_operations;');f.write_text(t)
 prior=json.loads((P/'engine-commands.json').read_text());base=next(r['command'] for r in prior if r['name']=='gnu-host-entry-main');base=base[:base.index('-o')]
 # Our command orders -c before -o; retain flags only.
 base=base[:base.index('-c')];base=[a for a in base if not a.startswith('-O')]+['-O0']
 commands=[run([*base,'-c',f,'-o',s/'entry.o'],'census-compile')]
 link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'));link=[str(s/'entry.o') if a.endswith('/entry-main.o') else a for a in link if not a.endswith('own-rt-iq3-entry.cpp.o')];link[link.index('-o')+1]=str(s/'fixture')
 commands.append(run(link,'census-link'));rows=[]
 from memory_gate import check,ARENA_LIMIT_BYTES
 ledger=json.loads((P/'memory-plan.json').read_text())
 for view in ('control','candidate'):
  selection=P/'selections'/view/'selection.json'
  for rank in (0,1):
   dest=s/(view+'-'+str(rank));dest.mkdir(exist_ok=True)
   cmd=[str(s/'fixture'),str(selection),sha(selection),str(rank),str(dest),'positive','1','0']
   cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
   (P/'evidence'/f'census-{view}-{rank}.log').write_text(cp.stdout+cp.stderr)
   assert cp.returncode==0,cp.stderr
   census=json.loads((dest/'census.json').read_text());gate=check(census,ledger,rank,mtp=True,context=4096,draft_rank=1,target_split=0)
   snapshots=[json.loads(f.read_text()) for f in sorted(dest.glob('snapshot-*.json'))]
   for snapshot in snapshots:
    if snapshot['position']!=32:snapshot.pop('sources')
   archive=P/'evidence'/f'census-{view}-{rank}.json.gz';archive.write_bytes(gzip.compress((dest/'census.json').read_bytes(),mtime=0))
   rows.append(dict(view=view,rank=rank,memory=gate,arena_headroom_bytes=ARENA_LIMIT_BYTES-census['totals']['device'],census=str(archive.relative_to(ROOT)),census_sha256=sha(archive),snapshots=snapshots,bindings=json.loads((dest/'binding131.json').read_text()) if rank==0 else None))
   shutil.rmtree(dest);print(view,rank,'census PASS',flush=True)
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'census131.py',P/'binding131.hpp',P/'strict_snapshot.hpp',P/'main.cpp',P/'rank.hpp',P/'memory_gate.py',P/'memory-plan.json',*(P/'selections'/v/'selection.json' for v in ('control','candidate')),*generated]}
 save(P/'evidence/census131.json',dict(passed=True,device_executed=False,model_payload_read=False,runs=rows,sources=sources,commands=commands))
 limits()
if __name__=='__main__':cpu_main();main()
