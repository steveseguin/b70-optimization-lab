"""Run-specific adaptation of equal16 control archive-helper.py; CPU/archive only."""
from pathlib import Path
import json,hashlib,tarfile,subprocess,os
R=Path('/dev/shm/sc117-dedicated-reset-aba64k-20261028-r1')
D=Path('/mnt/raid-models/ownrt-experiment-archives/2026-10-28/dedicated-reset-aba64k-r1')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def stamp(p):
 s=p.stat();return[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def save(p,d):
 tmp=p.with_suffix(p.suffix+'.tmp')
 with tmp.open('w')as f:f.write(json.dumps(d,indent=2,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
 tmp.replace(p)
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
terminal=json.loads((R/'output/terminal.json').read_text())
assert terminal['passed'] is True and terminal['error']is None and terminal['live_pids']==[] and terminal['returncodes']=={'0':0,'1':0,'2':0,'provider':0} and terminal['requests']==3
post=json.loads((R/'postflight.json').read_text());assert post['known_fault_baseline_matches']and not post['holders']
assert subprocess.run(['pgrep','-x','sc117-engine'],stdout=subprocess.DEVNULL).returncode==1
cold=json.loads((R/'output/cold-proof.json').read_text());repeat=json.loads((R/'output/request-02/repeated-a-proof.json').read_text())
assert cold['passed']and repeat['passed']and repeat['actual_output_ids_equal']and repeat['full_payload_bytes_compared']==4091763958
for i in [1,2]:
 p=json.loads((R/f'output/request-{i:02d}/cold-proof.json').read_text());assert p['passed']and p['full_payload_bytes_compared']==4091763958 and (p['target_canonical_sources'],p['inactive_bank_sources'],p['provider_canonical_sources'])==(2065,27,73)
roles={}
for label,group in [('startup-cold',cold['actual']['state']),('first-A',repeat['initial']),('final-A',repeat['actual'])]:
 for owner,v in group.items():roles[str(Path(v['path'])/'state.bundle')]=label+':owner'+owner
p=R/'output/stageprovider/native'
roles[str(p/'provider-cold-baseline/state.bundle')]='provider-native-cold-baseline'
roles[str(p/'request-2/provider-dump-1547/state.bundle')]='final-provider-dump'
roles[str(p/'request-2/provider-finish-1548/state.bundle')]='final-provider-finish'
expected={Path(p)for p in roles};assert len(expected)==15 and set((R/'output').rglob('state.bundle'))==expected
files=[]
for p in sorted(expected):
 assert p.is_file()and not p.is_symlink();base=p.parent;seal=(base/'state-seal.txt').read_text().splitlines();assert len(seal)==5 and int(seal[1])==p.stat().st_size
 assert sha(base/'state-index.tsv')==seal[3]and sha(base/'state.json')==seal[4]
 files.append({'path':str(p),'member':str(p.relative_to(R)),'role':roles[str(p)],'bytes':p.stat().st_size,'sha256':seal[2],'stat':stamp(p),'index_sha256':seal[3],'state_json_sha256':seal[4]})
D.mkdir(exist_ok=False);archive=D/'state-bundles.tar.zst'
proc=subprocess.Popen(['zstd','-1','-T2','-o',str(archive),'-'],stdin=subprocess.PIPE)
with tarfile.open(fileobj=proc.stdin,mode='w|',format=tarfile.PAX_FORMAT)as t:
 for row in files:
  p=Path(row['path']);assert stamp(p)==row['stat'];t.add(p,arcname=row['member'],recursive=False);assert stamp(p)==row['stat']
proc.stdin.close();assert proc.wait()==0
with archive.open('rb')as f:os.fsync(f.fileno())
archive_stat=stamp(archive);proc=subprocess.Popen(['zstd','-dc',str(archive)],stdout=subprocess.PIPE)
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
proc.stdout.close();assert proc.wait()==0 and stamp(archive)==archive_stat
receipt={'schema':'ownrt.dedicated-reset-state-archive.v1','archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive),'full_tar_bytes_compared':True,'actual_payload_sha256_matches_all_seals':True,'stable_original_and_archive_identities':True,'members':files,'freed_bytes':sum(x['bytes']for x in files),'removed_paths':[x['path']for x in files],'terminal_sha256':sha(R/'output/terminal.json'),'postflight_sha256':sha(R/'postflight.json'),'repeated_a_proof_sha256':sha(R/'output/request-02/repeated-a-proof.json'),'scope':'Exactly15 proof-derived completed state bundles; startupcold/firstA/finalA/providerbaseline/final-provider dumps preserved as named archive members. Cold duplicates already removed by controller alias receipts are not re-removed. All metadata and transport maps remain.','removal_completed':False}
assert stamp(archive)==archive_stat
save(D/'archive.json',receipt);save(R/'state-archive.json',receipt)
for row in files:
 p=Path(row['path']);assert stamp(p)==row['stat'];p.unlink()
receipt.update(removal_completed=True,removed_files_absent=all(not Path(x['path']).exists()for x in files))
save(D/'archive.json',receipt);save(R/'state-archive.json',receipt)
print(json.dumps({k:receipt[k]for k in ['archive','archive_bytes','archive_sha256','freed_bytes','removal_completed','removed_files_absent']}))
