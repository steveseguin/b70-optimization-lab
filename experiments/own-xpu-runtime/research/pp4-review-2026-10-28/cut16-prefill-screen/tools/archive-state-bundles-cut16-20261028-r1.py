"""Byte-verified archive+release of one completed run's sealed state bundles (adapted from
archive-reference-route-equal16-control-r1.py; generic root/output/destination arguments only)."""
from pathlib import Path
import json,hashlib,tarfile,subprocess,os,sys
R=Path(sys.argv[1]);OUT=sys.argv[2];D=Path(sys.argv[3]);PROOF=Path(sys.argv[4]) if len(sys.argv)>4 else None
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def stamp(p):
 s=p.stat();return[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
terminal=json.loads((R/OUT/'terminal.json').read_text());assert terminal['passed'] is True and terminal.get('error')is None and terminal['live_pids']==[] and terminal['returncodes']=={'0':0,'1':0,'2':0,'provider':0}
resultpath=R/OUT/'driver-result.json';result=json.loads(resultpath.read_text());assert result['passed'] is True and all(type(x)is int for x in result['output_ids'])
if PROOF is not None:assert json.loads(PROOF.read_text())['passed'] is True
prov=R/OUT/'stageprovider/native'
dumps=list(prov.glob('provider-dump-*'));finishes=list(prov.glob('provider-finish-*'));assert len(dumps)==1 and len(finishes)==1
expected={R/OUT/f'stage{i}/native/state-2147483647/state.bundle'for i in range(3)}|{dumps[0]/'state.bundle',finishes[0]/'state.bundle'}
files=[]
for p in sorted((R/OUT).rglob('state.bundle')):
 assert p.is_file()and not p.is_symlink();base=p.parent;seal=(base/'state-seal.txt').read_text().splitlines();assert len(seal)==5 and int(seal[1])==p.stat().st_size
 assert sha(base/'state-index.tsv')==seal[3]and sha(base/'state.json')==seal[4]
 files.append({'path':str(p),'member':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':seal[2],'stat':stamp(p)})
assert {Path(x['path'])for x in files}==expected and len(files)==5,sorted(x['path'] for x in files)
D.mkdir(exist_ok=False)
archive=D/'state-bundles.tar.zst';proc=subprocess.Popen(['zstd','-q','-1','-T2','-o',str(archive),'-'],stdin=subprocess.PIPE)
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
receipt={'schema':'ownrt.reference-route-dedicated-state-archive.v1','archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive),'full_tar_bytes_compared':True,'actual_payload_sha256_matches_all_seals':True,'members':files,'freed_bytes':sum(x['bytes']for x in files),'removed_paths':[x['path']for x in files],'terminal_sha256':sha(R/OUT/'terminal.json'),'driver_result_sha256':sha(resultpath),'proof_sha256':sha(PROOF) if PROOF else None,'scope':'Exactly five completed dedicated target/provider payloads removed after sealed full archive byte verification; metadata retained.'}
for p in [D/'archive.json',R/'archive.json']:p.write_text(json.dumps(receipt,indent=2)+'\n')
for row in files:
 p=Path(row['path']);assert stamp(p)==row['stat'];p.unlink()
receipt.update(removal_completed=True,removed_files_absent=all(not Path(x['path']).exists()for x in files))
for p in [D/'archive.json',R/'archive.json']:p.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:receipt[k]for k in ['archive','archive_bytes','archive_sha256','freed_bytes','removal_completed','removed_files_absent']}))
