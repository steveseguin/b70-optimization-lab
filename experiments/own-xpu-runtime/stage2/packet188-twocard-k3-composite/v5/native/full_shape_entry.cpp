#include <cxxabi.h>
#define main packet98_unexecuted_model_entry
#include "main.cpp"
#undef main
static std::string capture_digest(const Engine& e) {
 std::vector<uint8_t> bytes;
 auto add=[&](const auto& sites){for(const auto& site:sites)for(const auto& cmd:site.commands){
  require(!cmd.operation_bytes.empty(),"empty target capture audit");
  for(auto id:cmd.ids)ownrt::arguments::append(bytes,id); // packet183: bundle 8 has no class layouts
  auto operation=cmd.operation_bytes;
  // The Q8 fallback copies Bound metadata, including addresses, into its audit.
  // Normalize only its four verified weight pointer slots. Every input/output
  // address, extent, family and count remains checked byte for byte.
  if(std::string(reinterpret_cast<const char*>(operation.data()))=="N13p30integrated5SmallE"){
   constexpr size_t bound_bytes=6*sizeof(uintptr_t);
   require(operation.size()>=4*bound_bytes+sizeof(unsigned),"small metadata extent");
   const size_t begin=operation.size()-4*bound_bytes-sizeof(unsigned);
   unsigned count=0;std::memcpy(&count,operation.data()+operation.size()-sizeof(unsigned),sizeof(count));
   require(count<=4&&cmd.ids.size()==count*3,"small metadata count");
   for(unsigned j=0;j<count;++j){
    for(unsigned k=0;k<3;++k){uintptr_t pointer=0;std::memcpy(&pointer,operation.data()+begin+j*bound_bytes+k*sizeof(uintptr_t),sizeof(pointer));
     require(pointer==uintptr_t(e.devices.at(0)->arena.row(cmd.ids[j*3+k]).pointer),"small metadata pointer/binding differs");}
   }
  }
  bytes.insert(bytes.end(),operation.begin(),operation.end());
 }};
 if(e.miss_banks()){
  require(e.active_bank==0&&e.spare_bank==1&&e.bank_parity==0&&e.bank_cache_ready,"noncanonical bank capture");
  for(int a=0;a<3;++a)for(int b=0;b<3;++b)if(a!=b){
   const auto& c=e.bank_cache.at(a*3+b);const bool current=a==e.active_bank&&b==e.spare_bank;
   require(c.ready&&(current?e.context_extent:c.extent)==32,"bank capture extent");
   ownrt::arguments::append(bytes,a);ownrt::arguments::append(bytes,b);
   ownrt::arguments::append(bytes,current?e.context_extent:c.extent);
   const auto& sites=current?e.issue_sites:c.sites;require(!sites.empty(),"empty bank pair");add(sites);
  }
  require(e.alternate_context_extent==32,"alternate bank extent");ownrt::arguments::append(bytes,e.alternate_context_extent);
 }else {add(e.issue_sites);add(e.alternate_issue_sites);}
 require(!bytes.empty(),"empty target captures");return hash(bytes);
}
static void census(Engine& e,const fs::path& dest){
 std::ofstream f(dest);f<<"[";bool first=true;
 for(size_t i=0;i<e.issue_sites.size();++i){const auto& l=e.p.launches[i];const auto& site=e.issue_sites[i];
  for(size_t j=0;j<site.commands.size();++j){const auto& cmd=site.commands[j];if(!first)f<<",";first=false;
   std::string name(reinterpret_cast<const char*>(cmd.operation_bytes.data()));int status=0;char* dem=abi::__cxa_demangle(name.c_str(),nullptr,nullptr,&status);if(dem){name=dem;std::free(dem);}
   f<<"{\"site\":"<<i<<",\"command\":"<<j<<",\"label\":"<<ownrt::quote(l.label)<<",\"op\":"<<ownrt::quote(l.op)<<",\"kernel\":"<<ownrt::quote(name)<<",\"shape\":[";
   for(size_t k=0;k<l.shape.size();++k)f<<(k?",":"")<<l.shape[k];f<<"],\"inputs\":[";
   for(size_t k=0;k<l.inputs.size();++k)f<<(k?",":"")<<ownrt::quote(l.inputs[k]);f<<"],\"outputs\":[";
   for(size_t k=0;k<l.outputs.size();++k)f<<(k?",":"")<<ownrt::quote(l.outputs[k]);f<<"],\"operation_sha\":"<<ownrt::quote(hash(cmd.operation_bytes))<<",\"operation_hex\":"<<ownrt::quote([](const auto& bytes){std::string out;for(auto b:bytes){out+="0123456789abcdef"[b>>4];out+="0123456789abcdef"[b&15];}return out;}(cmd.operation_bytes))<<",\"bindings\":[";
   for(size_t k=0;k<cmd.ids.size();++k){const auto&r=e.dev(0).arena.row(cmd.ids[k]);f<<(k?",":"")<<"{\"id\":"<<cmd.ids[k]<<",\"label\":"<<ownrt::quote(r.label)<<",\"bytes\":"<<r.bytes<<",\"category\":"<<int(r.category)<<"}";}
   f<<"]}";
  }
 }f<<"]\n";
}
static int startup109(int argc,char**argv){std::unique_ptr<Engine> e;std::unique_ptr<mtp36::DraftRuntime> draft;try{
 Options a=parse(argc,argv);fs::create_directories(a.output);
 if(a.pipeline_canary){require(a.mini&&a.pipeline_mini&&a.rank>=0,"canary startup flags");save(a.output/"result.json","{\"passed\":true,\"canary_pre_engine\":true}");return 0;}
 packet26::dispatch.load(a.dispatch.string());Weights w(a);auto p=pipeline::split(plan(w,a),a.rank,false,a.draft_rank,a.target_split,pipeline::v3::rank0_extended(a)); /* packet186 layout */
 require(p.g.h==2560&&p.g.context==4096&&p.g.vocab==248320,"real production dimensions");
 e=std::make_unique<Engine>(w,a,p);e->initialize();std::unique_ptr<p105::Runtime> head_runtime;if(e->split_head())head_runtime=std::make_unique<p105::Runtime>(*e);
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
 fs::create_directories(a.output);const auto parent=fs::path(P98_PARENT_PATH);
 a.plan=parent/"lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/suite-inputs-20261012/code-review/plan.tsv";a.draft_manifest=parent/"mtp-manifest.tsv";
 packet26::dispatch.load(std::string(P185_DISPATCH_PATH));Weights w(a); // packet185: sealed lineage dispatch (identical for both selections)
 e=std::make_unique<Engine>(w,a,pipeline::split(plan(w,a),a.rank,false,1,0,pipeline::v3::rank0_extended(a)));e->initialize(); /* packet186: sealed layout */std::unique_ptr<p105::Runtime> head_runtime;if(e->split_head())head_runtime=std::make_unique<p105::Runtime>(*e);
 if(a.rank==0)pipeline::banks(*e);else{e->prepare_plan();e->prepare_commands();}
 {pipeline::SpeculativeImage image(*e);if(a.rank==1)draft=std::make_unique<mtp36::DraftRuntime>(*e);
 if(a.rank==0)image.census131(a.output/"image-census.json",0); // packet186: speculative image sources at real shape
 {std::ofstream f(a.output/"v3-load.json");f<<"{\"rank0_extended\":"<<(e->v3_extended?"true":"false")<<",\"moved_sites\":"<<e->v3_sites.size()<<",\"stored_sites\":"<<e->v3_store_sites.size()<<",\"kio_bytes\":"<<e->kio_bytes<<",\"kio_stage_bytes\":"<<e->kio_stage_bytes<<",\"kio_cards\":"<<e->kio.size()<<",\"private_buffers\":[";
  bool first=true;for(const auto& n:e->v3_private){f<<(first?"":",")<<ownrt::quote(n);first=false;}f<<"],\"banked_state\":[";
  first=true;for(const auto& [n,id]:e->state_spares){f<<(first?"":",")<<ownrt::quote(n);first=false;}f<<"]}\n";}
 e->bracket_weights_locked=true;const auto initial=e->bracket_arena_hash();
 auto capture=[&]{return capture_digest(*e)+(draft?draft->bracket_test_digest():"");};
 const auto control_capture=capture();size_t total=0;std::vector<std::string> captures;
 require(!e->dense_metadata(),"packet186: dense_scales must stay expanded");
 const auto startup_head=e->head_choice();const bool startup_extended=e->v3_extended;
 std::string skips="[";
 census(*e,a.output/"launches-initial.json");
 for(int view=0;view<5;++view){
  const auto selection=std::string(argv[view%2?5:1]),digest=std::string(argv[view%2?6:2]);
  auto dest=a.output/("view"+std::to_string(view));fs::create_directories(dest);
  e->lookup_ids["poison"]={7,8};e->history0=e->history1=123;e->selected[0]={9};e->loaded_layer[0]=12;
  e->fp32_sources[0]=e->scratch[0];e->fp32_extents[0]=123;
  e->admit_position(100);if(a.rank==0){
   if(e->miss_banks())for(int i=0;i<view+1;++i){if(i%2==0)e->rotate_spare_bank();else e->swap_state_banks();}
   else e->swap_state_banks();e->admit_position(200);
  }
  p98_writes.clear();p80_operations.clear();
  auto reset=dest/"reset.txt",meta=dest/"switch.txt",receipt=dest/"boundary.json";
  save(reset,dest.string()+"\n\n");save(meta,selection+"\n"+digest+"\n"+reset.string()+"\n"+receipt.string()+"\n");
  pipeline::Candidate candidate;int accepted=17;
  pipeline::bracket_boundary(*e,candidate,draft.get(),image,meta,accepted);
  require(!accepted&&e->bracket_arena_hash()==initial,"view allocation identity");
  for(const auto&[id,owner]:e->allocations){const auto& row=e->dev(owner.first).arena.row(id);
   if(row.category==Category::weights){require(!p98_writes.count(id),"reset touched weight bytes");continue;}
   if(row.category==Category::pinned_slab)continue;
   if(e->immutable_snapshot_tables.count(id)){require(!p98_writes.count(id),"reset wrote a registered immutable table");continue;} // packet153 static table: preserved by design
   auto found=p98_writes.find(id);require(found!=p98_writes.end(),"reset left allocation untouched: "+row.label);auto intervals=found->second;std::sort(intervals.begin(),intervals.end());size_t end=0;
   for(auto [off,n]:intervals){require(off<=end,"reset omitted allocation bytes");end=std::max(end,off+n);}
   require(end==row.bytes,"reset incomplete allocation extent");++total;
  }
  const auto& choices=e->sealed_selection.choices;
  require(choices.at("experts")=="exp-halfcache+down-tile16","expert physical layout changed");
  // packet186: a V3-layout load switches only boundary/snapshot_host (U <-> V3); storage never moves.
  // packet188: a k3-storage load switches boundary rank0 <-> rank0-k3 and the two trims; storage never moves.
  require(choices.at("dense_scales")=="expanded"&&e->head_choice()==startup_head&&e->v3_extended==startup_extended,"packet186 view selection");
  const bool k3_view=startup_extended&&choices.at("boundary")=="rank0-k3";
  require(startup_extended?choices.at("boundary")==(e->v3_active?(k3_view?"rank0-k3":"rank0"):"none"):!choices.contains("boundary"),"V3 execution flag");
  require(e->kio_active==(choices.contains("kernel_io")&&choices.at("kernel_io")=="kernel")&&e->prepare_async==(choices.contains("rank0_prepare")&&choices.at("rank0_prepare")=="async"),"packet188 trim flags");
  require(e->v3_end==(k3_view?27:26)||!startup_extended,"packet188 boundary set");
  {size_t skipped=0;for(auto x:e->v3_skip_half)skipped+=x;
   auto moved_layer=[&](const auto& l){for(int k=24;k<(k3_view?27:26);++k)if(l.label.starts_with("blk."+std::to_string(k)+"."))return true;return false;};
   const size_t expected=a.rank==0?e->v3_store_sites.size():(e->v3_active?size_t(std::count_if(e->p.launches.begin(),e->p.launches.end(),moved_layer)):0);
   require(skipped==expected,"half skip census");skips+=(view?",":"")+std::to_string(skipped);}
  require(!e->dense_metadata(),"packet185 dense scale source");
  census(*e,a.output/("launches-view"+std::to_string(view)+".json"));
  if(draft){std::ofstream k(a.output/("draft-kernels-view"+std::to_string(view)+".txt"));for(const auto& n:draft->bracket_test_kernels())k<<n<<'\n';}
  captures.push_back(capture());
  require(captures.back()==control_capture,"packet185: re-selected capture differs from fresh startup");
  if(view>=2)require(captures.back()==captures[view-2],"same selection must recapture identically");
 }
 skips+="]";
 // Unsupported layouts and malformed selections must refuse before mutation.
 auto before=e->bracket_arena_hash();auto original=e->sealed_selection.observed_sha256;
 auto text=[&](){std::ifstream f(argv[1]);return std::string((std::istreambuf_iterator<char>(f)),{});}();
 unsigned refusals=0;
 for(const auto& [key,value]:std::vector<std::pair<std::string,std::string>>{
   {"packed_dense","head-packed"},{"experts","exp-halfcache"},{"head","head-transpose"},
   {"hc_gate","hc-weightcache"},{"hc_norm","consumer"},{"host_retire","reply-first"},
   {"head_format","q4-g32"},{"head_prefix","coverage985"},{"route","production"},
   {"qsa_attention","unknown"},{"dense_scales","unknown"},{"dense_scales","metadata"},
   {"snapshot_host",startup_extended?"unknown":"static"},
   // packet185: the target-head split is a storage/allocation choice; an in-load switch must refuse.
   {"head",startup_head=="production"?"head-split-compute":"production"}}){
  auto bad=text;auto marker=ownrt::quote(key)+": ";auto at=bad.find(marker);require(at!=std::string::npos,"negative fixture field");
  at+=marker.size();auto end=bad.find('"',at+1);require(end!=std::string::npos,"negative fixture value");
  bad.replace(at,end-at+1,ownrt::quote(value));
  auto path=a.output/"bad-layout.json";save(path,bad);bool refused=false;
  try{e->bracket_select(path,hash(std::vector<uint8_t>(bad.begin(),bad.end())));}catch(const std::exception&){refused=true;}
  require(refused&&e->bracket_arena_hash()==before&&e->sealed_selection.observed_sha256==original,"layout refusal must not mutate owner");++refusals;
 }
 // packet186: V3 storage (rank0_layers) never switches in-load; malformed V3 values refuse.
 if(startup_extended)for(const auto& [key,value]:std::vector<std::pair<std::string,std::string>>{{"rank0_layers","0-23"},{"boundary","unknown"},{"rank0_layers","0-27"},{"rank0_layers",e->v3_store_end==27?"0-25":"0-26"},
   {"boundary",e->v3_store_end==27?"none":"rank0-k3"}}){
  auto bad=text;auto marker=ownrt::quote(key)+": ";auto at=bad.find(marker);require(at!=std::string::npos,"negative V3 fixture field");
  at+=marker.size();auto end=bad.find('"',at+1);bad.replace(at,end-at+1,ownrt::quote(value));
  auto path=a.output/"bad-layout.json";save(path,bad);bool refused=false;
  try{e->bracket_select(path,hash(std::vector<uint8_t>(bad.begin(),bad.end())));}catch(const std::exception&){refused=true;}
  require(refused&&e->bracket_arena_hash()==before&&e->sealed_selection.observed_sha256==original,"V3 layout refusal must not mutate owner");++refusals;
 }
 bool bad_hash=false;try{e->bracket_select(argv[1],std::string(64,'0'));}catch(const std::exception&){bad_hash=true;}
 require(bad_hash&&e->sealed_selection.observed_sha256==original,"bad hash changed selection");++refusals;
 pipeline::Candidate pending;pending.pending=true;int accepted=0;bool pending_refused=false;
 try{pipeline::bracket_boundary(*e,pending,draft.get(),image,a.output/"not-read",accepted);}catch(const std::exception&){pending_refused=true;}
 require(pending_refused&&e->bracket_arena_hash()==before&&e->sealed_selection.observed_sha256==original,"pending work switch not refused");++refusals;
 save(a.output/"census.json",e->dev(0).arena.census());
 std::string capture_json="[";for(size_t i=0;i<captures.size();++i)capture_json+=(i?",":"")+ownrt::quote(captures[i]);capture_json+="]";
 save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"views\":5,\"target_loads\":1,\"draft_loads\":"+std::to_string(a.rank==1?1:0)+",\"reset_extents_verified\":"+std::to_string(total)+",\"fresh_start_capture_identity\":true,\"layout_refused\":true,\"native_refusals\":"+std::to_string(refusals)+",\"half_skips_per_view\":"+skips+",\"rank0_extended\":"+(startup_extended?"true":"false")+",\"initial_capture\":"+ownrt::quote(control_capture)+",\"view_captures\":"+capture_json+"}");
 draft.reset();}
 e->shutdown();e.reset();return 0;
 }catch(const std::exception&x){std::cerr<<x.what()<<'\n';draft.reset();if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}
}
