#include "checkpoint_fixture.hpp"
int main(int argc,char** argv){assert(argc==2);fs::path root=argv[1];fs::create_directory(root);
 for(int stage:{0,1}){FixtureOwner e(root/("stage"+std::to_string(stage)));e.a.pipeline_stage=stage;
  for(auto name:{"error","position"})e.buffers[0][name]={e.allocate(0,name,4,Category::graph_static,Lifetime::graph)};
  auto active=e.allocate(0,"state",4097,Category::recurrent,Lifetime::request),spare=e.allocate(0,"alternate:state",4097,Category::recurrent,Lifetime::request);
  e.buffers[0]["state"]={active};if(stage==0)e.state_spares["state"]=spare;
  auto scratch=e.allocate(0,"scratch",8193,Category::scratch,Lifetime::transaction);
  auto kv=e.allocate(0,"kv",16385,Category::kv,Lifetime::request);
  auto weight=e.allocate(0,"weight",64,Category::weights,Lifetime::process);
  std::vector<Allocation> pinned;
  if(stage==0){e.a.pipeline_live_draft=true;e.a.mtp=true;
   pinned.push_back(e.allocate(0,"draft:publication",8,Category::output_ring,Lifetime::request,Memory::pinned));
   pinned.push_back(e.allocate(0,"draft:half-staging",20,Category::pinned_slab,Lifetime::transfer,Memory::pinned));
   assert(!e.allocations.count(pinned[0])&&!e.allocations.count(pinned[1])); // actual Engine::allocate contract
  }
  std::vector<Allocation> original;std::map<Allocation,std::vector<uint8_t>> expected;
  for(auto id:e.all_owned){if(id==weight)continue;auto& row=e.dev(0).arena.row(id);auto p=static_cast<uint8_t*>(row.pointer);if(id!=e.buffers[0]["error"].id&&id!=e.buffers[0]["position"].id)for(size_t j=0;j<row.bytes;++j)p[j]=uint8_t(j*13+id);original.push_back(id);expected[id]=e.readback(0,id,row.bytes);}
  e.put("position",32);expected[e.buffers[0]["position"].id]=e.readback(0,e.buffers[0]["position"].id,4);
  e.history0=7;e.history1=8;e.lookup_ids={{"lookup",{3,4,5}}};e.fp32_sources[0]=scratch;e.fp32_extents[0]=2;
  if(stage==0){
   refusal([&]{pipeline::StageCheckpointFor<FixtureOwner> rejected(e,true);});
   refusal([&]{pipeline::StageCheckpointFor<FixtureOwner> rejected(e,true,{pinned[0],pinned[0]});});
   refusal([&]{pipeline::StageCheckpointFor<FixtureOwner> rejected(e,true,{pinned[0],weight});});
  }
  pipeline::StageCheckpointFor<FixtureOwner> checkpoint(e,true,pinned);std::array<uint8_t,65536> shared{};shared.fill(42);
  {std::ifstream f(e.a.output/"wavefront-checkpoint-layout.json");std::string layout((std::istreambuf_iterator<char>(f)),{});
   assert(layout.find(stage==0?"\"pinned_bytes\":28":"\"pinned_bytes\":0")!=std::string::npos);}
  checkpoint.begin(shared.data());refusal([&]{checkpoint.begin(shared.data());});
  for(auto id:original){if(id==e.buffers[0]["error"].id)continue;auto& row=e.dev(0).arena.row(id);std::memset(row.pointer,0x9b,row.bytes);}
  if(stage==0)e.swap_state_banks();e.context_extent=64;e.history0=101;e.history1=102;e.lookup_ids.clear();e.selected={{9}};e.loaded_layer={8};e.fp32_sources[0]=0;e.fp32_extents[0]=99;shared.fill(9);
  checkpoint.abort();assert(!checkpoint.active()&&checkpoint.aborts()==1&&checkpoint.byte_checks()==1);
  for(auto id:original)assert(expected[id]==e.readback(0,id,expected[id].size()));
  assert(e.bank_parity==0&&e.active_bank==0&&e.spare_bank==1&&e.context_extent==32&&e.alternate_context_extent==32);
  assert(e.history0==7&&e.history1==8&&e.lookup_ids.at("lookup")==std::vector<uint8_t>({3,4,5})&&e.selected[0]==std::vector<uint32_t>({1,2})&&e.loaded_layer[0]==-1&&e.fp32_sources[0]==scratch&&e.fp32_extents[0]==2);
  assert(std::all_of(shared.begin(),shared.end(),[](auto x){return x==42;}));
  checkpoint.begin(shared.data());e.put("error",1);refusal([&]{checkpoint.abort();});assert(checkpoint.active()&&e.integer(0,"error")==1);e.put("error",0); // fixture cleanup only, production never erases a sticky error
  checkpoint.abort();
  ownrt::wavefront::Ledger ledger(false,128,128);for(int pos=0;pos<32;++pos){ledger.begin({pos+1,3,pos,0,false});ledger.commit(pos+1,3,pos,0,-1);}
  for(int ticket:{33,34}){ledger.begin({ticket,4,32,1,true});ledger.abort(ticket,4,32,1);}
  const auto dump=e.a.output/"state-7";fs::create_directory(dump);const std::string seal="CPU fixture seal bytes\n";save(dump/"state-seal.txt",seal);
  const auto attestation=e.a.output/"state-7.wavefront-state.json";
  checkpoint.attest(ledger,attestation,7);std::ifstream receipt(attestation);std::string attested((std::istreambuf_iterator<char>(receipt)),{});
  assert(attested.find(hash(std::vector<uint8_t>(seal.begin(),seal.end())))!=std::string::npos);
  assert(attested.find("\"actual_position\":32")!=std::string::npos&&attested.find("\"byteverified_restore_count\":2")!=std::string::npos);
  checkpoint.attest(ledger);checkpoint.attest(ledger,attestation,7);
  std::ifstream unchanged(attestation);assert(std::string((std::istreambuf_iterator<char>(unchanged)),{})==attested);
  save(dump/"state-seal.txt","changed fixture seal");refusal([&]{checkpoint.attest(ledger,attestation,7);});
  e.close();
 }
 std::cout<<"PASS actual checked checkpoint: complete scratch/KV/active+spare bytes,31/32 extent rollback,host metadata,shared output,sticky error refusal,sealed dump binding/immutability; CPU only\n";
}
