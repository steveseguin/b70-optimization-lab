"""Restore only this packet's aliases from hash-verified frozen parent artifacts."""
import json,os
from build_engine import P,ROOT,B,sha,limits,provenance,activate

def main():
 limits()
 from stopped_archive import require_fresh_chain
 require_fresh_chain(B);pins=provenance()
 from prepare_chain import main as restore_parent
 restore_parent()
 fixtures={sha(f):f for f in (P/'evidence').glob('composition-*.bin.gz')}
 for view in (P/'selections').iterdir():
  seal=json.loads((view/'screen-seal.json').read_text());selection=json.loads((view/'selection.json').read_text())
  for leaf,digest in seal['fixture_files'].items():
   dest=view/leaf
   if not dest.exists():dest.write_bytes(fixtures[digest].read_bytes())
   assert sha(dest)==digest
  binary=pins['variants'][selection['choices']['recurrence']]['binaries']
  for mode,item in binary.items():
   dest=view/'build'/mode/'own-rt-iq3';dest.parent.mkdir(parents=True,exist_ok=True)
   assert sha(ROOT/item['path'])==item['sha256']
   if not dest.exists():os.link(ROOT/item['path'],dest)
   assert sha(dest)==item['sha256']==seal['artifacts'][str(dest.relative_to(view))]
 active=json.loads((P/'bundle-selection.json').read_text()) if (P/'bundle-selection.json').exists() else json.loads((P/'baseline-pins.json').read_text())['selection']
 activate(active['recurrence'])
 print('Packet91 aliases restored without rebuilding or changing any parent')
if __name__=='__main__':main()
