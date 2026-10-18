#include <algorithm>
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion/native/async_backend.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/owner_retire.cpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/owner.hpp"
namespace ownrt {
void forget_event_queues(std::span<const Event>);
// A serial eager segment has no retained event consumers. Reclaim only after
// every owned event is complete; old IDs become foreign immediately. This
// does not release allocations, graphs, queues, contexts or reset the device.
void Device::retire_completed_events() {
  if (quiescing_ || closed_ || !fault_.empty() || !graphs_.empty())
    throw std::logic_error(
        "event retirement requires an open eager owner without graph leases");
  if (std::any_of(events_.begin(),events_.end(),[&](auto e){return !backend_->complete(e);}))
    throw std::logic_error("event retirement with pending work");
  try {
    p58v::foreground_sync(*backend_);
    backend_->clear_events();
    forget_event_queues(events_);
    events_.clear();
  } catch (const std::exception &e) {
    fault_ = e.what();
    throw;
  }
}
} // namespace ownrt
