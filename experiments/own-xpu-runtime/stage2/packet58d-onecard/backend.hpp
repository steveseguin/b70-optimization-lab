#pragma once
#include "owner.hpp"
#include "sycl_operation.hpp"
#include "prepared_submission.hpp"
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <level_zero/ze_api.h>
#include <mutex>
#include <sstream>
#include <thread>
#include <algorithm>

namespace tp2 {
// Shared native context and pointer registry; one Device/Arena owns both queues
// and their global dependency chain. No remote polling, atomics or imported leases.
class Context final : public ownrt::Backend {
  ze_context_handle_t native=nullptr;
  std::unique_ptr<sycl::context> context;
  std::array<std::unique_ptr<sycl::queue>,2> queues;
  using Tracked=ownrt::NativeTracked;
  std::vector<Tracked> events;
  Tracked& tracked(ownrt::Event e) {
    auto it=std::lower_bound(events.begin(),events.end(),e,[](const Tracked& t,ownrt::Event v){return t.handle<v;});
    if(it==events.end() || it->handle!=e)throw std::invalid_argument("retired/foreign native event");
    return *it;
  }
  bool profiling=false;

  // Conservative containment until cross-card native event residency has its
  // own small device qualification. Host completion preserves the DAG order.
  uint64_t cross_card_fences=0;
  struct Location {int card; size_t bytes;};
  std::map<void*,Location> locations;
  int location(const void* ptr,size_t bytes)const {
    auto address=reinterpret_cast<uintptr_t>(ptr);
    auto it=locations.upper_bound(const_cast<void*>(ptr));
    if(it!=locations.begin()) {
      --it;auto lo=reinterpret_cast<uintptr_t>(it->first);const auto& l=it->second;
      if(address>=lo && address-lo<=l.bytes && bytes<=l.bytes-(address-lo))return l.card;
    }
    throw std::invalid_argument("copy outside shared-context allocation");
  }
  std::mutex mutex;
  std::exception_ptr error;
  std::string label;
  void check() { std::lock_guard lock(mutex); if(error) std::rethrow_exception(error); }
  const std::vector<sycl::event>& dependencies(std::span<const ownrt::Event> deps,int target) {
    // In-order queues already serialize every earlier submission. Still reject
    // foreign-card fences: Engine must drain/retire on every card transition.
    for(auto e:deps)if(tracked(e).card!=target)
      throw std::logic_error("foreign-queue native dependency rejected");
    static const std::vector<sycl::event> empty;
    return empty;
  }

