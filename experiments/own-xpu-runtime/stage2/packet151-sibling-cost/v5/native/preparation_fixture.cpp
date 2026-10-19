#define main packet151_audit_unused_main
#include "audit-main.cpp"
#undef main
int main(int argc,char**argv){try{
 auto a=parse(argc,argv);a.output=std::getenv("P151_AUDIT_OUTPUT");fs::create_directories(a.output);
 require(!a.mini&&a.rank==0&&a.context==4096,"real rank0 geometry required");
 packet26::dispatch.load(a.dispatch);Weights w(a);auto p=pipeline::split(plan(w,a),a.rank,a.mini,a.draft_rank,a.target_split);
 Engine e(w,a,p);e.deadline=std::chrono::steady_clock::time_point::max();
 e.initialize();pipeline::banks(e);std::cout<<"load and preparation complete; h="<<p.g.h<<" mid="<<p.g.mid<<" top="<<p.g.top<<" sites="<<p.launches.size()<<std::endl;
 p151s::Sibling sibling(e);pipeline::SpeculativeImage image(e);pipeline::Candidate candidate;std::vector<uint8_t>shared(pipeline::shared_bytes);
 for(int pos: {0,1,2,31,32,33}){
  e.put(0,"position",&pos,4);candidate={};int fixture=pos<2?0:pos-1;
  pipeline::Request r{pipeline::half,2,pos,fixture,0,pos+1,{}};
  p151audit::site="half position "+std::to_string(pos);
  auto reply=pipeline::half_step(e,candidate,r,shared.data(),image,false,false,&sibling);
  require(!reply.error,"audit sticky error");
  if(!fixture)require(sibling.caches.empty(),"sibling active during prefill");
  else require(!sibling.caches.empty()&&sibling.paired_sites>0,"no real-shape sibling preparation");
  std::cout<<"position="<<pos<<" fixture="<<fixture<<" parity="<<e.bank_parity<<" prepared="<<p151audit::prepared<<" issued="<<p151audit::issued<<" paired="<<sibling.paired_sites<<std::endl;
 }
 e.shutdown();std::cout<<"PASS CPU device-branch preparation; arithmetic tested separately\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
