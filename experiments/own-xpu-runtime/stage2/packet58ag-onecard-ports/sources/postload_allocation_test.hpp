#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/postload_allocation_test.hpp"
// Included only in the CPU build, after Engine. No accelerator libraries or model reads.
// Exercise the actual Engine::initialize_cache, not a copied allocation sequence.
class AllocationOnlyMock final : public packet18::LifetimeMock {
  std::map<void*,void*> backing_allocations;
public:
  size_t allocation_calls=0, publication_copies=0, backing_bytes=0;
  void* allocate(size_t bytes, Memory memory) override {
    ++allocation_calls;
    // Tables are written by the real setup path. Expert banks and cache payload
    // are opaque addresses in this test: never read, pinned, or materialized.
    size_t backing=bytes<=2*1024*1024?bytes:1;
    backing_bytes+=backing+255;
    auto raw=LifetimeMock::allocate(backing+255,memory);
    auto aligned=reinterpret_cast<void*>((reinterpret_cast<uintptr_t>(raw)+255)&~uintptr_t(255));
    backing_allocations.emplace(aligned,raw);
    return aligned;
  }
  void release(void* pointer,Memory memory) override {
    LifetimeMock::release(backing_allocations.at(pointer),memory);
    backing_allocations.erase(pointer);
  }
  ownrt::Event copy(void*,const void*,size_t,std::span<const ownrt::Event> deps) override {
    ++publication_copies;
    return marker(deps);
  }
};

static int postload_allocation_test(const fs::path& destination) {
  require(getpriority(PRIO_PROCESS,0)==19,"nice19 required");
  require(!fs::exists(destination),"fresh CPU test output required");
  fs::create_directories(destination);
  const auto packet=fs::path(__FILE__).parent_path();
  Options a;
  a.card=0;a.cards=1;a.context=4096;a.stage="decode";a.memory="resident";
  a.miss_path="zero-copy";a.output=destination;
  a.selection=packet/"selection.json";
  {std::ifstream f(a.selection,std::ios::binary);std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(f)),{});a.selection_sha256=hash(bytes);}
  packet26::dispatch.load(packet/"dispatch-speed6.json");
  Options metadata_only;metadata_only.mini=true;
  Weights weights(metadata_only); // constructor cannot open a model
  weights.directory=flash::directory_from_loader(iq3::read_plan(
      packet.parent_path()/"suite-inputs-20261012/incident-retrospective/plan.tsv"));
  auto p=plan(weights,a);
  require(p.g.experts==512 && p.g.context==4096 && a.cache_bytes==21552729600ull,"KD geometry");
  Engine engine(weights,a,p);
  auto mock=std::make_unique<AllocationOnlyMock>();auto* observer=mock.get();
  engine.devices.push_back(std::make_unique<ownrt::Device>(std::move(mock)));
  engine.owned_bytes.resize(1);engine.weights.resize(1);engine.buffers.resize(1);
  // Model the already-loaded expert handles using exact metadata dimensions.
  // No payload file is opened. All logical sizes still go through Arena checks.
  for(const auto& [name,t]:weights.directory) {
    if(t.shape.size()!=3 || name.find("_exps.weight")==std::string::npos)continue;
    const size_t bytes=p49b_weight(weights,a,p,name)?p49b_weight_bytes(t):t.bytes;
    int layer=std::stoi(name.substr(4));
    int projection=name.find("ffn_gate_")!=std::string::npos?0:name.find("ffn_up_")!=std::string::npos?1:2;
    auto host=engine.allocate(0,"pinned-experts:"+name,bytes,Category::weights,Lifetime::process,Memory::pinned);
    auto table=engine.allocate(0,"expert-table:"+name,p.g.experts*sizeof(p58::Pointer),Category::weights,Lifetime::process);
    engine.expert_banks[name]={host,table,bytes/size_t(p.g.experts),layer,projection};
  }
  require(engine.expert_banks.size()==144,"full loaded-bank fixture");
  for(const auto& l:p.launches)if(l.op=="expert_gate_up") {
    auto id=engine.allocate(0,l.inputs.at(1),p.g.top*sizeof(iq3::Route),Category::scratch,Lifetime::transaction);
    engine.buffers[0][l.inputs[1]]={id,size_t(p.g.top),Scalar::f32};
  }
  // Both old requests must fail before the backend is called, with useful detail.
  const size_t before=observer->allocation_calls;
  size_t rejected=0;
  for(const auto& label:{"cache-table-staging","cache-route-readback"}) {
    try {engine.allocate(0,label,16,Category::pinned_slab,Lifetime::process,Memory::pinned);}
    catch(const std::logic_error& error) {
      const std::string expected="category lifetime violation: label=\"card0:"+std::string(label)+
        "\" category=pinned-copy-slab requested=process planned=transfer";
      require(error.what()==expected,"allocation diagnostic mismatch");++rejected;
    }
  }
  require(rejected==2 && observer->allocation_calls==before,"invalid lifetime reached backend");
  engine.initialize_cache(); // Entire real post-weight-upload allocation path.
  require(observer->allocation_calls-before==4,"post-load allocation sequence changed; audit gate");
  require(observer->publication_copies==144 && engine.route_sources.size()==48,"incomplete cache setup");
  require(engine.expert_cache && engine.expert_cache->resident_bytes()==0,"initial LRU state");
  const auto& arena=engine.dev(0).arena;
  require(arena.row(engine.cache_arena).bytes==21552729600ull,"cache allocation extent");
  require(arena.row(engine.table_staging).bytes==1179648 && arena.row(engine.route_log).bytes==5760,"pinned extent");
  require(arena.row(engine.table_staging).lifetime==Lifetime::transfer &&
          arena.row(engine.route_log).lifetime==Lifetime::transfer,"transfer lifetime");
  require(arena.row(engine.publication_device).bytes==1179648,"bounded publication device staging");
  require(observer->backing_bytes<4*1024*1024,"CPU backing bound");
  save(destination/"census.json",arena.census());
  const auto backing=observer->backing_bytes;
  auto receipt=engine.dev(0).shutdown(std::chrono::seconds(5));
  require(receipt.safe_to_exit && receipt.live_bytes==0 && receipt.in_flight==0,"postload teardown");
  save(destination/"teardown.json",receipt.json());
  save(destination/"result.json","{\"passed\":true,\"device_executed\":false,\"model_reads\":false,\"postload_allocations\":4,\"negative_cases\":2,\"expert_banks\":144,\"route_layers\":48,\"publication_copies\":144,\"backing_bytes\":"+std::to_string(backing)+"}\n");
  return 0;
}
