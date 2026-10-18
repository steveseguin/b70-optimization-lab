"""CPU-only final micro seal. Imports have no resource-setting side effects."""
import json
from pathlib import Path
from build_engine import limits,P
from build_layer import sha
ROOT=P.parents[3]
def main():
 limits()
 cpu=json.loads((P/'evidence/cpu-byte-identity.json').read_text());build=json.loads((P/'evidence/build-device.json').read_text())
 assert cpu['passed'] and build['passed']
 layer=json.loads((P/'evidence/cpu-layer.json').read_text());assert layer['passed'] and not layer['device_executed']
 assert sha(P/'evidence/full-gnu-host/receipt.json')==layer['receipt_sha256']
 host=json.loads((P/'evidence/build-gnu-host.json').read_text());assert host['passed']
 for name,h in host['artifacts'].items():assert sha(P/name)==h,name
 for receipt in (cpu,build,host):
  for name,h in receipt['sources'].items():assert sha(ROOT/name)==h,name
 for name,h in build['objects'].items():assert sha(ROOT/name)==h,name
 for name,h in build['artifacts'].items():assert sha(P/name)==h,name
 assert len(cpu['views']['p117']['runs'])==4
 for compiler in cpu['compilers']:assert sha(ROOT/compiler['binary'])==compiler['binary_sha256']
 files={}
 for pattern in ('*.py','*.cpp','*.hpp','*.json','rope.bf16','evidence/cpu-byte-identity.json','evidence/build-device.json','evidence/cpu-bytes/*','evidence/cpu-layer.json','evidence/build-gnu-host.json','evidence/full-gnu-host/*','evidence/registers.json','evidence/hc-register-summary.json'):
  for f in P.glob(pattern):
   if f.is_file() and f.name!='seal.json':files[str(f.relative_to(P))]=sha(f)
 (P/'seal.json').write_text(json.dumps(dict(schema='packet117.micro-seal.v1',passed=True,device_executed=False,files=files),indent=2)+'\n')
 print('micro sources, CPU receipts, native binary and frozen link inputs sealed; no device executed')
if __name__=='__main__':main()
