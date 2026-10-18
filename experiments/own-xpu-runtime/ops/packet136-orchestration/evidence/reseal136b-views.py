import sys,json,resource,importlib.util
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
o=Path('experiments/own-xpu-runtime/ops/packet136-orchestration').resolve();sys.path.insert(0,str(o))
from source_decision import O,P,ROOT,save,sha
sys.path.insert(0,str(P))
from bootstrap import install
install()
spec=importlib.util.spec_from_file_location('generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
key=str((P/'confirm136.py').relative_to(ROOT))
for view in sorted((P/'selections').iterdir()):
 if not (view/'screen-seal.json').exists():continue
 seal=json.loads((view/'screen-seal.json').read_text())
 changed=[n for n,h in seal['sources'].items() if sha(ROOT/n)!=h]
 if not changed:continue
 archive=O/'evidence'/('before-136b-view-'+sha(view/'screen-seal.json')+'.json')
 # Original pre-repair views were already archived before any reseal.
 changed=[n for n,h in seal['sources'].items() if sha(ROOT/n)!=h]
 assert set(changed)<={key,str((P/'startup103.json').relative_to(ROOT)),str((P/'evidence/startup103-runs.json.gz').relative_to(ROOT))},changed
 build=json.loads((view/'build-receipt.json').read_text());build['sources'].update({n:sha(ROOT/n) for n in changed if n in build['sources']});save(view/'build-receipt.json',build)
 fixture=json.loads((view/'byte-fixture.json').read_text());fixture['build_receipt_sha256']=sha(view/'build-receipt.json');save(view/'byte-fixture.json',fixture)
 new=view/'screen-seal-136b.tmp'
 generic.create(view,'tp2',view/'build-receipt.json',view/'byte-fixture.json',view/'build/device/own-rt-iq3',view/'dispatch-speed6.json',new)
 new.replace(view/'screen-seal.json')
 print('refreshed only confirm source and dependent hashes:',view.name)
from confirm136 import view
candidate=view('candidate')
(P/'screen-seal.json').write_bytes((candidate/'screen-seal.json').read_bytes())
bundle=json.loads((P/'bundle-selection.json').read_text());bundle['screen_seal_sha256']=sha(candidate/'screen-seal.json');save(P/'bundle-selection.json',bundle)
