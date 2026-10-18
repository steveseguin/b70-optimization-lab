"""Seal three byte-checked views only after actual full-shape startup succeeds."""
import importlib.util,json,os,gzip,hashlib
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import views,choices
from screen_jobs import WRAPPER
from common import verify_map,require
from cpu_seal import verify as verify_wrapper
def link(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True)
 if not dst.exists():os.link(src,dst)
 require(sha(src)==sha(dst),'artifact changed')
def main():
 limits();wrapper=verify_wrapper()
 build=json.loads((P/'build-device-receipt.json').read_text());fixture=json.loads((P/'evidence/cpu-byte-identity.json').read_text());shape=json.loads((P/'evidence/full-shape.json').read_text());py=json.loads((P/'evidence/python-tests.json').read_text())
 micro=json.loads((P/'evidence/microbench-build.json').read_text());offline=json.loads((P/'evidence/offline/report.json').read_text())
 verify_map(P,micro['artifacts'])
 admission=json.loads((P/'evidence/full-shape-admission.json').read_text())
 for row in (build,fixture,shape,py,admission,micro,offline):
  require(row['passed'] and not row['device_executed'],'CPU gate failed');verify_map(ROOT,row['sources'])
 verify_map(P,build['artifacts']);verify_map(ROOT,json.loads((P/'parent-source-manifest.json').read_text()))
 pin=json.loads((P/'shared-wrapper-pin.json').read_text());verify_map(ROOT,pin['sources'])
 require(shape['negative_extent_rejected'] and shape['selection_negatives_rejected']==5 and shape['binary_sha256']==sha(B/'full-shape/fixture'),'startup negatives incomplete')
 require({(r['view'],r['rank']) for r in shape['runs']}=={(n,r) for n in views() for r in (0,1)},'all full shapes required')
 require(all(r['passed'] and r['selection_key_consumers_verified'] and 0<r['postload_device_bytes']<=30*1024**3 for r in shape['runs']),'full shape result')
 require(len(shape['negative_allocations'])==6 and len(shape['scope_negatives'])==14,'all startup negatives required')
 require(len(admission['runs'])==6,'all memory admissions required')
 require(set(fixture['views'])==set(views()),'all CPU views required')
 spec=importlib.util.spec_from_file_location('p81_generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
 extras=list(P.glob('*.py'))+[P/'shared-wrapper-pin.json',P/'evidence/microbench-build.json',P/'evidence/offline/report.json',P/'build-device-receipt.json',P/'evidence/cpu-byte-identity.json',P/'evidence/full-shape.json',P/'evidence/python-tests.json',P/'evidence/full-shape-admission.json',*[P/'evidence'/('memory-plan-'+n+'.json') for n in views()],WRAPPER/'wrapper-seal.json',WRAPPER/'placement-validation/wrapper-seal.json']
 sources={**build['sources'],**fixture['sources'],**shape['sources'],**py['sources'],**wrapper['sources'],**pin['sources'],**micro['sources'],**offline['sources'],**{str(f.relative_to(ROOT)):sha(f) for f in extras}}
 sources.update({str(f.relative_to(ROOT)):sha(f) for f in (P/'evidence/cpu-bytes').iterdir() if f.is_file()})
 job_sources={str(f.relative_to(ROOT)):sha(f) for f in extras}
 for name in views():
  v=P/'compat/packet64-record-bundle/selections'/name;v.mkdir(parents=True,exist_ok=True)
  require(not (v/'screen-seal.json').exists(),'view already sealed')
  selected=fixture['views'][name];require(selected['passed'] and selected['choices']==choices(name),'wrong byte view')
  require({(r['compiler'],r['repeat']) for r in selected['runs']}=={(c,r) for c in ('GNU','Intel') for r in (1,2)},'fresh compiler repeats missing')
  for run in selected['runs']:
   require(run['cases']==32 and run['raw_fp32_chain_checks']>60000 and run['raw_fp32_tree_checks']>3000,'fixture coverage')
   require(run['candidate_sha256']==run['expected_sha256'],'bytes differ')
   retained=ROOT/run['raw_evidence'];require(sha(retained)==run['raw_evidence_sha256'],'raw archive changed');require(hashlib.sha256(gzip.decompress(retained.read_bytes())).hexdigest()==run['expected_sha256'],'raw bytes changed');require(sha(ROOT/run['cases_path'])==run['cases_sha256'],'case evidence changed')
  require(len({r['candidate_sha256'] for r in selected['runs']})==1,'cross compiler bytes differ')
  s=json.loads((P/'selection.json').read_text());s['choices']=choices(name);save(v/'selection.json',s)
  (v/'dispatch-speed6.json').write_bytes((P/'dispatch-speed6.json').read_bytes());(v/'memory-plan.json').write_bytes((P/'evidence'/('memory-plan-'+name+'.json')).read_bytes())
  for leaf in build['artifacts']:link(P/leaf,v/leaf)
  # Retain compact digest receipts after reading and checking all raw fixture bytes.
  for kind in ('expected','candidate'):(v/(kind+'.bin')).write_text(selected['runs'][0][kind+'_sha256']+'\n')
  audit=dict(placement='1',draft_rank=1,target_split=0,target_layers=[24,24],dispatch_sha256=sha(v/'dispatch-speed6.json'),binary_sha256=sha(v/'build/device/own-rt-iq3'),engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','mtp.hpp','rank.hpp','p49d_submit.cpp','p60_submit.cpp','p65_expert.hpp','p49d_expert_submit.cpp','p93_head.hpp','p93_kernel.hpp','p93_submit.cpp')})
  save(v/'placement-audit.json',audit);bound={**sources,str((v/'placement-audit.json').relative_to(ROOT)):sha(v/'placement-audit.json')}
  bp=v/'build-receipt.json';fp=v/'byte-fixture.json';receipt=dict(passed=True,device_executed=False,sources=bound,artifacts=build['artifacts'])
  refresh=P/'evidence/reseal-provenance.json'
  if refresh.exists():
   receipt['provenance_refresh']=json.loads(refresh.read_text());receipt['sources'][str(refresh.relative_to(ROOT))]=sha(refresh)
  save(bp,receipt)
  save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,changed_class='exact target Q6_K head word-plane decode or reversible transposed storage; complete raw comparisons retained compressed',command=selected['runs'][0]['command'],build_receipt_sha256=sha(bp),sources=fixture['sources'],expected=dict(path='expected.bin',sha256=sha(v/'expected.bin')),actual=dict(path='candidate.bin',sha256=sha(v/'candidate.bin')),raw_runs=selected['runs'],choices=choices(name)))
  generic.create(v,'tp2',bp,fp,v/'build/device/own-rt-iq3',v/'dispatch-speed6.json',v/'screen-seal.json')
  for leaf in ('selection.json','screen-seal.json','build-receipt.json','byte-fixture.json'):job_sources[str((v/leaf).relative_to(ROOT))]=sha(v/leaf)
 save(P/'screen-jobs-seal.json',dict(passed=True,device_executed=False,sources=job_sources,wrapper=str(WRAPPER.relative_to(ROOT)),wrapper_seal_sha256=sha(WRAPPER/'wrapper-seal.json')))
 print('three views sealed; original shared v4 pinned; no GPU')
if __name__=='__main__':main()
