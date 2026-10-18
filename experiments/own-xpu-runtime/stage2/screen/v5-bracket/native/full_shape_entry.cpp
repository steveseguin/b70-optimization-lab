#include <cxxabi.h>
#define main packet98_unexecuted_model_entry
#include "main.cpp"
#undef main
static std::string capture_digest(const Engine& e) {
 std::vector<uint8_t> bytes;
 auto add=[&](const auto& sites){for(const auto& site:sites)for(const auto& cmd:site.commands){
  bytes.insert(bytes.end(),cmd.argument_bytes.begin(),cmd.argument_bytes.end());
  bytes.insert(bytes.end(),cmd.operation_bytes.begin(),cmd.operation_bytes.end());
 }};
 add(e.issue_sites);add(e.alternate_issue_sites);return hash(bytes);
}
int main(int argc,char**argv){std::unique_ptr<Engine> e;std::unique_ptr<mtp36::DraftRuntime> draft;
 try {
 require(argc==7,"control hash rank output candidate hash");
 Options a;a.context=4096;a.cards=1;a.card=0;a.rank=std::stoi(argv[3]);a.draft_rank=1;a.target_split=0;
 a.mtp=true;a.memory="resident";a.gemv="r5";a.nongemv="parallel";a.selection=argv[1];a.selection_sha256=argv[2];a.output=argv[4];
 fs::create_directories(a.output);const auto parent=fs::path(P98_PARENT_PATH);
 a.plan=parent/"../suite-inputs-20261012/code-review/plan.tsv";a.draft_manifest=parent/"mtp-manifest.tsv";
 packet26::dispatch.load((parent/"dispatch-speed6.json").string());Weights w(a);
 e=std::make_unique<Engine>(w,a,pipeline::split(plan(w,a),a.rank,false,1,0));e->initialize();
 if(a.rank==0)pipeline::banks(*e);else{e->prepare_plan();e->prepare_commands();}
 {pipeline::SpeculativeImage image(*e);if(a.rank==1)draft=std::make_unique<mtp36::DraftRuntime>(*e);
 e->bracket_weights_locked=true;const auto initial=e->bracket_arena_hash();
 const auto control_capture=capture_digest(*e);size_t total=0;
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
  bool plus=false,route=false;
  for(const auto&[name,count]:p80_operations){plus|=name.find("p82brec::Kernel<true>")!=std::string::npos;route|=name.find("p78route::Kernel")!=std::string::npos;}
  require(plus==bool(view%2)&&route==bool(view%2),"view selected kernel consumers");
  if(view%2==0)require(capture_digest(*e)==control_capture,"restored control capture differs from fresh startup");
 }
 // Unsupported layouts and malformed selections must refuse before mutation.
 auto before=e->bracket_arena_hash();auto original=e->sealed_selection.observed_sha256;
 auto text=[&](){std::ifstream f(argv[1]);return std::string((std::istreambuf_iterator<char>(f)),{});}();
 auto bad=text;auto at=bad.find("\"packed_dense\": \"production\"");require(at!=std::string::npos,"negative fixture field");
 bad.replace(at,std::string("\"packed_dense\": \"production\"").size(),"\"packed_dense\": \"head-packed\"");
 auto path=a.output/"bad-layout.json";save(path,bad);bool refused=false;
 try{e->bracket_select(path,hash(std::vector<uint8_t>(bad.begin(),bad.end())));}catch(const std::exception&){refused=true;}
 require(refused&&e->bracket_arena_hash()==before&&e->sealed_selection.observed_sha256==original,"layout refusal must not mutate owner");
 save(a.output/"census.json",e->dev(0).arena.census());
 save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"views\":5,\"target_loads\":1,\"draft_loads\":"+std::to_string(a.rank==1?1:0)+",\"reset_extents_verified\":"+std::to_string(total)+",\"fresh_start_capture_identity\":true,\"layout_refused\":true}");
 draft.reset();}
 e->shutdown();e.reset();return 0;
 }catch(const std::exception&x){std::cerr<<x.what()<<'\n';draft.reset();if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}
}
