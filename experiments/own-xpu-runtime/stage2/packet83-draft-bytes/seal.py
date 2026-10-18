"""Seal draft-only candidates after target parity, fresh repeats and full startup."""
import importlib.util,json,os
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import views,selection
from memory_plans import ledger
from screen_jobs import WRAPPER
from common import verify_map,require
from cpu_seal import verify as verify_wrapper

def link(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True)
 if not dst.exists():os.link(src,dst)
 require(sha(src)==sha(dst),'artifact changed')

def main():
 limits();wrapper=verify_wrapper()
 build=json.loads((P/'build-device-receipt.json').read_text());mini=json.loads((P/'evidence/cpu-gates.json').read_text());shape=json.loads((P/'evidence/full-shape.json').read_text());real=json.loads((P/'evidence/real-head.json').read_text());target=json.loads((P/'evidence/target-identity.json').read_text());py=json.loads((P/'evidence/python-tests.json').read_text())
 for row in (build,mini,shape,real,target,py):
  require(row['passed'] and not row['device_executed'],'CPU gate failed');verify_map(ROOT,row['sources'])
 require(mini['build_receipt_sha256']==sha(P/'build-device-receipt.json'),'mini build changed')
 require(sha(P/'evidence/fixture-expected.bin')==sha(P/'evidence/fixture-actual.bin'),'target fixture changed')
 require(shape['q4_negative_extent_rejected'] and shape['negative_extent_rejected'] and shape['selection_negatives_rejected']==4,'startup negatives incomplete')
 require(shape['binary_sha256']==sha(B/'full-shape/fixture'),'startup binary changed')
 require({(r['view'],r['rank']) for r in shape['runs']}=={(n,r) for n in views() for r in (0,1)},'full shapes missing')
 require(all(r['memory_admission']['passed'] and r['selection_key_consumers_verified'] for r in shape['runs']),'startup admission failed')
 require({(r['compiler'],r['repeat']) for r in real['runs']}=={(c,r) for c in ('GNU','Intel') for r in (1,2)},'full real prefix repeats missing')
 require(all(r['rows']==91392 and r['columns']==2560 and r['actual_sha256']==r['expected_sha256'] for r in real['runs']),'full head reference failed')
 require(len({r['quantized_sha256'] for r in real['runs']})==len({r['actual_sha256'] for r in real['runs']})==1,'full head determinism failed')
 verify_map(P,build['artifacts']);verify_map(ROOT,json.loads((P/'parent-source-manifest.json').read_text()))
 pin=json.loads((P/'shared-wrapper-pin.json').read_text());verify_map(ROOT,pin['sources'])
 spec=importlib.util.spec_from_file_location('p83_generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
 extras=list(P.glob('*.py'))+[P/'shared-wrapper-pin.json',P/'coverage.json',P/'PREREGISTRATION.md',P/'build-device-receipt.json',*[P/'evidence'/n for n in ('cpu-gates.json','full-shape.json','real-head.json','target-identity.json','python-tests.json')],WRAPPER/'wrapper-seal.json',WRAPPER/'placement-validation/wrapper-seal.json']
 sources={**build['sources'],**mini['sources'],**shape['sources'],**real['sources'],**target['sources'],**py['sources'],**wrapper['sources'],**pin['sources'],**{str(f.relative_to(ROOT)):sha(f) for f in extras}}
 job_sources={str(f.relative_to(ROOT)):sha(f) for f in extras}
 for name in views():
  v=P/'compat/packet64-record-bundle/selections'/name;v.mkdir(parents=True,exist_ok=True)
  require(not (v/'screen-seal.json').exists(),'view already sealed')
  require(mini['views'][name]['identical_fresh_repeats'] and mini['views'][name]['target_matches_parent'],'draft repeats or target comparison failed')
  save(v/'selection.json',selection(name));save(v/'memory-plan.json',ledger(name));(v/'dispatch-speed6.json').write_bytes((P/'dispatch-speed6.json').read_bytes())
  for leaf in build['artifacts']:link(P/leaf,v/leaf)
  for kind in ('expected','actual'):link(P/'evidence'/('fixture-'+kind+'.bin'),v/(kind+'.bin'))
  audit=dict(placement='1',draft_rank=1,target_split=0,target_layers=[24,24],dispatch_sha256=sha(v/'dispatch-speed6.json'),binary_sha256=sha(v/'build/device/own-rt-iq3'),engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','mtp.hpp','rank.hpp','p49d_submit.cpp','p83_head.hpp','p59c_select.hpp')})
  save(v/'placement-audit.json',audit);bound={**sources,str((v/'placement-audit.json').relative_to(ROOT)):sha(v/'placement-audit.json')}
  bp=v/'build-receipt.json';fp=v/'byte-fixture.json';save(bp,dict(passed=True,device_executed=False,sources=bound,artifacts=build['artifacts']))
  save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,changed_class='Draft-only Q4/prefix; fixture is unchanged target bytes, draft repeat and full real head reference checks separately required',command=['python3','-B',str(P/'cpu_gate.py')],build_receipt_sha256=sha(bp),sources=mini['sources'],expected=dict(path='expected.bin',sha256=sha(v/'expected.bin')),actual=dict(path='actual.bin',sha256=sha(v/'actual.bin')),draft_may_differ_from_parent=True,draft_fresh_repeats=mini['views'][name],real_head_gate_sha256=sha(P/'evidence/real-head.json')))
  generic.create(v,'tp2',bp,fp,v/'build/device/own-rt-iq3',v/'dispatch-speed6.json',v/'screen-seal.json')
  for leaf in ('selection.json','memory-plan.json','screen-seal.json','build-receipt.json','byte-fixture.json'):job_sources[str((v/leaf).relative_to(ROOT))]=sha(v/leaf)
 save(P/'screen-jobs-seal.json',dict(passed=True,device_executed=False,sources=job_sources,wrapper=str(WRAPPER.relative_to(ROOT)),wrapper_seal_sha256=sha(WRAPPER/'wrapper-seal.json')))
 print('four views sealed; original shared v4 pinned; no GPU')
if __name__=='__main__':main()
