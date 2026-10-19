// Built without OWN_RT_HOST_ONLY. Only transport, weight bytes and observed
// priority are substituted. Production parser, plan, allocation ledger,
// resident lookup implementation, prepare and issue paths are real.
#define main unused_device_entry
#include "probe-main.cpp"
#undef main
#include "../frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/mock_device.hpp"
class ProbeBackend final : public ownrt::MockDevice, public ownrt::ForegroundPrefix {
  std::map<void*,size_t> backing, extents;
public:
  size_t captured=0,issued=0,copied=0,physical=0;
  bool foreground_prefix_complete() override {synchronize();return true;}
  void* allocate(size_t n,Memory memory) override {
    size_t bytes=(n<=32768||(memory==Memory::pinned&&n<=4*1024*1024))?n:256;void* ptr=nullptr;
    ptr=mmap(nullptr,n,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_NORESERVE,-1,0);
    require(ptr!=MAP_FAILED,"probe virtual extent");extents[ptr]=n;
    backing[ptr]=bytes;physical+=bytes;require(physical<1024ull*1024*1024,"probe backend RAM bound");return ptr;
  }
  void release(void* p,Memory) override {physical-=backing.at(p);backing.erase(p);require(munmap(p,extents.at(p))==0,"probe unmap");extents.erase(p);}
  ownrt::Event copy(void* d,const void* s,size_t n,std::span<const ownrt::Event> deps) override {
    // Opaque large weight/cache storage is never read or written. Real small
    // controls, lookup staging and request state copies preserve their bytes.
    auto fits=[&](const void* p){for(auto [base,bytes]:backing){auto off=uintptr_t(p)-uintptr_t(base);if(off<=bytes&&n<=bytes-off)return true;}return false;};
    if(fits(d)&&fits(s))std::memcpy(d,s,n);
    ++copied;return marker(deps);
  }
  ownrt::Event compute(const ownrt::Operation&,std::span<void*const>,std::span<const ownrt::Event> deps) override {++issued;return marker(deps);}
  std::function<ownrt::Event()> prepare(const ownrt::Operation&,std::span<void*const>) override {++captured;return [this]{++issued;return marker({});};}
};
static ProbeBackend* transport=nullptr;
namespace ownrt {
std::unique_ptr<Backend> make_sycl_device(size_t,bool){auto p=std::make_unique<ProbeBackend>();transport=p.get();return p;}
std::vector<std::string> enumerate_sycl_cards(){throw std::logic_error("CPU probe forbids device enumeration");}
}
int main(int argc,char**argv) {
  std::unique_ptr<Engine> engine;
  try {
    Options a=parse(argc,argv); // Unchanged argv, including authorization, dimensions and lookups.
    require(!a.mini&&a.resident_lookups&&a.wait_seconds==600,"real resident WSCREEN argv required");
    const char* output=std::getenv("ENTRY_PREPARE_OUTPUT");require(output,"probe output required");a.output=output;
    fs::create_directories(a.output);
    Options fixture;fixture.mini=true;Weights weights(fixture);
    weights.directory=flash::directory_from_loader(iq3::read_plan(a.plan));
    packet26::dispatch.load(a.dispatch);
    auto production=plan(weights,a);
    engine=std::make_unique<Engine>(weights,a,production);engine->allocation_probe=true;
    engine->initialize();
    // Preserve both packed row widths. Bound PLE's row count to the synthetic
    // metadata's 16*17 IDs; retain the complete embedding vocabulary.
    for(const char* key:{"token_embd.weight","per_layer_token_embd.weight"}) {
      auto& t=weights.directory.at(key);
      if(std::string(key)=="per_layer_token_embd.weight") {auto rb=t.bytes/t.shape[0];t.shape[0]=272;t.bytes=272*rb;}
      weights.synthetic[key].resize(t.bytes,0);
    }
    weights.load_resident_lookups();weights.use_resident_lookups=true;
    engine->prepare_plan();engine->prepare_commands();
    size_t sites=0,resets=0;
    const auto root=a.output;
    for(const auto& view:bracket_table(a)) {
      fs::create_directories(root/view.label);record_host_memory(root/view.label,"before_view_reset");
      p58as::spin_enabled=view.hc=="spin";
      engine->bracket_select(view.selection,view.digest,"p60fusion","hc-wide","wide64+halfcache","fused","ordered-foreground");
      engine->cache_mode(view.maintenance);engine->cache_capacity(view.capacity);record_host_memory(root/view.label,"after_view_reset");

      for(int request=0;request<12;++request) {
        auto destination=root/view.label/std::to_string(request);
        p58_reset_request(*engine,destination);++resets;
        engine->request_diagnostics=destination;
        int token=-1;std::ifstream input(a.inputs);input>>token;require(token>=0,"real prompt token");
        engine->cache_begin_position();engine->put(0,"token",&token,4);
        engine->prepare_token(token);
        for(const auto& l:engine->p.launches){auto& site=engine->issue_sites[&l-engine->p.launches.data()];if(!site.prefill_skip){engine->enqueue(l,engine->logical);++sites;}}
        engine->drain();engine->cache_after_position();
        engine->publish_cache_table(engine->expert_cache->table());engine->drain();
      }
    }
    require(resets==60||resets==12,"complete real arm/reset sequence");
    require(transport->captured>1000&&transport->issued>1000&&sites>1000,"full production preparation coverage");
    int token=-1;std::ifstream input(a.inputs);input>>token;
    a.output=root;
    auto result="{\"passed\":true,\"device_executed\":false,\"device_defines\":true,\"model_reads\":false,\"resident\":true,\"first_prompt_token\":"+std::to_string(token)+",\"prepared\":"+std::to_string(transport->captured)+",\"issued\":"+std::to_string(transport->issued)+",\"sites\":"+std::to_string(sites)+",\"backend_bytes\":"+std::to_string(transport->physical)+",\"synthetic_weights\":true,\"driver_stall_tested\":false}\n";
    engine->shutdown();engine.reset();
    save(fs::path(output)/"preparation.json",result);
    std::cout<<"PASS CPU device-branch resident preparation and first prefill\n";return 0;
  }catch(const std::exception& error){std::cerr<<error.what()<<'\n';if(engine)engine->shutdown();return 1;}
}
