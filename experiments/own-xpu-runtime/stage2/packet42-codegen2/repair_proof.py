"""CPU file-only proof that repaired executables retain recorded kernel bytes."""
import hashlib,json
from pathlib import Path
from seal import BINARIES
P=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 old=json.loads((P/'evidence/20261012-k0-empty-bindings/build-receipt.json').read_text())['native_binary_sha256']
 # Preserve prior fixture provenance after the arithmetic build rewrites its receipt.
 prior=json.loads((P/'evidence/20261012-k0-empty-bindings/tiny-cpu-gates.json').read_text())
 tiny=json.loads((P/'tiny-cpu-gates.json').read_text())
 for path,digest in prior['inherited_fixture_hashes'].items():assert sha((P.parent/path).read_bytes())==digest
 for key in ('inherited_fixture_hashes','generated_fixture_names'):tiny[key]=prior[key]
 tiny['source_hashes']['tiny_source_gate.py']=sha((P/'tiny_source_gate.py').read_bytes())
 (P/'tiny-cpu-gates.json').write_text(json.dumps(tiny,indent=2)+'\n')
 rows=[]
 for name,path in BINARIES.items():
  binary=(P/path).read_bytes();digests=[];records=[]
  if name in ('floor','tiny'):
   family='launch' if name=='floor' else 'tiny';record=family+'-assembly.json'
   digests=[r['sha256'] for r in json.loads((P/record).read_text())['artifacts'] if 'spv' in r];records=[record]
  elif name=='gemv':
   records=['native-module-binding.json'];digests=[r['module_sha256'] for r in json.loads((P/records[0]).read_text())['expert_modules']]
  elif name=='parallel':
   records=['parallel-current-binary-proof.json'];digests=[r['spv_sha256'] for r in json.loads((P/records[0]).read_text())]
  elif name=='route':
   records=['route42-offline.json'];digests=[r['sha256'] for r in json.loads((P/records[0]).read_text())['rows']]
  else:
   # Exact executable identity also preserves every linked module.
   assert sha(binary)==old[path]
  modules={sha(f.read_bytes()):f for f in (P/path).parent.joinpath('spv').glob('*.spv')}
  proof=[]
  for digest in digests:
   data=modules[digest].read_bytes();offset=binary.find(data);assert offset>=0
   proof.append(dict(spv_sha256=digest,bytes=len(data),binary_offset=offset))
  rows.append(dict(program=name,binary=path,previous_binary_sha256=old[path],binary_sha256=sha(binary),unchanged_executable=sha(binary)==old[path],historical_records=records,byte_identical_modules=proof))
 (P/'repair-module-proof.json').write_text(json.dumps(dict(passed=True,device_executed=False,rows=rows),indent=2)+'\n')
 (P/'BINARIES.sha256').write_text(''.join(r['binary_sha256']+'  '+r['binary']+'\n' for r in rows))
 print('six native identities and recorded kernel modules PASS')
if __name__=='__main__':main()
