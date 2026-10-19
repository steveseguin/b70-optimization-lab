"""Metadata only: bind layer weights without reading GGUF tensor bytes."""
import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];L=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1'
a=json.loads((L/'admission-receipt.json').read_text());assert a['passed']
rows=[]
for t in json.loads((L/'tensor-census.json').read_text())['tensors']:
 if not t['name'].startswith(('blk.0.','blk.3.')):continue
 src=Path(a['model_dir'])/Path(t['shard']).name
 st=next(v['after'] for v in a['files'] if Path(v['path']).name==src.name)
 rows.append(dict(name=t['name'],path=str(src),offset=t['file_offsets'][0],bytes=t['bytes'],type=t['type_id'],dims=t['dimensions'],stat=st))
(P/'weights.json').write_text(json.dumps(dict(identity='iq3-p49-split32-v1',layers=[0,3],tensors=rows),indent=2)+'\n')
text=['#pragma once\nstruct WeightSpec{const char*name;const char*path;size_t offset,bytes;unsigned type,k,rows;unsigned long long size,device,inode,mtime,ctime;};\ninline const WeightSpec weight_specs[]={\n']
for r in rows:
 dims=r['dims'];k=dims[0] if len(dims)>1 else 0;n=r['bytes'] if len(dims)==1 else __import__('math').prod(dims[1:]);st=r['stat']
 text.append('{'+','.join([json.dumps(r['name']),json.dumps(r['path']),str(r['offset']),str(r['bytes']),str(r['type']),str(k),str(n),*[str(st[f])+'ULL' for f in ('bytes','device','inode','mtime_ns','ctime_ns')]])+'},\n')
text.append('};\n');(P/'weights.hpp').write_text(''.join(text))
print(len(rows),'weight descriptors; GGUF bytes read: 0')