 public:
  // W0 only: materialize the executable bundle before starting work/wait clocks.
  auto canary_bundle() {
    return sycl::get_kernel_bundle<sycl::bundle_state::executable>(*context,
        std::vector<sycl::device>{queues[0]->get_device(),queues[1]->get_device()});
  }
  bool access_ab=false,access_ba=false;
  int allocation_card=0;
  Context(int a,int b,bool profile=true) : profiling(profile) {
    events.reserve(16384);
    std::vector<sycl::device> cards;
    for(auto p:sycl::platform::get_platforms())
      if(p.get_backend()==sycl::backend::ext_oneapi_level_zero)
        for(auto d:p.get_devices(sycl::info::device_type::gpu))cards.push_back(d);
    if(a<0 || b<0 || a==b || std::size_t(std::max(a,b))>=cards.size())
      throw std::invalid_argument("distinct physical Level Zero indices required");
    auto da=cards[a],db=cards[b];
    if(da.get_platform()!=db.get_platform())throw std::runtime_error("different Level Zero drivers");
    auto na=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(da);
    auto nb=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(db);
    ze_bool_t ab=0,ba=0;
    if(zeDeviceCanAccessPeer(na,nb,&ab)!=ZE_RESULT_SUCCESS ||
       zeDeviceCanAccessPeer(nb,na,&ba)!=ZE_RESULT_SUCCESS)
      throw std::runtime_error("peer query failed; no retry/fallback after error");
    access_ab=ab;access_ba=ba;
    if(!ab || !ba)throw std::runtime_error("TP2 requires peer access both ways; no fallback");
    std::ostringstream id;id<<"LevelZero shared-context queues";
    for(auto index:{a,b}) {
      auto d=cards[index];ze_device_properties_t props{};props.stype=ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES;
      if(zeDeviceGetProperties(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(d),&props)!=ZE_RESULT_SUCCESS)
        throw std::runtime_error("device identity query failed");
      id<<";card="<<index<<":"<<d.get_info<sycl::info::device::name>()
        <<":driver="<<d.get_info<sycl::info::device::driver_version>()<<":uuid=";
      for(auto v:props.uuid.id) {const char* hex="0123456789abcdef";id<<hex[v>>4]<<hex[v&15];}
    }
    label=id.str();
    auto handler=[this](sycl::exception_list errors){std::lock_guard lock(mutex);if(!error&&errors.size())error=*errors.begin();};
    ze_context_desc_t desc{};desc.stype=ZE_STRUCTURE_TYPE_CONTEXT_DESC;
    auto driver=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(da.get_platform());
    if(zeContextCreate(driver,&desc,&native)!=ZE_RESULT_SUCCESS)throw std::runtime_error("context create failed");
    try {
      context=std::make_unique<sycl::context>(sycl::make_context<sycl::backend::ext_oneapi_level_zero>(
          {native,{da,db},sycl::ext::oneapi::level_zero::ownership::keep},handler));
      for(int i=0;i<2;++i)queues[i]=std::make_unique<sycl::queue>(*context,i?db:da,handler,
          profiling?sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}}:
                    sycl::property_list{sycl::property::queue::in_order{}});
    } catch(...) {queues={};context.reset();zeContextDestroy(native);native=nullptr;throw;}
  }
  ~Context() override {
    if(native && events.empty() && locations.empty()) {
      // Constructor/admission failure before any allocation, or a partial
      // pair whose existing owner drained. No outstanding lease may disappear.
      try {synchronize();close_queue();close_context();}catch(...){ownrt::hold_for_supervisor();}
    }
    if(native||context||queues[0]||queues[1])ownrt::hold_for_supervisor();
  }
  std::string identity() const override {return label;}
  void* allocate(std::size_t n,ownrt::Memory m) override {
    check();if(allocation_card<0||allocation_card>1)throw std::logic_error("allocation card");
    auto p=m==ownrt::Memory::device?sycl::malloc_device(n,*queues[allocation_card]):
           m==ownrt::Memory::pinned?sycl::malloc_host(n,*context) : ::operator new(n);
    if(p)locations.emplace(p,Location{m==ownrt::Memory::device?allocation_card:-1,n});return p;
  }
  void release(void* p,ownrt::Memory m) override {
    if(m==ownrt::Memory::shadow)::operator delete(p);else sycl::free(p,*context);locations.erase(p);
  }
  ownrt::Event copy(void* dst,const void* src,std::size_t n,std::span<const ownrt::Event> deps) override {
    check();int d=location(dst,n),s=location(src,n);
    if(d>=0&&s>=0&&d!=s&&!(access_ab&&access_ba))throw std::logic_error("peer path without bidirectional access");
    int target=d>=0?d:s>=0?s:0;
    dependencies(deps,target);auto e=ownrt::next_handle();
    events.push_back({e,queues[target]->submit([&](sycl::handler& h){h.memcpy(dst,src,n);}),target});return e;
  }
  ownrt::Event compute(const ownrt::Operation& base,std::span<void* const> p,std::span<const ownrt::Event> deps) override {
    check();const auto& op=dynamic_cast<const ownrt::SyclOperation&>(base);
    // Device validates card ownership once per immutable binding set; releases
    // invalidate that cache. No bypass submission API is exposed by Engine.
    const auto& wait=dependencies(deps,allocation_card);auto e=ownrt::next_handle();
    events.push_back({e,op.submit(*queues[allocation_card],p,wait),allocation_card});return e;
  }

  std::function<ownrt::Event()> prepare_copy(void* dst,const void* src,size_t n) override {
    check();const int d=location(dst,n),s=location(src,n);
    if(d>=0&&s>=0&&d!=s&&!(access_ab&&access_ba))throw std::logic_error("prepared peer copy without access");
    const int target=d>=0?d:s>=0?s:0;
    auto* q=queues[target].get();
    return [this,q,dst,src,n,target] {
      check();
      if(events.size()>=events.capacity())throw std::length_error("native prepared copy event capacity");
      auto e=ownrt::next_handle();events.push_back({e,q->memcpy(dst,src,n),target});return e;
    };
  }

  std::function<ownrt::Event()> prepare(const ownrt::Operation& base,std::span<void* const> p) override {
    check();const auto& op=dynamic_cast<const ownrt::SyclOperation&>(base);
    const int card=allocation_card;
    if(card<0 || card>1)throw std::logic_error("prepared allocation card");
    std::unique_ptr<ownrt::PreparedSyclSubmission> captured;
    {ownrt::SubmissionCapture capture(captured);op.submit(*queues[card],p,{});}
    if(!captured)throw std::logic_error("native operation bypassed preparation");
    return captured->make_callback({&events,&mutex,&error,&allocation_card,card});
  }

  ownrt::Event marker(std::span<const ownrt::Event> deps) override {
    check();dependencies(deps,allocation_card);auto e=ownrt::next_handle();
    events.push_back({e,queues[allocation_card]->submit([&](sycl::handler& h){h.single_task([]{});}),allocation_card});return e;
  }
  bool complete(ownrt::Event e) override {check();return tracked(e).event.get_info<sycl::info::event::command_execution_status>()==sycl::info::event_command_status::complete;}
  bool wait(ownrt::Event e,ownrt::Deadline end) override {
    while(!complete(e)) {if(std::chrono::steady_clock::now()>=end)return false;std::this_thread::yield();}
    tracked(e).event.wait_and_throw();check();return true;
  }
  ownrt::EventTiming timing(ownrt::Event e) override {
    check();if(!profiling)throw std::logic_error("profiling disabled");try {return {tracked(e).event.get_profiling_info<sycl::info::event_profiling::command_start>(),
                        tracked(e).event.get_profiling_info<sycl::info::event_profiling::command_end>()};}
    catch(const sycl::exception& ex) {if(ex.code()!=sycl::errc::profiling)throw;return {0,0};}
  }
  void synchronize() override {for(auto& q:queues)q->wait_and_throw();check();}

  int closed_ranks=0;
  void clear_events() override {events.clear();}
  void close_queue() override {queues={};}
  void close_context() override {context.reset();if(zeContextDestroy(native)!=ZE_RESULT_SUCCESS)throw std::runtime_error("context destroy failed");native=nullptr;}
};

}
