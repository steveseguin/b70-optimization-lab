#include "owner.hpp"
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
