#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/native/ordered_retirement.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/native/async_backend.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/single_device.cpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/owner.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/prepared_submission.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <level_zero/ze_api.h>
#include <mutex>
#include <set>
#include <stdexcept>
#include <thread>

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
class SyclDevice final : public Backend, public p58v::AsyncBackend, public ForegroundPrefix {
  ForegroundTails foreground_tails_;
  std::unique_ptr<sycl::queue> maintenance_queue_;
  ze_command_list_handle_t maintenance_native_=nullptr;
  sycl::event fill_tail_;Event fill_ticket_=0;
  std::size_t card_;
  std::string label_;
  ze_context_handle_t native_=nullptr;
  std::unique_ptr<sycl::context> context_;
  std::unique_ptr<sycl::queue> queue_,copy_queue_;
  ze_command_list_handle_t native_copy_=nullptr;
  std::vector<NativeTracked> events_;int allocation_card_=0;
  sycl::event& event(Event e){auto it=std::lower_bound(events_.begin(),events_.end(),e,[](const auto& v,Event h){return v.handle<h;});if(it==events_.end()||it->handle!=e)throw std::logic_error("foreign native event");return it->event;}
  void capacity(){if(events_.size()>=events_.capacity())throw std::length_error("native event capacity");}
  Event record(sycl::event e,bool copy=false){auto id=next_handle();events_.push_back({id,std::move(e),0});foreground_tails_.record(id,copy);return id;}
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
    if(d.get_info<sycl::info::device::global_mem_size>()<26409219600ull+1500000000ull)throw std::runtime_error("device capacity cannot preserve admitted1.5GB reserve");
    if(!d.has(sycl::aspect::usm_host_allocations))throw std::runtime_error("USM host allocations not supported: zero-copy unavailable");
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
      auto native_device=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(d);
      uint32_t n=0;if(zeDeviceGetCommandQueueGroupProperties(native_device,&n,nullptr)!=ZE_RESULT_SUCCESS)throw std::runtime_error("copy engine query failed");
      std::vector<ze_command_queue_group_properties_t> groups(n);for(auto& g:groups)g.stype=ZE_STRUCTURE_TYPE_COMMAND_QUEUE_GROUP_PROPERTIES;
      if(zeDeviceGetCommandQueueGroupProperties(native_device,&n,groups.data())!=ZE_RESULT_SUCCESS)throw std::runtime_error("copy engine groups failed");
      uint32_t ordinal=~0u;for(uint32_t i=0;i<n;++i)if((groups[i].flags&ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COPY)&&!(groups[i].flags&ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COMPUTE)&&groups[i].numQueues){ordinal=i;break;}
      if(ordinal==~0u)throw std::runtime_error("dedicated copy engine required");
      ze_command_queue_desc_t cd{};cd.stype=ZE_STRUCTURE_TYPE_COMMAND_QUEUE_DESC;cd.ordinal=ordinal;cd.mode=ZE_COMMAND_QUEUE_MODE_ASYNCHRONOUS;cd.flags=ZE_COMMAND_QUEUE_FLAG_IN_ORDER;
      if(zeCommandListCreateImmediate(native_,native_device,&cd,&native_copy_)!=ZE_RESULT_SUCCESS)throw std::runtime_error("copy immediate command list creation failed");
      // UR Level Zero v2 imports immediate command lists only (regular queues return 44).
      copy_queue_=std::make_unique<sycl::queue>(sycl::make_queue<sycl::backend::ext_oneapi_level_zero>({native_copy_,d,sycl::ext::oneapi::level_zero::ownership::keep,properties},*context_,handler));
      label_+=":copy-only-ordinal="+std::to_string(ordinal);
      if(zeCommandListCreateImmediate(native_,native_device,&cd,&maintenance_native_)!=ZE_RESULT_SUCCESS)
        throw std::runtime_error("maintenance BCS immediate list failed");
      maintenance_queue_=std::make_unique<sycl::queue>(sycl::make_queue<sycl::backend::ext_oneapi_level_zero>(
        {maintenance_native_,d,sycl::ext::oneapi::level_zero::ownership::keep,properties},*context_,handler));
      owned_cards.insert(card);
    } catch(...) {maintenance_queue_.reset();if(maintenance_native_)zeCommandListDestroy(maintenance_native_);maintenance_native_=nullptr;copy_queue_.reset();if(native_copy_)zeCommandListDestroy(native_copy_);native_copy_=nullptr;queue_.reset(); context_.reset(); zeContextDestroy(native_); native_=nullptr; throw;}
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
    check_error();capacity();std::vector<sycl::event> after;for(auto e:deps)after.push_back(event(e));
    auto copied=copy_queue_->memcpy(dst,src,n,after);
    // The compute queue must observe copy completion even for prepared kernels.
    // The returned owned copy event also protects pinned-source lifetime.
    try {queue_->ext_oneapi_submit_barrier({copied});return record(copied,true);}
    catch(...) {
      // DMA was submitted before the dependency barrier failed. It is not yet
      // in Device's event ledger: prove completion before rethrowing, otherwise
      // retain this owner and both allocations for the coordinator.
      auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(60);
      try {while(copied.get_info<sycl::info::event::command_execution_status>()!=sycl::info::event_command_status::complete){
        if(std::chrono::steady_clock::now()>=deadline)hold_for_supervisor();std::this_thread::sleep_for(std::chrono::milliseconds(1));
      }copied.wait();}catch(...){hold_for_supervisor();}
      throw;
    }
  }
  Event marker(std::span<const Event> deps) override {
    check_error();capacity();dependencies(deps);return record(queue_->submit([&](sycl::handler& h){h.single_task<class IdleMarker>(packet26::checked([]{}));}));
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
    auto issue=captured->make_callback({&events_,&error_mutex_,&error_,&allocation_card_,0});
    return [this,issue=std::move(issue)]()mutable{auto event=issue();foreground_tails_.record(event);return event;};
  }
  std::function<Event()> prepare_copy(void* d,const void* s,size_t n) override {
    return [this,d,s,n]{std::vector<Event> deps;if(!events_.empty())deps.push_back(events_.back().handle);return copy(d,s,n,deps);};
  }
  EventTiming timing(Event e) override {
    check_error();
    if(!queue_->has_property<sycl::property::queue::enable_profiling>())
      throw std::logic_error("profiling disabled");
    return {event(e).get_profiling_info<sycl::info::event_profiling::command_start>(),
            event(e).get_profiling_info<sycl::info::event_profiling::command_end>()};
  }
  bool foreground_prefix_complete() override {
    check_error();
    if(!queue_->has_property<sycl::property::queue::in_order>()||!copy_queue_->has_property<sycl::property::queue::in_order>())
      throw std::logic_error("both foreground queues must be in order");
    // No event can be issued concurrently by the single owner thread here.
    // Both queues are still synchronized below to propagate async errors.
    return foreground_tails_.complete([this](Event event){return complete(event);});
  }
  bool complete(Event e) override {
    return event(e).get_info<sycl::info::event::command_execution_status>()==sycl::info::event_command_status::complete;
  }
  bool wait(Event e,Deadline deadline) override {
    while(!complete(e)) {
      check_error(); if(std::chrono::steady_clock::now()>=deadline) return false;
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    event(e).wait_and_throw(); check_error(); return true;
  }
  Event fill(void* dst,const void* src,size_t bytes) override {
    check_error();
    // A second in-order BCS queue owns its own chain, never the compute tail.
    std::vector<sycl::event> after;if(fill_ticket_)after.push_back(fill_tail_);
    auto copied=maintenance_queue_->memcpy(dst,src,bytes,after);
    try {fill_tail_=copied;fill_ticket_=next_handle();return fill_ticket_;}
    catch(...) {hold_for_supervisor();}
  }
  bool fill_complete(Event ticket) override {
    check_error();if(!ticket||ticket!=fill_ticket_)throw std::logic_error("foreign maintenance ticket");
    return fill_tail_.get_info<sycl::info::event::command_execution_status>()==sycl::info::event_command_status::complete;
  }
  size_t fills_pending() override {return fill_ticket_&&!fill_complete(fill_ticket_)?1:0;}
  void finish_fills() override {
    // Only shutdown / quiescent view transitions call this blocking operation.
    try {maintenance_queue_->wait();}catch(...){hold_for_supervisor();}
    maintenance_queue_->throw_asynchronous();check_error();
  }
  void foreground_sync() override {
    try {copy_queue_->wait();queue_->wait();}catch(...){hold_for_supervisor();}
    copy_queue_->throw_asynchronous();queue_->throw_asynchronous();check_error();
  }
  void synchronize() override {
    finish_fills();
    // Drain both queues before propagating an asynchronous error; short-circuit
    // wait_and_throw could otherwise skip the second queue and its barriers.
    try {copy_queue_->wait();queue_->wait();}catch(...){hold_for_supervisor();}
    copy_queue_->throw_asynchronous();queue_->throw_asynchronous();check_error();
  }
  void clear_events() override {events_.clear();foreground_tails_.clear();}
  void close_queue() override {maintenance_queue_.reset();fill_tail_=sycl::event{};fill_ticket_=0;if(maintenance_native_&&zeCommandListDestroy(maintenance_native_)!=ZE_RESULT_SUCCESS)throw std::runtime_error("maintenance queue destroy failed");maintenance_native_=nullptr;copy_queue_.reset();queue_.reset();if(native_copy_&&zeCommandListDestroy(native_copy_)!=ZE_RESULT_SUCCESS)throw std::runtime_error("copy immediate command list destroy failed");native_copy_=nullptr;}
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
