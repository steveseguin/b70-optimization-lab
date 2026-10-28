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
static void constructor_refusals(const fs::path& root){
 for(int mode=0;mode<4;++mode){FixtureOwner e(root/("refuse"+std::to_string(mode)));for(auto name:{"error","position"})e.buffers[0][name]={e.allocate(0,name,4,Category::graph_static,Lifetime::graph)};e.add_qsa();
  if(mode==0)e.p.launches.push_back({"norm","extra",{},{"blk.0.qsa.keys"},{},{}});
  if(mode==1)e.allocate(0,"unclassified.keys",64,Category::kv,Lifetime::request);
  if(mode==2)e.p.buffers.back().shape[0]=15;
  if(mode==3)for(auto& b:e.p.buffers)if(b.name.ends_with(".raw"))b.shape[0]=32;
  refusal([&]{pipeline::ring_next::CheckpointRingFor<FixtureOwner> rejected(e,true,{});});e.close();
 }
}
static void depth2_suffix(const fs::path& root){
 FixtureOwner e(root/"depth2");e.a.pipeline_ring_depth=2;e.a.prefill_rows=256;e.a.pipeline_ring_persistent_requests=true;for(auto name:{"error","position"})e.buffers[0][name]={e.allocate(0,name,4,Category::graph_static,Lifetime::graph)};const auto qsa=e.add_qsa();const auto target=e.all_owned;
 const auto shadow=e.allocate(0,"prefill:blk.*.qsa.keys",4096,Category::scratch,Lifetime::transaction);
 pipeline::ring_next::CheckpointRingFor<FixtureOwner> ring(e,true,{});std::array<uint8_t,65536> shared{};
 for(int start:{32,63}){e.put("position",start);std::map<Allocation,std::vector<uint8_t>> expected;for(auto id:target)expected[id]=e.readback(0,id,e.dev(0).arena.row(id).bytes);const int slot=ring.capture(shared.data());const int rows=start==63?1:2;
  std::memset(e.dev(0).arena.row(shadow).pointer,77,4096);
  for(int p=start;p<start+rows;++p)for(int i=0;i<4;++i){if(i==3&&(p+1)%4)continue;auto& row=e.dev(0).arena.row(qsa[size_t(i)]);const size_t bytes=row.bytes/size_t(i==3?16:64);std::memset(static_cast<uint8_t*>(row.pointer)+size_t(i==3?p/4:p)*bytes,0x91,bytes);}e.put("position",start+rows);ring.restore(slot);for(auto [id,bytes]:expected)assert(e.readback(0,id,bytes.size())==bytes);ring.release(slot);
  const auto transient=e.readback(0,shadow,4096);assert(std::all_of(transient.begin(),transient.end(),[](auto x){return x==77;}));
 }e.close();
}
int main(int argc,char** argv){options_gate();assert(argc==2);fs::path root=argv[1];fs::create_directory(root);constructor_refusals(root);depth2_suffix(root);FixtureOwner e(root/"owner");
 e.a.pipeline_live_draft=e.a.pipeline_draft_partition=e.a.mtp=true;e.a.pipeline_ring_depth=3;
 for(auto name:{"error","position"})e.buffers[0][name]={e.allocate(0,name,4,Category::graph_static,Lifetime::graph)};
 auto active=e.allocate(0,"state",4097,Category::recurrent,Lifetime::request),spare=e.allocate(0,"alternate:state",4097,Category::recurrent,Lifetime::request),scratch=e.allocate(0,"scratch",8193,Category::scratch,Lifetime::transaction);
 e.buffers[0]["state"]={active};e.state_spares["state"]=spare;const auto qsa=e.add_builder_qsa();
 auto write_qsa=[&](int at,int value){for(int i=0;i<4;++i){if(i==3&&(at+1)%4)continue;auto& row=e.dev(0).arena.row(qsa[size_t(i)]);const size_t row_bytes=row.bytes/size_t(i==3?16:64);std::memset(static_cast<uint8_t*>(row.pointer)+size_t(i==3?at/4:at)*row_bytes,value,row_bytes);}};
 std::set<Allocation> before;for(const auto& [id,owner]:e.allocations)before.insert(id);
 auto draft=e.allocate(0,"draft:state",257,Category::scratch,Lifetime::transaction);
 std::vector<Allocation> pins{e.allocate(0,"draft:publication",8,Category::output_ring,Lifetime::request,Memory::pinned),e.allocate(0,"draft:half-staging",20,Category::pinned_slab,Lifetime::transfer,Memory::pinned)};
 const auto partition=pipeline::admit_operator_partition(e,before,{draft},pins);
 pipeline::ring_next::CheckpointRingFor<FixtureOwner> ring(e,true,partition);const auto frozen=e.allocations.size();assert(frozen==before.size()+1+9);
 ring.write_layout(root/"ring-layout.json",true);{std::ifstream f(root/"ring-layout.json");std::string layout((std::istreambuf_iterator<char>(f)),{});assert(layout.find("ownrt.ring-checkpoint-layout.live.sparse.v2")!=std::string::npos&&layout.find("sparse-positional-qsa-rows")!=std::string::npos&&layout.find("slot_reserve_bytes")!=std::string::npos);}
 std::array<uint8_t,65536> shared{};shared.fill(1);e.put("position",31);e.history0=31;e.context_extent=e.alternate_context_extent=32;
 std::map<Allocation,std::vector<uint8_t>> before_first;for(auto id:before)before_first[id]=e.readback(0,id,e.dev(0).arena.row(id).bytes);const int first=ring.capture(shared.data());
 e.put("position",32);write_qsa(31,2);std::memset(e.dev(0).arena.row(scratch).pointer,2,8193);e.swap_state_banks();e.history0=32;shared.fill(2);
 const int second=ring.capture(shared.data());assert(first!=second);
 e.put("position",33);write_qsa(32,3);std::memset(e.dev(0).arena.row(scratch).pointer,3,8193);e.swap_state_banks();e.history0=33;e.context_extent=64;shared.fill(3);const int third=ring.capture(shared.data());refusal([&]{ring.capture(shared.data());});
 // Aborting the oldest slot must erase every later tentative QSA row while
 // leaving independently advanced canonical draft allocations untouched.
 for(auto id:{draft,pins[0],pins[1]})std::memset(e.dev(0).arena.row(id).pointer,77,e.dev(0).arena.row(id).bytes);
 ring.restore(first);ring.release(first);ring.release(second);ring.release(third);assert(e.integer(0,"position")==31&&e.history0==31&&e.bank_parity==0&&e.context_extent==32&&shared[0]==1);
 for(auto [id,bytes]:before_first)assert(e.readback(0,id,bytes.size())==bytes);
 for(auto id:{draft,pins[0],pins[1]}){auto bytes=e.readback(0,id,e.dev(0).arena.row(id).bytes);assert(std::all_of(bytes.begin(),bytes.end(),[](auto x){return x==77;}));}
 assert(ring.captures()==3&&ring.restores()==1&&ring.byte_checks()==1);refusal([&]{ring.release(second);});
 if(e.bank_parity)e.swap_state_banks();for(auto& [id,owner]:e.allocations)std::memset(e.dev(0).arena.row(id).pointer,0,e.dev(0).arena.row(id).bytes);
 e.history0=e.history1=0;e.context_extent=e.alternate_context_extent=64;ring.reset_after_owner_zero();assert(e.allocations.size()==frozen);
 const int a=ring.capture(shared.data());e.put("position",1);std::memset(e.dev(0).arena.row(scratch).pointer,4,8193);e.swap_state_banks();
 const int b=ring.capture(shared.data());e.put("position",2);std::memset(e.dev(0).arena.row(scratch).pointer,5,8193);e.swap_state_banks();
 ring.restore(a);ring.release(a);ring.release(b);assert(e.integer(0,"position")==0&&e.bank_parity==0&&ring.restores()==1&&ring.byte_checks()==1);
 const auto zero=e.readback(0,scratch,8193);assert(std::all_of(zero.begin(),zero.end(),[](auto x){return !x;}));
 e.put("position",1);const int negative=ring.capture(shared.data());auto* committed=static_cast<uint8_t*>(e.dev(0).arena.row(qsa[0]).pointer);committed[0]^=1;refusal([&]{ring.restore(negative);});committed[0]^=1;ring.restore(negative);ring.release(negative);
 const int tail=ring.capture(shared.data());auto& tail_row=e.dev(0).arena.row(qsa[0]);static_cast<uint8_t*>(tail_row.pointer)[tail_row.bytes-1]^=1;refusal([&]{ring.restore(tail);});static_cast<uint8_t*>(tail_row.pointer)[tail_row.bytes-1]^=1;ring.restore(tail);ring.release(tail);
 for(int start:{29,30}){e.put("position",start);e.history0=start;shared.fill(uint8_t(start));std::map<Allocation,std::vector<uint8_t>> expected;for(auto id:before)expected[id]=e.readback(0,id,e.dev(0).arena.row(id).bytes);const int oldest=ring.capture(shared.data());int middle=-1,newest=-1;
  for(int step=0;step<3;++step){write_qsa(start+step,100+step);std::memset(e.dev(0).arena.row(scratch).pointer,100+step,8193);e.put("position",start+step+1);e.history0=start+step+1;shared.fill(uint8_t(start+step+1));if(step==0)middle=ring.capture(shared.data());if(step==1)newest=ring.capture(shared.data());}
  ring.restore(oldest);for(auto [id,bytes]:expected)assert(e.readback(0,id,bytes.size())==bytes);ring.release(oldest);ring.release(middle);ring.release(newest);
 }
 e.allocate(0,"unexpected",4,Category::scratch,Lifetime::transaction);refusal([&]{ring.capture(shared.data());});
 e.close();std::cout<<"PASS actual checked sparse three-slot transport: per-slot QSA positions, oldest suffix restore, newer draft survives, full-allocation negative controls, zeroed table rebuild, census refusal; CPU only\n";
}
