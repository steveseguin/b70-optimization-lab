#!/usr/bin/env python3
"""Compare embedded device-program bytes; never execute either engine."""
import hashlib,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
def bundle(binary):
 listing=subprocess.check_output(['readelf','-SW',str(binary)],text=True)
 row=next(line.split() for line in listing.splitlines() if '__CLANG_OFFLOAD_BUNDLE__sycl-spir64' in line)
 offset,size=int(row[4],16),int(row[5],16)
 with binary.open('rb') as f:f.seek(offset);data=f.read(size)
 assert len(data)==size
 return dict(path=str(binary),section=row[1],bytes=size,sha256=hashlib.sha256(data).hexdigest())
def main():
 parent=bundle(P.with_name('packet61x-spin-hcfusion-wait')/'build/device/own-rt-iq3');candidate=bundle(P/'build/device/own-rt-iq3')
 assert (parent['sha256'],parent['bytes'])==(candidate['sha256'],candidate['bytes'])
 result=dict(passed=True,device_executed=False,parent=parent,candidate=candidate)
 (P/'evidence/kernel-bundle-identity.json').write_text(json.dumps(result,indent=2)+'\n');print('device program bytes identical',candidate['bytes'])
if __name__=='__main__':main()
