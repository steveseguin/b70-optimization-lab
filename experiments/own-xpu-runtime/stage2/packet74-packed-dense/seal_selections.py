"""CPU selector gate and three immutable selection views of one device binary."""
import importlib.util,json,os,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
sys.path.insert(0,str(P/'screen'))
from common import verify_map,require
from cpu_seal import verify as verify_wrapper
CHOICES={name:name for name in ('production','head-packed','dense-packed','combined')}
def link(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True)
 if dst.exists():require(sha(src)==sha(dst),'artifact changed')
 else:os.link(src,dst)
def main():
 limits();verify_wrapper()
 build=json.loads((P/'build-device-receipt.json').read_text());fixture=json.loads((P/'evidence/cpu-byte-identity.json').read_text())
 require(build['passed'] and fixture['passed'] and len(fixture['runs'])==4,'four compiler checks required')
 verify_map(ROOT,build['sources']);verify_map(P,build['artifacts']);verify_map(ROOT,fixture['sources'])
 micro=json.loads((P/'evidence/microbench-build.json').read_text());require(micro['passed'] and not micro['device_executed'],'microbench build');verify_map(ROOT,micro['sources'])
 for name,choice in CHOICES.items():
  v=P/'selections'/name;v.mkdir(parents=True,exist_ok=True);require(not (v/'screen-seal.json').exists(),'immutable view')
  s=json.loads((P/'selection.json').read_text());s['choices']['packed_dense']=choice;save(v/'selection.json',s)
 # Link the actual compiled selector implementation into a small CPU entry.
 cmds=json.loads((P/'engine-commands.json').read_text());base=next(r['command'] for r in cmds if r['name']=='gnu-host-entry-main');base=base[:base.index('-o')]
 commands=[[*base,'-c',str(P/'selection_test.cpp'),'-o',str(B/'selection-test.o')]]
 linkcmd=list(next(r['command'] for r in cmds if r['name']=='gnu-host-link'))
 replaced=[i for i,a in enumerate(linkcmd) if a.endswith('own-rt-iq3-entry.cpp.o')];require(len(replaced)==1,'CPU entry object')
 linkcmd[replaced[0]]=str(B/'selection-test.o');linkcmd[linkcmd.index('-o')+1]=str(B/'selection-test');commands.append(linkcmd)
 for i,cmd in enumerate(commands):
  with (B/f'selection-build-{i}.log').open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
 for name,choice in CHOICES.items():subprocess.run([str(B/'selection-test'),str(P/'selections'/name/'selection.json'),choice],stdin=subprocess.DEVNULL,check=True,timeout=30)
 bad=json.loads((P/'selection.json').read_text());bad['choices']['packed_dense']='unregistered';save(B/'bad-selection.json',bad)
 r=subprocess.run([str(B/'selection-test'),str(B/'bad-selection.json'),'production'],stdin=subprocess.DEVNULL,capture_output=True,timeout=30);require(r.returncode!=0,'unknown selector accepted')
 save(P/'evidence/selection-gate.json',dict(passed=True,device_executed=False,cpu_model_executed=False,views=list(CHOICES),unknown_rejected=True,source_sha256=sha(P/'selection_test.cpp'),binary_sha256=sha(B/'selection-test'),commands=commands))
 spec=importlib.util.spec_from_file_location('generic_screen_seal',P.parent/'screen/seal.py');generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
 extra=[P/'seal_selections.py',P/'selection_test.cpp',P/'evidence/selection-gate.json',P/'evidence/cpu-byte-identity.json',P/'screen/placement-validation/wrapper-seal.json',P/'VRAM.json',P/'memory_report.py',P/'evidence/microbench-build.json',P/'microbench.cpp',P/'build_microbench.py',P/'integrate.py',P/'prepare.py',P/'prepare_screen.py']
 extra.extend((P/'screen').glob('*.py'));extra.extend((P/'screen').glob('jobs-*.txt'))
 for name,choice in CHOICES.items():
  v=P/'selections'/name
  for leaf in ('dispatch-speed6.json','memory-plan.json'):(v/leaf).write_bytes((P/leaf).read_bytes())
  for leaf in build['artifacts']:link(P/leaf,v/leaf)
  for leaf in ('expected.bin','candidate.bin'):link(B/'cpu-gnu/repeat-1'/leaf,v/'fixture'/leaf)
  sources={**build['sources'],**fixture['sources'],**micro['sources'],**{str(f.relative_to(ROOT)):sha(f) for f in extra}}
  engine={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('main.cpp','rank.hpp','mtp.hpp','p56_config.hpp','p56_prefix.hpp','p74_packed.hpp','p74_submit.cpp','p49c_submit.cpp')}
  save(v/'placement-audit.json',dict(placement='1',draft_rank=1,target_split=0,target_layers=[24,24],dispatch_sha256=sha(v/'dispatch-speed6.json'),binary_sha256=sha(v/'build/device/own-rt-iq3'),engine_sources=engine,rationale='packet70 fixed placement; selected dense storage is packed; draft keeps expanded prefix'))
  for leaf in ('selection.json','dispatch-speed6.json','memory-plan.json','placement-audit.json'):sources[str((v/leaf).relative_to(ROOT))]=sha(v/leaf)
  bp=v/'build-receipt.json';fp=v/'byte-fixture.json'
  save(bp,dict(passed=True,device_executed=False,sources=sources,artifacts=build['artifacts']))
  save(fp,dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,changed_class='packed Q6/Q8 decode with original SG32 and split4 arithmetic',command=fixture['runs'][0]['command'],build_receipt_sha256=sha(bp),sources=fixture['sources'],expected=dict(path='fixture/expected.bin',sha256=sha(v/'fixture/expected.bin')),actual=dict(path='fixture/candidate.bin',sha256=sha(v/'fixture/candidate.bin')),fresh_repeats_per_compiler=2,compilers=['GNU','Intel'],cases_per_repeat=60))
  generic.create(v,'tp2',bp,fp,v/'build/device/own-rt-iq3',v/'dispatch-speed6.json',v/'screen-seal.json')
 print('four sealed views; one device binary; no device or CPU model run')
if __name__=='__main__':main()
