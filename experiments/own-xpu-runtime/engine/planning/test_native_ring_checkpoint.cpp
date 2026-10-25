// Canonical opt-in ring CPU validation: includes actual checked Device/CopyEngine/
// SnapshotFlat via the existing full-main host fixture. Do not run during GPU timing.
#include "checkpoint_fixture.hpp"
static void options_gate(){
 setenv("OMP_NUM_THREADS","2",1);
 const std::vector<std::string> base{"native","--output","/unused-ring-parser-output","--rank","0","--memory","resident","--gsq-packed","--activations","f32","--context","4096","--target-split","24","--retain-steps","none","--pipeline-stage","0","--pipeline-boundaries","0,12,24,36,48","--native-nice",std::to_string(getpriority(PRIO_PROCESS,0))};
 auto check=[&](std::vector<std::string> extra){auto args=base;args.insert(args.end(),extra.begin(),extra.end());std::vector<char*> pointers;for(auto& a:args)pointers.push_back(a.data());return parse(int(pointers.size()),pointers.data());};
 auto legacy=check({});assert(!legacy.pipeline_ring&&!legacy.pipeline_wavefront);
 const std::vector<std::string> ring{"--pipeline-ring","--pipeline-ring-request-sha256",std::string(64,'a'),"--pipeline-ring-verify-restore"};
 auto admitted=check(ring);assert(admitted.pipeline_ring&&admitted.pipeline_ring_verify&&admitted.pipeline_ring_request_sha256==std::string(64,'a'));
 for(const auto& extra:std::vector<std::vector<std::string>>{{"--pipeline-ring"},{"--pipeline-ring-verify-restore"},{"--pipeline-ring-request-sha256",std::string(64,'a')},{"--pipeline-ring","--pipeline-ring-request-sha256",std::string(64,'A')}})refusal([&]{check(extra);});
 for(const auto& extra:std::vector<std::vector<std::string>>{{"--pipeline-wavefront"},{"--pipeline-live-draft"},{"--pipeline-draft-partition"},{"--pipeline-persistent-requests"},{"--mtp"},{"--retain-steps","1"},{"--pipeline-ring-trace-limit","100001"}}){auto args=ring;args.insert(args.end(),extra.begin(),extra.end());refusal([&]{check(args);});}
}
int main(int argc,char** argv){options_gate();assert(argc==2);fs::path root=argv[1];fs::create_directory(root);FixtureOwner e(root/"owner");
 e.a.pipeline_live_draft=e.a.pipeline_draft_partition=e.a.mtp=true;
 for(auto name:{"error","position"})e.buffers[0][name]={e.allocate(0,name,4,Category::graph_static,Lifetime::graph)};
 auto active=e.allocate(0,"state",4097,Category::recurrent,Lifetime::request),spare=e.allocate(0,"alternate:state",4097,Category::recurrent,Lifetime::request),scratch=e.allocate(0,"scratch",8193,Category::scratch,Lifetime::transaction);
 e.buffers[0]["state"]={active};e.state_spares["state"]=spare;
 std::set<Allocation> before;for(const auto& [id,owner]:e.allocations)before.insert(id);
 auto draft=e.allocate(0,"draft:state",257,Category::scratch,Lifetime::transaction);
 std::vector<Allocation> pins{e.allocate(0,"draft:publication",8,Category::output_ring,Lifetime::request,Memory::pinned),e.allocate(0,"draft:half-staging",20,Category::pinned_slab,Lifetime::transfer,Memory::pinned)};
 const auto partition=pipeline::admit_operator_partition(e,before,{draft},pins);
 pipeline::ring_next::CheckpointRingFor<FixtureOwner> ring(e,true,partition);const auto frozen=e.allocations.size();assert(frozen==before.size()+1+6);
 std::array<uint8_t,65536> shared{};shared.fill(1);e.put("position",31);e.history0=31;e.context_extent=e.alternate_context_extent=32;
 const int first=ring.capture(shared.data());
 e.put("position",32);std::memset(e.dev(0).arena.row(scratch).pointer,2,8193);e.swap_state_banks();e.history0=32;shared.fill(2);
 std::map<Allocation,std::vector<uint8_t>> after_first;for(auto id:before)after_first[id]=e.readback(0,id,e.dev(0).arena.row(id).bytes);
 const int second=ring.capture(shared.data());assert(first!=second);refusal([&]{ring.capture(shared.data());});
 e.put("position",33);std::memset(e.dev(0).arena.row(scratch).pointer,3,8193);e.swap_state_banks();e.history0=33;e.context_extent=64;shared.fill(3);
 auto after_second=e.readback(0,scratch,8193);ring.release(first);assert(e.integer(0,"position")==33&&e.history0==33&&e.readback(0,scratch,8193)==after_second&&shared[0]==3);
 // Canonical draft advanced after both target snapshots; target restore must
 // not copy it backward. Include pinned IDs absent from the device registry.
 for(auto id:{draft,pins[0],pins[1]})std::memset(e.dev(0).arena.row(id).pointer,77,e.dev(0).arena.row(id).bytes);
 ring.restore(second);ring.release(second);assert(e.integer(0,"position")==32&&e.history0==32&&e.bank_parity==1&&e.context_extent==32&&shared[0]==2);
 for(auto [id,bytes]:after_first)assert(e.readback(0,id,bytes.size())==bytes);
 for(auto id:{draft,pins[0],pins[1]}){auto bytes=e.readback(0,id,e.dev(0).arena.row(id).bytes);assert(std::all_of(bytes.begin(),bytes.end(),[](auto x){return x==77;}));}
 assert(ring.captures()==2&&ring.restores()==1&&ring.byte_checks()==1);refusal([&]{ring.release(second);});
 if(e.bank_parity)e.swap_state_banks();for(auto& [id,owner]:e.allocations)std::memset(e.dev(0).arena.row(id).pointer,0,e.dev(0).arena.row(id).bytes);
 e.history0=e.history1=0;e.context_extent=e.alternate_context_extent=64;ring.reset_after_owner_zero();assert(e.allocations.size()==frozen);
 const int a=ring.capture(shared.data());e.put("position",1);std::memset(e.dev(0).arena.row(scratch).pointer,4,8193);e.swap_state_banks();
 const int b=ring.capture(shared.data());e.put("position",2);std::memset(e.dev(0).arena.row(scratch).pointer,5,8193);e.swap_state_banks();
 ring.restore(a);ring.release(a);ring.release(b);assert(e.integer(0,"position")==0&&e.bank_parity==0&&ring.restores()==1&&ring.byte_checks()==1);
 const auto zero=e.readback(0,scratch,8193);assert(std::all_of(zero.begin(),zero.end(),[](auto x){return !x;}));
 e.allocate(0,"unexpected",4,Category::scratch,Lifetime::transaction);refusal([&]{ring.capture(shared.data());});
 e.close();std::cout<<"PASS actual checked two-slot transport: immutable shared inventory, ACCEPT no rewind, oldest suffix restore once, newer draft survives, zeroed table rebuild, census refusal; CPU only\n";
}
