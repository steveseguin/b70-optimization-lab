#include "checkpoint_fixture.hpp"
int main(int argc,char** argv){assert(argc==2);const fs::path root=argv[1];fs::create_directory(root);FixtureOwner e(root/"owner");
 e.a.pipeline_live_draft=e.a.pipeline_draft_partition=e.a.mtp=true;
 for(auto name:{"error","position"})e.buffers[0][name]={e.allocate(0,name,4,Category::graph_static,Lifetime::graph)};
 const auto active=e.allocate(0,"state",257,Category::recurrent,Lifetime::request),spare=e.allocate(0,"alternate:state",257,Category::recurrent,Lifetime::request);
 e.buffers[0]["state"]={active};e.state_spares["state"]=spare;
 const auto scratch=e.allocate(0,"scratch",513,Category::scratch,Lifetime::transaction);
 std::set<Allocation> before;for(const auto& [id,owner]:e.allocations)before.insert(id);
 const auto draft_state=e.allocate(0,"draft:position",4,Category::scratch,Lifetime::transaction),draft_scratch=e.allocate(0,"draft:scratch",111,Category::scratch,Lifetime::transaction);
 e.allocate(0,"draft:immutable",64,Category::weights,Lifetime::process);
 const std::vector<Allocation> draft{draft_state,draft_scratch};
 const std::vector<Allocation> pinned{e.allocate(0,"draft:publication",8,Category::output_ring,Lifetime::request,Memory::pinned),e.allocate(0,"draft:half-staging",20,Category::pinned_slab,Lifetime::transfer,Memory::pinned)};
 assert(!e.allocations.count(pinned[0])&&!e.allocations.count(pinned[1]));
 refusal([&]{pipeline::admit_operator_partition(e,before,{draft_state},pinned);});
 refusal([&]{pipeline::admit_operator_partition(e,before,{draft_state,draft_state},pinned);});
 refusal([&]{pipeline::admit_operator_partition(e,before,{active,draft_scratch},pinned);});
 const auto partition=pipeline::admit_operator_partition(e,before,draft,pinned);
 assert(partition.enabled&&partition.draft_device.size()==2&&partition.target_device.size()==before.size());
 e.put("position",31);e.swap_state_banks();e.history0=7;e.history1=8;e.lookup_ids={{"target",{1,2}}};e.fp32_sources[0]=scratch;e.fp32_extents[0]=9;
 std::map<Allocation,std::vector<uint8_t>> target;
 for(auto id:before)target[id]=e.readback(0,id,e.dev(0).arena.row(id).bytes);
 pipeline::StageCheckpointFor<FixtureOwner> cp(e,true,pinned,partition);std::array<uint8_t,65536> shared{};shared.fill(33);cp.begin(shared.data());
 for(auto id:before){if(id==e.buffers[0]["error"].id)continue;auto& row=e.dev(0).arena.row(id);std::memset(row.pointer,99,row.bytes);}
 e.swap_state_banks();e.history0=20;e.history1=21;e.lookup_ids.clear();e.fp32_sources[0]=0;e.fp32_extents[0]=0;e.context_extent=64;
 // Simulate a newer canonical draft step between target capture and abort.
 int draft_host_position=32,draft_host_extent=64;std::map<Allocation,std::vector<uint8_t>> newer;
 for(auto id:{draft_state,draft_scratch,pinned[0],pinned[1]}){auto& row=e.dev(0).arena.row(id);std::memset(row.pointer,72,row.bytes);newer[id]=e.readback(0,id,row.bytes);}
 cp.abort();for(auto [id,bytes]:target)assert(e.readback(0,id,bytes.size())==bytes);
 for(auto [id,bytes]:newer)assert(e.readback(0,id,bytes.size())==bytes);
 assert(draft_host_position==32&&draft_host_extent==64&&e.history0==7&&e.history1==8&&e.context_extent==32&&e.bank_parity==1&&e.fp32_sources[0]==scratch&&e.fp32_extents[0]==9);
 // Model legacy reset's real registry behavior: tables and all device scratch
 // are zeroed; pinned allocations require their independent provider reset.
 if(e.bank_parity)e.swap_state_banks();
 for(const auto& [id,owner]:e.allocations){auto& row=e.dev(0).arena.row(id);if(row.category!=Category::weights)std::memset(row.pointer,0,row.bytes);}
 for(auto id:pinned)std::memset(e.dev(0).arena.row(id).pointer,0,e.dev(0).arena.row(id).bytes);
 e.history0=e.history1=0;e.lookup_ids.clear();e.fp32_sources[0]=0;e.fp32_extents[0]=0;e.context_extent=e.alternate_context_extent=64;
 cp.reset_at_boundary();assert(cp.aborts()==0&&cp.byte_checks()==0&&e.context_extent==32&&e.alternate_context_extent==32);
 cp.begin(shared.data());std::memset(e.dev(0).arena.row(scratch).pointer,77,513);std::memset(e.dev(0).arena.row(draft_scratch).pointer,88,111);cp.abort();
 const auto zeros=e.readback(0,scratch,513),retained=e.readback(0,draft_scratch,111);
 assert(std::all_of(zeros.begin(),zeros.end(),[](auto x){return x==0;})&&std::all_of(retained.begin(),retained.end(),[](auto x){return x==88;}));
 // Header/path admission never accepts an existing or outside-owner destination.
 auto metadata=root/"reset.txt";const auto destination=fs::absolute(e.a.output/"requests"/"cold-1");save(metadata,destination.string()+"\n\n");assert(pipeline::persistent_destination(metadata,e.a.output)==destination);
 fs::create_directories(destination);refusal([&]{pipeline::persistent_destination(metadata,e.a.output);});save(metadata,fs::absolute(root/"outside").string()+"\n\n");refusal([&]{pipeline::persistent_destination(metadata,e.a.output);});
 save(metadata,std::string(9000,'x'));refusal([&]{pipeline::persistent_destination(metadata,e.a.output);});
 save(metadata,fs::absolute(e.a.output/"requests"/"cold-2").string()+"\n\ntrailing\n");refusal([&]{pipeline::persistent_destination(metadata,e.a.output);});
 const auto dangling=e.a.output/"dangling";fs::create_symlink(root/"does-not-exist",dangling);save(metadata,fs::absolute(dangling/"child").string()+"\n\n");refusal([&]{pipeline::persistent_destination(metadata,e.a.output);});
 save(metadata,fs::absolute(dangling).string()+"\n\n");refusal([&]{pipeline::persistent_destination(metadata,e.a.output);});
 const auto fifo=root/"fifo";assert(!::mkfifo(fifo.c_str(),0600));refusal([&]{pipeline::persistent_destination(fifo,e.a.output);});
 // New partition attestations bind both inventory and independently sealed
 // canonical draft state, never claiming full-owner rollback coverage.
 ownrt::wavefront::Ledger ledger(false,128,128);ledger.begin({1,3,0,1,true});ledger.abort(1,3,0,1);
 fs::create_directory(e.a.output/"state-9");fs::create_directory(e.a.output/"state-9.draft");save(e.a.output/"state-9"/"state-seal.txt","target fixture seal\n");save(e.a.output/"state-9.draft"/"state-seal.txt","draft fixture seal\n");
 cp.attest(ledger,e.a.output/"state-9.wavefront-state.json",9);std::ifstream receipt(e.a.output/"state-9.wavefront-state.json");std::string json((std::istreambuf_iterator<char>(receipt)),{});
 assert(json.find("ownrt.wavefront-state.partition.v1")!=std::string::npos&&json.find("sparse_checkpoint_reserve_bytes")!=std::string::npos&&json.find("full_mutable_checkpoint_bytes")==std::string::npos&&json.find("target_mutable_checkpoint_bytes")==std::string::npos&&json.find("independent_draft_state_seal_sha256")!=std::string::npos);
 e.close();std::cout<<"PASS explicit provider census and disjoint ownership; target rollback preserves newer draft device+pinned state; reset reuploads zeroed checked tables; CPU only\n";
}
