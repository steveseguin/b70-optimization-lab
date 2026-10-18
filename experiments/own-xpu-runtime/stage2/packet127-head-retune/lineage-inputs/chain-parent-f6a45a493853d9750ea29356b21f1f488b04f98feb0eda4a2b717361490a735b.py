"""CPU-only targeted relink. Restore discarded objects; verify unchanged object bytes."""
import argparse,gzip,json,os,subprocess,time
from pathlib import Path
from seal import sha
P=Path(__file__).resolve().parent; B=P/'build'; E=P/'evidence/20261012-k2-repair'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['gnu-host','icpx-host','asan','device']);a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 from kernel_gate import mirror
 mirror()
 old={}
 with gzip.open(P/'evidence/regenerable-object-hashes.jsonl.gz','rt') as f:
  for line in f:
   r=json.loads(line)
   if r.get('kind')=='file' and r['path'].endswith('.o'):old[r['path']]=r['sha256']
 targets=['k2-fixtures','nongemv-fixtures','own-rt-iq3','p33-linked-fixtures']+(['jit-smoke'] if a.mode=='device' else [])
 cmd=['nice','-n','19','ionice','-c','3','cmake','--build',str(B/a.mode),'-j2','--target',*targets]
 before=time.monotonic()
 with (B/('repair-build-'+a.mode+'.log')).open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 metadata=json.loads((E/'before-build.json').read_text())['metadata']
 for name,content in metadata.items():
  if name.startswith('build/'+a.mode+'/'):assert (P/name).read_text()==content,('changed link command',name)
 objects=[]
 for f in sorted((B/a.mode).rglob('*.o')):
  name=str(f.relative_to(P));digest=sha(f)
  objects.append(dict(path=name,before=old.get(name),after=digest,changed=digest!=old.get(name),bytes=f.stat().st_size))
 # Reproducibility is checked, never assumed. Only fixture entry objects may differ.
 unexpected=[r for r in objects if r['changed'] and not r['path'].endswith(('entry-k2_fixture.cpp.o','entry-nongemv_fixture.cpp.o'))]
 report=dict(passed=not unexpected,device_executed=False,mode=a.mode,command=cmd,elapsed_seconds=time.monotonic()-before,fixture_source_sha256=sha(P/'fixture_driver.cpp'),link_commands_unchanged=True,objects=objects,unexpected=unexpected,binaries={t:sha(B/a.mode/t) for t in targets})
 (E/('build-'+a.mode+'.json')).write_text(json.dumps(report,indent=2)+'\n')
 assert not unexpected,unexpected
 # Objects were already declared regenerable in object-cleanup.json. Retain
 # their new hashes/commands before removing only these restored object files.
 for r in objects:(P/r['path']).unlink()
 print(a.mode,'rebuilt/relinked',len(targets),'unchanged objects',sum(not r['changed'] for r in objects),'changed objects',sum(r['changed'] for r in objects),flush=True)
if __name__=='__main__':main()
