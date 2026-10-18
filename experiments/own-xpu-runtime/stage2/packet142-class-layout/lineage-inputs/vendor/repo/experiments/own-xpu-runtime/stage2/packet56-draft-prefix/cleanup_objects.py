#!/usr/bin/env python3
"""Remove only regenerable packet-local object files after recording identities."""
import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
receipt_path=P/'object-cleanup-receipt.json'
previous=json.loads(receipt_path.read_text())['objects'] if receipt_path.exists() else []
rows=[]
for f in sorted(B.rglob('*.o')):
 if f.is_symlink():raise RuntimeError('object symlink')
 h=hashlib.sha256()
 with f.open('rb') as stream:
  for b in iter(lambda:stream.read(1048576),b''):h.update(b)
 rows.append(dict(path=str(f.relative_to(P)),bytes=f.stat().st_size,sha256=h.hexdigest()))
combined={r['path']:r for r in previous}
for row in rows:
 if row['path'] in combined and combined[row['path']]!=row:raise RuntimeError('changed previously removed object; preserve and review')
 combined[row['path']]=row
receipt=dict(reason='Only packet56 regenerable compiler objects removed after their consumers finish; executables and compile/link commands retained. Cumulative inventory supports staged cleanup within1.5GB build cap.',objects=list(combined.values()),bytes=sum(r['bytes'] for r in combined.values()))
(P/'object-cleanup-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
for r in rows:(P/r['path']).unlink()
print(receipt['bytes'],'regenerable object bytes removed')
