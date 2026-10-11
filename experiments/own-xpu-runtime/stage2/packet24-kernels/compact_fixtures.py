"""Retain complete fixture receipts gzip-verbatim; compact repeated call lists."""
import gzip,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 path=P/'fixture-gates.json';raw=path.read_bytes();data=json.loads(raw)
 if 'verbatim_archive' in data:
  archive=(P/data['verbatim_archive']['path']).read_bytes();assert sha(gzip.decompress(archive))==data['verbatim_archive']['uncompressed_sha256'];return
 packed=gzip.compress(raw,mtime=0);assert gzip.decompress(packed)==raw
 archive=P/'fixture-gates-verbatim.json.gz';archive.write_bytes(packed)
 def compact(value):
  if isinstance(value,dict):
   for k,v in list(value.items()):
    if k=='sequence' and isinstance(v,list):
     value[k+'_count']=len(v);value[k+'_sha256']=sha(json.dumps(v,separators=(',',':')).encode());del value[k]
    else:compact(v)
  elif isinstance(value,list):
   for v in value:compact(v)
 compact(data)
 data['verbatim_archive']=dict(path=archive.name,sha256=sha(packed),uncompressed_sha256=sha(raw),uncompressed_bytes=len(raw),retention='Complete CPU fixture receipts including every owner teardown call; gzip round-trip byte equality verified before compacting JSON.')
 path.write_text(json.dumps(data,indent=2)+'\n')
if __name__=='__main__':main()
