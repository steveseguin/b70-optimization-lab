"""Seal both host-report views after independent CPU and startup gates."""
import importlib.util,json,os,gzip,hashlib
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import views,choices,selection
from screen_jobs import WRAPPER
from common import verify_map,require
from cpu_seal import verify as verify_wrapper

def main():
 limits();wrapper=verify_wrapper();sources={}
 gates={}
 for name in ('build-device-receipt.json','evidence/cpu-byte-identity.json','evidence/mini-gate.json','evidence/full-shape.json','evidence/full-shape-admission.json','evidence/python-tests.json'):
  row=json.loads((P/name).read_text());require(row['passed'] and not row['device_executed'],'CPU gate failed: '+name);verify_map(ROOT,row['sources']);sources.update(row['sources']);gates[name]=row
 build=gates['build-device-receipt.json'];fixture=gates['evidence/cpu-byte-identity.json'];shape=gates['evidence/full-shape.json'];mini=gates['evidence/mini-gate.json']
 verify_map(P,build['artifacts']);verify_map(ROOT,json.loads((P/'parent-source-manifest.json').read_text()))
 pin=json.loads((P/'shared-wrapper-pin.json').read_text());verify_map(ROOT,pin['sources']);sources.update(pin['sources']);sources.update(wrapper['sources'])
 require({(r['view'],r['rank']) for r in shape['runs']}=={(n,r) for n in views() for r in (0,1)},'missing startup view/rank')
 require(all(r['selection_key_consumers_verified'] and 0<r['postload_device_bytes']<=30*1024**3 for r in shape['runs']),'startup proof')
 require(len(shape['negatives'])==4 and all(r['passed'] for r in shape['negatives']),'negative startup proof')
 require(len(mini['rows'])==5 and len({r['identity_sha256'] for r in mini['rows']})==1,'parent84/production/candidate identity')
 require({(r['compiler'],r['repeat']) for r in fixture['runs']}=={(c,r) for c in ('GNU','Intel') for r in (1,2)},'dual compiler repeat proof')
 require(all(r['negative_cases']==9 and r['expected_sha256']==r['candidate_sha256'] for r in fixture['runs']),'mock state/error proof')
 require(len({r['candidate_sha256'] for r in fixture['runs']})==1,'cross compiler bytes')
 for r in fixture['runs']:
  path=ROOT/r['raw_evidence'];require(sha(path)==r['raw_evidence_sha256'],'raw archive changed');require(hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()==r['expected_sha256'],'raw bytes changed')
 spec=importlib.util.spec_from_file_location('generic_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
 extras=list(P.glob('*.py'))+[P/'shared-wrapper-pin.json',P/'parent-source-manifest.json',P/'packet92-host.patch',*[P/n for n in gates],*[P/'evidence'/('memory-plan-'+n+'.json') for n in views()],WRAPPER/'wrapper-seal.json',WRAPPER/'placement-validation/wrapper-seal.json']
 extras += [f for f in (P/'evidence').iterdir() if f.suffix in ('.gz','.bin') or f.name.startswith('mini-') and f.suffix=='.json']
 sources.update({str(f.relative_to(ROOT)):sha(f) for f in extras});job_sources={str(f.relative_to(ROOT)):sha(f) for f in extras}
 for name in views():
  v=P/'compat/packet64-record-bundle/selections'/name;v.mkdir(parents=True,exist_ok=True);require(not (v/'screen-seal.json').exists(),'never replace a seal')
  save(v/'selection.json',selection(name))
  for src,dst in ((P/'dispatch-speed6.json',v/'dispatch-speed6.json'),(P/'evidence'/('memory-plan-'+name+'.json'),v/'memory-plan.json')):dst.write_bytes(src.read_bytes())
  for leaf in build['artifacts']:
   dst=v/leaf;dst.parent.mkdir(parents=True,exist_ok=True)
   if not dst.exists():os.link(P/leaf,dst)
   require(sha(dst)==build['artifacts'][leaf],'binary identity')
  for leaf in ('expected.bin','candidate.bin'):(v/leaf).write_bytes(gzip.decompress((ROOT/fixture['runs'][0]['raw_evidence']).read_bytes()))
  save(v/'placement-audit.json',dict(placement='1',draft_rank=1,target_split=0,target_layers=[24,24],dispatch_sha256=sha(v/'dispatch-speed6.json'),binary_sha256=sha(v/'build/device/own-rt-iq3'),engine_sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','rank.hpp','native_controller.hpp','mtp.hpp','reply_first.hpp','p49d_submit.cpp')}))
  bound={**sources,str((v/'placement-audit.json').relative_to(ROOT)):sha(v/'placement-audit.json')}
  bp=v/'build-receipt.json';fp=v/'byte-fixture.json';save(bp,dict(passed=True,device_executed=False,sources=bound,artifacts=build['artifacts']))
  save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,changed_class='host report scheduling; real mailbox plus mock state/error, unchanged kernels, miniature engine parity with packet84',command=fixture['runs'][0]['command'],build_receipt_sha256=sha(bp),sources=fixture['sources'],expected=dict(path='expected.bin',sha256=sha(v/'expected.bin')),actual=dict(path='candidate.bin',sha256=sha(v/'candidate.bin')),raw_runs=fixture['runs'],choices=choices(name)))
  generic.create(v,'tp2',bp,fp,v/'build/device/own-rt-iq3',v/'dispatch-speed6.json',v/'screen-seal.json')
  for leaf in ('selection.json','screen-seal.json','build-receipt.json','byte-fixture.json'):job_sources[str((v/leaf).relative_to(ROOT))]=sha(v/leaf)
 save(P/'screen-jobs-seal.json',dict(passed=True,device_executed=False,sources=job_sources,wrapper=str(WRAPPER.relative_to(ROOT)),wrapper_seal_sha256=sha(WRAPPER/'wrapper-seal.json')))
 print('two views sealed; original shared v4 pinned; no GPU')
if __name__=='__main__':main()
