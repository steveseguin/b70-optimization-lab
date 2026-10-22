"""CPU-only seal refresh; does not grant device readiness."""
import hashlib,json,resource,shutil,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet190-record-bundle-k3x'
sys.path.insert(0,str(P))
def main():
 assert shutil.disk_usage('/').free>=27_000_000_000
 from chain_seal import orchestration_files
 # Packet copies of exactly the ops files chain_seal pins (the guard sees only packet-internal pins).
 snapshot=P/'orchestration-snapshot';snapshot.mkdir(exist_ok=True)
 live={f.name for f in orchestration_files()}
 for f in snapshot.iterdir():
  if f.is_file() and f.name not in live:f.unlink()
 for f in orchestration_files():shutil.copy2(f,snapshot/f.name)
 for leaf in ('packet189-native.json','packet136-chain-seal.json'):shutil.copy2(O/'inputs'/leaf,P/'lineage-inputs'/leaf)
 for leaf in ('composition-bytes.json','real-shape.json'):shutil.copy2(O/'evidence'/leaf,P/'evidence'/leaf)
 from chain_seal import checked,verify
 (P/'build-receipt.json').write_text(json.dumps(checked(),indent=2)+'\n');verify()
 # Use the repaired submission implementation, never an inherited external writer.
 sys.path.insert(0,str(O))
 import importlib.util
 spec=importlib.util.spec_from_file_location('p190_submission',O/'submission_evidence.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 m.pin_resealed_packet56()
 print('packet190 source/native/selection seal and submission pins PASS')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
