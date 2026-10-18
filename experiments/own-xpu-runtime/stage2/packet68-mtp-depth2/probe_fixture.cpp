// Bounded target-half fixture, synthetic weights only, no CPU model generation.
#define main unused_p68_main
#include "main.cpp"
#undef main
int main(int argc,char**argv){try{
 require(argc==3,"output and on/off");fs::path out=argv[1];fs::create_directories(out);
 std::ofstream actual(out/"state.bin",std::ios::binary);
 for(int rows:{1,2,3}){
  Options a;a.mini=true;a.pipeline_mini=true;a.rank=0;a.draft_rank=1;a.context=64;
  a.memory="resident";a.nongemv="parallel";a.timing="token";a.output=out;a.seconds=120;
  Weights w(a);Engine e(w,a,pipeline::split(plan(w,a),0,true));e.initialize();pipeline::banks(e);
  pipeline::SpeculativeImage image(e);pipeline::Candidate c;
  std::vector<uint8_t> shared(pipeline::shared_bytes);
  auto state=[&](){std::vector<uint8_t> all;
   for(auto [name,s]:e.buffers[0]){auto b=e.readback(0,s.id,s.n*flash::scalar_bytes(s.type));all.insert(all.end(),b.begin(),b.end());}
   for(auto [name,id]:e.state_spares){auto b=e.readback(0,id,e.dev(0).arena.row(id).bytes);all.insert(all.end(),b.begin(),b.end());}
   for(auto n:{e.history0,e.history1,int64_t(e.bank_parity),int64_t(e.context_extent),int64_t(e.alternate_context_extent)}){
    auto* b=reinterpret_cast<uint8_t*>(&n);all.insert(all.end(),b,b+sizeof n);}
   all.insert(all.end(),shared.begin(),shared.end());return all;
  };
  for(int pos=0;pos<rows;++pos){
   pipeline::Request r{pipeline::half,(pos*7+3)%e.p.g.vocab,pos,pos+1,0,0,{0,0}};
   pipeline::half_step(e,c,r,shared.data(),image);require(!c.cancelled,"fixture cancelled");c={};
   auto before=state();
   if(std::string(argv[2])=="on")pipeline::depth2_cost_probe(e,c,image,shared.data(),pos+1,pos+1);
   require(before==state(),"discarded row changed target state");
   auto digest=hash(before);actual.write(digest.data(),digest.size());
  }
  image.boundary();e.shutdown();
 }
 actual.close();require(bool(actual),"fixture bytes");
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"target_rows\":[1,2,3],\"discarded_rows\":6,\"full_model_runs\":0}\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
