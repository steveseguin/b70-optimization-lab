import pathlib,json,hashlib,tarfile,os,time,shutil
R=pathlib.Path('/dev/shm/sc117-router-tie-target244-20261028-r2');D=pathlib.Path('/mnt/raid-models/ownrt-experiment-archives/sc117-router-tie-target244-native-state-20261028-r2');assert not D.exists();D.mkdir()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def stamp(p):
 s=p.stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
terminal=json.load(open(R/'output/terminal.json'));assert terminal['passed']and not terminal['live_pids']and all(v==0 for v in terminal['returncodes'].values())
assert json.load(open(R/'comparison-cpu.json'))['matches_saved_cpu']
files=[];deletes=[]
for rank in [0,1]:
 base=R/f'output/native/rank{rank}/state-244';seal=(base/'state-seal.txt').read_text().splitlines();assert len(seal)==5
 for n,h in [('state.bundle',seal[2]),('state-index.tsv',seal[3]),('state.json',seal[4])]:assert sha(base/n)==h
 assert (base/'state.bundle').stat().st_size==int(seal[1]);deletes.append(base/'state.bundle')
 for n in ['state.bundle']:
  p=base/n;assert p.is_file()and not p.is_symlink();files.append({'path':str(p),'member':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p),'stat':stamp(p)})
archive=D/'state-bundles.tar'
with tarfile.open(archive,'x',format=tarfile.PAX_FORMAT)as t:
 for row in files:t.add(row['path'],arcname=row['member'],recursive=False)
with archive.open('rb')as f:os.fsync(f.fileno())
with tarfile.open(archive,'r')as t:
 members=t.getmembers();assert [m.name for m in members]==[r['member']for r in files]
 for row,m in zip(files,members):
  p=pathlib.Path(row['path']);assert stamp(p)==row['stat']and m.isfile()and m.size==row['bytes'];h=hashlib.sha256();count=0
  with p.open('rb')as original:
   f=t.extractfile(m)
   for b in iter(lambda:f.read(1024*1024),b''):
    assert original.read(len(b))==b;h.update(b);count+=len(b)
   assert original.read(1)==b''
  assert count==row['bytes']and h.hexdigest()==row['sha256']and stamp(p)==row['stat']
receipt={'schema':'ownrt.router-tie.native-state-archive.v1','verified':True,'archive':str(archive),'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'members':files,'full_tar_bytes_compared':True,'terminal_sha256':sha(R/'output/terminal.json'),'comparison_sha256':sha(R/'comparison-cpu.json'),'removed_paths':[str(p)for p in deletes],'freed_bytes':sum(p.stat().st_size for p in deletes),'scope':'Only two completed native state.bundle originals removed after full archive equality. All indices/seals/metadata/layer/router/replay evidence retained; archived sealed full states remain recoverable.'}
(D/'archive.json').write_text(json.dumps(receipt,indent=2)+'\n');(R/'archive.json').write_text(json.dumps(receipt,indent=2)+'\n')
for p in deletes:
 row=next(x for x in files if x['path']==str(p));assert stamp(p)==row['stat'];p.unlink()
receipt['removal_completed']=True;receipt['removed_files_absent']=all(not p.exists()for p in deletes)
for p in [D/'archive.json',R/'archive.json']:p.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'archive':str(archive),'freed_bytes':receipt['freed_bytes'],'archive_sha256':receipt['archive_sha256'],'removed_files_absent':receipt['removed_files_absent']}))
