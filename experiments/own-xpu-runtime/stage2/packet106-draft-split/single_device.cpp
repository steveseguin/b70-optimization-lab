#include "owner.hpp"
#include "ordered_queue.hpp"
#include "prepared_submission.hpp"
#include "sycl_operation.hpp"
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <level_zero/ze_api.h>
#include <mutex>
#include <set>
#include <stdexcept>
#include <thread>
#include "host_spin.hpp"
#include "p105_common.hpp"

namespace ownrt {
namespace {
std::mutex registry_mutex;
std::set<std::size_t> owned_cards;
std::vector<sycl::device> cards() {
  std::vector<sycl::device> out;
  for(const auto& p:sycl::platform::get_platforms())
    if(p.get_backend()==sycl::backend::ext_oneapi_level_zero)
      for(const auto& d:p.get_devices(sycl::info::device_type::gpu)) out.push_back(d);
  return out;
}
class SyclDevice final : public Backend, public OrderedQueue {
  std::size_t card_;
  std::string label_;
  ze_context_handle_t native_=nullptr;
  std::unique_ptr<sycl::context> context_;
  std::unique_ptr<sycl::queue> queue_,copy_queue_;
  ze_command_queue_handle_t native_copy_=nullptr;
  sycl::queue& copy_queue(){
    if(copy_queue_)return *copy_queue_;
    auto d=queue_->get_device();auto native_d=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(d);uint32_t n=0;
    if(zeDeviceGetCommandQueueGroupProperties(native_d,&n,nullptr)!=ZE_RESULT_SUCCESS)throw std::runtime_error("p105 BCS census failed");
    std::vector<ze_command_queue_group_properties_t> props(n);for(auto&x:props)x.stype=ZE_STRUCTURE_TYPE_COMMAND_QUEUE_GROUP_PROPERTIES;
    if(zeDeviceGetCommandQueueGroupProperties(native_d,&n,props.data())!=ZE_RESULT_SUCCESS)throw std::runtime_error("p105 BCS census failed");
    uint32_t ordinal=n;for(uint32_t i=0;i<n;++i)if((props[i].flags&ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COPY)&&!(props[i].flags&ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COMPUTE)&&props[i].numQueues){ordinal=i;break;}
    if(ordinal==n)throw std::runtime_error("p105 dedicated BCS unavailable; no silent fallback");
    ze_command_queue_desc_t desc{};desc.stype=ZE_STRUCTURE_TYPE_COMMAND_QUEUE_DESC;desc.ordinal=ordinal;desc.index=0;desc.mode=ZE_COMMAND_QUEUE_MODE_ASYNCHRONOUS;desc.priority=ZE_COMMAND_QUEUE_PRIORITY_NORMAL;
    if(zeCommandQueueCreate(native_,native_d,&desc,&native_copy_)!=ZE_RESULT_SUCCESS)throw std::runtime_error("p105 BCS create failed");
    try{copy_queue_=std::make_unique<sycl::queue>(sycl::make_queue<sycl::backend::ext_oneapi_level_zero>({native_copy_,d,sycl::ext::oneapi::level_zero::ownership::keep,sycl::property_list{sycl::property::queue::in_order{}}},*context_,[this](sycl::exception_list errors){std::lock_guard lock(error_mutex_);if(!error_&&errors.size())error_=*errors.begin();}));}
    catch(...){zeCommandQueueDestroy(native_copy_);native_copy_=nullptr;throw;}
    label_+=":p105-BCS-ordinal="+std::to_string(ordinal);return *copy_queue_;
  }
  std::vector<NativeTracked> events_;int allocation_card_=0;
  sycl::event& event(Event e){auto it=std::lower_bound(events_.begin(),events_.end(),e,[](const auto& v,Event h){return v.handle<h;});if(it==events_.end()||it->handle!=e)throw std::logic_error("foreign native event");return it->event;}
  void capacity(){if(events_.size()>=events_.capacity())throw std::length_error("native event capacity");}
  Event record(sycl::event e){auto id=next_handle();events_.push_back({id,std::move(e),0});return id;}
  std::mutex error_mutex_;
  std::exception_ptr error_;
  void check_error() { std::lock_guard lock(error_mutex_); if(error_) std::rethrow_exception(error_); }
  std::vector<sycl::event> dependencies(std::span<const Event> deps) {
    for(auto e:deps)(void)event(e); return {}; // Same in-order queue; validate ownership, omit redundant dependencies.
  }
 public:
  explicit SyclDevice(std::size_t card,bool profiling):card_(card) {
    events_.reserve(65536);
    std::lock_guard lock(registry_mutex);
    if(owned_cards.contains(card)) throw std::logic_error("card already has an owner");
    auto found=cards(); if(card>=found.size()) throw std::out_of_range("Level Zero GPU index");
    auto d=found[card];
    label_="LevelZero:"+std::to_string(card)+":"+d.get_info<sycl::info::device::name>();
    if(profiling) label_+=":driver="+d.get_info<sycl::info::device::driver_version>();
    auto handler=[this](sycl::exception_list errors) {
      std::lock_guard error_lock(error_mutex_);
      if(!error_ && errors.size()) error_=*errors.begin();
    };
    ze_context_desc_t desc{}; desc.stype=ZE_STRUCTURE_TYPE_CONTEXT_DESC;
    auto driver=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(d.get_platform());
    if(zeContextCreate(driver,&desc,&native_)!=ZE_RESULT_SUCCESS)
      throw std::runtime_error("zeContextCreate failed; no fallback context");
    try {
      // Intel SYCL Level Zero interop API, ownership::keep: we explicitly
      // release native context only AFTER SYCL event/queue/context wrappers.
      context_=std::make_unique<sycl::context>(sycl::make_context<sycl::backend::ext_oneapi_level_zero>(
        {native_,{d},sycl::ext::oneapi::level_zero::ownership::keep},handler));
      auto properties=profiling
        ? sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}}
        : sycl::property_list{sycl::property::queue::in_order{}};
      queue_=std::make_unique<sycl::queue>(*context_,d,handler,properties);
      owned_cards.insert(card);
    } catch(...) {queue_.reset(); context_.reset(); zeContextDestroy(native_); native_=nullptr; throw;}
  }
  ~SyclDevice() override {
    // Device must finish its protocol before allowing backend destruction.
    if(queue_ || context_ || native_) hold_for_supervisor();
  }
  std::string identity() const override {return label_;}
  void* allocate(std::size_t n,Memory m) override {
    check_error();
    if(m==Memory::shadow) return ::operator new(n);
    return m==Memory::device?sycl::malloc_device(n,*queue_):sycl::malloc_host(n,*queue_);
  }
  void release(void* p,Memory m) override {
    if(m==Memory::shadow) ::operator delete(p); else sycl::free(p,*context_);
  }
  Event copy(void* dst,const void* src,std::size_t n,std::span<const Event> deps) override {
    check_error();capacity();
    if(p105::copy_bcs){std::vector<sycl::event> waits;for(auto e:deps)waits.push_back(event(e));return record(copy_queue().memcpy(dst,src,n,waits));}
    dependencies(deps);return record(queue_->memcpy(dst,src,n));
  }
  Event marker(std::span<const Event> deps) override {
    check_error();capacity();dependencies(deps);return record(queue_->submit([&](sycl::handler& h){h.single_task<class IdleMarker>([]{});}));
  }
  Event compute(const Operation& op,std::span<void* const> bindings,std::span<const Event> deps) override {
    const auto& native=dynamic_cast<const SyclOperation&>(op);
    check_error();capacity();auto wait=dependencies(deps);return record(native.submit(*queue_,bindings,wait));
  }
  std::function<Event()> prepare(const Operation& op,std::span<void*const> p) override {
    check_error();const auto& native=dynamic_cast<const SyclOperation&>(op);
    std::unique_ptr<PreparedSyclSubmission> captured;
    {SubmissionCapture scope(captured);native.submit(*queue_,p,{});}
    if(!captured)throw std::logic_error("native operation bypassed preparation");
    return captured->make_callback({&events_,&error_mutex_,&error_,&allocation_card_,0});
  }
  std::function<Event()> prepare_copy(void* d,const void* s,size_t n) override {
    return [this,d,s,n]{check_error();capacity();return record(queue_->memcpy(d,s,n));};
  }
  EventTiming timing(Event e) override {
    check_error();
    if(!queue_->has_property<sycl::property::queue::enable_profiling>())
      throw std::logic_error("profiling disabled");
    return {event(e).get_profiling_info<sycl::info::event_profiling::command_start>(),
            event(e).get_profiling_info<sycl::info::event_profiling::command_end>()};
  }
  bool ordered_prefix_complete(Event e) override {
    check_error();
    if(!queue_->has_property<sycl::property::queue::in_order>())throw std::logic_error("ordered retirement requires in-order queue");
    return complete(e);
  }
  bool complete(Event e) override {
    return event(e).get_info<sycl::info::event::command_execution_status>()==sycl::info::event_command_status::complete;
  }
  bool wait(Event e,Deadline deadline) override {
    if(!p56x::wait([&]{return complete(e);},[&]{check_error();},deadline)) return false;
    event(e).wait_and_throw(); check_error(); return true;
  }
  void synchronize() override {queue_->wait_and_throw();if(copy_queue_)copy_queue_->wait_and_throw();check_error();}
  void clear_events() override {events_.clear();}
  void close_queue() override {copy_queue_.reset();if(native_copy_){if(zeCommandQueueDestroy(native_copy_)!=ZE_RESULT_SUCCESS)throw std::runtime_error("p105 BCS destroy failed");native_copy_=nullptr;}queue_.reset();}
  void close_context() override {
    context_.reset();
    if(native_ && zeContextDestroy(native_)!=ZE_RESULT_SUCCESS) throw std::runtime_error("zeContextDestroy failed");
    native_=nullptr; std::lock_guard lock(registry_mutex); owned_cards.erase(card_);
  }
};
}
std::unique_ptr<Backend> make_sycl_device(std::size_t card,bool profiling) {return std::make_unique<SyclDevice>(card,profiling);}
std::vector<std::string> enumerate_sycl_cards() {
  std::vector<std::string> names;
  for(const auto& d:cards()) names.push_back(d.get_info<sycl::info::device::name>());
  return names;
}
}
