// Packet186: state correctness of the moved layers (mini GDN layer 2 = full-model layers 24-25)
// on the actual rank-0 miniature engine, host backend (packet153 state_bytes.cpp pattern).
// Packet188: the k3 storage (rank0_layers=0-26) uses the five-layer miniature (G Q G G Q): mini GDN layers
// 2-3 = full-model layers 24-26. The same sequences run for boundary=rank0 (layer 3 idle on rank 0) and
// boundary=rank0-k3 (layers 2-3 in the boundary), each with kernel_io copy|kernel x rank0_prepare sync|async;
// the gate requires byte-identical canonical transcripts across the four trim combinations.
//
// One rank-0 Engine in the V3 dual layout (rank0_layers=0-25, boundary=rank0; argv selects the
// snapshot host mode). Every step compares the canonical bytes of ALL rank-0 allocations
// (including the moved layer's recurrent state and the exported shared slot) against a direct,
// never-speculative sequence:
//   * hits (speculative half accepted, then boundary);
//   * misses at every cancellation cut (rollback with redo, corrected half, accept, boundary);
//   * abandoned redos (fallback restore), no-guess steps;
// Guards that must refuse (each leaves the owner unchanged): boundary with a pending candidate,
// boundary for a different token or position, boundary without an accept, boundary for a decode
// position whose token differs from rank 1's verification, a rank-0 half before the pending
// boundary, a second boundary for the same position.
// Negative control (proves the comparison would see a leak): issuing the moved layer while a
// speculation is outstanding and then rolling back leaves different bytes, because the moved
// layers are deliberately outside the speculative image.
#define main p186_unused_model_entry
#include "../native-src/main.cpp"
#undef main
static std::string canonical(Engine& e,const std::vector<uint8_t>& shared,std::string* detail=nullptr) {
 std::ostringstream out;std::set<Allocation> represented;
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
 out<<hash(std::vector<uint8_t>(shared.begin(),shared.begin()+pipeline::slot_bytes));auto s=out.str();if(detail)*detail=s;return hash(std::vector<uint8_t>(s.begin(),s.end()));
}
static std::string moved_state(Engine& e){
 std::ostringstream out;for(const auto& name:e.v3_private){auto& slot=e.buffers[0].at(name);out<<name<<':'<<hash(e.readback(0,slot.id,slot.n*flash::scalar_bytes(slot.type)))<<'\n';}
 auto s=out.str();return hash(std::vector<uint8_t>(s.begin(),s.end()));
}
int main(int argc,char**argv){std::unique_ptr<Engine> e;try{
 require(argc==4,"selection hash output");Options a;
 a.mini=true;a.pipeline_mini=true;a.context=320;a.cards=1;a.card=0;a.rank=0;a.draft_rank=1;
 a.memory="resident";a.gemv="r5";a.nongemv="parallel";a.selection=argv[1];a.selection_sha256=argv[2];a.output=argv[3];
 fs::create_directories(a.output);Weights w(a);
 e=std::make_unique<Engine>(w,a,pipeline::split(plan(w,a),0,true,1,0,pipeline::v3::rank0_extended(a)));e->initialize();pipeline::banks(*e);
 require(e->v3_extended&&e->v3_active&&!e->v3_sites.empty()&&!e->v3_private.empty(),"V3 dual layout with boundary=rank0 required");
 for(const auto& name:e->v3_private)require(!e->state_spares.count(name),"moved-layer state must not be banked");
 unsigned cases=0,refusals=0,negatives=0;std::ostringstream evidence;
 {pipeline::SpeculativeImage image(*e);std::vector<uint8_t> shared(pipeline::shared_bytes,0);pipeline::Candidate c;pipeline::V3Boundary v;int accepted=0;
 auto verify_none=[&]{pipeline::verification(shared.data()).position_plus_one=UINT32_MAX;pipeline::verification(shared.data()).token=-1;};
 auto reset=[&](int position){image.boundary();c={};v.reset();
  auto meta=a.output/"reset.txt";save(meta,a.output.string()+"\n\n");pipeline::request_reset(*e,c,nullptr,meta,accepted);
  e->admit_position(0);e->swap_state_banks();e->admit_position(0);e->swap_state_banks();
  std::fill(shared.begin(),shared.end(),0);verify_none();e->put(0,"position",&position,4);e->a.cancel_launch=-1;};
 auto half=[&](int token,int position,bool spec,int fixture=0){pipeline::Request r{pipeline::half,token,position,fixture,int(spec),1,{0,0}};pipeline::v3_before_half(*e,v,r);return pipeline::half_step(*e,c,r,shared.data(),image);};
 auto accept=[&]{pipeline::publish(*e,c);if(c.speculative)image.accept();pipeline::v3_accepted(*e,v,c);c={};};
 auto boundary=[&](int token,int position,int fixture=0){pipeline::Request r{pipeline::v3::boundary_op,token,position,fixture,0,1,{0,0}};return pipeline::v3_boundary_step(*e,v,r,shared.data(),c);};
 auto refuse=[&](const char* what,auto fn){const auto before=canonical(*e,shared);const bool was_ready=v.ready;bool refused=false;
  try{fn();}catch(const std::exception&){refused=true;}
  require(refused,std::string("guard did not refuse: ")+what);require(canonical(*e,shared)==before&&v.ready==was_ready,std::string("refusal mutated the owner: ")+what);
  evidence<<"refused:"<<what<<'\n';++refusals;};
 // 1. Direct, never-speculative reference sequence (half -> accept -> boundary).
 std::vector<std::string> direct,moved,details;reset(0);
 for(int p=0;p<64;++p){half(5,p,false);accept();boundary(5,p);std::string d;direct.push_back(canonical(*e,shared,&d));details.push_back(d);moved.push_back(moved_state(*e));}
 require(std::set<std::string>(moved.begin(),moved.end()).size()>8,"moved-layer state must evolve with position");
 // 2. Mixed hits / misses (every live cancellation cut) / abandoned redos / no-guess, compared per step.
 std::vector<int> cuts;size_t command_count=0;
 for(size_t i=0;i<e->p.launches.size();++i){if(e->v3_skip_half[i])continue;command_count+=e->issue_sites[i].commands.size();const auto& op=e->p.launches[i].op;
  if(op=="conv"||op=="gdn"||op=="qsa_append_pool")cuts.push_back(int(command_count));}
 require(!cuts.empty(),"cancellation coverage");cuts.push_back(int(command_count-1));cuts.push_back(-1);
 reset(0);
 for(int p=0;p<64;++p){
  const int kind=p%5;
  if(kind==0){half(5,p,true);accept();boundary(5,p);}                       // hit
  else if(kind==4){half(5,p,false);accept();boundary(5,p);}                 // no guess
  else {e->a.cancel_launch=cuts[(p/5)%cuts.size()];half(7,p,true);          // miss at a cut
   if(kind==3){ // the moved layer cannot be advanced with the guessed candidate pending
    refuse("boundary-with-pending-guess",[&]{boundary(7,p);});
    refuse("half-before-resolving",[&]{half(5,p,false);});}
   pipeline::undo(*e,c,image,kind!=2,p,5);e->a.cancel_launch=-1;
   if(kind==2)require(!image.before_command(false,-1,-1),"abandoned redo fallback");
   else require(image.before_command(true,p,5),"matching redo");
   half(5,p,false);if(kind!=2)image.finish_redo();accept();
   if(kind==1){refuse("boundary-wrong-token",[&]{boundary(7,p);});refuse("boundary-wrong-position",[&]{boundary(5,p+1);});
    refuse("half-before-boundary",[&]{half(5,p+1,true);});}
   boundary(5,p);}
  if(p==9)refuse("second-boundary",[&]{boundary(5,p);});
  std::string d;const auto actual=canonical(*e,shared,&d);
  if(actual!=direct[p]){save(a.output/"expected-state.txt",details[p]);save(a.output/"actual-state.txt",d);throw std::runtime_error("V3 state differs from the direct sequence at position "+std::to_string(p));}
  require(moved_state(*e)==moved[p],"moved-layer state differs at position "+std::to_string(p));
  evidence<<"sequence:"<<p<<':'<<kind<<':'<<actual<<'\n';++cases;
 }
 refuse("boundary-without-accept",[&]{boundary(5,64);});
 // 3. Decode positions: the boundary token must equal rank 1's published verification.
 reset(0);for(int p=0;p<4;++p){half(5,p,false);accept();boundary(5,p);}
 {half(5,4,false,2);accept();
  pipeline::verification(shared.data()).position_plus_one=4;pipeline::verification(shared.data()).token=6;
  refuse("boundary-token-differs-from-rank1-verification",[&]{boundary(5,4,2);});
  pipeline::verification(shared.data()).token=5;boundary(5,4,2);verify_none();
  require(canonical(*e,shared)==direct[4],"verified decode boundary differs");++cases;}
 // 4. Negative control: advancing the moved layer on a GUESSED token while speculating, then
 //    rolling back, must leave a detectable difference (the moved layer is outside the image).
 for(int which=0;which<2;++which){
  reset(0);for(int p=0;p<8;++p){half(5,p,false);accept();boundary(5,p);}
  const auto before=canonical(*e,shared),moved_before=moved_state(*e);
  half(7,8,true);
  for(size_t index:e->v3_sites)e->enqueue(e->p.launches[index],e->logical);e->drain(); // illegal: guessed token
  pipeline::undo(*e,c,image,which==1,8,5);if(which==1){require(image.before_command(true,8,5),"negative redo");half(5,8,false);image.finish_redo();c={};}
  else require(canonical(*e,shared)!=before,"a moved-layer advance on a guessed token was hidden by rollback");
  require(moved_state(*e)!=moved_before,"negative control did not reach the moved layer");
  evidence<<"negative:"<<which<<":detected\n";++negatives;
 }
 reset(0);
 auto raw=evidence.str();save(a.output/"cases.txt",raw);
 save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"cases\":"+std::to_string(cases)+",\"refusals\":"+std::to_string(refusals)+",\"negatives\":"+std::to_string(negatives)+
   ",\"moved_sites\":"+std::to_string(e->v3_sites.size())+",\"stored_sites\":"+std::to_string(e->v3_store_sites.size())+",\"moved_private_buffers\":"+std::to_string(e->v3_private.size())+",\"snapshot_host\":"+ownrt::quote(e->sealed_selection.choices.at("snapshot_host"))+
   ",\"kernel_io\":"+ownrt::quote(e->kio_active?"kernel":"copy")+",\"rank0_prepare\":"+ownrt::quote(e->prepare_async?"async":"sync")+",\"kio_sync_transfers\":"+std::to_string(e->kio_sync_transfers)+",\"kio_async_copies\":"+std::to_string(e->kio_async_copies)+",\"staged_halves\":"+std::to_string(e->staged_halves)+
   ",\"boundary\":"+ownrt::quote(e->sealed_selection.choices.at("boundary"))+",\"rank0_layers\":"+ownrt::quote(e->sealed_selection.choices.at("rank0_layers"))+
   ",\"canonical_sha256\":"+ownrt::quote(hash(std::vector<uint8_t>(raw.begin(),raw.end())))+"}");
 }
 e->shutdown();e.reset();return 0;
 }catch(const std::exception&x){std::cerr<<x.what()<<'\n';if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}}
