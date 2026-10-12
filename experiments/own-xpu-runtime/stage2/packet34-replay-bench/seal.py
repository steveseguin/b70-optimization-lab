"""Bind final CPU evidence to binaries and source closure, no native execution."""
import hashlib,json,os,subprocess
from pathlib import Path
from build import sha
P=Path(__file__).resolve().parent;B=P/'build';ROOT=P.parents[3]
def main():
 receipt=json.loads((P/'build-receipt.json').read_text())
 binaries={str(x.relative_to(B)):sha(x) for mode in ['host','icpx-host','asan','device'] for name in ['replay-bench','jit-smoke'] if (x:=B/mode/name).is_file()}
 assert len(binaries)==5 and binaries==receipt['binaries']
 gates={name:json.loads((P/name).read_text()) for name in ['cpu-tests.json','capture-gates.json','lifetime-tests.json','window-tests.json','raw-abi-gate.json']}
 assert all(x['passed'] for x in gates.values())
 for row in gates['cpu-tests.json']['rows']:assert row['binary_sha256']==binaries[row['compiler']+'/replay-bench']
 assert gates['capture-gates.json']['binary_sha256']=={k:v for k,v in binaries.items() if k.startswith('device/')}
 source_proof=json.loads((P/'source-proof.json').read_text())
 for name,digest in source_proof['unchanged_packet29_inputs'].items():assert sha(ROOT/name)==digest,name
 census=json.loads((P/'census.json').read_text());assert census['native_launches_source_census']==1142
 assert census['device_bytes']==4766268444
 files={str(f.relative_to(ROOT)):sha(f) for f in P.iterdir() if f.is_file() and (f.suffix in ['.cpp','.hpp','.py','.tsv'] or f.name in ['CMakeLists.txt','dispatch-measured.json'])}
 versions={}
 for c in ['/usr/bin/g++','/opt/intel/oneapi/compiler/2026.0/bin/icpx']:
  versions[c]=subprocess.check_output(['nice','-n','19','ionice','-c','3',c,'--version'],text=True).splitlines()[0]
 receipt.update(passed=True,device_executed=False,qualified=False,modes_built=['direct','graph-whole','graph-layer'],raw_available=False,native_launches_source_census=1142,application_device_bytes=census['device_bytes'],gate_receipts={n:sha(P/n) for n in gates},source_files=files,upstream_source_proof_sha256=sha(P/'source-proof.json'),compiler_versions=versions,preparation_affinity=sorted(os.sched_getaffinity(0)),preparation_nice=os.getpriority(os.PRIO_PROCESS,0),host_only_gates=True)
 (P/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 (P/'BINARY-HASHES.md').write_text('# CPU-built binaries\n\nNo device executable ran during preparation.\n\n| Binary | SHA-256 |\n| --- | --- |\n'+''.join(f'| `build/{name}` | `{digest}` |\n' for name,digest in binaries.items()))
 print(json.dumps({'passed':True,'binaries':len(binaries),'device_executed':False}))
if __name__=='__main__':main()
