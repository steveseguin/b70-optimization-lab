#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#include "stage2/packet194-expert-diet-engine/owner.hpp"
#include "stage2/packet194-expert-diet-engine/ordered_queue.hpp"
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#include "stage1/packet3-prep/src/sycl_operation.hpp"
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <sycl/ext/oneapi/experimental/clock.hpp> // OWNRT_TP_EXCHANGE_STATS (diagnostic)
#include <level_zero/ze_api.h>
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <mutex>
#include <set>
#include <stdexcept>
#include <thread>
#include "stage2/packet194-expert-diet-engine/host_spin.hpp"

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
// OWNRT_TP_CARD_CONTEXT=1 (2026-10-29, opt-in; research/tp/fault-ladder-2026-10-29): one SYCL context per card instead of
// one shared by both. Each still holds BOTH devices and wraps the SAME native Level Zero context, so the native context,
// the peer access between the cards and the context's device list (Level Zero v2 makes each device allocation resident on
// the context's peer devices) are unchanged; only the SYCL/UR context objects differ, one per submitting card.
// Why: libsycl 2026.0's fast kernel cache cannot hold one kernel for two devices of one context. On a miss,
// KernelProgramCache::saveKernel appends {kernel name, device} (24 B) to MProgramToFastKernelCacheKeyMap[program], which
// is never trimmed while the program lives, and, when the name is already cached in this context, destroys a temporary
// FastKernelSubcacheWrapper whose destructor erases every subcache entry of this context, the other card's included. With
// both cards submitting the same kernels, every submission missed, took the slow lookup and appended a record: one vector
// per program per card, growing for the life of the process; each doubling's copy cost 0.4-24 MiB of host page faults
// inside a half (the 30-50 ms TP tail halves). With a context per card each card's cache only ever sees its own device.
// Cross-queue SYCL event dependencies (peer_copy / peer_wait) would cross contexts and are refused with this flag; the
// direct exchange (OWNRT_TP_EXCHANGE=direct) synchronises on device flags and uses neither.
inline bool tp_card_context(){static const bool on=[]{const char* v=std::getenv("OWNRT_TP_CARD_CONTEXT");return v&&v[0]=='1';}();return on;}
struct SharedGroup {
  ze_context_handle_t native=nullptr;std::unique_ptr<sycl::context> context;std::vector<sycl::device> devices;
  std::vector<std::unique_ptr<sycl::context>> card_contexts; // OWNRT_TP_CARD_CONTEXT: one per member, same native context
  ~SharedGroup(){card_contexts.clear();context.reset();if(native)zeContextDestroy(native);}
};
class SyclDevice final : public Backend, public OrderedQueue {
  std::shared_ptr<SharedGroup> group_;
  std::size_t card_;
  std::string label_;
  ze_context_handle_t native_=nullptr;
  std::unique_ptr<sycl::context> context_;
  std::unique_ptr<sycl::queue> queue_;
  std::vector<NativeTracked> events_;int allocation_card_=0;
  sycl::event& event(Event e){auto it=std::lower_bound(events_.begin(),events_.end(),e,[](const auto& v,Event h){return v.handle<h;});if(it==events_.end()||it->handle!=e)throw std::logic_error("foreign native event");return it->event;}
  void capacity(){if(events_.size()>=events_.capacity())throw std::length_error("native event capacity");}
  // events_ is appended by this card's submission thread and read (back()) by a peer card's thread in peer_copy /
  // peer_wait; the mutex orders those two (uncontended on a one-card process).
  mutable std::mutex events_mutex_;
  Event record(sycl::event e){auto id=next_handle();std::lock_guard lock(events_mutex_);events_.push_back({id,std::move(e),0});return id;}
  std::mutex error_mutex_;
  std::exception_ptr error_;
  void check_error() { std::lock_guard lock(error_mutex_); if(error_) std::rethrow_exception(error_); }
  std::vector<sycl::event> dependencies(std::span<const Event> deps) {
    for(auto e:deps)(void)event(e); return {}; // Same in-order queue; validate ownership, omit redundant dependencies.
  }
 public:
  // Group member: the shared context, this card's own in-order queue.
  SyclDevice(std::size_t card,bool profiling,std::shared_ptr<SharedGroup> group,std::size_t index):group_(std::move(group)),card_(card) {
    events_.reserve(65536);
    std::lock_guard lock(registry_mutex);
    if(owned_cards.contains(card)) throw std::logic_error("card already has an owner");
    auto d=group_->devices.at(index);
    const bool own=!group_->card_contexts.empty();
    label_="LevelZero:"+std::to_string(card)+":"+d.get_info<sycl::info::device::name>()+(own?":shared-native-card-context":":shared-context");
    if(profiling) label_+=":driver="+d.get_info<sycl::info::device::driver_version>();
    auto handler=[this](sycl::exception_list errors) {
      std::lock_guard error_lock(error_mutex_);
      if(!error_ && errors.size()) error_=*errors.begin();
    };
    context_=std::make_unique<sycl::context>(own?*group_->card_contexts.at(index):*group_->context);
    auto properties=profiling
      ? sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}}
      : sycl::property_list{sycl::property::queue::in_order{}};
    queue_=std::make_unique<sycl::queue>(*context_,d,handler,properties);
    owned_cards.insert(card);
  }
  bool shares(const SyclDevice& o) const {return group_&&group_==o.group_;}
  // The latest submission on this in-order queue (none when every tracked event has been retired).
  bool last_native(sycl::event& out) const {std::lock_guard lock(events_mutex_);if(events_.empty())return false;out=events_.back().event;return true;}
  Event peer_copy(void* d,const void* s,std::size_t n,Backend& source) override {
    check_error();capacity();auto& src=dynamic_cast<SyclDevice&>(source);
    if(!shares(src)||&src==this)throw std::logic_error("peer copy needs two cards of one shared context");
    if(!group_->card_contexts.empty())throw std::logic_error("OWNRT_TP_CARD_CONTEXT: peer copy would depend on another context's event (use OWNRT_TP_EXCHANGE=direct)");
    sycl::event dep;const bool has=src.last_native(dep);
    return record(queue_->submit([&](sycl::handler& h){if(has)h.depends_on(dep);h.memcpy(d,s,n);}));
  }
  Event peer_wait(Backend& peer) override {
    check_error();capacity();auto& other=dynamic_cast<SyclDevice&>(peer);
    if(!shares(other)||&other==this)throw std::logic_error("peer wait needs two cards of one shared context");
    if(!group_->card_contexts.empty())throw std::logic_error("OWNRT_TP_CARD_CONTEXT: peer wait would depend on another context's event (use OWNRT_TP_EXCHANGE=direct)");
    sycl::event dep;const bool has=other.last_native(dep);
    return record(queue_->submit([&](sycl::handler& h){if(has)h.depends_on(dep);h.single_task<class PeerWaitMarker>(packet26::checked([]{}));}));
  }
  // Kernel-direct exchange (2026-10-28; qualified in research/p2p/direct-store-2026-10-28): no cross-queue event.
  // Phase 1: plain stores of this card's rows into the peer's memory, then a system-scope release fence. Each work-group
  // counts itself in this site's local counter; the count gives the execution epoch (both cards run every exchange site
  // the same number of times, in plan order), and the last group stores the epoch into the peer's flag word for this
  // site (a plain store between system-scope fences; the cards have no peer atomics). The waiting groups (the last one
  // in mode 0, every group in mode 1) poll their own flag word with system-scope atomic loads, at most `cap` polls; a
  // timeout sets the engine's sticky error and this card's abort word, and later waits skip. Mode 1 then copies the
  // peer's slots from local staging into the routed output (a fresh kernel's plain loads after the acquire fence).
  sycl::event submit_exchange(const Exchange& x) {
    if(exchange_stats_skip()>=0)return submit_exchange_stats(x); // OWNRT_TP_EXCHANGE_STATS (diagnostic, default off)
    using u32=std::uint32_t;namespace L=exchange_layout;constexpr u32 wg=256;
    const u32 mode=x.mode,words=x.words,rows=x.rows,parity=x.parity,cap=x.cap,run=x.run,stride=x.dst_stride;
    const u32 owned=mode==1u?((x.top+1u-parity)/2u)*rows:words,other=mode==1u?((x.top+parity)/2u)*rows:0u; // mode 2: words, like mode 0
    const u32 groups=std::clamp<u32>((std::max(owned,other)+511u)/512u,2u,16u);
    const u32* src=static_cast<const u32*>(x.src);u32* local=static_cast<u32*>(x.local_dst);u32* remote=static_cast<u32*>(x.peer_dst);
    const u32* staging=static_cast<const u32*>(x.select_src);u32* out=static_cast<u32*>(x.select_dst);const u32* routes=static_cast<const u32*>(x.routes);
    u32* ctl=x.control;u32* error=x.error;const u32 record_at=L::header+x.slot*L::stride;
    u32* peer_flag=x.peer_control+record_at+L::flag;
    return queue_->submit([&](sycl::handler& h){
      h.parallel_for<class TpDirectExchange>(sycl::nd_range<1>(std::size_t(groups)*wg,wg),packet26::checked([=](sycl::nd_item<1> it){
        using dev_ref=sycl::atomic_ref<u32,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>;
        using sys_ref=sycl::atomic_ref<u32,sycl::memory_order::relaxed,sycl::memory_scope::system,sycl::access::address_space::global_space>;
        const u32 gid=u32(it.get_global_linear_id()),lid=u32(it.get_local_linear_id()),step=groups*wg;
        if(mode==0u&&run==0u){for(u32 i=gid;i<words;i+=step){const u32 v=src[i];if(local)local[i]=v;remote[i]=v;}}
        else if(mode==0u){for(u32 i=gid;i<words;i+=step){const u32 v=src[i],w=(i/run)*stride+i%run;if(local)local[w]=v;remote[w]=v;}}
        else if(mode==2u){for(u32 i=gid;i<words;i+=step)if(routes[3u*(i/run)]!=0xfffffffeu)remote[i]=src[i];} // OWNRT_PREFILL_EXPERT_PARITY/_BALANCE: this card's rows (its filtered route is not the skip route)
        else for(u32 i=gid;i<owned;i+=step){const u32 w=(2u*(i/rows)+parity)*rows+i%rows;remote[w]=src[w];}
        sycl::atomic_fence(sycl::memory_order::release,sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
        if(lid==0u){
          const u32 old=dev_ref(ctl[record_at+L::counter]).fetch_add(1u,sycl::memory_order::acq_rel);
          const u32 epoch=old/groups+1u;const bool last=(old+1u)%groups==0u;
          if(last){
            sycl::atomic_fence(sycl::memory_order::acq_rel,sycl::memory_scope::system);
            *reinterpret_cast<volatile u32*>(peer_flag)=epoch;
            sycl::atomic_fence(sycl::memory_order::release,sycl::memory_scope::system);
          }
          if((mode==1u||last)&&dev_ref(ctl[L::abort]).load()==0u){
            sys_ref flag(ctl[record_at+L::flag]);u32 polls=0,v=flag.load();
            while(v<epoch&&polls<cap){++polls;v=flag.load();}
            if(v<epoch){dev_ref(ctl[L::abort]).store(1u);dev_ref(ctl[L::timeouts]).fetch_add(1u);dev_ref(*error).store(1u);}
            else sycl::atomic_fence(sycl::memory_order::acquire,sycl::memory_scope::system);
            dev_ref(ctl[L::waits]).fetch_add(1u);
            if(polls){dev_ref(ctl[L::spun]).fetch_add(1u);dev_ref(ctl[L::spin_sum]).fetch_add(polls);dev_ref(ctl[L::max_spin]).fetch_max(polls);}
          }
        }
        if(mode==1u){
          sycl::group_barrier(it.get_group());
          sycl::atomic_fence(sycl::memory_order::acquire,sycl::memory_scope::system);
          for(u32 i=gid;i<other;i+=step){const u32 w=(2u*(i/rows)+1u-parity)*rows+i%rows;out[w]=staging[w];}
        }
      }));
    });
  }
  // OWNRT_TP_EXCHANGE_STATS=N (diagnostic, default off; research/tp/stage-overhead-2026-10-30): the same exchange, plus
  // per-site wait statistics in the unused words 1..13 of this card's own site record (never touched by the peer; the
  // peer's flag is word 16, another 64-byte line). Only the single waiting work-item of a mode-0 exchange writes them,
  // and only for epochs > N (N = 1 skips each site's first execution). Clock: the EU thread's sub-group clock
  // (sycl_ext_oneapi_clock; B70 offers no device-scope clock), read three times by that one work-item, so every interval
  // is within one hardware thread: own = kernel entry -> start of the wait (stores, fences, barrier, counter, flag
  // store), wait = start -> end of the poll loop. Words: 1 n, 2-3 wait cycles (u64), 4-5 own cycles (u64), 6 max wait
  // cycles, 7 polls, 8-12 wait histogram (< 1400, < 5600, < 22400, < 89600, >= 89600 cycles), 13 waits that polled.
  // Data movement, fences, flag protocol and poll loop are the unchanged kernel's; the statistics are relaxed
  // device-scope atomics on local words after the wait.
  static int exchange_stats_skip() {
    static const int skip=[]{const char* v=std::getenv("OWNRT_TP_EXCHANGE_STATS");if(!v||!*v)return -1;
      char* end=nullptr;const long n=std::strtol(v,&end,10);if(*end||n<0||n>1000000)throw std::invalid_argument("OWNRT_TP_EXCHANGE_STATS must be a skip count >= 0");return int(n);}();
    return skip;
  }
  sycl::event submit_exchange_stats(const Exchange& x) {
    using u32=std::uint32_t;using u64=std::uint64_t;namespace L=exchange_layout;constexpr u32 wg=256;
    const u32 mode=x.mode,words=x.words,rows=x.rows,parity=x.parity,cap=x.cap,run=x.run,stride=x.dst_stride;
    const u32 owned=mode==1u?((x.top+1u-parity)/2u)*rows:words,other=mode==1u?((x.top+parity)/2u)*rows:0u; // mode 2: words, like mode 0
    const u32 groups=std::clamp<u32>((std::max(owned,other)+511u)/512u,2u,16u);
    const u32 skip=u32(exchange_stats_skip());
    const u32* src=static_cast<const u32*>(x.src);u32* local=static_cast<u32*>(x.local_dst);u32* remote=static_cast<u32*>(x.peer_dst);
    const u32* staging=static_cast<const u32*>(x.select_src);u32* out=static_cast<u32*>(x.select_dst);const u32* routes=static_cast<const u32*>(x.routes);
    u32* ctl=x.control;u32* error=x.error;const u32 record_at=L::header+x.slot*L::stride;
    u32* peer_flag=x.peer_control+record_at+L::flag;
    return queue_->submit([&](sycl::handler& h){
      h.parallel_for<class TpDirectExchangeStats>(sycl::nd_range<1>(std::size_t(groups)*wg,wg),packet26::checked([=](sycl::nd_item<1> it){
        namespace X=sycl::ext::oneapi::experimental;
        using dev_ref=sycl::atomic_ref<u32,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>;
        using dev64=sycl::atomic_ref<unsigned long long,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>;
        using sys_ref=sycl::atomic_ref<u32,sycl::memory_order::relaxed,sycl::memory_scope::system,sycl::access::address_space::global_space>;
        const u32 gid=u32(it.get_global_linear_id()),lid=u32(it.get_local_linear_id()),step=groups*wg;
        u64 t_entry=0;if(lid==0u)t_entry=X::clock<X::clock_scope::sub_group>();
        if(mode==0u&&run==0u){for(u32 i=gid;i<words;i+=step){const u32 v=src[i];if(local)local[i]=v;remote[i]=v;}}
        else if(mode==0u){for(u32 i=gid;i<words;i+=step){const u32 v=src[i],w=(i/run)*stride+i%run;if(local)local[w]=v;remote[w]=v;}}
        else if(mode==2u){for(u32 i=gid;i<words;i+=step)if(routes[3u*(i/run)]!=0xfffffffeu)remote[i]=src[i];} // OWNRT_PREFILL_EXPERT_PARITY/_BALANCE: this card's rows (its filtered route is not the skip route)
        else for(u32 i=gid;i<owned;i+=step){const u32 w=(2u*(i/rows)+parity)*rows+i%rows;remote[w]=src[w];}
        sycl::atomic_fence(sycl::memory_order::release,sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
        if(lid==0u){
          const u32 old=dev_ref(ctl[record_at+L::counter]).fetch_add(1u,sycl::memory_order::acq_rel);
          const u32 epoch=old/groups+1u;const bool last=(old+1u)%groups==0u;
          if(last){
            sycl::atomic_fence(sycl::memory_order::acq_rel,sycl::memory_scope::system);
            *reinterpret_cast<volatile u32*>(peer_flag)=epoch;
            sycl::atomic_fence(sycl::memory_order::release,sycl::memory_scope::system);
          }
          if((mode==1u||last)&&dev_ref(ctl[L::abort]).load()==0u){
            sys_ref flag(ctl[record_at+L::flag]);
            const u64 t_arrive=X::clock<X::clock_scope::sub_group>();
            u32 polls=0,v=flag.load();
            while(v<epoch&&polls<cap){++polls;v=flag.load();}
            const u64 t_release=X::clock<X::clock_scope::sub_group>();
            if(v<epoch){dev_ref(ctl[L::abort]).store(1u);dev_ref(ctl[L::timeouts]).fetch_add(1u);dev_ref(*error).store(1u);}
            else sycl::atomic_fence(sycl::memory_order::acquire,sycl::memory_scope::system);
            dev_ref(ctl[L::waits]).fetch_add(1u);
            if(polls){dev_ref(ctl[L::spun]).fetch_add(1u);dev_ref(ctl[L::spin_sum]).fetch_add(polls);dev_ref(ctl[L::max_spin]).fetch_max(polls);}
            if((mode==0u||mode==2u)&&epoch>skip){
              u32* r=ctl+record_at;const u64 wait=t_release-t_arrive,own=t_arrive-t_entry;const u32 w32=wait>0xffffffffull?0xffffffffu:u32(wait);
              dev_ref(r[1]).fetch_add(1u);
              dev64(*reinterpret_cast<unsigned long long*>(r+2)).fetch_add(wait);
              dev64(*reinterpret_cast<unsigned long long*>(r+4)).fetch_add(own);
              dev_ref(r[6]).fetch_max(w32);dev_ref(r[7]).fetch_add(polls);
              dev_ref(r[w32<1400u?8:w32<5600u?9:w32<22400u?10:w32<89600u?11:12]).fetch_add(1u);
              if(polls)dev_ref(r[13]).fetch_add(1u);
            }
          }
        }
        if(mode==1u){
          sycl::group_barrier(it.get_group());
          sycl::atomic_fence(sycl::memory_order::acquire,sycl::memory_scope::system);
          for(u32 i=gid;i<other;i+=step){const u32 w=(2u*(i/rows)+1u-parity)*rows+i%rows;out[w]=staging[w];}
        }
      }));
    });
  }
  Event exchange(const Exchange& x) override {check_error();capacity();return record(submit_exchange(x));}
  std::function<Event()> prepare_exchange(const Exchange& x) override {return [this,x]{check_error();capacity();return record(submit_exchange(x));};}
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
    check_error();capacity();dependencies(deps);return record(queue_->memcpy(dst,src,n));
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
  void synchronize() override {queue_->wait_and_throw(); check_error();}
  void clear_events() override {std::lock_guard lock(events_mutex_);events_.clear();}
  void clear_events_through(Event last) override { // OWNRT_RETIRE_DEFERRED: handles are increasing, events_ is sorted
    std::lock_guard lock(events_mutex_);
    auto end=std::upper_bound(events_.begin(),events_.end(),last,[](Event h,const auto& v){return h<v.handle;});
    events_.erase(events_.begin(),end);
  }
  void close_queue() override {queue_.reset();}
  void close_context() override {
    context_.reset();
    if(native_ && zeContextDestroy(native_)!=ZE_RESULT_SUCCESS) throw std::runtime_error("zeContextDestroy failed");
    native_=nullptr; group_.reset(); std::lock_guard lock(registry_mutex); owned_cards.erase(card_);
  }
};
}
std::unique_ptr<Backend> make_sycl_device(std::size_t card,bool profiling) {return std::make_unique<SyclDevice>(card,profiling);}
std::vector<std::unique_ptr<Backend>> make_sycl_device_group(const std::vector<std::size_t>& indices,bool profiling) {
  auto found=cards();if(indices.size()<2)throw std::invalid_argument("device group needs two or more cards");
  auto group=std::make_shared<SharedGroup>();
  for(auto i:indices){if(i>=found.size())throw std::out_of_range("Level Zero GPU index");group->devices.push_back(found[i]);}
  for(size_t a=0;a<group->devices.size();++a)for(size_t b=0;b<group->devices.size();++b)if(a!=b) {
    ze_bool_t can=0;auto da=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(group->devices[a]),db=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(group->devices[b]);
    if(zeDeviceCanAccessPeer(da,db,&can)!=ZE_RESULT_SUCCESS||!can)throw std::runtime_error("cards cannot access each other's memory");
  }
  ze_context_desc_t desc{};desc.stype=ZE_STRUCTURE_TYPE_CONTEXT_DESC;
  auto driver=sycl::get_native<sycl::backend::ext_oneapi_level_zero>(group->devices[0].get_platform());
  if(zeContextCreate(driver,&desc,&group->native)!=ZE_RESULT_SUCCESS)throw std::runtime_error("zeContextCreate failed; no fallback context");
  if(tp_card_context()) {
    for(size_t i=0;i<indices.size();++i)group->card_contexts.push_back(std::make_unique<sycl::context>(sycl::make_context<sycl::backend::ext_oneapi_level_zero>(
      {group->native,group->devices,sycl::ext::oneapi::level_zero::ownership::keep},[](sycl::exception_list){})));
  } else
  group->context=std::make_unique<sycl::context>(sycl::make_context<sycl::backend::ext_oneapi_level_zero>(
    {group->native,group->devices,sycl::ext::oneapi::level_zero::ownership::keep},[](sycl::exception_list){}));
  std::vector<std::unique_ptr<Backend>> out;
  for(size_t i=0;i<indices.size();++i)out.push_back(std::make_unique<SyclDevice>(indices[i],profiling,group,i));
  return out;
}
std::vector<std::string> enumerate_sycl_cards() {
  std::vector<std::string> names;
  for(const auto& d:cards()) names.push_back(d.get_info<sycl::info::device::name>());
  return names;
}
}
