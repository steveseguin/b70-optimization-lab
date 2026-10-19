"""Build CPU transport probes from each actual512-cap device entry source."""
import importlib.util,json,os,resource,shutil,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,STAGE,turn,limits,sha,save

def once(s,a,b):assert s.count(a)==1,a;return s.replace(a,b,1)
def main(name):
 p=P/name;B=p/'build/preparation163';B.mkdir(parents=True,exist_ok=True)
 inputs=json.loads((p/'lineage/build-inputs.json').read_text());cmd=inputs['compile'].copy();link=inputs['link'].copy()
 mirror=p/'native-source/repo'
 original=(STAGE/'packet58aj-onecard-resident/build/native/main.cpp'if name=='one-card'else STAGE/'packet131-snapshot-banks/build/checked/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/main.cpp')
 main_source=mirror/original.relative_to(ROOT);text=main_source.read_text()
 text=once(text,'getpriority(PRIO_PROCESS, 0) == a.native_nice','getpriority(PRIO_PROCESS, 0) == 19 /* CPU probe observed priority; real argv retained */')
 if name=='one-card':
  text=once(text,'static constexpr bool allocation_probe=false, legacy_pointer_probe=false;','bool allocation_probe=false, legacy_pointer_probe=false;')
  (B/'probe-main.cpp').write_text(text)
  fixture=(STAGE/'packet58aj-onecard-resident/native/preparation_probe.cpp').read_text()
  fixture=fixture.replace('a.wait_seconds==300','a.wait_seconds==600')
  mock=STAGE/'packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/mock_device.hpp'
  (B/'mock_device.hpp').write_text(mock.read_text().replace(str(ROOT)+'/',str(mirror)+'/'))
  # This header includes only backend.hpp; copy its sibling dependency.
  for f in mock.parent.glob('*.hpp'):
   if f.name=='backend.hpp':shutil.copy2(f,B/f.name)
  fixture=fixture.replace('../frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/mock_device.hpp','mock_device.hpp')
  # Exercise output-head preparation too; no actual tensor arithmetic claimed.
  fixture=fixture.replace('    if(site.prefill_skip)continue;','    /* Include first-decode sites in the CPU preparation probe. */')
  fixture=fixture.replace('PASS CPU device-branch resident preparation and first prefill','PASS CPU device-branch preparation; prefill and first-decode sites')
 else:
  backend=(STAGE/'packet151-sibling-cost/v5/native/preparation_backend.hpp').read_text()
  backend='#include '+json.dumps(str(next(mirror.rglob('ordered_queue.hpp'))))+'\n'+backend
  backend=backend.replace('class Backend final:public ownrt::Backend {','class Backend final:public ownrt::Backend, public ownrt::OrderedQueue {')
  backend=backend.replace('public:\n std::string identity()', 'public:\n bool ordered_prefix_complete(ownrt::Event) override {return true;}\n std::string identity()')
  for leaf in('prepared_submission.hpp','sycl_operation.hpp'):
   actual=next(mirror.rglob(leaf));backend=__import__('re').sub(r'#include "[^"]*/'+leaf+'"','#include '+json.dumps(str(actual)),backend)
  start=backend.index('  // Frozen M=1');end=backend.index('\n }\n ownrt::EventTiming',start)
  backend=backend[:start]+'  ++prepared;return []{++issued;return ownrt::next_handle();};'+backend[end:]
  (B/'preparation_backend.hpp').write_text(backend)
  text='#include '+json.dumps(str(B/'preparation_backend.hpp'))+'\n'+text
  text=once(text,'Weights(const Options &a) : mini(a.mini) {','Weights(const Options &a) : mini(a.mini) { directory=flash::directory_from_loader(iq3::read_plan(a.plan));return;')
  text=once(text,'std::vector<int64_t> metadata() {','std::vector<int64_t> metadata() { return std::vector<int64_t>(35,17);')
  text=once(text,'weights[c][name] = id;','weights[c][name] = id; return; // no model payload')
  text=once(text,'auto id=dev(c).arena.allocate(','p151audit::weight_allocation=cat==Category::weights; auto id=dev(c).arena.allocate(')
  text=once(text,'if(m==Memory::device){owned_bytes[c]+=bytes;','p151audit::weight_allocation=false; if(m==Memory::device){owned_bytes[c]+=bytes;')
  text=once(text,'void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) {','void upload(int c, Allocation dst, size_t offset, const void *src, size_t n) { if(dev(c).arena.row(dst).category==Category::weights)return;')
  text=once(text,'ownrt::make_sycl_device(a.card,profile_events||a.rank==0||a.mtp||!a.draft_capture.empty())','std::make_unique<p151audit::Backend>()')
  text=once(text,'save(a.output/"device-contact.json","{\\"device_contact\\":true}");','/* CPU backend; no device contact */')
  text=once(text,'void lookup(const flash::Launch &l) {','void lookup(const flash::Launch &l) { return; // no model payload')
  (B/'probe-main.cpp').write_text(text)
  fixture='''#define main unused_device_entry
#include "probe-main.cpp"
#undef main
int main(int argc,char**argv){try{
 auto a=parse(argc,argv);a.output=std::getenv("ENTRY_PREPARE_OUTPUT");fs::create_directories(a.output);
 require(!a.mini&&a.context==4096&&a.tokens==512,"real512 production geometry required");
 packet26::dispatch.load(a.dispatch);Weights w(a);auto p=pipeline::split(plan(w,a),a.rank,a.mini,a.draft_rank,a.target_split);
 Engine e(w,a,p);e.deadline=std::chrono::steady_clock::time_point::max();e.initialize();pipeline::banks(e);
 pipeline::SpeculativeImage image(e);pipeline::Candidate c;std::vector<uint8_t> shared(pipeline::shared_bytes);
 for(int pos: {0,1,511,512}){
  e.put(0,"position",&pos,4);c={};pipeline::Request r{pipeline::half,2,pos,pos<2?0:1,0,pos+1,{}};
  auto reply=pipeline::half_step(e,c,r,shared.data(),image,false);require(!reply.error,"sticky error");
  if(a.rank==1){e.reply_report.published();e.reply_report.flush();}
 }
 require(p151audit::prepared>0&&p151audit::issued>0,"preparation bypassed");e.shutdown();
 std::cout<<"PASS CPU device-branch preparation; prefill and first-decode sites; rank="<<a.rank<<" prepared="<<p151audit::prepared<<" issued="<<p151audit::issued<<std::endl;return0;
}catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return1;}}
'''.replace('return0','return 0').replace('return1','return 1')
 (B/'fixture.cpp').write_text(fixture)
 cmd[cmd.index('-c')+1]=str(B/'fixture.cpp');cmd[cmd.index('-o')+1]=str(B/'fixture.o');cmd[cmd.index('-MF')+1]=str(B/'fixture.d')
 link=[str(B/'fixture.o')if x.endswith('/entry-main.o')else x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o') and (name!='one-card'or not x.endswith('single_device.o'))]
 link[link.index('-o')+1]=str(B/'prepare-probe')
 for label,command in [('compile',cmd),('link',link)]:
  with turn(),(B/(label+'.log')).open('w')as log:
   subprocess.run(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
  print(name,'probe',label,'PASS',flush=True)
 save(p/'evidence/preparation-build.json',dict(passed=True,device_executed=False,device_defines=True,source_main_sha256=sha(main_source),binary_sha256=sha(B/'prepare-probe'),commands=[cmd,link],substitutions='CPU transport, synthetic/opaque weight storage, nice19 observation, scratch output; no arithmetic/speed claims',peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main(sys.argv[1])
