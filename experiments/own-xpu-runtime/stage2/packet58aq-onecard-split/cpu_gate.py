"""Bounded native exactness, real resets, publish skip/repair and refusal gates."""
import json,resource,subprocess,tempfile,hashlib,sys
from pathlib import Path
from build_engine import P,sha,save,limits,compiler_turn
from launch_env import environment

def run(cmd,ok=True):
 cp=subprocess.run(['ionice','-c3',*map(str,cmd)],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=environment())
 if ok and cp.returncode:raise AssertionError(cp.stderr[-2000:]+cp.stdout[-500:])
 return cp

def main():
 limits();resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 records=[]
 with tempfile.TemporaryDirectory(dir=P/'build',prefix='split-cpu-') as d:
  d=Path(d);base=['--mini','--pipeline-mini','--memory','resident','--cache-maintenance','overlap','--context','32','--tokens','8','--retain-steps','1-8','--lookups','resident','--hc','p60fusion','--hc-geometry','hc-wide','--experts','wide64+halfcache','--other-fusion','fused','--retirement','ordered-foreground','--selection',P/'selection.json','--selection-sha256',sha(P/'selection.json')]
  ref=d/'reference';parent=P.with_name('packet58aj-onecard-resident')/'build/gnu-host/own-rt-iq3'
  run([parent,*base,'--output',ref]);result=json.loads((ref/'result.json').read_text())
  def files(o):return {str(f.relative_to(o)):sha(f) for f in o.glob('step*/*') if f.is_file()}
  expected=files(ref);assert expected
  tokens=d/'tokens';tokens.write_text('2 5 3 7 1\n');oracle=d/'oracle';oracle.write_text(' '.join(map(str,result['tokens']))+'\n')
  suite=d/'suite';suite.write_text(''.join(f'r{i} {tokens} {oracle}\n' for i in range(12)))
  table=d/'bracket';arms=[('A0','control'),('U0','no-upload'),('S0','no-scatter'),('D0','drain-only'),('W0','wait-split'),('A1','control')]
  table.write_text(''.join(f'{label} {P/"selection.json"} {sha(P/"selection.json")} overlap max {arm}\n' for label,arm in arms))
  for mode in ('gnu-host','intel-host'):
   out=d/mode;binary=P/'build'/mode/'own-rt-iq3'
   run([binary,*base,'--publication-diagnostic','--suite-inputs',suite,'--bracket-inputs',table,'--output',out])
   resets=0;arenas=set()
   for label,arm in arms:
    assert [json.loads(x)['phase'] for x in (out/label/'host-memory.jsonl').read_text().splitlines()]==['before_view_reset','after_view_reset']
    arenas.add(json.loads((out/label/'boundary.json').read_text())['arena_descriptors_sha256'])
    for i in range(12):
     request=out/label/f'r{i}';assert files(request)==expected
     assert json.loads((request/'result.json').read_text())['tokens']==result['tokens']
     sensors=[json.loads(x) for x in (request/'host-memory.jsonl').read_text().splitlines()]
     assert [v['phase'] for v in sensors]==['before_reset','after_reset'] and all(v['MemAvailable']>0 for v in sensors)
     resets+=1
   assert len(arenas)==1
   records.append(dict(compiler=mode,binary_sha256=sha(binary),passed=True,resets=resets,real_sensor_samples=2*resets+12,view_resets=6,all_fixture_bytes_equal=True))
  # Native oracle refusal must prevent the second view.
  oracle.write_text('31\n');bad=d/'bad';cp=run([P/'build/gnu-host/own-rt-iq3',*base,'--publication-diagnostic','--suite-inputs',suite,'--bracket-inputs',table,'--output',bad],False)
  assert cp.returncode!=0 and not (bad/'U0').exists()
  # Test actual Publish host implementation, including no-upload/no-scatter and final repair.
  source=d/'publish.cpp';source.write_text('#include "'+str(P/'native/publish.hpp')+'"\n#include <cassert>\nint main(){std::array<uint64_t*,144> ptr;uint64_t src[288],stage[288],dst[288];for(int i=0;i<288;++i){src[i]=i+7;stage[i]=31;dst[i]=47;}for(int i=0;i<144;++i)ptr[i]=dst+i*2;void* p[]={stage};p58v::Publish(ptr,2,src,true,false).run(p);for(int i=0;i<288;++i)assert(dst[i]==31);p58v::Publish(ptr,2,src,false,true).run(p);for(int i=0;i<288;++i)assert(dst[i]==31&&stage[i]==src[i]);p58v::Publish(ptr,2,src).run(p);for(int i=0;i<288;++i)assert(dst[i]==src[i]);}\n')
  # Existing entry compiler include set is exactly the right ABI.
  build=json.loads((P/'evidence/build.json').read_text())
  template=next(r['command'] for r in build['commands'] if r['name']=='gnu-host-entry-main')
  for compiler in ('/usr/bin/g++','/opt/intel/oneapi/compiler/2026.0/bin/icpx'):
   cmd=[compiler,*[x for x in template[1:] if x.startswith('-I')],'-std=c++20','-DOWN_RT_HOST_ONLY',source,'-o',d/'publish']
   with compiler_turn():run(cmd)
   run([d/'publish'])
 save(P/'evidence/cpu-exactness.json',dict(passed=True,device_executed=False,records=records,synthetic_weights=True,oracle_refusal=True,publish_skip_repair=True,miniature_cache_publication=False,fullshape_publication_covered_by='preparation.json',parent_binary_sha256=sha(parent),peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024))
 print('PASS GNU/Intel 144 request resets, byte equality, oracle refusal, publication skip/repair')
if __name__=='__main__':main()
