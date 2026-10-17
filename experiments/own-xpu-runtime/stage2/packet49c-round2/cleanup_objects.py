#!/usr/bin/env python3
"""Remove only regenerable packet-local object files after recording identities."""
import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
rows=[]
for f in sorted(B.rglob('*.o')):
 if f.is_symlink():raise RuntimeError('object symlink')
 h=hashlib.sha256()
 with f.open('rb') as stream:
  for b in iter(lambda:stream.read(1048576),b''):h.update(b)
 rows.append(dict(path=str(f.relative_to(P)),bytes=f.stat().st_size,sha256=h.hexdigest()))
receipt=dict(reason='Regenerable packet49c compiler objects removed after CPU gates to fit both registered chains; compiled binaries (sanitizers retained as verified gzip) and compile/link commands retained. CPU preparation peak is capped at 2.5 GB.',objects=rows,bytes=sum(r['bytes'] for r in rows))
(P/'object-cleanup-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
for r in rows:(P/r['path']).unlink()
print(receipt['bytes'],'regenerable object bytes removed')
