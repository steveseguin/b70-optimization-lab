#pragma once
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <span>
#include <string>
#include <vector>

// Original lab implementation. Ownership/order: ../../DESIGN.md. Bounded
// uploads follow the lab's 2026-10-04 EXTERNAL_HOST_PTR diagnosis, not runtime
// source code. No graph execution, peer copy or compute overlap is assumed.
namespace ownrt {
using Event = std::uint64_t;
using Allocation = std::uint64_t;
using Deadline = std::chrono::steady_clock::time_point;
std::uint64_t next_handle(); // process-unique across owners and mock/native backends
enum class Memory { device, pinned, shadow };
enum class Category { weights, kv, recurrent, scratch, graph_static,
                      pinned_slab, output_ring, loader_staging, host_shadow,
                      runtime_overhead };
enum class Lifetime { process, request, transaction, graph, transfer };
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
  void admit() const;
  void validate(std::span<const Event>) const;
  bool drain(Deadline);
  Receipt receipt(std::string error = {});
 public:
  Arena arena;
  explicit Device(std::unique_ptr<Backend>);
  Device(const Device&) = delete;
  Device& operator=(const Device&) = delete;
  ~Device(); // cooperative drain; never abandon work through an early exit
  std::string identity() const;
  std::size_t in_flight();
  bool wait(Event, std::chrono::milliseconds);
  void graph(std::string, std::vector<Allocation>, std::function<void()>);
  Receipt shutdown(std::chrono::milliseconds timeout);
};
// On an unrecoverable backend error, keep ownership alive for the supervisor.
// No _Exit/terminate, automatic reset, kill, retry or successful exit receipt.
[[noreturn]] void hold_for_supervisor();
std::unique_ptr<Backend> make_sycl_device(std::size_t card);
std::vector<std::string> enumerate_sycl_cards();
}
