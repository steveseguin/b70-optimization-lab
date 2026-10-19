// Actual miniature target, snapshot, rollback and redo on the host backend.
#define main p121_unused_model_entry
#include "../native-src/main.cpp"
#undef main
static std::string canonical(Engine& e,const std::vector<uint8_t>& shared,std::string* detail=nullptr) {
 std::ostringstream out;
 std::set<Allocation> represented;
 for(const auto& [name,slot]:e.buffers[0]){represented.insert(slot.id);out<<"buffer:"<<name<<':'<<hash(e.readback(0,slot.id,slot.n*flash::scalar_bytes(slot.type)))<<'\n';}
 for(const auto& [name,id]:e.state_spares){represented.insert(id);out<<"spare:"<<name<<':'<<hash(e.readback(0,id,e.dev(0).arena.row(id).bytes))<<'\n';}
 for(const auto& [name,id]:e.state_reserves)represented.insert(id);
 for(const auto&[id,owner]:e.allocations){const auto&r=e.dev(owner.first).arena.row(id);
  if(!r.live||r.category==Category::weights||r.category==Category::pinned_slab||represented.count(id))continue;
  if(e.immutable_snapshot_tables.contains(id))continue;
  if(r.label=="card0:speculative-private-image"||r.label=="card0:speculative-copy-table")continue;
  out<<r.label<<':'<<hash(e.readback(owner.first,id,r.bytes))<<'\n';
 }
 out<<e.history0<<':'<<e.history1<<':'<<e.bank_parity<<':'<<e.context_extent<<':'<<e.alternate_context_extent<<'\n';
 for(auto&[name,value]:e.lookup_ids)out<<name<<':'<<hash(value)<<'\n';
 for(auto v:e.fp32_sources)out<<(v?e.dev(0).arena.row(v).label:"null")<<':';for(auto v:e.fp32_extents)out<<v<<':';
 for(auto&v:e.selected)for(auto x:v)out<<x<<':';for(auto x:e.loaded_layer)out<<x<<':';
 out<<hash(shared);auto s=out.str();if(detail)*detail=s;return hash(std::vector<uint8_t>(s.begin(),s.end()));
}
int main(int argc,char**argv){std::unique_ptr<Engine> e;try{
 require(argc==5||(argc==6&&std::string(argv[5])=="sequence-only"),"selection hash output mode [sequence-only]");Options a;
 a.mini=true;a.pipeline_mini=true;a.context=320;a.cards=1;a.card=0;a.rank=0;a.draft_rank=1;
 a.memory="resident";a.gemv="r5";a.nongemv="parallel";a.selection=argv[1];a.selection_sha256=argv[2];a.output=argv[3];
 fs::create_directories(a.output);Weights w(a);
 e=std::make_unique<Engine>(w,a,pipeline::split(plan(w,a),0,true,1,0));e->initialize();pipeline::banks(*e);
 unsigned cases=0,position_classes=0,negative=0;std::ostringstream evidence;
 {pipeline::SpeculativeImage image(*e);std::vector<uint8_t> shared(pipeline::shared_bytes,0);pipeline::Candidate c;int accepted=0;
 std::map<Allocation,std::string> table_hash;
 for(auto id:e->immutable_snapshot_tables)table_hash[id]=hash(e->readback(0,id,e->dev(0).arena.row(id).bytes));
 require(table_hash.size()==1,"one immutable rotation-independent table");
 std::set<std::pair<unsigned,unsigned>> roles;
 auto reset=[&](int position){image.boundary();c={};
  auto meta=a.output/"reset.txt";save(meta,a.output.string()+"\n\n");pipeline::request_reset(*e,c,nullptr,meta,accepted);
  for(auto [id,digest]:table_hash)require(hash(e->readback(0,id,e->dev(0).arena.row(id).bytes))==digest,"reset rewrote immutable descriptors");
  // Request reset preserves compiled launch extents. Give reference and
  // candidate exactly the same initial prepared banks, retaining both extents
  // in the canonical comparison rather than hiding this non-byte state.
  e->admit_position(0);e->swap_state_banks();e->admit_position(0);e->swap_state_banks();
  std::fill(shared.begin(),shared.end(),0);
  // Position zero is a fixture-only edge: a zeroed publication means "none"
  // in production, which never speculates before the initial target token.
  pipeline::verification(shared.data()).position_plus_one=UINT32_MAX;
  e->put(0,"position",&position,4);e->a.cancel_launch=-1;
 };
 auto half=[&](int token,int position,bool spec){roles.insert({e->active_bank,e->spare_bank});pipeline::Request r{pipeline::half,token,position,0,int(spec),1,{0,0}};return pipeline::half_step(*e,c,r,shared.data(),image);};
 auto accept=[&]{pipeline::publish(*e,c);if(c.speculative)image.accept();c={};};
 std::vector<int> positions;for(int i=0;i<32;++i)positions.push_back(i);
 for(int p:{32,33,63,64,95,96,127,128,255,256,319})positions.push_back(p);
 for(int p:positions){if(argc==6)break;++position_classes;
  reset(p);half(5,p,false);accept();const auto expected=canonical(*e,shared);
  std::vector<int> cuts{-1};if(p==3||p==4||p==31||p==32||p==63||p==64||p==127||p==128||p==319)cuts={-1,0,1,17};
  for(int cut:cuts){
   reset(p);e->a.cancel_launch=cut;auto stopped=half(7,p,true);
   require(c.cancelled==(cut>=0)&&(cut<0||stopped.reserved[1]==cut),"forced miss cancellation cut not reached");
   pipeline::undo(*e,c,image,true,p,5);e->a.cancel_launch=-1;
   require(image.before_command(true,p,5),"matching redo not recognized");half(5,p,false);
   require(!c.cancelled&&c.swapped,"redo incomplete");image.finish_redo();accept();
   const auto actual=canonical(*e,shared);require(actual==expected,"redo differs from direct corrected target in canonical bytes");evidence<<p<<':'<<cut<<":redo:"<<actual<<'\n';++cases;
   for(int abandon=0;abandon<4;++abandon){
    reset(p);const auto before=canonical(*e,shared);e->a.cancel_launch=cut;auto stopped=half(7,p,true);
    require(c.cancelled==(cut>=0)&&(cut<0||stopped.reserved[1]==cut),"forced fallback cancellation cut not reached");
    pipeline::undo(*e,c,image,abandon!=0,p,5);
    if(abandon==1)require(!image.before_command(false,-1,-1),"dump/end fallback");
    if(abandon==2)require(!image.before_command(true,p,6),"wrong token fallback");
    if(abandon==3)require(!image.before_command(true,p+1,5),"wrong position fallback");
    const auto after=canonical(*e,shared);require(after==before,"terminal/abandoned redo changed canonical bytes");
    image.boundary();require(canonical(*e,shared)==before,"terminal boundary changed committed bytes");
    for(const auto&[name,id]:e->state_reserves){auto raw=e->readback(0,id,e->dev(0).arena.row(id).bytes);require(std::all_of(raw.begin(),raw.end(),[](auto x){return x==0;}),"cancelled reserve not retired");}
    evidence<<p<<':'<<cut<<":fallback"<<abandon<<':'<<after<<'\n';++cases;
   }
  }
  reset(p);half(5,p,true);accept();require(canonical(*e,shared)==expected,"accepted hit differs from direct target");++cases;
  std::cerr<<"position "<<p<<" PASS\n";
 }
 // Two bank parities, live committed histories/KV, and repeated table rebuilds
 // across 31->32 and 63->64. Compare each step to a direct-target sequence.
 std::vector<std::string> direct,details;reset(0);
 std::vector<int> live_cuts;size_t command_count=0;
 for(size_t i=0;i<e->p.launches.size();++i){
  command_count+=e->issue_sites[i].commands.size();const auto& op=e->p.launches[i].op;
  if(op=="conv"||op=="gdn"||op=="qsa_append_pool")live_cuts.push_back(int(command_count));
 }
 require(!live_cuts.empty()&&command_count>0,"live cancellation coverage missing");live_cuts.push_back(int(command_count-1));
 for(int p=0;p<98;++p){half(5,p,false);accept();std::string detail;direct.push_back(canonical(*e,shared,&detail));details.push_back(detail);}
 reset(0);
 for(int p=0;p<98;++p){
  if(p%3==0){half(5,p,true);accept();}
  else {
   e->a.cancel_launch=live_cuts[(p/3)%live_cuts.size()];auto stopped=half(7,p,true);
   require(c.cancelled&&stopped.reserved[1]==e->a.cancel_launch,"live cancellation cut not reached");
   pipeline::undo(*e,c,image,true,p,5);e->a.cancel_launch=-1;
   if(p%3==2)require(!image.before_command(false,-1,-1),"consecutive fallback");
   else require(image.before_command(true,p,5),"consecutive redo");
   half(5,p,false);if(p%3==1)image.finish_redo();accept();
  }
  std::string detail;const auto actual=canonical(*e,shared,&detail);
  if(actual!=direct[p]){save(a.output/"expected-state.txt",details[p]);save(a.output/"actual-state.txt",detail);throw std::runtime_error("consecutive target state differs at position "+std::to_string(p));}
  evidence<<"sequence:"<<p<<':'<<actual<<'\n';++cases;
 }
 for(int which=0;which<3;++which){
  reset(32);const auto before=canonical(*e,shared);half(7,32,true);
  image.corrupt_protected_for_gate(which);pipeline::undo(*e,c,image);
  require(canonical(*e,shared)!=before,"corrupted protected/omitted bytes hidden");
  evidence<<"negative:"<<which<<":detected\n";++negative;
 }
 reset(0);
 // The private reserve can hold stale uncommitted bytes, but every byte
 // must be retired before a reset/dump boundary, without changing logical state.
 auto before_boundary=canonical(*e,shared);image.boundary();
 require(canonical(*e,shared)==before_boundary,"boundary changed committed state");
 for(const auto&[name,id]:e->state_reserves){auto raw=e->readback(0,id,e->dev(0).arena.row(id).bytes);require(std::all_of(raw.begin(),raw.end(),[](auto x){return x==0;}),"private reserve retirement");}
 require(roles.size()==6,"all six rotation states must be exercised");
 for(auto [id,digest]:table_hash)require(hash(e->readback(0,id,e->dev(0).arena.row(id).bytes))==digest,"cycles rewrote immutable descriptors");
 auto raw=evidence.str();save(a.output/"cases.txt",raw);
 save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"cases\":"+std::to_string(cases)+",\"position_classes\":"+std::to_string(position_classes)+",\"canonical_sha256\":"+ownrt::quote(hash(std::vector<uint8_t>(raw.begin(),raw.end())))+"}");
 }
 e->shutdown();e.reset();return 0;
 }catch(const std::exception&x){std::cerr<<x.what()<<'\n';if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}}
