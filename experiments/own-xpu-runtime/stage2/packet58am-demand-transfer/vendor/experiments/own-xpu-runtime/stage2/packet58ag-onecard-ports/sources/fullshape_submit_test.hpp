#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/fullshape_submit_test.hpp"
// Full production initialization and every submit check; no payload reads or kernels.
#include <sys/mman.h>
class FullShapeMock final : public packet18::LifetimeMock {
  std::map<void*,size_t> mappings;
public:
  size_t logical_bytes=0,captured=0;
  void* allocate(size_t bytes,Memory) override {
    // Reserve actual disjoint extents. Linux page alignment exceeds native's 16B
    // contract. No MAP_POPULATE, locking, host tuning, or materialized weights.
    auto p=mmap(nullptr,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_NORESERVE,-1,0);
    require(p!=MAP_FAILED,"fullshape mmap");mappings[p]=bytes;logical_bytes+=bytes;return p;
  }
  void release(void* p,Memory) override {require(munmap(p,mappings.at(p))==0,"fullshape munmap");mappings.erase(p);}
  ownrt::Event copy(void*,const void*,size_t,std::span<const ownrt::Event> deps) override {return marker(deps);}
  std::function<ownrt::Event()> prepare_owned(std::shared_ptr<const ownrt::Operation>,std::span<void*const>) override {
    ++captured;return [this]{throw std::logic_error("fullshape must never execute");return marker({});};
  }
  ownrt::Event compute(const ownrt::Operation&,std::span<void*const>,std::span<const ownrt::Event>) override {throw std::logic_error("fullshape compute forbidden");}
};
static int fullshape_submit_test(const fs::path& destination,const fs::path& selection,const std::string& window,const std::string& miss) {
  require(getpriority(PRIO_PROCESS,0)==19,"nice19 required");
  require(!fs::exists(destination),"fresh fullshape output");fs::create_directories(destination);
  const auto packet=fs::path(__FILE__).parent_path();
  Options a;a.card=0;a.cards=1;a.context=4096;a.stage="decode";a.memory="resident";a.miss_path=miss;a.output=destination;
  a.selection=selection;a.tokens=(window=="KD"||window=="W2m")?8:128;a.retain_steps.parse((window=="KD"||window=="W2m"||window=="WS")?"1-8":"none");
  {std::ifstream f(a.selection,std::ios::binary);std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(f)),{});a.selection_sha256=hash(bytes);}
  packet26::dispatch.load(packet/"dispatch-speed6.json");
  Options metadata_only;metadata_only.mini=true;Weights weights(metadata_only);
  weights.directory=flash::directory_from_loader(iq3::read_plan(packet.parent_path()/"suite-inputs-20261012/incident-retrospective/plan.tsv"));
  Engine engine(weights,a,plan(weights,a));
  auto backend=std::make_unique<FullShapeMock>();auto* observer=backend.get();
  engine.allocation_probe=true;engine.devices.push_back(std::make_unique<ownrt::Device>(std::move(backend)));
  try {
    engine.initialize();engine.prepare_plan();
    save(destination/"census.json",engine.dev(0).arena.census());
    engine.legacy_pointer_probe=true;
    std::string failure;
    try {engine.prepare_commands();}catch(const std::exception& error){failure=error.what();}
    require(failure.find("p28 extent/alignment")!=std::string::npos,"58f must reproduce original refusal: "+failure);
    save(destination/"58f-refusal.txt",failure+"\n");std::cout<<failure<<"\n";
    engine.legacy_pointer_probe=false;engine.prepare_commands();
    size_t commands=0;for(auto& site:engine.issue_sites)commands+=site.commands.size();
    // Re-run the same production bind/submit path at full context capacity.
    engine.context_extent=4096;engine.prepared.clear();engine.matrices.clear();engine.prepare_plan();engine.prepare_commands();
    save(destination/"result.json","{\"passed\":true,\"device_executed\":false,\"model_reads\":false,\"legacy_refused\":true,\"sites\":"+std::to_string(engine.p.launches.size())+",\"commands\":"+std::to_string(commands)+",\"logical_bytes\":"+std::to_string(observer->logical_bytes)+",\"contexts\":[32,4096]}\n");
    engine.issue_sites.clear();engine.prepared.clear();engine.matrices.clear();
    auto receipt=engine.dev(0).shutdown(std::chrono::seconds(5));require(receipt.safe_to_exit,"fullshape shutdown");save(destination/"teardown.json",receipt.json());
  } catch(...) {engine.issue_sites.clear();engine.prepared.clear();engine.matrices.clear();engine.dev(0).shutdown(std::chrono::seconds(5));throw;}
  return 0;
}
