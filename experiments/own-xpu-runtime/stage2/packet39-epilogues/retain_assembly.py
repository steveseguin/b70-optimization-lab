"""Retain exact final offline evidence, verifying every archived member's bytes."""
import gzip,hashlib,io,json,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent
files=set()
for row in json.loads((P/'candidate-modules.json').read_text()):
 files.add(P/row['module'])
 files.update(f for f in (P/row['dump']).iterdir() if f.suffix in {'.asm','.dat','.progbin','.zeinfo'})
rows=[]
archive=P/'evidence'/'final-offline.tar.gz'
with archive.open('wb') as raw, gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,filename='') as gz, tarfile.open(fileobj=gz,mode='w|') as tf:
 for f in sorted(files):
  data=f.read_bytes();name=str(f.relative_to(P));h=hashlib.sha256(data).hexdigest()
  info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;info.mtime=0
  tf.addfile(info,io.BytesIO(data));rows.append(dict(path=name,bytes=len(data),sha256=h))
with tarfile.open(archive,'r:gz') as tf:
 for row in rows:
  assert hashlib.sha256(tf.extractfile(row['path']).read()).hexdigest()==row['sha256']
receipt=dict(schema='packet39.offline-retention.v1',device_executed=False,archive=str(archive.relative_to(P)),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),bytes=archive.stat().st_size,members=rows,all_member_bytes_verified=True,reason='Exact disassembly and ELF text proof for every shipped fused/control kernel; not reproducible from a count summary alone.',restore='Extract only into this packet directory; members retain their build/ paths. Re-run analyze.py and assembly_gate.py to review.')
(P/'offline-retention.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(len(rows),'members',receipt['bytes'],'bytes, all verified')
