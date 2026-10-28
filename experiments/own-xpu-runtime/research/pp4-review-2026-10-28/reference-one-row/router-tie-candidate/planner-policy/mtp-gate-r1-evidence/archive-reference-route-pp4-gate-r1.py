from pathlib import Path
import json,hashlib,tarfile,subprocess,os
R=Path('/dev/shm/sc117-reference-route-pp4-gate-20261028-r1');D=Path('/mnt/raid-models/ownrt-experiment-archives/2026-10-28/reference-route-pp4-gate-r1')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def stamp(p):
 s=p.stat();return[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
result=json.loads((R/'output/result.json').read_text())
assert result['passed'] is True and result['error'] is None and result['live_pids']==[] and result['returncodes']=={str(i):0 for i in range(4)}
for name in ('target-comparison.json','draft-comparison.json'):
 assert json.loads((R/'output'/name).read_text())['passed'] is True
required=set()
for index,name in enumerate(('serial','pipeline')):
 folder=R/'output'/f'request-{index:02d}-{name}'
 original=json.loads((folder/'target-set.json').read_text());provenance=json.loads((folder/'target-set.prefill-provenance.json').read_text())
 assert provenance['prefill_provenance']['schema']=='ownrt.prefill-trace-provenance.v1'
 assert len(original['stages'])==4 and {x['id']for x in original['stages']}==set(range(4))
 for stage in original['stages']:
  dump=(folder/stage['dump']).resolve();assert dump.is_relative_to(R/'output') and dump.name==f'state-{2000000000+index}'
  required.add(dump/'state.bundle')
  if stage['id']==0:required.add(Path(str(dump)+'.draft')/'state.bundle')
assert len(required)==10 and all(p.is_file()for p in required)

files=[]
for p in sorted(p for stage in range(4) for p in (R/'output'/f'stage{stage}'/'native').rglob('state.bundle')):
 assert p.is_file()and not p.is_symlink();base=p.parent;seal=(base/'state-seal.txt').read_text().splitlines();assert len(seal)==5 and int(seal[1])==p.stat().st_size
 assert sha(base/'state-index.tsv')==seal[3]and sha(base/'state.json')==seal[4]
 files.append({'path':str(p),'member':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':seal[2],'stat':stamp(p)})
assert required.issubset({Path(x['path'])for x in files})
assert 10<=len(files)<=16
for row in files:
 p=Path(row['path']);assert p in required or p.parent.name in ('state-2147483647','state-2147483647.draft') or p==R/'output/stage0/native/requests/request-01-pipeline/draft-final-state-sealed/state.bundle'
D.mkdir(exist_ok=False)
archive=D/'state-bundles.tar.zst';proc=subprocess.Popen(['zstd','-1','-T2','-o',str(archive),'-'],stdin=subprocess.PIPE)
with tarfile.open(fileobj=proc.stdin,mode='w|',format=tarfile.PAX_FORMAT)as t:
 for row in files:
  p=Path(row['path']);assert stamp(p)==row['stat'];t.add(p,arcname=row['member'],recursive=False);assert stamp(p)==row['stat']
proc.stdin.close();assert proc.wait()==0
with archive.open('rb')as f:os.fsync(f.fileno())
proc=subprocess.Popen(['zstd','-dc',str(archive)],stdout=subprocess.PIPE)
with tarfile.open(fileobj=proc.stdout,mode='r|')as t:
 for row in files:
  m=t.next();assert m and m.isfile()and m.name==row['member']and m.size==row['bytes'];p=Path(row['path']);assert stamp(p)==row['stat'];h=hashlib.sha256();count=0
  with p.open('rb')as original:
   f=t.extractfile(m)
   for b in iter(lambda:f.read(1024*1024),b''):
    assert original.read(len(b))==b;h.update(b);count+=len(b)
   assert not original.read(1)
  assert count==row['bytes']and h.hexdigest()==row['sha256']and stamp(p)==row['stat']
 assert t.next()is None
proc.stdout.close();assert proc.wait()==0
receipt={'schema':'ownrt.reference-route-pp4-state-archive.v1','archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive),'full_tar_bytes_compared':True,'actual_payload_sha256_matches_all_seals':True,'members':files,'freed_bytes':sum(x['bytes']for x in files),'removed_paths':[x['path']for x in files],'result_sha256':sha(R/'output/result.json'),'scope':'Only exact inventoried sealed PP4 serial/pipeline and terminal payloads removed after full-byte archive comparison; all metadata/provenance/reset evidence retained. Serial five bundles independently extractable.', 'proof_sha256':{name:sha(R/'output'/name)for name in ('target-comparison.json','draft-comparison.json')},'serial_restore_members':[str(p.relative_to(R))for p in sorted(required)if 'request-00-serial' in str(p)]}
for p in [D/'archive.json',R/'archive.json']:p.write_text(json.dumps(receipt,indent=2)+'\n')
for row in files:
 p=Path(row['path']);assert stamp(p)==row['stat'];p.unlink()
receipt.update(removal_completed=True,removed_files_absent=all(not Path(x['path']).exists()for x in files))
for p in [D/'archive.json',R/'archive.json']:p.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:receipt[k]for k in ['archive','archive_bytes','archive_sha256','freed_bytes','removal_completed','removed_files_absent']}))
