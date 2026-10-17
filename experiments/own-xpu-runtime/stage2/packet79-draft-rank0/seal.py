"""Seal six placement/HC views after CPU gates; never starts a device."""
import importlib.util,json,os
from build_engine import P,ROOT,B,BASE,sha,save,limits
from bundle_selection import PLACEMENTS,choices
from bootstrap import install,WRAPPER

def main():
 limits();install()
 from common import verify_map,require
 build=json.loads((P/'build-device-receipt.json').read_text())
 reports={n:json.loads((P/'evidence'/n).read_text()) for n in ('cpu-gates.json','composed-byte-identity.json','protocol.json','full-shape.json','memory-admission.json')}
 for r in [build,*reports.values()]:
  require(r['passed'] and r['device_executed'] is False,'CPU gate missing');verify_map(ROOT,r['sources'])
 verify_map(P,build['artifacts'])
 require(reports['cpu-gates.json']['build_receipt_sha256']==sha(P/'build-device-receipt.json'),'mini build changed')
 require(len(reports['full-shape.json']['runs'])==12 and len(reports['cpu-gates.json']['rows'])==13,'missing full shape/mini executions')
 # Record every unchanged target/draft kernel and native controller source.
 unchanged={}
 for f in P.rglob('*'):
  rel=f.relative_to(P)
  if rel.parts[0] in ('build','selections','evidence') or f.suffix not in ('.cpp','.hpp','.inc') or not (BASE/rel).is_file():continue
  if rel.as_posix()=='mtp.hpp':continue
  require(sha(f)==sha(BASE/rel),'unexpected kernel/controller edit: '+str(rel));unchanged[str(f.relative_to(ROOT))]=sha(f)
 save(P/'evidence/kernel-identity.json',dict(passed=True,device_executed=False,unchanged_sources=unchanged,
      rebuilt_host_path='entry-main / mtp.hpp loader only',kernel_objects='byte-identical packet75 objects; evidence/object-identity.json',
      source_delta='rank0 admission, prefix-only allocation and prefix receipt; no arithmetic edits'))
 sources=dict(build['sources'])
 for r in reports.values():sources.update(r['sources'])
 sources.update(json.loads((P/'dependency-pins.json').read_text()))
 for f in list(P.glob('*.py'))+[P/'placement-policy.json',P/'dependency-pins.json',P/'selection.json']+list((P/'evidence').glob('*.json')):
  if f.name not in ('final-check.json','python-tests.json','queue-plans.json','screen-plans.json'):sources[str(f.relative_to(ROOT))]=sha(f)
 spec=importlib.util.spec_from_file_location('packet79_generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
 allviews=[]
 for placement,(rank,split,boundary) in PLACEMENTS.items():
  for hc in ('production','hc-wide'):
   view=P/'selections'/(placement+'--'+hc);require(not (view/'screen-seal.json').exists(),'never replace a sealed view');view.mkdir(parents=True,exist_ok=True)
   s=json.loads((P/'selection.json').read_text());s['choices']=choices('production',hc,'wide64');save(view/'selection.json',s)
   for n in ('dispatch-speed6.json','memory-plan.json'):(view/n).write_bytes((P/n).read_bytes())
   binary=view/'build/device/own-rt-iq3';binary.parent.mkdir(parents=True,exist_ok=True)
   if not binary.exists():os.link(B/'device/own-rt-iq3',binary)
   selected=reports['composed-byte-identity.json']['views']['production--'+hc+'--wide64']
   require(selected['passed'] and selected['choices']==s['choices'],'selected bytes untested')
   require({(r['compiler'],r['repeat']) for r in selected['runs']}=={(c,r) for c in ('GNU','Intel') for r in (1,2)},'two compiler repeats missing')
   for r in selected['runs']:
    require(r['expected_sha256']==r['candidate_sha256']==sha(ROOT/r['path']/'candidate.bin'),'composed bytes changed')
   for n in ('expected','actual'):
    f=view/('fixture-'+n+'.bin');f.write_bytes((P/'evidence'/('fixture-'+n+'.bin')).read_bytes())
   audit=dict(placement=placement,draft_rank=rank,target_split=split,layer_boundary=boundary,target_layers=[boundary,48-boundary],
      draft_prefix_rows=91392,rank0_private_prefix_bytes=308904960 if rank==0 else 0,
      dispatch_sha256=sha(view/'dispatch-speed6.json'),binary_sha256=sha(binary),
      engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','rank.hpp','mtp.hpp','native_controller.hpp','p56_config.hpp','p56_prefix.hpp')},
      memory_sources=reports['memory-admission.json']['sources'])
   save(view/'placement-audit.json',audit);src={**sources,str((view/'placement-audit.json').relative_to(ROOT)):sha(view/'placement-audit.json')}
   bp=view/'build-receipt.json';fp=view/'byte-fixture.json'
   save(bp,dict(passed=True,device_executed=False,sources=src,artifacts={'build/device/own-rt-iq3':sha(binary)}))
   save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,build_receipt_sha256=sha(bp),sources=reports['cpu-gates.json']['sources'],
      changed_class='Host placement and prefix allocation only. Native miniature target/draft/state match packet75; GNU/Intel composed operator bytes and delayed MTP protocol pass.',
      command=['python3','-B',str(P/'cpu_gate.py')],
      **{k:dict(path='fixture-'+k+'.bin',sha256=sha(view/('fixture-'+k+'.bin'))) for k in ('expected','actual')}))
   generic.create(view,'tp2',bp,fp,binary,view/'dispatch-speed6.json',view/'screen-seal.json');allviews.append(view)
 # Bind all consumers plus candidate seals before any plans or proposed queue job.
 jobsources={str((v/'screen-seal.json').relative_to(ROOT)):sha(v/'screen-seal.json') for v in allviews}
 for n in ('screen_jobs.py','run_screens.py','run_screen.py','worker.py','bootstrap.py','placement.py','placement-policy.json','compare.py','dependency-pins.json'):jobsources[str((P/n).relative_to(ROOT))]=sha(P/n)
 save(P/'screen-jobs-seal.json',dict(passed=True,device_executed=False,wrapper_seal_sha256=sha(WRAPPER/'wrapper-seal.json'),sources=jobsources))
 print('six views sealed; device execution pending')
if __name__=='__main__':main()
