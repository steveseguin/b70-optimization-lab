"""Bundle8 chain metadata plus hash-bound packet153 static native closure."""
import json
from pathlib import Path
from reuse_build import verify_native,sha
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
O=ROOT/'experiments/own-xpu-runtime/ops/packet155-orchestration'
def require(value,message):
 if not value:raise ValueError(message)
def check_map(root,entries):
 require(bool(entries),'empty source map')
 for name,digest in entries.items():require(sha(root/name)==digest,'sealed bytes changed: '+name)
def checked():
 native=verify_native()
 parent=json.loads((O/'inputs/packet136-chain-seal.json').read_text())
 require(parent['passed'] and parent['arithmetic']=='iq3-p49-split32-v1','parent identity')
 from bundle_selection import selected
 choice=selected()
 from shared_oracle import static_binding
 require(static_binding()==parent['shared_oracle'],'oracle authority changed')
 from memory_gate import configuration
 ledger=json.loads((P/'memory-plan.json').read_text());configuration(ledger,4096,1,0)
 for leaf in ('composition-bytes.json','real-shape.json'):
  r=json.loads((O/'evidence'/leaf).read_text());require(r['passed'] and not r['device_executed'],'CPU proof missing')
 artifacts=dict(parent['artifacts_sha256'])
 for mode in ('device','gnu-host'):artifacts[mode+'/own-rt-iq3']=native['binaries']['build/'+mode+'/own-rt-iq3']['sha256']
 check_map(B,artifacts)
 require(sha(B/'input/input.json')==parent['input_sha256'],'input changed')
 sources={}
 for directory in (P,O):
  for f in directory.iterdir():
   if f.is_file() and not f.is_symlink() and (f.suffix in ('.py','.sh','.hpp','.cpp','.inc','.patch','.bf16','.tsv','.jsonl') or f.name in ('selection.json','bundle-selection.json','memory-plan.json','chain-registration.json','screen-seal.json','oracle-binding.json','chain-binding.json','policy155.json','storage-measurements.json','startup103.json')):
    sources[str(f.relative_to(ROOT))]=sha(f)
 for name in native['sources']:sources[str((P/name).relative_to(ROOT))]=sha(P/name)
 for f in (O/'inputs/packet153-native.json',O/'inputs/packet136-chain-seal.json',P/'calibration/selection.json',P/'calibration/preregistration.json',O/'evidence/composition-bytes.json',O/'evidence/real-shape.json'):
  sources[str(f.relative_to(ROOT))]=sha(f)
 # Preserve parent closure for unchanged linked helpers; local overrides above win.
 for name,digest in parent['sources'].items():
  if '/oracle/' in name:continue
  if 'packet136-record-bundle/' in name:
   local=P/name.split('packet136-record-bundle/',1)[1]
   if local.exists() and sha(local)==digest:sources[str(local.relative_to(ROOT))]=digest
 check_map(ROOT,sources)
 row=dict(parent,sources=sources,artifacts_sha256=artifacts,original_artifacts_sha256=artifacts,
  bundle_selection=choice,memory_plan=ledger,screen_seal_sha256=choice['screen_seal_sha256'],
  selection=dict(selection_sha256=sha(P/'selection.json'),choices=json.loads((P/'selection.json').read_text())['choices']),
  scope=dict(qualification='CPU preparation only; packet155 fresh chain unmeasured',admission='lane A cards 0+1; whole-host timing windows as packet136'),
  packet155_native_binding_sha256=sha(O/'inputs/packet153-native.json'))
 return row
def verify():
 row=json.loads((P/'build-receipt.json').read_text());require(row==checked(),'chain source/build/selection binding changed');return row
if __name__=='__main__':verify();print('packet155 chain seal PASS')
def main():verify();print('packet155 chain seal PASS')
