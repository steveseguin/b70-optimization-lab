#include "native_sequence_helpers.hpp"
int main(int argc,char**argv) {
 std::unique_ptr<Engine> engine;
 try {
  auto a=parse(argc,argv);require(!a.mini&&a.resident_lookups,"real resident argv");
  a.output=std::getenv("ENTRY_PREPARE_OUTPUT");const auto root=a.output;fs::create_directories(root);
  Options fixture;fixture.mini=true;Weights weights(fixture);
  weights.directory=flash::directory_from_loader(iq3::read_plan(a.plan));packet26::dispatch.load(a.dispatch);
  engine=std::make_unique<Engine>(weights,a,plan(weights,a));auto& e=*engine;
  e.allocation_probe=true;e.initialize();
  for(const char* key:{"token_embd.weight","per_layer_token_embd.weight"}) {
   auto& t=weights.directory.at(key);
   if(std::string(key)=="per_layer_token_embd.weight"){auto rb=t.bytes/t.shape[0];t.shape[0]=272;t.bytes=272*rb;}
   weights.synthetic[key].resize(t.bytes,0);
  }
  weights.load_resident_lookups();weights.use_resident_lookups=true;e.prepare_plan();e.prepare_commands();
  const auto before=identities(e);size_t total=0;
  for(const auto& id:sequence_ids()) {
   auto dest=root/id;auto poisoned=poison_samples(e);p58_reset_request(e,dest);
   require(reset_samples(e)==poisoned,"mutable sample coverage");identity_check(e,before);total+=poisoned;sensors(e,id);
   if(id!="after-suite") {
    int token=2;e.request_diagnostics=dest;e.checkpoint("prefill-start");
    e.cache_begin_position();e.put(0,"token",&token,4);e.prepare_token(token);
    for(const auto& launch:e.p.launches)e.enqueue(launch,e.logical);
    e.cache_plan_during_position();e.drain();e.cache_after_position();
    e.checkpoint("first-prefill-complete");
   }
  }
  bool refused=false;e.poisoned=true;
  try{p58_reset_request(e,root/"not-opened");}catch(const std::exception&){refused=true;}
  require(refused,"poisoned target reset accepted");e.poisoned=false;
  require(transport->captured>1000&&transport->issued>1000,"production preparation coverage");
  e.shutdown();engine.reset();std::cout<<"PASS native sequence requests=13 target_resets=14 mutable_samples="<<total<<"\n";return 0;
 }catch(const std::exception& error){std::cerr<<error.what()<<'\n';if(engine)engine->shutdown();return 1;}
}
