#include <sys/mman.h>
// All methods below replace transport/storage boundaries only. The parser,
// Engine initialization, real-shape bindings and prepared issue path are shared.
class DemandProbe final:public ownrt::Backend,public p58v::AsyncBackend,public ownrt::ForegroundPrefix,public p58am::Backend {
 std::map<void*,size_t> allocations;std::set<uint64_t> events,demand;
public:
 size_t captured=0,issued=0,logical_bytes=0;uint64_t fill_ticket=0;
 std::string identity()const override{return "CPU-sparse-demand-probe:no-device";}
 void* allocate(size_t n,Memory)override{auto*p=mmap(nullptr,n,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_NORESERVE,-1,0);require(p!=MAP_FAILED,"probe sparse allocation");allocations[p]=n;logical_bytes+=n;return p;}
 void release(void*p,Memory)override{require(munmap(p,allocations.at(p))==0,"probe release");allocations.erase(p);}
 uint64_t marker(std::span<const uint64_t> deps)override{for(auto e:deps)require(events.count(e),"probe foreign foreground event");auto e=ownrt::next_handle();events.insert(e);return e;}
 uint64_t copy(void*d,const void*s,size_t n,std::span<const uint64_t> deps)override{if(n<=32768)std::memcpy(d,s,n);return marker(deps);}
 uint64_t compute(const ownrt::Operation&,std::span<void*const>,std::span<const uint64_t> deps)override{++issued;return marker(deps);}
 std::function<uint64_t()> prepare(const ownrt::Operation&,std::span<void*const>)override{++captured;return [this]{++issued;return marker({});};}
 std::function<uint64_t()> prepare_copy(void*d,const void*s,size_t n)override{return [=,this]{return copy(d,s,n,{});};}
 bool complete(uint64_t e)override{require(events.count(e),"probe retired/foreign foreground");return true;}
 bool wait(uint64_t e,ownrt::Deadline)override{return complete(e);}
 ownrt::EventTiming timing(uint64_t)override{throw std::logic_error("probe has no device timestamps");}
 void synchronize()override{}
 bool foreground_prefix_complete()override{return true;}
 void foreground_sync()override{}
 void clear_events()override{events.clear();demand.clear();}
 void close_queue()override{require(allocations.empty(),"probe queue owns allocations");}
 void close_context()override{}
 uint64_t fill(void*,const void*,size_t)override{return fill_ticket=ownrt::next_handle();}
 bool fill_complete(uint64_t e)override{require(e==fill_ticket,"probe foreign fill");return true;}
 size_t fills_pending()override{return 0;}
 void finish_fills()override{}
 uint64_t demand_copy(void*d,const void*s,size_t n,uint64_t producer)override{if(producer)require(events.count(producer),"probe cross-queue producer");if(n<=sizeof(p58am::Map))std::memcpy(d,s,n);auto e=ownrt::next_handle();demand.insert(e);return e;}
 bool demand_complete(uint64_t e)override{require(demand.count(e),"probe foreign demand");return true;}
 void demand_barrier(uint64_t e)override{require(demand.count(e),"probe cross-queue consumer");}
 void demand_drain()override{}
 size_t demand_pending()override{return 0;}
 void demand_retire()override{demand.clear();}
 std::array<uint64_t,2> demand_timing(uint64_t)override{throw std::logic_error("CPU probe has no device timestamps");}
};
static int preparation_probe(Options a){
 require(!a.mini&&a.context==4096&&a.hc=="p60fusion"&&a.hc_geometry=="hc-wide"&&a.experts=="wide64+halfcache"&&a.other_fusion=="fused"&&a.retirement=="ordered-foreground","probe real composition");
 require(!fs::exists(a.output),"probe output must be fresh");fs::create_directories(a.output);
 if(!a.dispatch.empty())packet26::dispatch.load(a.dispatch);
 const auto views=bracket_table(a);
 Options synthetic;synthetic.mini=true;Weights weights(synthetic);
 weights.directory=flash::directory_from_loader(iq3::read_plan(a.plan));
 Engine e(weights,a,plan(weights,a));e.allocation_probe=true;
 auto backend=std::make_unique<DemandProbe>();auto* observed=backend.get();e.devices.push_back(std::make_unique<ownrt::Device>(std::move(backend)));
 try {
  e.initialize();e.prepare_plan();e.prepare_commands();const auto arena=e.bracket_arena_hash();
  size_t hooks=0,sites=0;
  for(const auto&view:views){
   e.cache_quiesce();e.bracket_select(view.selection,view.digest,"p60fusion");e.cache_capacity("max");
   e.a.demand=(view.label=="B0"||view.label=="B1"||view.label=="S1")?"bcs-demand-retained32x2":"off";
   p58_reset_request(e,a.output/(view.label.empty()?"single":view.label));
   for(int parity=0;parity<2;++parity){
    // Rebuild with actual parity-bank pointer bindings, rather than mutating
    // captured argument blocks. No model bytes are materialized.
    if(parity)e.swap_state_banks();e.prepare_plan();e.prepare_commands();e.cache_begin_position();
    for(unsigned layer=0;layer<48;++layer){auto&x=e.demand_layers[layer];auto*desc=static_cast<p58am::Map*>(e.demand_pointer(x.descriptor));*desc={};
     for(unsigned slot=0;slot<10;++slot){auto&s=desc->slots[slot];s.valid=1;s.expert=slot;s.resident=slot%2==0;s.generation=1;}
    }
    for(const auto& launch:e.p.launches){e.enqueue(launch,e.logical);++sites;if(launch.op=="expert_gate_up")++hooks;}
    e.drain();e.demand_consumed();e.maintenance.end(true);
    e.demand_pool.discard(e.maintenance_position);
    if(parity)e.swap_state_banks();
   }
   require(arena==e.bracket_arena_hash(),"probe changed allocation identities");
  }
  save(a.output/"allocation-census.json",e.dev(0).arena.census());
  auto prepared=observed->captured,issued=observed->issued,logical=observed->logical_bytes;e.shutdown();
  require(hooks==views.size()*96&&issued>1000,"probe all router hooks/both parity banks");
  save(a.output/"preparation.json","{\"passed\":true,\"device_executed\":false,\"gpu_enumeration\":false,\"model_reads\":false,\"real_parser\":true,\"real_prepare\":true,\"first_decode\":true,\"mock_transport_storage_and_kernel_execution\":true,\"views\":"+std::to_string(views.size())+",\"router_hooks\":"+std::to_string(hooks)+",\"sites\":"+std::to_string(sites)+",\"prepared\":"+std::to_string(prepared)+",\"issued\":"+std::to_string(issued)+",\"logical_bytes\":"+std::to_string(logical)+"}\n");
  return 0;
 }catch(...){e.shutdown();throw;}
}
