"""CPU path probe: device preprocessing after Host declaration, exact native argv.
Geometry, dispatch and rank argv are real; device buffers are numerical tokens.
The ordinary host build alone would compile away the timing collector.
"""
import json,os,resource,subprocess
from pathlib import Path
from p157_v5_build_engine import P,LOCAL,ROOT,B,CHECKED,sha,save,limits,run

def main():
 limits();out=B/'preparation';out.mkdir(exist_ok=True)
 source=(P/'native-src/main.cpp').read_text()
 # Numerical allocation tokens and no-op payload operations keep real shape,
 # dispatch, preparation and bounds checks below the 4 GiB CPU cap.
 helper=(LOCAL/'full_shape.py').read_text()
 host=helper.split("t=t[:start]+r"+chr(39)*3)[1].split(chr(39)*3)[0]
 host=host.replace('public:\n bool ordered_prefix_complete','public:\n ownrt::EventTiming timing(ownrt::Event e) override {return {e*1000+1,e*1000+501};}\n bool ordered_prefix_complete')
 begin=source.index('class Host final');end=source.index('\n#endif',begin)
 source=source[:begin]+host+source[end:]
 def body(text,marker,value):
  start=text.index('{',text.index(marker));depth=1;i=start+1
  while depth:
   if text[i]=='{':depth+=1
   if text[i]=='}':depth-=1
   i+=1
  return text[:start+1]+value+text[i-1:]
 source=body(source,'Weights(const Options &a)','directory=flash::directory_from_loader(iq3::read_plan(a.plan));')
 source=body(source,'std::vector<uint8_t> read(const std::string &name','require(n<=65536,"CPU probe forbids full weight reads");return std::vector<uint8_t>(n,0);')
 source=body(source,'std::vector<int64_t> metadata()','std::vector<int64_t> v{3,5,7};v.insert(v.end(),16,17);for(int i=0;i<16;++i)v.push_back(17*i);return v;')
 source=body(source,'void warm_lookups()','')
 source=source.replace('    weights[c][name] = id;','    weights[c][name] = id; return; // CPU payload elision')
 source=source.replace('class Engine final', '#undef OWN_RT_HOST_ONLY\nclass Engine final',1)
 source=source.replace('#ifdef OWN_RT_HOST_ONLY\n  require(!a.authorized', '#if 0\n  require(!a.authorized',1)
 source=source.replace('ownrt::make_sycl_device(a.card,profile_events||a.rank==0||a.mtp||!a.draft_capture.empty())','std::make_unique<Host>()')
 source=source.replace('getpriority(PRIO_PROCESS, 0) == a.native_nice','(getpriority(PRIO_PROCESS, 0)==19 && a.native_nice==0)')
 # Preserve the selected draft preparation. Only weight upload is replaced.
 mtp=(P/'native-src/mtp.hpp').read_text()
 mtp=mtp.replace('mutable_ids.erase(w.id);','mutable_ids.erase(w.id);weights[name]=w;return; // CPU payload elision\n')
 mtp=body(mtp,'if(store){require(store->reads.size()', '')
 mtp=body(mtp,'void dump_all_state(const fs::path& path)', '')
 (out/'mtp.hpp').write_text(mtp)
 source=source.replace('#include "'+str(P/'native-src/mtp.hpp')+'"','#define OWN_RT_HOST_ONLY\n#include "'+str(out/'mtp.hpp')+'"\n#undef OWN_RT_HOST_ONLY')
 source=source.replace('#include "'+str(P/'native-src/rank.hpp')+'"','#define OWN_RT_HOST_ONLY\n#include "'+str(P/'native-src/rank.hpp')+'"\n#undef OWN_RT_HOST_ONLY')
 # CPU capture serializer names are a test ABI only; preserve the field value.
 fusion=(CHECKED/'p109_fusion.hpp').read_text().replace('struct SharedDown final:p49c::Base {\n unsigned capacity;', 'struct SharedDown final:p49c::Base {\n unsigned n;').replace('auto b=bind(p,capacity);','auto b=bind(p,n);').replace('k.capacity=capacity','k.n=capacity')
 (out/'p109_fusion.hpp').write_text(fusion)
 source=source.replace(str(CHECKED/'p109_fusion.hpp'),str(out/'p109_fusion.hpp'))
 main=out/'main.cpp';main.write_text(source)
 entry=out/'probe.cpp';entry.write_text('''#include <cxxabi.h>
#define OWN_RT_HOST_ONLY
#define main unused_native_entry
#include "main.cpp"
#undef main
int main(int argc,char** argv){
 std::unique_ptr<Engine> engine;
 try {
  auto a=parse(argc,argv);require(a.authorized&&a.rank>=0&&(a.rank==0||a.mtp),"real native rank argv required");
  const int rank=a.rank;require(!a.mini&&a.context==4096,"real device preparation geometry");
  a.output=getenv("P157_PREP_OUTPUT");fs::create_directories(a.output);
  packet26::dispatch.load(a.dispatch);
  Weights weights(a);auto plan0=pipeline::split(plan(weights,a),rank,false,a.draft_rank,a.target_split);
  engine=std::make_unique<Engine>(weights,a,plan0);engine->initialize();
  std::unique_ptr<p105::Runtime> head_runtime;if(engine->split_head())head_runtime=std::make_unique<p105::Runtime>(*engine);
  if(rank==0)pipeline::banks(*engine);else {engine->prepare_plan();engine->prepare_commands();}
  const auto begin=std::chrono::steady_clock::now();
  if(rank==1){
   mtp36::DraftRuntime draft(*engine);p157::Identity identity(100,9);
   bool started=false;p157::measure("draft_issue",1,false,[&]{started=draft.begin(1,1,true);});
   require(started,"first decode draft not submitted");
   auto done=draft.poll_result();require(bool(done),"CPU ordered draft not complete");engine->drain();
   require(!p157::device_samples.empty(),"device-defined timing branch was not exercised");
   std::set<int> groups;for(const auto& x:p157::device_samples)groups.insert(x.group);
   require(groups.size()==8,"missing draft groups in preparation probe");
   draft.dump_all_state(a.output/"draft-state");save(a.output/"census.json",engine->dev(0).arena.census());
   std::ofstream result(a.output/"probe.json");result<<"{\\"passed\\":true,\\"device_executed\\":false,\\"synthetic_event_clock\\":true,\\"rank\\":1,\\"groups\\":8,\\"guess\\":"<<done->token<<"}\\n";
   p157::flush(engine->timings,rank);engine->timings.flush();
  }else {
   engine->prepare_token(1);for(const auto& l:engine->p.launches)engine->enqueue(l,engine->logical);engine->drain();save(a.output/"census.json",engine->dev(0).arena.census());
   save(a.output/"probe.json","{\\"passed\\":true,\\"device_executed\\":false,\\"rank\\":0,\\"first_position\\":true}\\n");
  }
  head_runtime.reset();engine->shutdown();engine.reset();return 0;
 }catch(const std::exception& ex){std::cerr<<ex.what()<<std::endl;if(engine){try{engine->shutdown();}catch(...){}engine.reset();}return 1;}
}
''')
 prior=json.loads((P/'engine-commands.json').read_text());args=list(next(r['command'] for r in prior if r['name']=='gnu-host-entry-main'));args=[x for x in args[:args.index('-c')] if x!='-DOWN_RT_HOST_ONLY']
 signature=sha(entry)+sha(main)+sha(out/'mtp.hpp')+sha(out/'p109_fusion.hpp');stamp=out/'compile-signature.txt'
 if not (out/'probe.o').exists() or not stamp.exists() or stamp.read_text()!=signature:
  run([*args,'-c',entry,'-o',out/'probe.o'],'preparation-compile');stamp.write_text(signature)
 link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'));link=[str(out/'probe.o') if x.endswith('/entry-main.o') else x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')];link[link.index('-o')+1]=str(out/'probe');run(link,'preparation-link')
 receipt=P/'evidence/entry-gate.json'
 if receipt.exists():argv_rows=json.loads(receipt.read_text())['rows'][0]['argv'];origin='packet157 real entry interception'
 else:
  src=LOCAL.with_name('packet154-rank1-split')/'v5/evidence/entry-gate.json'
  argv_rows=json.loads(src.read_text().replace('packet154-rank1-split','packet157-draft-decomp'))['rows'][0]['argv'];origin='vendored unchanged transport argv; rerun against packet157 entry required before readiness'
 rows=[]
 for rank,argv in enumerate(argv_rows):
  native=next(i for i,x in enumerate(argv) if x.endswith('/own-rt-iq3'));args=[str(out/'probe'),*argv[native+1:]]
  # Entry probe's adapter selection path is scratch. Bind the same sealed bytes.
  args[args.index('--selection')+1]=str(P/'lineage/split/selection.json');args[args.index('--selection-sha256')+1]=sha(P/'lineage/split/selection.json')
  args[args.index('--dispatch')+1]=str(P/'lineage/split/dispatch-speed6.json')
  args[args.index('--plan')+1]=str(LOCAL/'lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/suite-inputs-20261012/code-review/plan.tsv')
  if '--draft-manifest' in args:args[args.index('--draft-manifest')+1]=str(LOCAL/'mtp-manifest.tsv')
  for repeat in (1,2):
   limits()
   dest=out/(f'rank{rank}-{repeat}');env=dict(os.environ,OMP_NUM_THREADS='2',P157_PREP_OUTPUT=str(dest))
   cp=subprocess.run(args,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True)
   log=P/'evidence'/f'preparation-rank{rank}-{repeat}.log';log.write_text(cp.stdout+cp.stderr);assert cp.returncode==0,log.read_text()[-5000:]
   census=json.loads((dest/'census.json').read_text());live=[x for x in census['allocations'] if x['live'] and x['memory']=='device'];device_bytes=sum(x['bytes'] for x in live)
   assert device_bytes<json.loads((P/'lineage/split/memory-plan.json').read_text())['arena_limit_bytes']
   rows.append(dict(rank=rank,repeat=repeat,numerical_device_bytes=device_bytes,allocation_count=len(live),result=json.loads((dest/'probe.json').read_text()),argv=args,log_sha256=sha(log)))
 assert rows[2]['result']==rows[3]['result']
 save(P/'evidence/preparation.json',dict(passed=True,device_executed=False,model_payload_read=False,full_shape_payload_read=False,metadata_plan_read=True,argv_origin=origin,rows=rows,
  device_defines_active_in_engine=True,backend='CPU numerical allocation/operation mock and synthetic event clock',substitutions=['CPU Host backend','payload elision, numerical allocations, unchanged full geometry','priority observation nice19','scratch output/selection paths'],
  sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'preparation_probe.py',P/'native-src/main.cpp',P/'native-src/mtp.hpp',P/'native/split_timing.hpp']},peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 print('CPU device-branch load/prepare/first-position PASS')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
