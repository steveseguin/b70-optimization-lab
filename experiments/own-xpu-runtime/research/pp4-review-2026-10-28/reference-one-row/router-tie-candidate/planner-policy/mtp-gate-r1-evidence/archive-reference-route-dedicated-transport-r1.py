from pathlib import Path
import subprocess,json,hashlib
roots=[Path('/dev/shm/sc117-reference-route-mtp-plans-20261028-r1/dedicated-output')]
paths=[]
for root in roots:
 receipt=root/('terminal.json' if (root/'terminal.json').exists()else 'result.json');x=json.loads(receipt.read_text());assert x['passed'] is True and x.get('error')is None and x['live_pids']==[] and x['returncodes']and all(type(v)is int and v==0 for v in x['returncodes'].values())
 paths+=list(root.glob('stage*/prefill.bin'))+list(root.glob('stage*/shared.bin'))
assert paths and all(p.is_file()and not p.is_symlink()and p.name in ('prefill.bin','shared.bin')for p in paths)
out=Path('/mnt/raid-models/ownrt-experiment-archives/2026-10-28/reference-route-dedicated-gate-r1-transport.tar.zst');assert not out.exists()
subprocess.run(['nice','-n','19','taskset','-c','8-15','tar','-I','zstd -1 -T2','-cf',str(out),'-C','/dev/shm',*[str(p.relative_to('/dev/shm')) for p in paths]],check=True)
subprocess.run(['nice','-n','19','taskset','-c','8-15','tar','-I','zstd -T2','-df',str(out),'-C','/dev/shm'],check=True)
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
rec=dict(schema='ownrt.completed-transport-archive.v1',archive=str(out),archive_sha256=digest(out),archive_bytes=out.stat().st_size,full_tar_compare_passed=True,source_roots=[str(p) for p in roots],members=[dict(path=str(p),bytes=p.stat().st_size,sha256=digest(p)) for p in paths],released_bytes=sum(p.stat().st_size for p in paths))
record=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/pp4-review-2026-10-28/reference-route-dedicated-gate-r1-transport-archive.json');record.write_text(json.dumps(rec,indent=2)+'\n')
for p in paths:p.unlink()
rec['removed_files_absent']=all(not p.exists()for p in paths);rec['removal_completed']=True;record.write_text(json.dumps(rec,indent=2)+'\n')
print(json.dumps({k:v for k,v in rec.items() if k!='members'}))
