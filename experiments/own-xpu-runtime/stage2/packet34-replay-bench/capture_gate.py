"""ELF/compile-only argument and K0 image closure gates. Never dlopen/execute."""
import collections,hashlib,json,struct,subprocess,os
from pathlib import Path
from build import sha
P=Path(__file__).resolve().parent;B=P/'build'
def image_hashes(binary):
 data=binary.read_bytes();h=struct.unpack_from('<16sHHIQQQIHHHHHH',data);assert h[0][:6]==b'\x7fELF\x02\x01'
 sections=[struct.unpack_from('<IIQQQQIIQQ',data,h[6]+i*h[11]) for i in range(h[12])]
 rows=[]
 symbols=subprocess.check_output(['nice','-n','19','ionice','-c','3','nm','-S',str(binary)],text=True)
 for line in symbols.splitlines():
  fields=line.split()
  if len(fields)!=4 or not fields[3].startswith('.sycl_offloading.') or not fields[3].endswith('.data'):continue
  address,size=int(fields[0],16),int(fields[1],16)
  s=next(s for s in sections if s[3]<=address and address+size<=s[3]+s[5]);start=s[4]+address-s[3]
  image=data[start:start+size];assert image[:4]==b'\x03\x02\x23\x07','expected final SPIR-V image'
  rows.append({'symbol':fields[3],'bytes':size,'sha256':hashlib.sha256(image).hexdigest()})
 assert rows;return rows

def main():
 os.environ['TMPDIR']=str(B/'tmp')
 runtime=B/'device/replay-bench';smoke=B/'device/jit-smoke'
 images=image_hashes(runtime);k0=image_hashes(smoke)
 assert collections.Counter(r['sha256'] for r in images)==collections.Counter(r['sha256'] for r in k0),'K0 and R1 device images differ'
 nm=subprocess.check_output(['nice','-n','19','ionice','-c','3','nm','-S','-C',str(runtime)],text=True);sizes=[]
 for line in nm.splitlines():
  if 'packet26::capture_size<' in line:
   fields=line.split(None,3);sizes.append({'kernel':fields[3],'bytes':int(fields[1],16)})
 assert sizes and max(r['bytes'] for r in sizes)<=1024
 probe=B/'oversized.cpp';probe.write_text('#include "'+str(P.parent/'packet29-merged/kernel_guard.hpp')+'"\n#include <array>\nvoid test(){packet26::checked(std::array<char,1025>{});}\n')
 cmd=['nice','-n','19','ionice','-c','3','/opt/intel/oneapi/compiler/2026.0/bin/icpx','-std=c++20','-fsycl','-fsyntax-only',str(probe)]
 r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode and 'device kernel capture exceeds 1024 bytes' in r.stderr
 (P/'oversized-capture.log').write_text(r.stderr);probe.unlink()
 result={'passed':True,'device_executed':False,'compiler_capture_count':len(sizes),'maximum_capture_bytes':max(r['bytes'] for r in sizes),'negative_1025_rejected':True,'k0_r1_device_images_identical':True,'image_count':len(images),'images':images,'binary_sha256':{'device/replay-bench':sha(runtime),'device/jit-smoke':sha(smoke)},'captures':sizes}
 (P/'capture-gates.json').write_text(json.dumps(result,indent=2)+'\n');print(len(sizes),'captures;',len(images),'identical K0/R1 images')
if __name__=='__main__':main()
