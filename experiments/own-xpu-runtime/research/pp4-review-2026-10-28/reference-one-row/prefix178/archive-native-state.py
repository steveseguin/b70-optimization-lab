import pathlib,json,hashlib,tarfile,os,time,shutil
R=pathlib.Path('/dev/shm/sc117-reference-prefix178-20261028-r1');D=pathlib.Path('/mnt/raid-models/ownrt-experiment-archives/sc117-prefix178-native-state-20261028-r1');assert not D.exists();D.mkdir()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def stamp(p):
 s=p.stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
terminal=json.load(open(R/'output/terminal.json'));assert terminal['passed']and not terminal['live_pids']and all(v==0 for v in terminal['returncodes'].values())
for n in ['comparison-cpu-r1.json','native178-vs-native244-row177.json']:assert json.load(open(R/n))['passed']
files=[];deletes=[]
for rank in [0,1]:
 base=R/f'output/native/rank{rank}/state-178';seal=(base/'state-seal.txt').read_text().splitlines();assert len(seal)==5
 for n,h in [('state.bundle',seal[2]),('state-index.tsv',seal[3]),('state.json',seal[4])]:assert sha(base/n)==h
 assert (base/'state.bundle').stat().st_size==int(seal[1]);deletes.append(base/'state.bundle')
 for n in ['state.bundle','state-index.tsv','state.json','state-seal.txt']:
  p=base/n;assert p.is_file()and not p.is_symlink();files.append({'path':str(p),'member':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p),'stat':stamp(p)})
extract=R/'router-lastrow-extract';assert not extract.exists();extract.mkdir();extracted=[]
for rank in [0,1]:
 base=R/f'output/native/rank{rank}/state-178';table={}
 for line in (base/'state-index.tsv').read_text().splitlines()[1:]:
  name,offset,size,h=line.split('\t');table[name]=(int(offset),int(size),h)
 before=stamp(base/'state.bundle')
 with (base/'state.bundle').open('rb')as f:
  for layer in range(0 if rank==0 else 23,23 if rank==0 else 48):
   for field,size in [('router',2048),('ids',40),('prob',40),('routes',120),('routes.down',120)]:
    name=f'blk.{layer}.{field}.bin';off,n,h=table[name];assert n==size;f.seek(off);data=f.read(n);assert len(data)==n and hashlib.sha256(data).hexdigest()==h
    (extract/name).write_bytes(data);extracted.append({'layer':layer,'owner':rank,'name':name,'offset':off,'bytes':n,'sha256':h,'source_bundle_sha256':next(x['sha256']for x in files if x['path']==str(base/'state.bundle'))})
 assert stamp(base/'state.bundle')==before
assert len(extracted)==240
(extract/'receipt.json').write_text(json.dumps({'schema':'ownrt.prefix178.native-router-extract.v1','position':177,'full_sealed_source_hash_verified':True,'members':extracted,'bytes':sum(x['bytes']for x in extracted)},indent=2)+'\n')
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
receipt={'schema':'ownrt.prefix178.native-state-archive.v1','verified':True,'archive':str(archive),'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'members':files,'full_tar_bytes_compared':True,'terminal_sha256':sha(R/'output/terminal.json'),'comparison_sha256':sha(R/'comparison-cpu-r1.json'),'history_check_sha256':sha(R/'native178-vs-native244-row177.json'),'removed_paths':[str(p)for p in deletes],'freed_bytes':sum(p.stat().st_size for p in deletes),'scope':'Only two completed native state.bundle originals removed after full archive equality. All indices/seals/metadata/layer/router/replay evidence retained; archived sealed full states remain recoverable.'}
(D/'archive.json').write_text(json.dumps(receipt,indent=2)+'\n');(R/'archive.json').write_text(json.dumps(receipt,indent=2)+'\n')
for p in deletes:
 row=next(x for x in files if x['path']==str(p));assert stamp(p)==row['stat'];p.unlink()
receipt['removal_completed']=True;receipt['removed_files_absent']=all(not p.exists()for p in deletes)
for p in [D/'archive.json',R/'archive.json']:p.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'archive':str(archive),'freed_bytes':receipt['freed_bytes'],'archive_sha256':receipt['archive_sha256'],'removed_files_absent':receipt['removed_files_absent']}))
