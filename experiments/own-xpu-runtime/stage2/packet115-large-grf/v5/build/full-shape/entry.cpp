#include <cxxabi.h>
#define main packet98_unexecuted_model_entry
#include "main.cpp"
#undef main
static std::string capture_digest(const Engine& e) {
 std::vector<uint8_t> bytes;
 auto add=[&](const auto& sites){for(const auto& site:sites)for(const auto& cmd:site.commands){
  require(!cmd.operation_bytes.empty(),"empty target capture audit");
  for(auto id:cmd.ids)ownrt::arguments::append(bytes,id);
  bytes.insert(bytes.end(),cmd.operation_bytes.begin(),cmd.operation_bytes.end());
 }};
 add(e.issue_sites);add(e.alternate_issue_sites);require(!bytes.empty(),"empty target captures");return hash(bytes);
}
static void census(Engine& e,const fs::path& dest){
 std::ofstream f(dest);f<<"[";bool first=true;
 for(size_t i=0;i<e.issue_sites.size();++i){const auto& l=e.p.launches[i];const auto& site=e.issue_sites[i];
  for(size_t j=0;j<site.commands.size();++j){const auto& cmd=site.commands[j];if(!first)f<<",";first=false;
   std::string name(reinterpret_cast<const char*>(cmd.operation_bytes.data()));int status=0;char* dem=abi::__cxa_demangle(name.c_str(),nullptr,nullptr,&status);if(dem){name=dem;std::free(dem);}
   f<<"{\"site\":"<<i<<",\"command\":"<<j<<",\"label\":"<<ownrt::quote(l.label)<<",\"op\":"<<ownrt::quote(l.op)<<",\"kernel\":"<<ownrt::quote(name)<<",\"shape\":[";
   for(size_t k=0;k<l.shape.size();++k)f<<(k?",":"")<<l.shape[k];f<<"],\"inputs\":[";
   for(size_t k=0;k<l.inputs.size();++k)f<<(k?",":"")<<ownrt::quote(l.inputs[k]);f<<"],\"outputs\":[";
   for(size_t k=0;k<l.outputs.size();++k)f<<(k?",":"")<<ownrt::quote(l.outputs[k]);f<<"],\"bindings\":[";
   for(size_t k=0;k<cmd.ids.size();++k){const auto&r=e.dev(0).arena.row(cmd.ids[k]);f<<(k?",":"")<<"{\"id\":"<<cmd.ids[k]<<",\"label\":"<<ownrt::quote(r.label)<<",\"bytes\":"<<r.bytes<<",\"category\":"<<int(r.category)<<"}";}
   f<<"]}";
  }
 }f<<"]\n";
}
static int startup109(int argc,char**argv){std::unique_ptr<Engine> e;std::unique_ptr<mtp36::DraftRuntime> draft;try{
 Options a=parse(argc,argv);fs::create_directories(a.output);
 if(a.pipeline_canary){require(a.mini&&a.pipeline_mini&&a.rank>=0,"canary startup flags");save(a.output/"result.json","{\"passed\":true,\"canary_pre_engine\":true}");return 0;}
 packet26::dispatch.load(a.dispatch.string());Weights w(a);auto p=pipeline::split(plan(w,a),a.rank,false,a.draft_rank,a.target_split);
 require(p.g.h==2560&&p.g.context==4096&&p.g.vocab==248320,"real production dimensions");
 e=std::make_unique<Engine>(w,a,p);e->initialize();
 if(!a.draft_capture.empty()){e->prepare_plan();draft=std::make_unique<mtp36::DraftRuntime>(*e);}
 else {if(a.rank==0)pipeline::banks(*e);else{e->prepare_plan();e->prepare_commands();}
  {pipeline::SpeculativeImage image(*e);if(a.mtp)draft=std::make_unique<mtp36::DraftRuntime>(*e);}}
 save(a.output/"census.json",e->dev(0).arena.census());
 save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"context\":4096,\"hidden\":2560,\"vocab\":248320,\"prepared\":"+std::string(e->prepared_path?"true":"false")+"}");
 draft.reset();e->shutdown();e.reset();return 0;
 }catch(const std::exception&x){std::cerr<<x.what()<<'\n';draft.reset();if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}}
