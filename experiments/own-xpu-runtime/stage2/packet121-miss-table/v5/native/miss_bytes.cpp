// Actual miniature target, snapshot, rollback and redo on the host backend.
#define main p121_unused_model_entry
#include "../native-src/main.cpp"
#undef main
static std::string canonical(Engine& e,const std::vector<uint8_t>& shared,std::string* detail=nullptr) {
 std::ostringstream out;
 for(const auto&[id,owner]:e.allocations){const auto&r=e.dev(owner.first).arena.row(id);
  if(!r.live||r.category==Category::weights||r.category==Category::pinned_slab)continue;
  // The private backup/table contain addresses and are not model state. Their
  // explicit retirement is checked by boundary; no canonical byte is omitted.
  if(r.label=="card0:speculative-private-image"||r.label=="card0:speculative-copy-table")continue;
  out<<id<<':'<<r.label<<':'<<hash(e.readback(owner.first,id,r.bytes))<<'\n';
 }
 out<<e.history0<<':'<<e.history1<<':'<<e.bank_parity<<':'<<e.context_extent<<':'<<e.alternate_context_extent<<'\n';
 for(auto&[name,value]:e.lookup_ids)out<<name<<':'<<hash(value)<<'\n';
 for(auto v:e.fp32_sources)out<<v<<':';for(auto v:e.fp32_extents)out<<v<<':';
 for(auto&v:e.selected)for(auto x:v)out<<x<<':';for(auto x:e.loaded_layer)out<<x<<':';
 for(auto&[name,slot]:e.buffers[0])out<<name<<':'<<slot.id<<'\n';
 for(auto&[name,id]:e.state_spares)out<<name<<':'<<id<<'\n';
 out<<hash(shared);auto s=out.str();if(detail)*detail=s;return hash(std::vector<uint8_t>(s.begin(),s.end()));
}
static unsigned transport_cases(){
 unsigned checks=0;
 for(size_t shift:{0,1,7,15,16,31})for(size_t n:{1,3,15,16,17,4095,4096,4097,8209}){
  std::vector<uint8_t> source(n+64),original,backup(n+64,0xa5);
  for(size_t i=0;i<source.size();++i)source[i]=uint8_t(i*31+n);original=source;
  pipeline::SnapshotFlat::Item row{backup.data()+shift,source.data()+shift,n,(n+4095)/4096};
  pipeline::SnapshotFlat capture;capture.count=1;capture.tiles=row.end_tile;std::array<void*,1> pointers{&row};capture.run(pointers);
  std::fill(source.begin()+shift,source.begin()+shift+n,0x39);
  pipeline::SnapshotReverse restore;restore.count=1;restore.tiles=row.end_tile;restore.run(pointers);
  require(source==original,"reverse kernel odd extent/tail bytes");++checks;
 }
 return checks;
}
int main(int argc,char**argv){std::unique_ptr<Engine> e;try{
 require(argc==5||(argc==6&&std::string(argv[5])=="sequence-only"),"selection hash output mode [sequence-only]");Options a;
 a.mini=true;a.pipeline_mini=true;a.context=320;a.cards=1;a.card=0;a.rank=0;a.draft_rank=1;
 a.memory="resident";a.gemv="r5";a.nongemv="parallel";a.selection=argv[1];a.selection_sha256=argv[2];a.output=argv[3];
 fs::create_directories(a.output);Weights w(a);
 e=std::make_unique<Engine>(w,a,pipeline::split(plan(w,a),0,true,1,0));e->initialize();pipeline::banks(*e);
 unsigned cases=0,position_classes=0,negative=0;std::ostringstream evidence;
 {pipeline::SpeculativeImage image(*e);std::vector<uint8_t> shared(pipeline::shared_bytes,0);pipeline::Candidate c;int accepted=0;
 auto reset=[&](int position){image.boundary();c={};
  auto meta=a.output/"reset.txt";save(meta,a.output.string()+"\n\n");pipeline::request_reset(*e,c,nullptr,meta,accepted);
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
 auto half=[&](int token,int position,bool spec){pipeline::Request r{pipeline::half,token,position,0,int(spec),1,{0,0}};return pipeline::half_step(*e,c,r,shared.data(),image);};
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
    evidence<<p<<':'<<cut<<":fallback"<<abandon<<':'<<after<<'\n';++cases;
   }
  }
  reset(p);half(5,p,true);accept();require(canonical(*e,shared)==expected,"accepted hit differs from direct target");++cases;
  std::cerr<<"position "<<p<<" PASS\n";
 }
 // Two bank parities, live committed histories/KV, and repeated table rebuilds
 // across 31->32 and 63->64. Compare each step to a direct-target sequence.
 std::vector<std::string> direct,details;reset(0);
 for(int p=0;p<98;++p){half(5,p,false);accept();std::string detail;direct.push_back(canonical(*e,shared,&detail));details.push_back(detail);}
 reset(0);
 for(int p=0;p<98;++p){
  if(p%3==0){half(5,p,true);accept();}
  else {
   half(7,p,true);pipeline::undo(*e,c,image,true,p,5);
   if(p%3==2)require(!image.before_command(false,-1,-1),"consecutive fallback");
   else require(image.before_command(true,p,5),"consecutive redo");
   half(5,p,false);if(p%3==1)image.finish_redo();accept();
  }
  std::string detail;const auto actual=canonical(*e,shared,&detail);
  if(actual!=direct[p]){save(a.output/"expected-state.txt",details[p]);save(a.output/"actual-state.txt",detail);throw std::runtime_error("consecutive target state differs at position "+std::to_string(p));}
  evidence<<"sequence:"<<p<<':'<<actual<<'\n';++cases;
 }
 if(e->reuse_restore_table()){
  reset(32);half(7,32,true);image.p121_corrupt_descriptor_for_gate();bool refused=false;
  try{pipeline::undo(*e,c,image);}catch(const std::exception& x){refused=std::string(x.what()).find("physical identity")!=std::string::npos;}
  require(refused,"stale descriptor negative control not detected");++negative;
  // This intentionally poisoned image cannot be resolved; discard the owner
  // without continuing inference. Engine shutdown still drains normally.
 }
 const auto counters=image.p121_gate_counts();
 if(e->reuse_restore_table())require(counters[2]>0&&counters[1]==counters[2],"every reverse restore must be one guarded submission");
 else require(counters[2]==0,"production unexpectedly used reverse table");
 auto raw=evidence.str();save(a.output/"cases.txt",raw);
 save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"cases\":"+std::to_string(cases)+",\"position_classes\":"+std::to_string(position_classes)+",\"transport_tail_cases\":"+std::to_string(transport_cases())+",\"negative_controls\":"+std::to_string(negative)+",\"capture_submissions\":"+std::to_string(counters[0])+",\"restore_submissions\":"+std::to_string(counters[1])+",\"reused_tables\":"+std::to_string(counters[2])+",\"canonical_sha256\":"+ownrt::quote(hash(std::vector<uint8_t>(raw.begin(),raw.end())))+"}");
 }
 e->shutdown();e.reset();return 0;
 }catch(const std::exception&x){std::cerr<<x.what()<<'\n';if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}}
