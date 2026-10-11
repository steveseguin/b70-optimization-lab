#pragma once
#include "exchange.hpp"
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <level_zero/ze_api.h>
#include <mutex>
#include <sstream>
#include <thread>

namespace peer {
// Packet-local backend; the unchanged Device/Arena/CopyEngine owner manages
// the union of both queues. No remote polling, atomics, IPC or imported leases.
class Backend final : public ownrt::Backend {
  ze_context_handle_t native=nullptr;
  std::unique_ptr<sycl::context> context;
  std::array<std::unique_ptr<sycl::queue>,2> queues;
  std::map<ownrt::Event,sycl::event> events;
  std::map<void*,int> locations;
  std::mutex mutex;
  std::exception_ptr error;
  std::string label;
  void check() { std::lock_guard lock(mutex); if(error) std::rethrow_exception(error); }
  std::vector<sycl::event> dependencies(std::span<const ownrt::Event> deps) {
    std::vector<sycl::event> r;for(auto e:deps)r.push_back(events.at(e));return r;
  }
 public:
  bool access_ab=false,access_ba=false;
  int allocation_card=0;
  Backend(int a,int b) {
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
          sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});
    } catch(...) {queues={};context.reset();zeContextDestroy(native);native=nullptr;throw;}
  }
  ~Backend() override {if(native||context||queues[0]||queues[1])ownrt::hold_for_supervisor();}
  std::string identity() const override {return label;}
  void* allocate(std::size_t n,ownrt::Memory m) override {
    check();if(allocation_card<0||allocation_card>1)throw std::logic_error("allocation card");
    auto p=m==ownrt::Memory::device?sycl::malloc_device(n,*queues[allocation_card]):
           m==ownrt::Memory::pinned?sycl::malloc_host(n,*context) : ::operator new(n);
    if(p)locations.emplace(p,m==ownrt::Memory::device?allocation_card:-1);return p;
  }
  void release(void* p,ownrt::Memory m) override {
    if(m==ownrt::Memory::shadow)::operator delete(p);else sycl::free(p,*context);locations.erase(p);
  }
  ownrt::Event copy(void* dst,const void* src,std::size_t n,std::span<const ownrt::Event> deps) override {
    check();int d=locations.at(dst),s=locations.at(const_cast<void*>(src));
    if(d>=0&&s>=0&&d!=s&&!(access_ab&&access_ba))throw std::logic_error("peer path without bidirectional access");
    auto wait=dependencies(deps);auto e=ownrt::next_handle();auto [it,ok]=events.try_emplace(e);(void)ok;
    it->second=queues[d>=0?d:s>=0?s:0]->submit([&](sycl::handler& h){h.depends_on(wait);h.memcpy(dst,src,n);});return e;
  }
  ownrt::Event compute(const ownrt::Operation& base,std::span<void* const> p,std::span<const ownrt::Event> deps) override {
    check();auto op=dynamic_cast<const Combine&>(base);
    if(p.size()!=3||locations.at(p[0])!=0||locations.at(p[1])!=0||locations.at(p[2])!=0)
      throw std::logic_error("combine requires three A allocations");
    auto a=static_cast<const float*>(p[0]),b=static_cast<const float*>(p[1]);auto out=static_cast<float*>(p[2]);
    auto wait=dependencies(deps);auto e=ownrt::next_handle();auto [it,ok]=events.try_emplace(e);(void)ok;
    it->second=queues[0]->submit([&](sycl::handler& h){h.depends_on(wait);
      h.parallel_for(sycl::range<1>(op.count),[=](sycl::id<1> i){out[i]=a[i]+b[i];});});return e;
  }
  ownrt::Event marker(std::span<const ownrt::Event> deps) override {
    check();auto wait=dependencies(deps);auto e=ownrt::next_handle();auto [it,ok]=events.try_emplace(e);(void)ok;
    it->second=queues[0]->submit([&](sycl::handler& h){h.depends_on(wait);h.single_task([]{});});return e;
  }
  bool complete(ownrt::Event e) override {check();return events.at(e).get_info<sycl::info::event::command_execution_status>()==sycl::info::event_command_status::complete;}
  bool wait(ownrt::Event e,ownrt::Deadline end) override {
    while(!complete(e)) {if(std::chrono::steady_clock::now()>=end)return false;std::this_thread::yield();}
    events.at(e).wait_and_throw();check();return true;
  }
  ownrt::EventTiming timing(ownrt::Event e) override {
    check();try {return {events.at(e).get_profiling_info<sycl::info::event_profiling::command_start>(),
                        events.at(e).get_profiling_info<sycl::info::event_profiling::command_end>()};}
    catch(const sycl::exception& ex) {if(ex.code()!=sycl::errc::profiling)throw;return {0,0};}
  }
  void synchronize() override {for(auto& q:queues)q->wait_and_throw();check();}
  void clear_events() override {events.clear();}
  void close_queue() override {queues={};}
  void close_context() override {context.reset();if(zeContextDestroy(native)!=ZE_RESULT_SUCCESS)throw std::runtime_error("context destroy failed");native=nullptr;}
};
}
