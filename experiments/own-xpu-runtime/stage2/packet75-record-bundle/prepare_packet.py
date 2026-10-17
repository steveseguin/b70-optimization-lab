"""Seal all 24 CPU-checked compositions; shared wrapper stays referenced and pinned."""
import importlib.util,json,os,sys
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import views,choices
from chain_seal import check_map

def link(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True)
 if not dst.exists():os.link(src,dst)
 assert sha(src)==sha(dst)
def main():
 limits()
 build=json.loads((P/'build-device-receipt.json').read_text());fixture=json.loads((P/'evidence/cpu-byte-identity.json').read_text());shape=json.loads((P/'evidence/full-shape.json').read_text())
 assert build['passed'] and fixture['passed'] and shape['passed'] and shape['negative_extent_rejected']
 assert len(fixture['runs'])==8 and len(shape['runs'])==48
 for r in (build,fixture,shape):check_map(ROOT,r['sources'])
 check_map(P,build['artifacts'])
 pin=json.loads((P/'shared-wrapper-pin.json').read_text());check_map(ROOT,pin['sources'])
 sys.path.insert(0,str(P.parent/'screen'))
 spec=importlib.util.spec_from_file_location('screen_generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
 extras=[P/'prepare_packet.py',P/'bundle_selection.py',P/'shared-wrapper-pin.json',P/'evidence/cpu-byte-identity.json',P/'evidence/full-shape.json',P/'build-device-receipt.json',P/'full_shape.py']
 for name,v in views().items():
  view=P/'selections'/name;view.mkdir(parents=True,exist_ok=True);assert not (view/'screen-seal.json').exists()
  s=json.loads((P/'selection.json').read_text());s['choices']=choices(*v);save(view/'selection.json',s)
  for leaf in ('dispatch-speed6.json','memory-plan.json'):(view/leaf).write_bytes((P/leaf).read_bytes())
  for leaf in build['artifacts']:link(P/leaf,view/leaf)
  for leaf in ('expected.bin','candidate.bin'):link(B/'composed-fixture'/leaf,view/'fixture'/leaf)
  sources={**build['sources'],**fixture['sources'],**shape['sources'],**pin['sources'],**{str(f.relative_to(ROOT)):sha(f) for f in extras}}
  audit=dict(placement='1',draft_rank=1,target_split=0,target_layers=[24,24],dispatch_sha256=sha(view/'dispatch-speed6.json'),binary_sha256=sha(view/'build/device/own-rt-iq3'),engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','mtp.hpp','rank.hpp','p49d_submit.cpp','p74_submit.cpp','p60_submit.cpp','p49d_expert_submit.cpp')})
  save(view/'placement-audit.json',audit);sources[str((view/'placement-audit.json').relative_to(ROOT))]=sha(view/'placement-audit.json')
  bp=view/'build-receipt.json';fp=view/'byte-fixture.json';save(bp,dict(passed=True,device_executed=False,sources=sources,artifacts=build['artifacts']))
  save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,changed_class='Independent packed dense plus HC/expert load scheduling; full production allocation/capture path with mock backend',command=['python3','-B',str(P/'cpu_gate.py')],build_receipt_sha256=sha(bp),sources=fixture['sources'],expected=dict(path='fixture/expected.bin',sha256=sha(view/'fixture/expected.bin')),actual=dict(path='fixture/candidate.bin',sha256=sha(view/'fixture/candidate.bin')),compilers=['GNU','Intel'],fresh_repeats_per_compiler=2,composed_choices=choices(*v)))
  generic.create(view,'tp2',bp,fp,view/'build/device/own-rt-iq3',view/'dispatch-speed6.json',view/'screen-seal.json')
 save(P/'cpu-validation.json',dict(passed=True,device_executed=False,cpu_model_executed=False,files={str(f.relative_to(ROOT)):sha(f) for f in [P/'evidence/cpu-byte-identity.json',P/'evidence/full-shape.json',P/'full_shape.py',P/'cpu_gate.py',P/'shared-wrapper-pin.json']}))
 print('24 views sealed; no device execution')
if __name__=='__main__':main()
