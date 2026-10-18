"""Immutable selections using the shared wrapper; never copy or alter it."""
import importlib.util,json,os
from build_engine import P,ROOT,B,sha,save,limits
from screen_jobs import WRAPPER
from common import verify_map,require
from cpu_seal import verify as verify_wrapper

def link(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True)
 if dst.exists():require(sha(src)==sha(dst),'existing artifact changed')
 else:os.link(src,dst)

def main():
 limits();wrapper=verify_wrapper()
 build=json.loads((P/'build-device-receipt.json').read_text())
 fixture=json.loads((P/'evidence/cpu-byte-identity.json').read_text())
 full=json.loads((P/'evidence/fullshape.json').read_text())
 py=json.loads((P/'evidence/python-tests.json').read_text())
 for row in (build,fixture,full,py):
  require(row['passed'] and not row['device_executed'],'CPU gate failed')
  verify_map(ROOT,row['sources'])
 require(len(fixture['runs'])==4 and len(full['results'])==8,'incomplete CPU gates')
 verify_map(P,build['artifacts'])
 parent=P.parent/'packet70-record-bundle'
 pins=json.loads((P/'parent-source-manifest.json').read_text());verify_map(ROOT,pins)
 modified={'main.cpp','rank.hpp','owner_api.hpp','owner_retire.cpp','single_device.cpp','p49d_submit.cpp','selection.json'}
 unchanged={}
 for source,digest in pins.items():
  leaf=Path(source).name
  if leaf not in modified:
   require(sha(P/leaf)==digest,'unexpected parent delta: '+leaf);unchanged[leaf]=digest
 save(P/'evidence/kernel-identity.json',dict(passed=True,device_executed=False,unchanged_parent_files=unchanged,
      modified=sorted(modified),arithmetic_changed=False,qualifying=False,
      rationale='only event retirement, host timing, backend capability and selection parsing changed; inherited numerical objects are byte-pinned'))
 spec=importlib.util.spec_from_file_location('generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
 sources={**build['sources'],**fixture['sources'],**full['sources'],**py['sources'],**wrapper['sources']}
 extra=list(P.glob('*.py'))+[P/'evidence/kernel-identity.json',P/'evidence/cpu-byte-identity.json',P/'evidence/fullshape.json',P/'evidence/python-tests.json',WRAPPER/'wrapper-seal.json',WRAPPER/'placement-validation/wrapper-seal.json',P/'fullshape_test.cpp',P/'retirement_test.cpp']
 sources.update({str(f.relative_to(ROOT)):sha(f) for f in extra})
 for choice in ('production','ordered'):
  v=P/'selections'/choice;v.mkdir(parents=True,exist_ok=True)
  require(not (v/'screen-seal.json').exists(),'selection already sealed')
  s=json.loads((P/'selection.json').read_text());s['choices']['host_retire']=choice;save(v/'selection.json',s)
  for leaf in ('dispatch-speed6.json','memory-plan.json'):(v/leaf).write_bytes((P/leaf).read_bytes())
  for leaf in build['artifacts']:link(P/leaf,v/leaf)
  for leaf in ('expected.bin','candidate.bin'):link(B/'cpu-gnu/repeat-1'/leaf,v/'fixture'/leaf)
  bp=v/'build-receipt.json';fp=v/'byte-fixture.json'
  save(bp,dict(passed=True,device_executed=False,sources=sources,artifacts=build['artifacts']))
  save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,
       changed_class='rank1 ordered-prefix event retirement; identical tiny mock operation/output stream',
       command=fixture['runs'][0]['command'],build_receipt_sha256=sha(bp),sources=fixture['sources'],
       expected=dict(path='fixture/expected.bin',sha256=sha(v/'fixture/expected.bin')),
       actual=dict(path='fixture/candidate.bin',sha256=sha(v/'fixture/candidate.bin')),
       fresh_repeats_per_compiler=2,compilers=['GNU','Intel'],byte_values_per_repeat=3072))
  generic.create(v,'tp2',bp,fp,v/'build/device/own-rt-iq3',v/'dispatch-speed6.json',v/'screen-seal.json')
 job_sources={str(f.relative_to(ROOT)):sha(f) for f in extra}
 for v in (P/'selections').iterdir():
  for leaf in ('selection.json','screen-seal.json','build-receipt.json','byte-fixture.json'):
   job_sources[str((v/leaf).relative_to(ROOT))]=sha(v/leaf)
 save(P/'screen-jobs-seal.json',dict(passed=True,device_executed=False,sources=job_sources,
      wrapper=str(WRAPPER.relative_to(ROOT)),wrapper_seal_sha256=sha(WRAPPER/'wrapper-seal.json')))
 print('production and ordered views sealed; shared v4 pinned; no GPU')

from pathlib import Path
if __name__=='__main__':main()
