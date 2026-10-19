// Tiny real CPU arithmetic: timing on/off may alter receipts, never state/proposals.
#define main p157_unused_model_entry
#include "../native-src/main.cpp"
#undef main
int main(int argc,char**argv){
 std::unique_ptr<Engine> e;
 try {
  require(argc==4,"selection digest output");Options a;a.mini=true;a.pipeline_mini=true;
  a.context=64;a.cards=1;a.rank=1;a.draft_rank=1;a.memory="resident";a.gemv="r5";a.nongemv="parallel";
  a.selection=argv[1];a.selection_sha256=argv[2];a.output=argv[3];fs::create_directories(a.output);
  Weights w(a);e=std::make_unique<Engine>(w,a,pipeline::split(plan(w,a),1,true));e->initialize();e->prepare_plan();e->prepare_commands();
  std::vector<int> proposals;
  {
   mtp36::DraftRuntime draft(*e);
   for(int pos=1;pos<=4;++pos){
    p157::Identity identity(pos,9);std::vector<uint16_t> input(4*e->p.g.h,iq3::bf16_bits(float(pos)/16));e->put(0,"streams",input.data(),input.size()*2);
    require(draft.begin(pos,pos,true),"mini draft begin");auto result=draft.poll_result();require(bool(result),"mini publication incomplete");proposals.push_back(result->token);e->drain();
   }
   draft.dump_all_state(a.output/"draft-state");
  }
  e->shutdown();e.reset();
  std::cout<<"{\"passed\":true,\"device_executed\":false,\"proposals\":[";
  for(size_t i=0;i<proposals.size();++i)std::cout<<(i?",":"")<<proposals[i];std::cout<<"]}"<<std::endl;return 0;
 }catch(const std::exception& ex){std::cerr<<ex.what()<<std::endl;if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}
}
