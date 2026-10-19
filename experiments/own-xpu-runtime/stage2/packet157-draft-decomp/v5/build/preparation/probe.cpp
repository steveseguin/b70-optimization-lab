#include <cxxabi.h>
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
   std::ofstream result(a.output/"probe.json");result<<"{\"passed\":true,\"device_executed\":false,\"synthetic_event_clock\":true,\"rank\":1,\"groups\":8,\"guess\":"<<done->token<<"}\n";
   p157::flush(engine->timings,rank);engine->timings.flush();
  }else {
   engine->prepare_token(1);for(const auto& l:engine->p.launches)engine->enqueue(l,engine->logical);engine->drain();save(a.output/"census.json",engine->dev(0).arena.census());
   save(a.output/"probe.json","{\"passed\":true,\"device_executed\":false,\"rank\":0,\"first_position\":true}\n");
  }
  head_runtime.reset();engine->shutdown();engine.reset();return 0;
 }catch(const std::exception& ex){std::cerr<<ex.what()<<std::endl;if(engine){try{engine->shutdown();}catch(...){}engine.reset();}return 1;}
}
