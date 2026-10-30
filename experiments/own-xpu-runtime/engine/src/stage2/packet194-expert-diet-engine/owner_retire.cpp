#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#include "stage2/packet194-expert-diet-engine/owner.hpp"
#include "stage2/packet194-expert-diet-engine/ordered_queue.hpp"
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

namespace ownrt {
void Device::retire_prefix(std::size_t n) {
  if (quiescing_ || closed_ || !fault_.empty() || !graphs_.empty() || capture_)
    throw std::logic_error("prefix retirement requires an open eager owner");
  if (n > events_.size()) throw std::logic_error("prefix retirement beyond the recorded events");
  if (!n) return;
  try {
    // Each of these was complete when its retirement was deferred; re-check the last one (cheap, never pending).
    if (!backend_->complete(events_[n - 1])) throw std::logic_error("prefix retirement with pending work");
    backend_->clear_events_through(events_[n - 1]);
    forget_event_queues(std::span<const Event>(events_.data(), n));
    events_.erase(events_.begin(), events_.begin() + std::ptrdiff_t(n));
  } catch (const std::exception &e) {fault_ = e.what(); throw;}
}
} // namespace ownrt
