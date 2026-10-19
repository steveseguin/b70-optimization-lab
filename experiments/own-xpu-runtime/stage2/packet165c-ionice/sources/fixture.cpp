// Built without OWN_RT_HOST_ONLY. Only transport, weight bytes and observed
// priority are substituted. Production parser, plan, allocation ledger,
// resident lookup implementation, prepare and issue paths are real.
#define main unused_device_entry
#include "probe-main.cpp"
#undef main
#include "mock_device.hpp"
class ProbeBackend final : public ownrt::MockDevice, public ownrt::ForegroundPrefix, public p58v::AsyncBackend {
  std::map<void*,size_t> backing, extents;
public:
  size_t captured=0,issued=0,copied=0,physical=0;
  ownrt::Event fill(void* d,const void* s,size_t n) override {return copy(d,s,n,{});}
  bool fill_complete(ownrt::Event) override {return true;}
  size_t fills_pending() override {return 0;}
  void finish_fills() override {}
  void foreground_sync() override {synchronize();}
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
    auto available=[&](const void* p){for(auto [base,extent]:extents){auto off=uintptr_t(p)-uintptr_t(base);if(off<extent){auto bytes=backing.at(base);return off<bytes?bytes-off:size_t(0);}}return n;};
    const auto clipped=std::min(n,std::min(available(d),available(s)));if(clipped)std::memcpy(d,s,clipped);
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
#include "native_sequence_helpers.hpp"
int main(int argc,char**argv) {
 std::unique_ptr<Engine> engine;
 try {
  auto a=parse(argc,argv);require(!a.mini&&a.resident_lookups,"real resident argv");
  a.output=std::getenv("ENTRY_PREPARE_OUTPUT");const auto root=a.output;fs::create_directories(root);
  Options fixture;fixture.mini=true;Weights weights(fixture);
  weights.directory=flash::directory_from_loader(iq3::read_plan(a.plan));packet26::dispatch.load(a.dispatch);
  engine=std::make_unique<Engine>(weights,a,plan(weights,a));auto& e=*engine;
  e.allocation_probe=true;e.initialize();
  for(const char* key:{"token_embd.weight","per_layer_token_embd.weight"}) {
   auto& t=weights.directory.at(key);
   if(std::string(key)=="per_layer_token_embd.weight"){auto rb=t.bytes/t.shape[0];t.shape[0]=272;t.bytes=272*rb;}
   weights.synthetic[key].resize(t.bytes,0);
  }
  weights.load_resident_lookups();weights.use_resident_lookups=true;e.prepare_plan();e.prepare_commands();
  const auto before=identities(e);size_t total=0;
  for(const auto& id:sequence_ids()) {
   auto dest=root/id;auto poisoned=poison_samples(e);p58_reset_request(e,dest);
   require(reset_samples(e)==poisoned,"mutable sample coverage");identity_check(e,before);total+=poisoned;sensors(e,id);
   if(id!="after-suite") {
    int token=2;e.request_diagnostics=dest;e.checkpoint("prefill-start");
    e.cache_begin_position();e.put(0,"token",&token,4);e.prepare_token(token);
    for(const auto& launch:e.p.launches)e.enqueue(launch,e.logical);
    e.cache_plan_during_position();e.drain();e.cache_after_position();
    e.checkpoint("first-prefill-complete");
   }
  }
  bool refused=false;e.poisoned=true;
  try{p58_reset_request(e,root/"not-opened");}catch(const std::exception&){refused=true;}
  require(refused,"poisoned target reset accepted");e.poisoned=false;
  require(transport->captured>1000&&transport->issued>1000,"production preparation coverage");
  e.shutdown();engine.reset();std::cout<<"PASS native sequence requests=13 target_resets=14 mutable_samples="<<total<<"\n";return 0;
 }catch(const std::exception& error){std::cerr<<error.what()<<'\n';if(engine)engine->shutdown();return 1;}
}
