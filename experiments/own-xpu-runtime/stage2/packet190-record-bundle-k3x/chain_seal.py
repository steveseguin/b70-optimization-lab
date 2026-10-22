"""Bundle8 chain metadata plus the hash-bound packet189 k3x native closure (V3 head placement + k3 boundary + trims + static snapshot)."""
import json
from pathlib import Path
from reuse_build import verify_native,sha
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
O=ROOT/'experiments/own-xpu-runtime/ops/packet190-orchestration'
def require(value,message):
 if not value:raise ValueError(message)
SUFFIXES=('.py','.sh','.hpp','.cpp','.inc','.patch','.bf16','.tsv','.jsonl')
NAMES=('selection.json','bundle-selection.json','memory-plan.json','chain-registration.json','screen-seal.json','oracle-binding.json','chain-binding.json','policy190.json','storage-measurements.json','startup103.json')
def pinned_file(f):return f.is_file() and not f.is_symlink() and (f.suffix in SUFFIXES or f.name in NAMES)
def orchestration_files():return sorted(f for f in O.iterdir() if pinned_file(f))
def real(f):
 r=Path(f).resolve();require(r.is_relative_to(P),'path leaves packet190: '+str(f));return r
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
 # Packet-root hard links (guard_layout190.py) carry the same inodes as the build/ names the chain runs.
 import os
 for name in artifacts:require(os.stat(P/name).st_ino==os.stat(B/name).st_ino,'packet-root artifact link differs from build/: '+name)
 link_targets=P/'lineage-inputs/link-targets/build/fusion-fixtures'
 fixtures={str((link_targets/k).relative_to(ROOT)):v for k,v in parent['fixture_inputs_sha256'].items()}
 for k in parent['fixture_inputs_sha256']:require(os.stat(link_targets/k).st_ino==os.stat(B/'fusion-fixtures'/k).st_ino,'fixture link differs from build/fusion-fixtures: '+k)
 check_map(ROOT,fixtures)
 oracle={'experiments/own-xpu-runtime/stage2/packet49-integrate/oracle/'+k:v for k,v in parent['oracle_inputs_sha256'].items()}
 check_map(ROOT,oracle)
 require(sha(B/'input/input.json')==parent['input_sha256'],'input changed')
 # Every pin names a byte inside this packet (lane-queue pin guard: 0 cross-packet mutable pins).
 # ops/packet190-orchestration files are pinned through their byte-identical packet copies in
 # orchestration-snapshot/ (refreshed by seal190.py) and every live ops file must equal its copy;
 # symlinked provenance directories (calibration/, prefix-calibration/, parent-snapshot/) are pinned
 # at their real lineage-inputs/ paths (packet143 layout).
 sources={}
 for f in P.iterdir():
  if pinned_file(f):sources[str(f.relative_to(ROOT))]=sha(f)
 S=P/'orchestration-snapshot'
 live={f.name for f in orchestration_files()}
 require(live=={f.name for f in S.iterdir() if f.is_file()},'orchestration snapshot file set differs from ops/packet190-orchestration')
 for f in orchestration_files():
  require(sha(S/f.name)==sha(f),'ops file differs from its sealed packet copy: '+f.name)
  sources[str((S/f.name).relative_to(ROOT))]=sha(S/f.name)
 for name in native['sources']:sources[str(real(P/name).relative_to(ROOT))]=sha(P/name)
 for live_copy,local in ((O/'inputs/packet189-native.json',P/'lineage-inputs/packet189-native.json'),(O/'inputs/packet136-chain-seal.json',P/'lineage-inputs/packet136-chain-seal.json'),
                         (O/'evidence/composition-bytes.json',P/'evidence/composition-bytes.json'),(O/'evidence/real-shape.json',P/'evidence/real-shape.json')):
  require(sha(live_copy)==sha(local),'ops input/evidence differs from its packet copy: '+live_copy.name)
  sources[str(local.relative_to(ROOT))]=sha(local)
 for f in (P/'calibration/selection.json',P/'calibration/preregistration.json'):
  sources[str(real(f).relative_to(ROOT))]=sha(f)
 # Preserve parent closure for unchanged linked helpers; local overrides above win.
 for name,digest in parent['sources'].items():
  if '/oracle/' in name:continue
  if 'packet136-record-bundle/' in name:
   local=P/name.split('packet136-record-bundle/',1)[1]
   if local.exists() and sha(local)==digest:sources[str(real(local).relative_to(ROOT))]=digest
 require(all(real(ROOT/name).is_relative_to(P) for name in sources),'a sealed source lies outside packet190')
 check_map(ROOT,sources)
 row=dict(parent,sources=sources,artifacts_sha256=artifacts,original_artifacts_sha256=artifacts,fixture_inputs_sha256=fixtures,oracle_inputs_sha256=oracle,
  bundle_selection=choice,memory_plan=ledger,screen_seal_sha256=choice['screen_seal_sha256'],
  selection=dict(selection_sha256=sha(P/'selection.json'),choices=json.loads((P/'selection.json').read_text())['choices']),
  scope=dict(qualification='CPU preparation only; packet190 k3x fresh chain unmeasured',admission='lane A cards 0+1; whole-host timing windows as packet136'),
  packet190_native_binding_sha256=sha(O/'inputs/packet189-native.json'),
  v3=json.loads((P/'bundle-selection.json').read_text())['v3'],k3x=json.loads((P/'bundle-selection.json').read_text())['k3x'])
 return row
def verify():
 row=json.loads((P/'build-receipt.json').read_text());require(row==checked(),'chain source/build/selection binding changed');return row
if __name__=='__main__':verify();print('packet190 chain seal PASS')
def main():verify();print('packet190 chain seal PASS')
