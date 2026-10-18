// Real miniature CPU backend: poison every mutable byte and verify full reset.
#define main packet98_unexecuted_model_entry
#include "../native-src/main.cpp"
#undef main
static std::map<Allocation,std::string> bytes(Engine& e,bool weights) {
 std::map<Allocation,std::string> result;
 for(const auto&[id,owner]:e.allocations){const auto& row=e.dev(owner.first).arena.row(id);
  if((row.category==Category::weights)!=weights)continue;
  if(row.memory!=Memory::device){auto p=static_cast<uint8_t*>(row.pointer);result[id]=hash(std::vector<uint8_t>(p,p+row.bytes));}
  else result[id]=hash(e.readback(owner.first,id,row.bytes));
 }return result;
}
int main(int argc,char**argv){std::unique_ptr<Engine> e;std::unique_ptr<mtp36::DraftRuntime> draft;
 try {
 require(argc==7,"control hash rank output candidate hash");Options a;
 a.mini=true;a.pipeline_mini=true;a.context=64;a.cards=1;a.card=0;a.rank=std::stoi(argv[3]);a.draft_rank=1;
 a.mtp=true;a.memory="resident";a.gemv="r5";a.nongemv="parallel";a.selection=argv[1];a.selection_sha256=argv[2];a.output=argv[4];
 fs::create_directories(a.output);Weights w(a);
 e=std::make_unique<Engine>(w,a,pipeline::split(plan(w,a),a.rank,true,1,0));e->initialize();
 if(a.rank==0)pipeline::banks(*e);else{e->prepare_plan();e->prepare_commands();}
 size_t verified=0,rollback_checks=0;
 {pipeline::SpeculativeImage image(*e);if(a.rank==1)draft=std::make_unique<mtp36::DraftRuntime>(*e);
 e->bracket_weights_locked=true;auto weight_bytes=bytes(*e,true);
 std::map<Allocation,std::string> clean;
 for(int view=0;view<5;++view){
  auto dest=a.output/("view"+std::to_string(view));fs::create_directories(dest);
  if(view){
   std::vector<uint8_t> poison(4*1024*1024,uint8_t(0x51+view));
   for(const auto&[id,owner]:e->allocations){const auto& row=e->dev(owner.first).arena.row(id);
    if(row.category==Category::weights)continue;
    if(row.memory!=Memory::device){std::memset(row.pointer,0x51+view,row.bytes);continue;}
    for(size_t off=0;off<row.bytes;off+=poison.size())e->upload(owner.first,id,off,poison.data(),std::min(poison.size(),row.bytes-off));
   }
   uint32_t zero=0;e->put(0,"error",&zero,4);
   require(bytes(*e,false)!=clean,"negative control failed to dirty state");
   e->lookup_ids["poison"]={4,5,6};e->history0=e->history1=51;e->selected[0]={3};e->loaded_layer[0]=1;
   e->token_ids.fill(51);for(auto& d:e->token_lookups)std::fill(d.values.begin(),d.values.end(),51);
   if(a.rank==0)e->swap_state_banks();
  }
  auto reset=dest/"reset.txt",meta=dest/"switch.txt",receipt=dest/"boundary.json";
  save(reset,dest.string()+"\n\n");save(meta,std::string(argv[view%2?5:1])+"\n"+argv[view%2?6:2]+"\n"+reset.string()+"\n"+receipt.string()+"\n");
  pipeline::Candidate candidate;int accepted=17;
  pipeline::bracket_boundary(*e,candidate,draft.get(),image,meta,accepted);
  const auto actual=bytes(*e,false);if(!view)clean=actual;
  require(actual==clean,"reset did not restore every mutable allocation byte");
  require(bytes(*e,true)==weight_bytes,"reset changed immutable weight bytes");
  require(e->history0==e->p.g.eos&&e->history1==e->p.g.eos,"EOS host reset");
  require(std::all_of(e->token_ids.begin(),e->token_ids.end(),[](auto x){return x==0;}),"token ID scratch reset");
  for(const auto& d:e->token_lookups)require(std::all_of(d.values.begin(),d.values.end(),[](auto x){return x==0;}),"lookup scratch reset");
  verified+=actual.size();
  if(a.rank==0){
   e->prepare_token(1);e->drain();auto h0=e->history0,h1=e->history1;
   auto hist=e->readback(0,e->buffers[0].at("token_history").id,16);
   std::array<uint8_t,65536> shared{};image.begin(shared.data());
   e->prepare_token(2);e->drain();
   std::vector<std::vector<uint8_t>> expected;
   for(const auto& d:e->token_lookups)expected.push_back(e->readback(d.card,d.output,d.values.size()*2));
   int64_t poison_history[2]={51,52};e->put(0,"token_history",poison_history,16);shared.fill(77);
   image.restore();e->drain();
   require(e->history0==h0&&e->history1==h1,"snapshot host history restore");
   require(e->readback(0,e->buffers[0].at("token_history").id,16)==hist,"snapshot device history restore");
   require(std::all_of(shared.begin(),shared.end(),[](auto x){return x==0;}),"snapshot shared restore");
   e->prepare_token(2);e->drain();size_t i=0;
   for(const auto& d:e->token_lookups)require(e->readback(d.card,d.output,d.values.size()*2)==expected.at(i++),"post-rollback lookup differs");
   ++rollback_checks;
  }
 }
 // Locked weight uploads fail before changing bytes.
 auto id=e->weights[0].begin()->second;uint8_t value=7;bool refused=false;
 try{e->upload(0,id,0,&value,1);}catch(const std::exception&){refused=true;}
 require(refused&&bytes(*e,true)==weight_bytes,"immutable weight guard failed");
 draft.reset();}
 save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"views\":5,\"all_mutable_byte_hashes_equal\":true,\"weights_byte_identical\":true,\"poison_negative_control\":true,\"weight_write_refused\":true,\"rollback_checks\":"+std::to_string(rollback_checks)+",\"allocation_checks\":"+std::to_string(verified)+"}");
 e->shutdown();e.reset();return 0;
 }catch(const std::exception&x){std::cerr<<x.what()<<'\n';draft.reset();if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}
}
