#define main unused_device_entry
#include "probe-main.cpp"
#undef main
#include "../../native_arm_order.hpp"
// Snapshot transport must actually copy bytes. Treating it as a marker would
// make a zero-filled fixture pass without exercising restoration.
ownrt::Event p151audit::Backend::compute(const ownrt::Operation& op,std::span<void*const> ptr,std::span<const ownrt::Event>) {
 if(auto b=dynamic_cast<const pipeline::SnapshotFlat*>(&op)){
  auto rows=static_cast<const pipeline::SnapshotFlat::Item*>(ptr[0]);
  for(size_t i=0;i<b->count;++i)std::memcpy(rows[i].dst,rows[i].src,rows[i].bytes);
 }else if(auto b=dynamic_cast<const pipeline::SnapshotBatch*>(&op)){
  for(size_t i=0;i<b->count;++i)std::memcpy(b->items[i].dst,b->items[i].src,b->items[i].bytes);
 }else throw std::logic_error("CPU fixture refuses unrecognized direct compute");
 return ownrt::next_handle();
}
int main(int argc,char**argv){try{
 auto a=parse(argc,argv);a.output=std::getenv("ENTRY_PREPARE_OUTPUT");fs::create_directories(a.output);
 require(a.census_probe&&!a.mini&&a.context==4096,"private production diagnostic parser");
 packet26::dispatch.load(a.dispatch);Weights w(a);
 auto plan_=pipeline::split(plan(w,a),a.rank,a.mini,a.draft_rank,a.target_split);
 Engine e(w,a,plan_);e.deadline=std::chrono::steady_clock::time_point::max();e.initialize();
 if(a.rank==0)pipeline::banks(e);else{e.prepare_plan();e.prepare_commands();}
 pipeline::SpeculativeImage image(e,true);pipeline::Candidate candidate;
 // Production allocation census including diagnostic snapshot backing.
 save(a.output/"census.json",e.dev(0).arena.census());
 std::vector<uint8_t> shared(pipeline::shared_bytes);
 const auto initial=p168::signature(e);image.begin(shared.data());
 auto stream=e.buffers[0].at("streams");std::memset(e.dev(0).arena.row(stream.id).pointer,0xa5,stream.n*flash::scalar_bytes(stream.type));
 require(p168::signature(e)!=initial,"snapshot poison did not change actual bytes");
 image.restore();e.drain();require(p168::signature(e)==initial,"real snapshot poison was not restored");
 // Production preparation and copies execute on a CPU marker transport.
 // Compute kernels are markers, so this proves lifecycle, not arithmetic.
 std::map<int,size_t> physical;
 for(size_t index=0;index<e.p.launches.size();++index){
  const auto& l=e.p.launches[index];
  physical[p168::classify(l)]+=e.issue_sites.at(index).commands.size();
  if(l.op=="route"||l.op=="moe_combine"||l.label.find("shexp")!=std::string::npos)
   require(p168::classify(l)==3,"split fused router/shared class");
 }
 for(int arm:{1,2,3,4,6,7})require(physical[arm]>0,"empty physical class");
 {
  std::ofstream ownership(a.output/"class-ownership.jsonl");
  for(size_t index=0;index<e.p.launches.size();++index){
   const auto& l=e.p.launches[index];
   ownership<<"{\"label\":"<<ownrt::quote(l.label)<<",\"op\":"<<ownrt::quote(l.op)
    <<",\"arm\":"<<p168::classify(l)<<",\"physical_commands\":"<<e.issue_sites.at(index).commands.size()<<"}\n";
  }
 }
 // v3: probe at the REAL device positions (prompt tokens + 63) after admitting
 // only P-1, which is the state the 64-token setup request leaves. Count the
 // prompts whose prepared qsa extent does not cover P: that is the v2 device
 // failure condition (control pass sticky error at benchmark-analysis, P=128).
 std::vector<int> positions;
 {const char* s=std::getenv("P168_PROBE_POSITIONS");require(s!=nullptr,"P168_PROBE_POSITIONS required");
  std::stringstream in(s);std::string x;while(std::getline(in,x,','))positions.push_back(std::stoi(x));}
 require(positions.size()==12,"twelve real probe positions");
 int uncovered=0,observations=0;
 for(int view:p168::arm_order){
   for(int prompt=0;prompt<12;++prompt){
     const int pos=positions[prompt];
     e.admit_position(pos-1);e.put(0,"position",&pos,4);p168::sensor(e,"fixture-before-reset");
     image.boundary();p168::sensor(e,"fixture-after-reset");
     uncovered+=pos>e.context_extent-1; // device guard: pos>launch_extent-tokens
     pipeline::Request r{20,view,prompt,3,0,prompt+1,{}}; // REPEATS=3
     p168::probe(e,image,r,shared.data());observations+=3;
     require(pos<=e.context_extent-1&&e.integer(0,"position")==pos,"probe extent/position after restore");
   }
 }
 for(int arm:{1,5,8,9}){
  bool refused=false;
  try{pipeline::Request r{20,arm,0,1,0,1,{}};p168::probe(e,image,r,shared.data());}
  catch(const std::exception&){refused=true;}
  require(refused,"residual or split-fusion arm accepted");
 }
 require(p151audit::prepared>0&&p151audit::issued>0,"actual preparation/issue bypassed");
 e.shutdown();std::cout<<"PASS private native arm lifecycle rank="<<a.rank
   <<" observations="<<observations<<" v2_uncovered_probe_positions="<<uncovered<<" residual_arms_refused=true; five-class sequence at real probe positions, marker transport, not arithmetic or native interval qualification\n";
 return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
