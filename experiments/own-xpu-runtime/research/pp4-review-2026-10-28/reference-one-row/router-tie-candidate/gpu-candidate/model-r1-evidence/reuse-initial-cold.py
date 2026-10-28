from pathlib import Path
import json,gzip,hashlib,tarfile,subprocess
R=Path('/dev/shm/sc117-gpu-route-seven-plus-twelve-20261028-r1');D=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/pp4-review-2026-10-28/reference-one-row/router-tie-candidate/historical-seven-r1-evidence');receipt=json.loads((D/'archive.json').read_text());old=json.loads(gzip.decompress((D/'output-cold-initial.json.gz').read_bytes())) if(D/'output-cold-initial.json.gz').exists()else json.loads(Path('/dev/shm/sc117-router-tie-historical-seven-20261028-r1/output/cold-initial.json').read_text());actual=json.loads((R/'output/cold-initial.json').read_text());want={}
def stamp(p):
 s=p.stat();return[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
for rank in ('0','1'):
 a,b=actual['state'][rank],old['state'][rank];assert a['sources']==b['sources']and a['bundle_sha256']==b['bundle_sha256'];source=Path(a['path'])/'state.bundle';assert source.is_relative_to(R/'output/native')and not source.is_symlink();ref=next(x for x in receipt['members']if x['path']==str(Path(b['path'])/'state.bundle'));assert ref['sha256']==a['bundle_sha256'];want[ref['member']]={'path':str(source),'bytes':source.stat().st_size,'sha256':ref['sha256'],'identity':stamp(source),'archive_member':ref['member']}
assert len(want)==2 and sum(x['bytes']for x in want.values())==430521248
archive=Path(receipt['archive']);archivebefore=stamp(archive);proc=subprocess.Popen(['zstd','-dc',str(archive)],stdout=subprocess.PIPE);verified=[]
with tarfile.open(fileobj=proc.stdout,mode='r|')as t:
 for member in t:
  if member.name not in want:continue
  row=want.pop(member.name);p=Path(row['path']);assert member.isfile()and member.size==row['bytes']and stamp(p)==row['identity'];h=hashlib.sha256();count=0
  with p.open('rb')as f:
   z=t.extractfile(member)
   for b in iter(lambda:z.read(1024**2),b''):
    assert f.read(len(b))==b;h.update(b);count+=len(b)
   assert not f.read(1)
  assert count==row['bytes']and h.hexdigest()==row['sha256']and stamp(p)==row['identity'];verified.append(row)
assert not want;proc.stdout.close();assert proc.wait()==0 and stamp(archive)==archivebefore
out={'schema':'ownrt.gpu-route-initial-cold-archive-reuse.v1','passed':True,'reference_archive':str(archive),'reference_verified_archive_sha256':receipt['archive_sha256'],'reference_archive_rehashed':False,'all_source_maps_and_bundle_SHA_equal':True,'actual_full_byte_archive_comparison':True,'removed':verified,'freed_bytes':sum(x['bytes']for x in verified),'scope':'Exactlytwo completed initialcold payloads reuse old verified archive after actual wholepayload comparison. Allmetadata andallphase-b/result/CPUreference inputs unchanged.'}
(R/'initial-cold-archive-reuse.json').write_text(json.dumps(out,indent=2)+'\n')
for row in verified:
 p=Path(row['path']);assert stamp(p)==row['identity'];p.unlink()
out.update(removal_completed=True,removed_files_absent=all(not Path(x['path']).exists()for x in verified));(R/'initial-cold-archive-reuse.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k]for k in ['freed_bytes','removal_completed','removed_files_absent']}))
