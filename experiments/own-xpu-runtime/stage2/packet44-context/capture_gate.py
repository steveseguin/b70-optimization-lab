"""Inspect compiled capture sizes and reject1025-byte control; no device runs."""
import subprocess,json,resource,hashlib,gzip
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build';IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
def archive_diagnostic(raw):
 digest=hashlib.sha256(raw).hexdigest();packed=gzip.compress(raw,mtime=0)
 assert gzip.decompress(packed)==raw
 path=P/'oversized-capture.log.gz';path.write_bytes(packed)
 return dict(path=path.name,raw_sha256=digest,sha256=hashlib.sha256(packed).hexdigest(),raw_bytes=len(raw))
def main():
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 probe=B/'oversized-capture.cpp';probe.write_text('#include "'+str(P/'kernel_guard.hpp')+'"\n#include <array>\nvoid test(){packet26::checked(std::array<char,1025>{});}\n')
 r=subprocess.run([IC,'-std=c++20','-fsycl','-fsyntax-only',str(probe)],capture_output=True,text=True);assert r.returncode!=0 and 'device kernel capture exceeds 1024 bytes' in r.stderr
 diagnostic=archive_diagnostic(r.stderr.encode())
 nm=subprocess.check_output(['nm','-S','-C',str(B/'device/jit-smoke')],text=True);rows=[]
 for line in nm.splitlines():
  if 'packet26::capture_size<' in line:
   words=line.split(None,3);rows.append(dict(kernel=words[3],bytes=int(words[1],16)))
 assert rows and max(x['bytes'] for x in rows)<=1024
 (P/'kernel-sizes.json').write_text(json.dumps(dict(passed=True,device_executed=False,measurement='compiler sizeof(F) from ELF symbol size; K0 still required for device ABI/JIT',kernel_classes=len(rows),max_after=max(x['bytes'] for x in rows),negative_1025_rejected=True,negative_compile_log=diagnostic,rows=rows),indent=2)+'\n');print(len(rows),'captures;',max(x['bytes'] for x in rows),'bytes maximum')
 probe.unlink()
if __name__=='__main__':main()
