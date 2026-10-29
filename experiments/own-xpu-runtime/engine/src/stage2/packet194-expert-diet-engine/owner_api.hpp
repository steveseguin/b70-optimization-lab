#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include <unordered_map>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>
#include <type_traits>
#include <cstring>
#include <ostream>
#include "stage2/packet194-expert-diet-engine/argument_block.hpp"

// Original lab implementation. Ownership/order: ../../DESIGN.md. Bounded
// uploads follow the lab's 2026-10-04 EXTERNAL_HOST_PTR diagnosis, not runtime
// source code. No graph execution, peer copy or compute overlap is assumed.
namespace ownrt {
// Direct-exchange control words (u32) per card: a header, then one 128-byte record per exchange site.
namespace exchange_layout {
inline constexpr std::uint32_t header=32, stride=32, counter=0, flag=16, slots=256;
inline constexpr std::uint32_t abort=0, timeouts=1, waits=2, spun=3, max_spin=4, spin_sum=5;
inline constexpr std::size_t bytes=std::size_t(header+stride*slots)*4;
}
using Event = std::uint64_t;
using Allocation = std::uint64_t;
using Deadline = std::chrono::steady_clock::time_point;
std::uint64_t next_handle(); // process-unique across owners and mock/native backends
enum class Memory { device, pinned, shadow };
enum class Category { weights, kv, recurrent, scratch, graph_static,
                      pinned_slab, output_ring, loader_staging, host_shadow,
                      runtime_overhead };
enum class Lifetime { process, request, transaction, graph, transfer };
struct EventTiming { std::uint64_t start_ns, end_ns; };
struct Operation { virtual ~Operation() = default; };
std::string quote(const std::string&);
const char* name(Memory);
const char* name(Category);
const char* name(Lifetime);

// Backend owns events, queue and context. All work must enter through Device;
// no borrowed raw queue, untracked submissions or foreign events are accepted.
struct Backend {
  virtual ~Backend() = default;
  virtual std::string identity() const = 0;
  virtual void* allocate(std::size_t, Memory) = 0;
  virtual void release(void*, Memory) = 0;
  virtual Event copy(void*, const void*, std::size_t, std::span<const Event>) = 0;
  virtual Event marker(std::span<const Event>) = 0;
  virtual Event compute(const Operation&, std::span<void* const>, std::span<const Event>) {
    throw std::logic_error("compute unsupported by backend");
  }
  virtual std::function<Event()> prepare_copy(void* d,const void* s,size_t n) { return [this,d,s,n]{return copy(d,s,n,{});}; }
  virtual std::function<Event()> prepare(const Operation&, std::span<void* const>) { throw std::logic_error("prepared backend unsupported"); }
  virtual std::function<Event()> prepare_owned(std::shared_ptr<const Operation> op, std::span<void* const> pointers) { return prepare(*op,pointers); }
  virtual EventTiming timing(Event) { throw std::logic_error("profiling disabled"); }
  // Multi-card (2026-10-25): devices that share one context. peer_copy runs on this queue after everything already
  // submitted to `source`'s queue; peer_wait puts a marker on this queue that waits for `peer`'s latest work.
  virtual Event peer_copy(void*, const void*, std::size_t, Backend& /*source*/) { throw std::logic_error("peer copy unsupported"); }
  virtual std::function<Event()> prepare_peer_copy(void* d, const void* s, std::size_t n, Backend& source) { return [this,d,s,n,&source]{return peer_copy(d,s,n,source);}; }
  virtual Event peer_wait(Backend& /*peer*/) { throw std::logic_error("peer wait unsupported"); }
  // Kernel-direct exchange (2026-10-28, OWNRT_TP_EXCHANGE=direct; research/p2p/direct-store-2026-10-28). One kernel on
  // this card stores this card's rows into the peer's memory (plain stores between system-scope release fences), raises
  // the peer's flag for `slot`, then waits (bounded) for the peer's flag. Resolved pointers; see Device::exchange.
  struct Exchange {
    const void* src=nullptr;void* local_dst=nullptr;void* peer_dst=nullptr;std::uint32_t words=0; // mode 0: contiguous words
    const void* select_src=nullptr;void* select_dst=nullptr;                                    // mode 1: slot rows
    std::uint32_t mode=0,rows=0,top=0,parity=0,slot=0;
    std::uint32_t* control=nullptr;std::uint32_t* peer_control=nullptr;std::uint32_t* error=nullptr;
    std::uint32_t cap=0;
    std::uint32_t run=0,dst_stride=0; // mode 0 strided destination: word i goes to (i/run)*dst_stride + i%run (0 = contiguous)
  };
  virtual Event exchange(const Exchange&) { throw std::logic_error("direct exchange unsupported"); }
  virtual std::function<Event()> prepare_exchange(const Exchange& x) { return [this,x]{return exchange(x);}; }
  virtual bool complete(Event) = 0;
  virtual bool wait(Event, Deadline) = 0;
  virtual void synchronize() = 0; // only after all tracked events complete
  virtual void clear_events() = 0;
  virtual void close_queue() = 0;
  virtual void close_context() = 0;
};

struct Row {
  Allocation id;
  std::string label;
  Category category;
  Lifetime lifetime;
  Memory memory;
  std::size_t bytes;
  void* pointer;
  bool live = true;
};
struct Receipt {
  std::string backend;
  std::string status = "refused";
  int exit_code = 75; // incomplete: NOT permission to exit the process
  bool safe_to_exit = false;
  bool idle_marker_complete = false;
  std::size_t in_flight = 0;
  std::size_t live_bytes = 0;
  std::string error;
  std::vector<std::string> sequence;
  std::string json() const;
};
struct PreparedCompute {
  std::function<Event()> submit;
  std::vector<Allocation> ids;
  std::vector<void*> pointers;
  uint64_t generation=0;
  int queue=-1;
  const void* owner=nullptr;
  std::vector<unsigned char> argument_bytes, operation_bytes;
  uint64_t* copy_counter=nullptr;
};
class Device;
class Arena {
  friend class Device;
  Device& owner_;
  std::vector<Row> rows_;
  explicit Arena(Device& owner) : owner_(owner) {}
  void release_group(int);
 public:
  Allocation allocate(std::string, std::size_t, Memory, Category, Lifetime);
  void release(Allocation);
  const Row& row(Allocation) const;
  std::size_t total(Memory) const;
  std::string census() const;
};
class CopyEngine {
  Device& owner_;
  const std::size_t limit_, depth_;
 public:
  explicit CopyEngine(Device&, std::size_t limit = 128ull*1024*1024,
                      std::size_t depth = 2);
  Event copy(Allocation dst, std::size_t dst_offset, Allocation src,
             std::size_t src_offset, std::size_t bytes,
             std::span<const Event> dependencies);
};
class Device {
  friend class Arena;
  friend class CopyEngine;
  struct Graph { std::string label; std::vector<Allocation> buffers;
                 std::function<void()> destroy; };
  std::unique_ptr<Backend> backend_;
  bool quiescing_ = false, closed_ = false, idle_ = false;
  std::vector<Event> events_;
  std::vector<Graph> graphs_;
  std::vector<std::string> sequence_;
  Event final_marker_ = 0;
  std::string fault_;
  uint64_t generation_=next_handle();
  std::vector<PreparedCompute>* capture_=nullptr;
  Event capture_operation(const Operation&, std::shared_ptr<const Operation>, std::span<const Allocation>);
  void admit() const;
  void validate(std::span<const Event>) const;
  bool drain(Deadline);
  Receipt receipt(std::string error = {});
 public:
  Arena arena;
  // Same-thread launch-boundary observers; capture/preparation never invokes them.
  // Cancellation observer runs outside backend fault handling, before submission.
  std::function<void()> before_compute;
  std::function<void(Event)> after_compute;
  std::ostream* argument_audit=nullptr;
  bool audit_prepare_each=false;
  // Row views: replay an unchanged single-row operation on row `view_row` of multi-row storage. While view_row>=0,
  // every binding whose allocation has a view is redirected: `stride` views point at target.pointer+row*stride;
  // `alternate` views point at the target on odd rows and at the allocation itself on even rows (recurrent bank
  // alternation, as consecutive single-row steps would swap banks). Views apply when a command is computed or
  // captured; a captured command keeps the pointers it was captured with. Kernel, arguments and arithmetic are unchanged.
  struct RowView {Allocation target=0;std::size_t stride=0;bool alternate=false;};
  std::unordered_map<Allocation,RowView> row_views;
  int view_row=-1;
  void apply_row_views(std::span<const Allocation> ids,std::span<void*> pointers,int queue) const;
  explicit Device(std::unique_ptr<Backend>);
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  ~Device(); // cooperative drain; never abandon work through an early exit
  std::string identity() const;
  std::size_t in_flight();
  bool complete(Event); // owned event poll; never retires or waits
  bool wait(Event, std::chrono::milliseconds);
  EventTiming timing(Event); // completed, owned event only; profiling is opt-in
  // Device-only bindings; host/UVA pointers require a separate admission path.
  Event compute(const Operation&, std::span<const Allocation>, std::span<const Event>);
  template<class T> requires (std::is_base_of_v<Operation,T> && !std::is_same_v<Operation,T>)
  Event compute(const T& op, std::span<const Allocation> ids, std::span<const Event> deps) {
#ifdef OWN_RT_HOST_ONLY
    if(argument_audit) {
      auto before=arguments::block(op);T clone(op);auto after=arguments::block(clone);
      if(before!=after)throw std::logic_error("prepared functor argument mismatch");
      *argument_audit<<"{\"ids\":[";for(size_t i=0;i<ids.size();++i)*argument_audit<<(i?",":"")<<ids[i];
      *argument_audit<<"],\"legacy_argument_hex\":\"";for(auto b:before)*argument_audit<<"0123456789abcdef"[b>>4]<<"0123456789abcdef"[b&15];
      *argument_audit<<"\",\"prepared_argument_hex\":\"";for(auto b:after)*argument_audit<<"0123456789abcdef"[b>>4]<<"0123456789abcdef"[b&15];*argument_audit<<"\"}\n";
    }
    if(!capture_&&audit_prepare_each) {
      std::vector<PreparedCompute> scratch;begin_capture(scratch);
      try {capture_operation(op,std::make_shared<T>(op),ids);end_capture();}
      catch(...){end_capture();throw;}
      return issue(scratch.front());
    }
#endif
    if(!capture_)return compute(static_cast<const Operation&>(op),ids,deps);
    for(auto dep:deps)if(!dep||dep>capture_->size())throw std::logic_error("foreign captured dependency");
#ifdef OWN_RT_HOST_ONLY
    auto copy=std::make_shared<T>(op);
    auto result=capture_operation(op,std::move(copy),ids);
    if(argument_audit)capture_->back().operation_bytes=arguments::block(op);
    return result;
#else
    return capture_operation(op,{},ids);
#endif
  }
  bool capturing() const noexcept { return capture_!=nullptr; }
  void begin_capture(std::vector<PreparedCompute>& out) { admit(); if(capture_)throw std::logic_error("nested capture");capture_=&out; }
  void end_capture() noexcept { capture_=nullptr; }
  Event issue(const PreparedCompute&);
  // Multi-card (2026-10-25): both Devices belong to one shared-context group (make_sycl_device_group).
  // peer_copy: copy source's allocation bytes into this Device's allocation, after all work submitted to `source`.
  // peer_wait: a marker on this queue after all work submitted to `peer` (protects a buffer the peer still reads).
  Event peer_copy(Device& source, Allocation dst, std::size_t dst_offset, Allocation src, std::size_t src_offset, std::size_t bytes);
  Event peer_wait(Device& peer, int queue = -1); // queue: this Device's queue index (card<N>: allocations), -1 = infer
  // peer_push: copy this Device's allocation bytes into `dest`'s allocation, on this queue (ordered after this card's
  // own work only; the receiver orders its readers with peer_wait).
  Event peer_push(Device& dest, Allocation dst, std::size_t dst_offset, Allocation src, std::size_t src_offset, std::size_t bytes);
  // exchange (2026-10-28, OWNRT_TP_EXCHANGE=direct): one kernel on this queue, no cross-queue event.
  //  mode 0 (dense row halves): words of src -> local_dst+local_offset (optional) and peer_dst+peer_offset on `peer`.
  //  mode 1 (expert slots): src holds top x rows F32 slot rows; the slots s with s%2==parity go to peer_dst (the peer's
  //   staging copy, same layout); after the peer's flag, the other slots are copied from select_src (this card's staging)
  //   into select_dst. Bitwise copies only.
  //  control / peer_control: the two cards' exchange words (layout in single_device.cpp); slot: this site's flag pair.
  //  A wait that exceeds `cap` polls sets *error=1 and this card's abort word (later waits skip); stores always happen.
  struct ExchangeSpec {
    Allocation src=0;std::size_t src_offset=0;Allocation local_dst=0;std::size_t local_offset=0;
    Allocation peer_dst=0;std::size_t peer_offset=0;std::size_t bytes=0;
    Allocation select_src=0,select_dst=0;
    std::uint32_t mode=0,rows=0,top=0,parity=0,slot=0,cap=0;
    Allocation control=0,peer_control=0,error=0;
    std::uint32_t run=0,dst_stride=0; // mode 0: destination runs of `run` words, `dst_stride` words apart (0 = contiguous)
  };
  Event exchange(Device& peer, const ExchangeSpec&);
  void invalidate_prepared() { if(in_flight())throw std::logic_error("invalidate while pending");generation_=next_handle(); }
  uint64_t generation() const noexcept {return generation_;}
  // Packet4 eager segments only: retire completed events, preserving allocations.
  // Implementation lives with that integration; graph leases forbid retirement.
  void retire_completed_events();
  void retire_ordered_events(); // Packet76: explicit ordered-backend capability
  void graph(std::string, std::vector<Allocation>, std::function<void()>);
  Receipt shutdown(std::chrono::milliseconds timeout);
};
// On an unrecoverable backend error, keep ownership alive for the supervisor.
// No _Exit/terminate, automatic reset, kill, retry or successful exit receipt.
[[noreturn]] void hold_for_supervisor();
std::unique_ptr<Backend> make_sycl_device(std::size_t card, bool profiling = false);
// One shared Level Zero context over several cards, one in-order queue each (peer access required).
std::vector<std::unique_ptr<Backend>> make_sycl_device_group(const std::vector<std::size_t>& cards, bool profiling = false);
std::vector<std::string> enumerate_sycl_cards();
}