int main(int argc,char**argv){if(argc>1&&std::string(argv[1])=="--startup109")return startup109(argc-1,argv+1);std::unique_ptr<Engine> e;std::unique_ptr<mtp36::DraftRuntime> draft;
 try {
 require(argc==7,"control hash rank output candidate hash");
 Options a;a.context=4096;a.cards=1;a.card=0;a.rank=std::stoi(argv[3]);a.draft_rank=1;a.target_split=0;
 a.mtp=true;a.argument_audit=true;a.memory="resident";a.gemv="r5";a.nongemv="parallel";a.selection=argv[1];a.selection_sha256=argv[2];a.output=argv[4];
 fs::create_directories(a.output);const auto parent=fs::path("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet103-record-bundle");
 a.plan=parent/"../suite-inputs-20261012/code-review/plan.tsv";a.draft_manifest=parent/"mtp-manifest.tsv";
 packet26::dispatch.load((parent/"dispatch-speed6.json").string());Weights w(a);
 e=std::make_unique<Engine>(w,a,pipeline::split(plan(w,a),a.rank,false,1,0));e->initialize();
 if(a.rank==0)pipeline::banks(*e);else{e->prepare_plan();e->prepare_commands();}
 {pipeline::SpeculativeImage image(*e);if(a.rank==1)draft=std::make_unique<mtp36::DraftRuntime>(*e);
 e->bracket_weights_locked=true;const auto initial=e->bracket_arena_hash();
 auto capture=[&]{return capture_digest(*e)+(draft?draft->bracket_test_digest():"");};
 const auto control_capture=capture();size_t total=0;std::vector<std::string> captures;
 census(*e,a.output/"launches-initial.json");
 for(int view=0;view<5;++view){
  const auto selection=std::string(argv[view%2?5:1]),digest=std::string(argv[view%2?6:2]);
  auto dest=a.output/("view"+std::to_string(view));fs::create_directories(dest);
  e->lookup_ids["poison"]={7,8};e->history0=e->history1=123;e->selected[0]={9};e->loaded_layer[0]=12;
  e->fp32_sources[0]=e->scratch[0];e->fp32_extents[0]=123;
  e->admit_position(100);if(a.rank==0){e->swap_state_banks();e->admit_position(200);}
  p98_writes.clear();p80_operations.clear();
  auto reset=dest/"reset.txt",meta=dest/"switch.txt",receipt=dest/"boundary.json";
  save(reset,dest.string()+"\n\n");save(meta,selection+"\n"+digest+"\n"+reset.string()+"\n"+receipt.string()+"\n");
  pipeline::Candidate candidate;int accepted=17;
  pipeline::bracket_boundary(*e,candidate,draft.get(),image,meta,accepted);
  require(!accepted&&e->bracket_arena_hash()==initial,"view allocation identity");
  for(const auto&[id,owner]:e->allocations){const auto& row=e->dev(owner.first).arena.row(id);
   if(row.category==Category::weights){require(!p98_writes.count(id),"reset touched weight bytes");continue;}
   if(row.category==Category::pinned_slab)continue;
   auto intervals=p98_writes.at(id);std::sort(intervals.begin(),intervals.end());size_t end=0;
   for(auto [off,n]:intervals){require(off<=end,"reset omitted allocation bytes");end=std::max(end,off+n);}
   require(end==row.bytes,"reset incomplete allocation extent");++total;
  }
  const auto& choices=e->sealed_selection.choices;
  require(choices.at("experts")=="exp-halfcache+down-tile16","expert physical layout changed");
  // The exact capture bytes must change for a candidate and restore for control.
  if(view%2 && std::string(argv[1])!=std::string(argv[5]))
    require(capture()!=control_capture,"candidate expert selector did not change captures");
  census(*e,a.output/("launches-view"+std::to_string(view)+".json"));
  captures.push_back(capture());
  if(view%2==0)require(captures.back()==control_capture,"restored control capture differs from fresh startup");
 }
 // Unsupported layouts and malformed selections must refuse before mutation.
 auto before=e->bracket_arena_hash();auto original=e->sealed_selection.observed_sha256;
 auto text=[&](){std::ifstream f(argv[1]);return std::string((std::istreambuf_iterator<char>(f)),{});}();
 unsigned refusals=0;
 for(const auto& [key,value]:std::vector<std::pair<std::string,std::string>>{
   {"packed_dense","head-packed"},{"experts","exp-halfcache"},{"head","head-transpose"},
   {"hc_gate","hc-weightcache"},{"hc_norm","consumer"},{"host_retire","reply-first"},
   {"head_format","q4-g32"},{"head_prefix","coverage985"},{"route","production"},
   {"qsa_attention","unknown"},{"expert_kernels","unknown"}}){
  auto bad=text;auto marker=ownrt::quote(key)+": ";auto at=bad.find(marker);require(at!=std::string::npos,"negative fixture field");
  at+=marker.size();auto end=bad.find('"',at+1);require(end!=std::string::npos,"negative fixture value");
  bad.replace(at,end-at+1,ownrt::quote(value));
  auto path=a.output/"bad-layout.json";save(path,bad);bool refused=false;
  try{e->bracket_select(path,hash(std::vector<uint8_t>(bad.begin(),bad.end())));}catch(const std::exception&){refused=true;}
  require(refused&&e->bracket_arena_hash()==before&&e->sealed_selection.observed_sha256==original,"layout refusal must not mutate owner");++refusals;
 }
 bool bad_hash=false;try{e->bracket_select(argv[1],std::string(64,'0'));}catch(const std::exception&){bad_hash=true;}
 require(bad_hash&&e->sealed_selection.observed_sha256==original,"bad hash changed selection");++refusals;
 pipeline::Candidate pending;pending.pending=true;int accepted=0;bool pending_refused=false;
 try{pipeline::bracket_boundary(*e,pending,draft.get(),image,a.output/"not-read",accepted);}catch(const std::exception&){pending_refused=true;}
 require(pending_refused&&e->bracket_arena_hash()==before&&e->sealed_selection.observed_sha256==original,"pending work switch not refused");++refusals;
 save(a.output/"census.json",e->dev(0).arena.census());
 std::string capture_json="[";for(size_t i=0;i<captures.size();++i)capture_json+=(i?",":"")+ownrt::quote(captures[i]);capture_json+="]";
 save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"views\":5,\"target_loads\":1,\"draft_loads\":"+std::to_string(a.rank==1?1:0)+",\"reset_extents_verified\":"+std::to_string(total)+",\"fresh_start_capture_identity\":true,\"layout_refused\":true,\"native_refusals\":"+std::to_string(refusals)+",\"initial_capture\":"+ownrt::quote(control_capture)+",\"view_captures\":"+capture_json+"}");
 draft.reset();}
 e->shutdown();e.reset();return 0;
 }catch(const std::exception&x){std::cerr<<x.what()<<'\n';draft.reset();if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}
}
