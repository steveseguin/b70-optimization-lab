// Actual miniature engine, synthetic weights only. No full-shape/model reads.
#define main p154_unexecuted_entry
#include "../native-src/main.cpp"
#undef main
static std::map<Allocation,std::string> mutable_bytes(Engine& e){
 std::map<Allocation,std::string> result;
 for(const auto& [name,row]:e.buffers[0])
  result[row.id]=hash(e.readback(0,row.id,row.n*flash::scalar_bytes(row.type)));
 for(const auto& [name,id]:e.state_spares)
  result[id]=hash(e.readback(0,id,e.dev(0).arena.row(id).bytes));
 return result;
}
int main(int argc,char** argv){
 std::unique_ptr<Engine> e;
 try{
  require(argc==5,"selection digest output replay");Options a;
  a.mini=true;a.pipeline_mini=true;a.context=64;a.cards=1;a.card=0;a.rank=0;a.draft_rank=1;
  a.memory="resident";a.gemv="r5";a.nongemv="parallel";a.selection=argv[1];
  a.selection_sha256=argv[2];a.output=argv[3];fs::create_directories(a.output);
  Weights w(a);e=std::make_unique<Engine>(w,a,pipeline::split(plan(w,a),0,true));
  e->initialize();pipeline::banks(*e);
  {
   pipeline::SpeculativeImage image(*e);std::array<uint8_t,65536> shared{};
   for(int token=1;token<=7;++token){
    const auto h0=e->history0,h1=e->history1;
    e->prepare_token(token);e->drain();
    const auto expected=mutable_bytes(*e);const auto lookups=e->lookup_ids;
    const auto post0=e->history0,post1=e->history1;
    // Identical current production function and its exact saved host inputs.
    e->history0=h0;e->history1=h1;e->prepare_token(token);e->drain();
    require(mutable_bytes(*e)==expected&&e->lookup_ids==lookups&&
            e->history0==post0&&e->history1==post1,"token duplicate changed bytes/history");
    auto before=mutable_bytes(*e);
    image.begin(shared.data());e->drain();
    // Source streams/history may change; private copy must restore them exactly.
    std::vector<uint8_t> poison(4*e->p.g.h*2,0x19);
    e->put(0,"streams",poison.data(),poison.size());
    int64_t history[2]={51,52};e->put(0,"token_history",history,16);shared.fill(77);
    image.restore();e->drain();
    require(mutable_bytes(*e)==before,"snapshot replay/restore changed model bytes");
    require(e->history0==post0&&e->history1==post1&&e->lookup_ids==lookups,"snapshot host restore changed");
    require(std::all_of(shared.begin(),shared.end(),[](auto x){return x==0;}),"shared restore changed");
   }
  }
  e->shutdown();e.reset();
  std::cout<<"{\"passed\":true,\"device_executed\":false,\"tokens\":7,\"all_model_bytes_equal\":true,\"poison_restore\":true}"<<std::endl;
  return 0;
 }catch(const std::exception& error){std::cerr<<error.what()<<std::endl;if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}
}
