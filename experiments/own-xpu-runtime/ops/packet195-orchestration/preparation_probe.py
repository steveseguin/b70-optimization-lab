"""Real packet194 exp-diet Engine load/prepare/first-position using CPU numerical buffers (packet195 chain argv).

Device Engine preprocessor branch stays active; only Host transport, payload
reads and process priority/output are replaced. No model or device access.
"""
import json,os,resource,subprocess,sys,shutil,importlib.util
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet';S=P/'diet-native';OUT=P/'build/preparation195'
sys.path.insert(0,str(P))
from reuse_build import sha,verify_native

def body(text,marker,value):
 start=text.index('{',text.index(marker));depth=1;i=start+1
 while depth:
  if text[i]=='{':depth+=1
  if text[i]=='}':depth-=1
  i+=1
 return text[:start+1]+value+text[i-1:]
def main():
 assert shutil.disk_usage('/').free>=27_000_000_000
 verify_native();OUT.mkdir(exist_ok=True)
 # The immutable source snapshot retains original include spellings. Compiler
 # input closure is hash-checked before and after this CPU-only probe build.
 source=(S/'native-src/main.cpp').read_text();helper=(P/'full_shape.py').read_text()
 host=helper.split("t=t[:start]+r"+chr(39)*3)[1].split(chr(39)*3)[0]
 host=host.replace('public:\n bool ordered_prefix_complete','public:\n ownrt::EventTiming timing(ownrt::Event e) override {return {e*1000+1,e*1000+501};}\n bool ordered_prefix_complete')
 start=source.index('class Host final');end=source.index('\n#endif',start);source=source[:start]+host+source[end:]
 source=body(source,'Weights(const Options &a)','directory=flash::directory_from_loader(iq3::read_plan(a.plan));')
 source=body(source,'std::vector<uint8_t> read(const std::string &name','require(n<=65536,"CPU probe forbids full weight reads");return std::vector<uint8_t>(n,0);')
 source=body(source,'std::vector<int64_t> metadata()','std::vector<int64_t> v{3,5,7};v.insert(v.end(),16,17);for(int i=0;i<16;++i)v.push_back(17*i);return v;')
 source=body(source,'void warm_lookups()','')
 source=source.replace('    weights[c][name] = id;','    weights[c][name] = id; return; // CPU payload elision')
 source=source.replace('class Engine final','#undef OWN_RT_HOST_ONLY\nclass Engine final',1)
 source=source.replace('#ifdef OWN_RT_HOST_ONLY\n  require(!a.authorized','#if 0\n  require(!a.authorized',1)
 source=source.replace('ownrt::make_sycl_device(a.card,profile_events||a.rank==0||a.mtp||!a.draft_capture.empty())','std::make_unique<Host>()')
 source=source.replace('getpriority(PRIO_PROCESS, 0) == a.native_nice','(getpriority(PRIO_PROCESS, 0)==19 && a.native_nice==0)')
 old=ROOT/'experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine';checked=old/'build/checked'/old.relative_to(ROOT)
 mtp=(S/'native-src/mtp.hpp').read_text().replace('mutable_ids.erase(w.id);','mutable_ids.erase(w.id);weights[name]=w;return; // CPU payload elision\n')
 mtp=body(mtp,'if(store){require(store->reads.size()','');mtp=body(mtp,'void dump_all_state(const fs::path& path)','')
 (OUT/'mtp.hpp').write_text(mtp)
 source=source.replace('#include "'+str(old/'v5/native-src/mtp.hpp')+'"','#define OWN_RT_HOST_ONLY\n#include "'+str(OUT/'mtp.hpp')+'"\n#undef OWN_RT_HOST_ONLY')
 source=source.replace('#include "'+str(old/'v5/native-src/rank.hpp')+'"','#define OWN_RT_HOST_ONLY\n#include "'+str(S/'native-src/rank.hpp')+'"\n#undef OWN_RT_HOST_ONLY')
 fusion=(S/'native-base'/old.relative_to(ROOT)/'p109_fusion.hpp').read_text().replace('struct SharedDown final:p49c::Base {\n unsigned capacity;','struct SharedDown final:p49c::Base {\n unsigned n;').replace('auto b=bind(p,capacity);','auto b=bind(p,n);').replace('k.capacity=capacity','k.n=capacity')
 (OUT/'p109_fusion.hpp').write_text(fusion);source=source.replace(str(checked/'p109_fusion.hpp'),str(OUT/'p109_fusion.hpp'))
 (OUT/'main.cpp').write_text(source)
 (OUT/'probe.cpp').write_text('''#include <cxxabi.h>
#define OWN_RT_HOST_ONLY
#define main unused_native_entry
#include "main.cpp"
#undef main
int main(int argc,char** argv){std::unique_ptr<Engine> e;try{
 auto a=parse(argc,argv);require(a.authorized&&a.rank>=0&&!a.mini&&a.context==4096,"real native rank argv");
 a.output=getenv("ENTRY_PREPARE_OUTPUT");fs::create_directories(a.output);
 packet26::dispatch.load(a.dispatch);Weights w(a);auto p=pipeline::split(plan(w,a),a.rank,false,a.draft_rank,a.target_split,pipeline::v3::rank0_extended(a));
 e=std::make_unique<Engine>(w,a,p);e->initialize();
 std::unique_ptr<p105::Runtime> head;if(e->split_head())head=std::make_unique<p105::Runtime>(*e);
 if(a.rank==0)pipeline::banks(*e);else{e->prepare_plan();e->prepare_commands();}
 {pipeline::SpeculativeImage image(*e);
 if(a.rank==1){mtp36::DraftRuntime d(*e);require(d.begin(1,1,true),"first draft decode");require(bool(d.poll_result()),"draft completion");e->drain();}
 else{e->prepare_token(1);for(const auto& l:e->p.launches)e->enqueue(l,e->logical);e->drain();}}
 save(a.output/"census.json",e->dev(0).arena.census());head.reset();e->shutdown();e.reset();
 std::cout<<"PASS CPU device-branch preparation first decode\\n";return 0;
 }catch(const std::exception& x){std::cerr<<x.what()<<std::endl;if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}}
''')
 prior=json.loads((old/'v5/engine-commands.json').read_text())
 args=list(next(r['command'] for r in prior if r['name']=='gnu-host-entry-main'));args=[x for x in args[:args.index('-c')] if x!='-DOWN_RT_HOST_ONLY']
 cmd=[*args,'-c',str(OUT/'probe.cpp'),'-o',str(OUT/'probe.o')]
 link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'));link=[str(OUT/'probe.o') if x.endswith('/entry-main.o') else x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')];link[link.index('-o')+1]=str(OUT/'probe')
 spec=importlib.util.spec_from_file_location('compile_turn195',O.parent/'compile_turn.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 with module.turn(),(O/'evidence/preparation-build.log').open('w') as log:
  for c in (cmd,link):subprocess.run(c,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
 verify_native()
 (O/'evidence/preparation-build.json').write_text(json.dumps(dict(passed=True,device_executed=False,commands=[cmd,link],binary_sha256=sha(OUT/'probe'),device_defines_active_in_engine=True,sources={str(f.relative_to(ROOT)):sha(f) for f in [Path(__file__),OUT/'main.cpp',OUT/'mtp.hpp',OUT/'p109_fusion.hpp',OUT/'probe.cpp']},peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),indent=2)+'\n')
 print('CPU preparation executable built; real-argv execution remains required')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
