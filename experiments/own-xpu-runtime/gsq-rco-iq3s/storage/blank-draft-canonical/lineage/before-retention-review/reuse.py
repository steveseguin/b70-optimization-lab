"""Verify and separately release fixed duplicate closed draft bytes; retain canonical."""
from pathlib import Path
import argparse,gzip,hashlib,json,os,stat
P=Path(__file__).resolve().parent;L=P.parents[1]
RAW=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-dense-q6-p33-engine-a')
REVIEW=L/'dense-q6-p33/operating/evidence/device-a/review.json'
REVIEW_SHA='8e9c69ae212a45f1bf2491dd25a75743b01a19395064d52b06d713497f686d14'
INDEX=REVIEW.parent/'artifact-index.jsonl.gz'
CANON='prompt-00-none/rank0/draft-final-state/blk.0.qsa.keys.bin'
ZERO='bb9f8df61474d25e71fa00722318cd387396ca1736605e1248821cc0de3d3af8'
SIZE=4194304
def need(v,m):
 if not v:raise ValueError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(path,value):
 with path.open('x') as f:json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def inventory():
 need(sha(REVIEW)==REVIEW_SHA,'closed review identity');r=json.loads(REVIEW.read_text())
 need(r['passed'] and r['physical_drain'] and r['all12_exact'],'closed exact owner')
 need(sha(INDEX)==r['index_sha256'],'audited index identity')
 with gzip.open(INDEX,'rt') as f:rows=[json.loads(line) for line in f]
 rows=[x for x in rows if x['root']=='evidence' and x['path'].endswith(('/draft-final-state/blk.0.qsa.keys.bin','/draft-final-state/blk.0.qsa.values.bin')) and x['bytes']==SIZE and x['sha256']==ZERO]
 need(len(rows)==28 and len({x['path'] for x in rows})==28 and CANON in {x['path'] for x in rows},'fixed28 duplicate inventory')
 need(RAW.resolve()==RAW and RAW.stat().st_dev==2050,'canonical USB filesystem')
 return rows
def held(relative):
 p=RAW/relative;need(p.resolve()==p and '..' not in Path(relative).parts,'canonical file path')
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  st=os.fstat(fd);need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_dev==2050 and st.st_size==SIZE,'raw inode extent')
  h=hashlib.sha256()
  while b:=os.read(fd,1024*1024):h.update(b)
  end=os.fstat(fd);stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
  need(stamp(st)==stamp(end) and h.hexdigest()==ZERO and stamp(p.stat())==stamp(end),'stable exact canonical bytes')
  return fd,dict(path=relative,bytes=SIZE,sha256=ZERO,identity=list(stamp(end)),mode=stat.S_IMODE(st.st_mode),uid=st.st_uid,gid=st.st_gid,mtime_ns=st.st_mtime_ns)
 except BaseException:os.close(fd);raise
def main():
 ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['verify','release']);a=ap.parse_args();rows=inventory();P.joinpath('evidence').mkdir(exist_ok=True)
 evidence=P/'evidence';manifest=evidence/'restore-map.json'
 if a.phase=='verify':
  result=[]
  for x in rows:
   fd,row=held(x['path']);os.close(fd);result.append(row)
  save(manifest,dict(schema='gsq.blank-draft.canonical.v1',source_sha256=sha(__file__),review_sha256=REVIEW_SHA,index_sha256=sha(INDEX),canonical=CANON,rows=result,release_paths=[x['path'] for x in rows if x['path']!=CANON],recoverable_bytes=27*SIZE,restore='Copy exact canonical bytes to each released path, verify size/SHA256, then apply retained mode/uid/gid/mtime metadata. Canonical remains protected.'))
  print(json.dumps(dict(verified=True,files=28,release_bytes=27*SIZE)));return
 review=json.loads((evidence/'independent-review.json').read_text());need(review['passed'] and review['source_sha256']==sha(__file__),'independent release review')
 m=json.loads(manifest.read_text());need(m['source_sha256']==sha(__file__) and m['index_sha256']==sha(INDEX) and m['canonical']==CANON,'durable restore identity')
 expected={x['path'] for x in rows}-{CANON};need(set(m['release_paths'])==expected and len(m['release_paths'])==27,'fixed27 release only')
 originals={x['path']:x for x in m['rows']};need(set(originals)==expected|{CANON},'restore inventory')
 cfd,canonical=held(CANON)
 try:
  need(canonical['identity']==originals[CANON]['identity'],'canonical preserved identity')
  released=[]
  for i,relative in enumerate(m['release_paths']):
   need(relative!=CANON,'never remove canonical');fd,row=held(relative)
   try:
    need(row['identity']==originals[relative]['identity'],'verified raw identity unchanged')
    save(evidence/f'release-{i:02d}-before.json',dict(raw=row,canonical=canonical,restore_map_sha256=sha(manifest)))
    os.unlink(RAW/relative);released.append(relative)
   finally:os.close(fd)
  need(sha(RAW/CANON)==ZERO,'canonical retained after release')
  save(evidence/'complete.json',dict(passed=True,released=released,recovered_bytes=len(released)*SIZE,canonical=canonical,restore_map_sha256=sha(manifest)))
  print(json.dumps(dict(passed=True,recovered_bytes=len(released)*SIZE)))
 finally:os.close(cfd)
if __name__=='__main__':main()
