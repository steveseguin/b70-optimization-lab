#define P58R_SELECTIONS "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet180-session-swap-v2/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/selections"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet180-session-swap-v2/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet180-session-swap-v2/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/fullshape_submit_test.hpp"
// Full production initialization and every submit check; no payload reads or kernels.
#include <sys/mman.h>
class FullShapeMock final : public packet18::LifetimeMock, public p58v::AsyncBackend {
  std::map<void*,size_t> mappings;
public:
  size_t logical_bytes=0,captured=0,fill_calls=0;
  ownrt::Event fill_ticket=0;bool allow_completion=false;
  ownrt::Event fill(void*,const void*,size_t) override {++fill_calls;return fill_ticket=ownrt::next_handle();}
  bool fill_complete(ownrt::Event ticket) override {require(ticket==fill_ticket,"mock maintenance event");return allow_completion;}
  size_t fills_pending() override {return fill_ticket&&!allow_completion?1:0;}
  void finish_fills() override {allow_completion=true;}
  void foreground_sync() override {packet18::LifetimeMock::synchronize();}

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
  Options a;a.card=0;a.cards=1;a.context=4096;a.stage="decode";a.memory="resident";a.miss_path=miss;a.output=destination;a.cache_bytes=21552729600ull;
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
    const auto arena=engine.bracket_arena_hash();
    std::ostringstream port_census;port_census<<"[";bool first_port=true;
    for(const auto* mode:{"serial","overlap"}) for(const auto* name:{"production","hc-wide","wide64","halfcache","other-fusion","ordered-retirement","p60fusion","production"}) {
      auto path=fs::path(P58R_SELECTIONS)/"tile16.json";
      std::ifstream f(path,std::ios::binary);std::vector<uint8_t> raw((std::istreambuf_iterator<char>(f)),{});
      engine.maintenance.running=true;
      bool hc_refused=false;try{engine.bracket_select(path,hash(raw),"p60fusion");}catch(const std::exception&){hc_refused=true;}
      require(hc_refused,"HC switch during active position admitted");engine.maintenance.running=false;
      *static_cast<uint32_t*>(engine.dev(0).arena.row(engine.slab[0]).pointer)=37;
      hc_refused=false;try{engine.bracket_select(path,hash(raw),"p60fusion");}catch(const std::exception&){hc_refused=true;}
      require(hc_refused,"HC boundary erased sticky failure");
      // FullShapeMock.copy intentionally does no transfer. Its error readback
      // must therefore explicitly represent the clean zero device-error word.
      std::memset(engine.dev(0).arena.row(engine.slab[0]).pointer,0,4);
      const std::string profile=name;
      engine.bracket_select(path,hash(raw),profile=="p60fusion"?"p60fusion":"production",
        profile=="hc-wide"?"hc-wide":"",profile=="wide64"?"wide64":profile=="halfcache"?"wide64+halfcache":"",profile=="other-fusion"?"fused":"",profile=="ordered-retirement"?"ordered-foreground":"");engine.cache_mode(mode);engine.cache_capacity("max");require(engine.expert_cache->capacity()==21552729600ull,"fullshape active cache cap");engine.publish_cache_table(engine.expert_cache->table());require(arena==engine.bracket_arena_hash(),"fullshape switch allocations changed");
      require(engine.a.hc=="p60fusion","HC fusion must remain on in every view");
      require(engine.a.hc_geometry==((profile=="hc-wide"||profile=="p60fusion")?"hc-wide":"production"),"independent HC dimension");
      require(engine.a.experts==(profile=="wide64"?"wide64":(profile=="halfcache"||profile=="p60fusion")?"wide64+halfcache":"production"),"independent expert dimension");
      require(engine.a.other_fusion==((profile=="other-fusion"||profile=="p60fusion")?"fused":"production"),"independent fusion dimension");
      require(ownrt::ordered_retirement(engine.dev(0))==(profile=="ordered-retirement"||profile=="p60fusion"),"independent retirement dimension");
      size_t commands32=0;for(const auto& site:engine.issue_sites)commands32+=site.commands.size();
      // Exercise the selected view at both startup and maximum context, then
      // let the next real switch reset it from 4096 back to 32.
      engine.context_extent=4096;engine.prepared.clear();engine.alternate_prepared.clear();
      engine.issue_sites.clear();engine.matrices.clear();engine.prepare_plan();engine.prepare_commands();
      require(arena==engine.bracket_arena_hash(),"full-context view allocations changed");
      size_t commands4096=0;for(const auto& site:engine.issue_sites)commands4096+=site.commands.size();
      port_census<<(first_port?"":",")<<"{\"maintenance\":"<<ownrt::quote(mode)<<",\"profile\":"<<ownrt::quote(profile)<<",\"hc_fusion_enabled\":true,\"commands32\":"<<commands32<<",\"commands4096\":"<<commands4096<<"}";first_port=false;
      if(std::string(name)=="p60fusion") {
        std::array<unsigned,4> counts{};unsigned hooks=0;
        for(size_t i=0;i<engine.p.launches.size();++i) {
          const auto& l=engine.p.launches[i];const auto& site=engine.issue_sites[i];int stage=p60::stage(l.label);
          if(stage>=0){++counts[stage];require(site.commands.size()==size_t(stage<3),"HC absorbed capture/command count");}
          if(site.layer_end){require(ends(l.label,".ffn.combine"),"ordinary layer hook label");++hooks;}
        }
        require(counts[0]==96&&counts[1]==96&&counts[2]==96&&hooks==48,"all 48 layers and both HC sides");
      }

    }
    port_census<<"]";save(destination/"port-census.json",port_census.str());
    // Exercise the real full-shape async Engine wiring with delayed mock DMA.
    // No weight bytes are read and no prepared model kernel is executed.
    engine.cache_mode("overlap");
    engine.cache_begin_position();
    for(unsigned layer=0;layer<48;++layer)for(unsigned expert=0;expert<10;++expert)
      engine.previous_routes.push_back(layer*512+expert);
    engine.cache_plan_during_position();
    require(engine.maintenance.state==p58v::Protocol::State::planned,"native plan path");
    bool refused=false;try{engine.cache_boundary();}catch(const std::exception&){refused=true;}
    require(refused,"native publication while running must refuse");
    refused=false;try{engine.cache_capacity("18GB");}catch(const std::exception&){refused=true;}
    require(refused,"native capacity switch while running must refuse");
    engine.maintenance.end(true);
    engine.cache_begin_position();
    require(observer->fill_calls==1440&&engine.dev(0).in_flight()==1,"native fill chain coverage/ownership");
    engine.maintenance.end(true);engine.cache_begin_position();
    require(engine.maintenance.state==p58v::Protocol::State::filling,"native delayed completion published early");
    observer->allow_completion=true;
    require(!engine.maintenance.may_publish(true),"native completion mid-position published early");
    engine.maintenance.end(true);engine.cache_begin_position();
    require(engine.maintenance.state==p58v::Protocol::State::idle&&engine.expert_cache->resident(0),"native completed publication/commit");
    engine.maintenance.end(true);engine.cache_mode("serial");
    size_t commands=0;for(auto& site:engine.issue_sites)commands+=site.commands.size();
    // Re-run the same production bind/submit path at full context capacity.
    engine.context_extent=4096;engine.prepared.clear();engine.matrices.clear();engine.prepare_plan();engine.prepare_commands();
    save(destination/"result.json","{\"passed\":true,\"device_executed\":false,\"model_reads\":false,\"legacy_refused\":true,\"sites\":"+std::to_string(engine.p.launches.size())+",\"commands\":"+std::to_string(commands)+",\"logical_bytes\":"+std::to_string(observer->logical_bytes)+",\"contexts\":[32,4096]}\n");
    engine.issue_sites.clear();engine.prepared.clear();engine.matrices.clear();
    auto receipt=engine.dev(0).shutdown(std::chrono::seconds(5));require(receipt.safe_to_exit,"fullshape shutdown");save(destination/"teardown.json",receipt.json());
  } catch(...) {engine.issue_sites.clear();engine.prepared.clear();engine.matrices.clear();engine.dev(0).shutdown(std::chrono::seconds(5));throw;}
  return 0;
}
