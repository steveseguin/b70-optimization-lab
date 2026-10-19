"""Real rank argv/shapes, device compiler/defines, CPU transport-only preparation.

GGUF data is replaced by descriptors from the saved plan, weights by inert
disjoint virtual addresses and kernel execution by markers. No device is enumerated.
Old direct q.submit calls are trapped BEFORE queue contact. Frozen inherited M=1 operations are mocked (some query queue capabilities);
all new paired operations must populate the actual SubmissionCapture used by SyclDevice::prepare.
This proves preparation/dispatch, not numerical inference on the real model.
"""
import json,os,resource,subprocess,sys
from pathlib import Path
from p151_v5_build_engine import P,LOCAL,ROOT,B,save,sha
import freeze_safe
freeze_safe.install()
OUT=B/'preparation'
HEADERS=('production_rows.hpp','batched_rows.hpp','batched_experts.hpp')
def once(s,a,b):
 assert s.count(a)==1,a
 return s.replace(a,b,1)
def generate(mode):
 out=OUT/mode;out.mkdir(parents=True,exist_ok=True)
 source=LOCAL/'lineage-inputs/p151d-before' if mode=='old' else LOCAL
 for name in HEADERS:
  s=(source/name).read_text().replace('q.submit(', 'p151audit::bypass(')
  for dep in HEADERS:s=s.replace(str(LOCAL/dep),str(out/dep))
  (out/name).write_text(s)
 s=(P/'native/sibling.hpp').read_text()
 for name in HEADERS:s=s.replace(str(LOCAL/name),str(out/name))
 s=s.replace('bool paired_site(const flash::Launch&l){','bool paired_site(const flash::Launch&l){ p151audit::site=l.label;')
 (out/'sibling.hpp').write_text(s)
 s=(source/'v5/native-src/rank.hpp').read_text().replace(str(P/'native/sibling.hpp'),str(out/'sibling.hpp'))
 (out/'rank.hpp').write_text(s)
 s=(P/'native-src/main.cpp').read_text()
 s='#include "'+str(P/'native/preparation_backend.hpp')+'"\n'+s
 s=once(s,'getpriority(PRIO_PROCESS, 0) == a.native_nice','getpriority(PRIO_PROCESS, 0) == 19') # CPU probe stays nice19, argv remains byte-for-byte
 s=once(s,'Weights(const Options &a) : mini(a.mini) {','Weights(const Options &a) : mini(a.mini) { directory=flash::directory_from_loader(iq3::read_plan(a.plan));return;')
 s=once(s,'std::vector<int64_t> metadata() {','std::vector<int64_t> metadata() { return std::vector<int64_t>(35,17);')
 s=once(s,'weights[c][name] = id;','weights[c][name] = id; return; // descriptor-only load')
 s=once(s,'auto id=dev(c).arena.allocate(', 'p151audit::weight_allocation=cat==Category::weights; auto id=dev(c).arena.allocate(')
 s=once(s,'if(m==Memory::device){owned_bytes[c]+=bytes;', 'p151audit::weight_allocation=false; if(m==Memory::device){owned_bytes[c]+=bytes;')
 s=once(s,'void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {','void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) { if(dev(c).arena.row(dst).category==Category::weights)return;')
 s=once(s,'ownrt::make_sycl_device(a.card,profile_events||a.rank==0||a.mtp||!a.draft_capture.empty())','std::make_unique<p151audit::Backend>()')
 s=once(s,'save(a.output/"device-contact.json","{\\"device_contact\\":true}");','/* CPU backend: no device contact */')
 s=once(s,'void lookup(const flash::Launch &l) {','void lookup(const flash::Launch &l) { return; // no model payload')
 s=once(s,'void execute_site(const flash::Launch& l) {int c=l.card;','void execute_site(const flash::Launch& l) { p151audit::site=l.label; int c=l.card;')
 s=s.replace(str(P/'native-src/rank.hpp'),str(out/'rank.hpp'))
 (out/'audit-main.cpp').write_text(s)
 (out/'fixture.cpp').write_text((P/'native/preparation_fixture.cpp').read_text())
 return out

def main():
 prior=json.loads((P/'engine-commands.json').read_text());commands=[];results=[]
 launch=P/'evidence/device-sibling-smoke-B/run/ranks/rank0-launch.json'
 argv=json.loads(launch.read_text())['argv']
 for mode in ('old','fixed'):
  out=generate(mode)
  cmd=list(next(r['command'] for r in prior if r['name']=='device-entry-main'))
  cmd[cmd.index('-c')+1]=str(out/'fixture.cpp');cmd[cmd.index('-o')+1]=str(out/'fixture.o')
  link=list(next(r['command'] for r in prior if r['name']=='device-link'))
  link=[str(out/'fixture.o') if x.endswith('/entry-main.o') else x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')]
  link[link.index('-o')+1]=str(out/'fixture')
  with (out/'compile.log').open('w') as log:
   for c in (cmd,link):subprocess.run(c,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
  commands.extend((cmd,link))
  env=dict(os.environ,OMP_NUM_THREADS='2',P151_AUDIT_OUTPUT=str(out/'run'))
  r=subprocess.run([str(out/'fixture'),*argv[1:]],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True)
  (out/'run.log').write_text(r.stdout+r.stderr)
  print(mode,r.returncode,r.stdout+r.stderr,flush=True)
  if mode=='old':assert r.returncode!=0 and 'native operation bypassed preparation' in r.stderr
  else:assert r.returncode==0
  results.append(dict(mode=mode,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
 paths=[*[LOCAL/'lineage-inputs/p151d-before'/n for n in (*HEADERS,'v5/native-src/rank.hpp')],Path(argv[argv.index('--plan')+1]),Path(argv[argv.index('--selection')+1]),Path(__file__),P/'native/preparation_fixture.cpp',P/'native/preparation_backend.hpp',P/'native/sibling.hpp',P/'native-src/main.cpp',P/'native-src/rank.hpp',launch,*[LOCAL/n for n in HEADERS]]
 save(P/'evidence/preparation.json',dict(passed=True,device_executed=False,model_read=False,real_rank_argv=argv,device_defines=True,real_shapes=True,transport_only=True,arithmetic_proof='pair-cpu.json and sibling-state.json',commands=commands,runs=results,sources={str(p.relative_to(ROOT)):sha(p) for p in paths},max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
 from state_gate import compiler_turn
 with compiler_turn():main()
