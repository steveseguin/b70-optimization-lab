#define main unused_device_entry
#include "probe-main.cpp"
#undef main
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
 std::vector<uint8_t> shared(pipeline::shared_bytes);
 const auto initial=p168::signature(e);image.begin(shared.data());
 auto stream=e.buffers[0].at("streams");std::memset(e.dev(0).arena.row(stream.id).pointer,0xa5,stream.n*flash::scalar_bytes(stream.type));
 require(p168::signature(e)!=initial,"snapshot poison did not change actual bytes");
 image.restore();e.drain();require(p168::signature(e)==initial,"real snapshot poison was not restored");
 // Production preparation and copies execute on a CPU marker transport.
 // Compute kernels are markers, so this proves lifecycle, not arithmetic.
 for(int view:{0,1,2,3,4,0,5,6,7,9,0}){
   for(int prompt=0;prompt<12;++prompt){
     e.put(0,"position",&prompt,4);p168::sensor(e,"fixture-before-reset");
     image.boundary();p168::sensor(e,"fixture-after-reset");
     pipeline::Request r{20,view,prompt,1,0,prompt+1,{}};
     p168::probe(e,image,r,shared.data());
   }
 }
 bool missing_transfer_refused=false;
 try{pipeline::Request r{20,8,0,1,0,1,{}};p168::probe(e,image,r,shared.data());}
 catch(const std::exception&){missing_transfer_refused=true;}
 require(missing_transfer_refused,"unimplemented transfer accepted");
 require(p151audit::prepared>0&&p151audit::issued>0,"actual preparation/issue bypassed");
 e.shutdown();std::cout<<"PASS private native arm lifecycle rank="<<a.rank
   <<" observations=132 missing_transfer_refused=true; marker transport, not arithmetic or complete census qualification\n";
 return 0;
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
