// CPU-only: actual checkpoint class + checked Device/CopyEngine/SnapshotFlat,
// injected small owner metadata. No model files, device API or SYCL runtime.
#define main unused_wavefront_native_entry
#include "gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp"
#undef main
#include <cassert>
struct FixtureOwner {
 struct Options {bool pipeline_wavefront=true,mtp=false,pipeline_live_draft=false;int prefill_rows=0,pipeline_stage=0;fs::path output;bool pipeline_enabled()const{return true;}bool pipeline_first()const{return pipeline_stage==0;}} a;
 struct Buffer {Allocation id;};
 std::unique_ptr<ownrt::Device> device=std::make_unique<ownrt::Device>(std::make_unique<Host>());
 bool resident=true,poisoned=false,progress_pending=false,prepare_async=false;
 std::function<void()> progress_callback,correction_exchange,head_export,head_publish,head_merge;
 struct Reports {bool pending()const{return false;}} reply_report;
 std::map<Allocation,std::pair<int,size_t>> allocations;
 std::vector<std::map<std::string,Buffer>> buffers{1};std::map<std::string,Allocation> state_spares;
 unsigned bank_parity=0;int active_bank=0,spare_bank=1,context_extent=32,alternate_context_extent=32;
 int64_t history0=0,history1=0;
 std::map<std::string,std::vector<uint8_t>> lookup_ids;
 std::vector<std::vector<uint32_t>> selected{{1,2}};
 std::vector<int> loaded_layer{-1};std::vector<Allocation> fp32_sources{0};std::vector<size_t> fp32_extents{0};
 ownrt::Event tail=0;
 explicit FixtureOwner(const fs::path& output){a.output=output;fs::create_directory(output);}
 ownrt::Device& dev(int c){assert(c==0);return *device;}
 Allocation allocate(int c,const std::string& name,size_t n,Category category,Lifetime life,Memory memory=Memory::device){auto id=dev(c).arena.allocate("card0:"+name,n,memory,category,life);allocations[id]={c,n};std::memset(dev(c).arena.row(id).pointer,0,n);return id;}
 void upload(int c,Allocation id,size_t offset,const void* source,size_t n){auto& row=dev(c).arena.row(id);assert(offset+n<=row.bytes);std::memcpy(static_cast<uint8_t*>(row.pointer)+offset,source,n);}
 void drain(){if(tail){assert(dev(0).wait(tail,std::chrono::seconds(5)));tail=0;}}
 std::vector<uint8_t> readback(int c,Allocation id,size_t n){drain();auto& row=dev(c).arena.row(id);assert(n<=row.bytes);auto p=static_cast<uint8_t*>(row.pointer);return {p,p+n};}
 int integer(int c,const std::string& name){int value;auto b=readback(c,buffers[c].at(name).id,4);std::memcpy(&value,b.data(),4);return value;}
 void put(const std::string& name,int n){upload(0,buffers[0].at(name).id,0,&n,4);}
 void admit_position(int n){context_extent=((n+32)/32)*32;}
 void swap_state_banks(){for(auto& [name,id]:state_spares)std::swap(buffers[0].at(name).id,id);std::swap(active_bank,spare_bank);std::swap(context_extent,alternate_context_extent);bank_parity^=1;fp32_sources[0]=0;fp32_extents[0]=0;}
 void close(){drain();for(auto& [id,owner]:allocations)dev(0).arena.release(id);auto receipt=dev(0).shutdown(std::chrono::seconds(5));assert(receipt.safe_to_exit);}
};
template<class F>void refusal(F f){bool got=false;try{f();}catch(const std::exception&){got=true;}assert(got);}
int main(int argc,char** argv){assert(argc==2);fs::path root=argv[1];fs::create_directory(root);
 for(int stage:{0,1}){FixtureOwner e(root/("stage"+std::to_string(stage)));e.a.pipeline_stage=stage;
  for(auto name:{"error","position"})e.buffers[0][name]={e.allocate(0,name,4,Category::graph_static,Lifetime::graph)};
  auto active=e.allocate(0,"state",4097,Category::recurrent,Lifetime::request),spare=e.allocate(0,"alternate:state",4097,Category::recurrent,Lifetime::request);
  e.buffers[0]["state"]={active};if(stage==0)e.state_spares["state"]=spare;
  auto scratch=e.allocate(0,"scratch",8193,Category::scratch,Lifetime::transaction);
  auto kv=e.allocate(0,"kv",16385,Category::kv,Lifetime::request);
  auto weight=e.allocate(0,"weight",64,Category::weights,Lifetime::process);
  if(stage==0){e.a.pipeline_live_draft=true;e.a.mtp=true;
   e.allocate(0,"draft:publication",8,Category::output_ring,Lifetime::request,Memory::pinned);
   e.allocate(0,"draft:half-staging",20,Category::pinned_slab,Lifetime::transfer,Memory::pinned);
  }
  std::vector<Allocation> original;std::map<Allocation,std::vector<uint8_t>> expected;
  for(auto& [id,owner]:e.allocations){if(id==weight)continue;auto& row=e.dev(0).arena.row(id);auto p=static_cast<uint8_t*>(row.pointer);if(id!=e.buffers[0]["error"].id&&id!=e.buffers[0]["position"].id)for(size_t j=0;j<row.bytes;++j)p[j]=uint8_t(j*13+id);original.push_back(id);expected[id]=e.readback(0,id,row.bytes);}
  e.put("position",32);expected[e.buffers[0]["position"].id]=e.readback(0,e.buffers[0]["position"].id,4);
  e.history0=7;e.history1=8;e.lookup_ids={{"lookup",{3,4,5}}};e.fp32_sources[0]=scratch;e.fp32_extents[0]=2;
  pipeline::StageCheckpointFor<FixtureOwner> checkpoint(e,true);std::array<uint8_t,65536> shared{};shared.fill(42);
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
