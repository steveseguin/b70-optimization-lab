#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/owner_retire.cpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/build/checked/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/owner.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/build/checked/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/ordered_queue.hpp"
namespace ownrt {
void forget_event_queues(std::span<const Event>);
// A serial eager segment has no retained event consumers. Reclaim only after
// every owned event is complete; old IDs become foreign immediately. This
// does not release allocations, graphs, queues, contexts or reset the device.
void Device::retire_completed_events() {
  if (quiescing_ || closed_ || !fault_.empty() || !graphs_.empty())
    throw std::logic_error(
        "event retirement requires an open eager owner without graph leases");
  if (in_flight())
    throw std::logic_error("event retirement with pending work");
  try {
    backend_->synchronize();
    backend_->clear_events();
    forget_event_queues(events_);
    events_.clear();
  } catch (const std::exception &e) {
    fault_ = e.what();
    throw;
  }
}
} // namespace ownrt

namespace ownrt {
void Device::retire_ordered_events() {
  if (quiescing_ || closed_ || !fault_.empty() || !graphs_.empty() || capture_)
    throw std::logic_error("ordered retirement requires an open eager owner");
  auto* ordered=dynamic_cast<OrderedQueue*>(backend_.get());
  if(!ordered)throw std::logic_error("backend has no ordered-prefix proof");
  try {
    if(!events_.empty() && !ordered->ordered_prefix_complete(events_.back()))
      throw std::logic_error("ordered event retirement with pending work");
    // Same error propagation and native cleanup as the original path. The
    // only elision is the redundant individual completion query for each
    // earlier event. No new work can enter this same-thread owner here.
    backend_->synchronize();
    backend_->clear_events();
    forget_event_queues(events_);
    events_.clear();
  } catch(const std::exception& e) {fault_=e.what();throw;}
}
}
