#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/native/ordered_retirement.hpp"
#include <algorithm>
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/native/async_backend.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/owner_retire.cpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/owner.hpp"
namespace ownrt {
void forget_event_queues(std::span<const Event>);
// A serial eager segment has no retained event consumers. Reclaim only after
// every owned event is complete; old IDs become foreign immediately. This
// does not release allocations, graphs, queues, contexts or reset the device.
void Device::retire_completed_events() {
  if (quiescing_ || closed_ || !fault_.empty() || !graphs_.empty())
    throw std::logic_error(
        "event retirement requires an open eager owner without graph leases");
  if(ordered_retirement(*this)) {
    if(capture_)throw std::logic_error("ordered retirement during capture");
    auto* prefix=dynamic_cast<ForegroundPrefix*>(backend_.get());
#ifdef OWN_RT_HOST_ONLY
    // Existing CPU shape/capture mocks have no asynchronous foreground work.
    // The dedicated delayed-prefix fixture implements the actual capability.
    const bool complete=prefix?prefix->foreground_prefix_complete():!std::any_of(events_.begin(),events_.end(),[&](auto e){return !backend_->complete(e);});
#else
    if(!prefix)throw std::logic_error("foreground prefix proof unavailable");
    const bool complete=prefix->foreground_prefix_complete();
#endif
    if(!complete)throw std::logic_error("ordered retirement with pending foreground work");
  } else if (std::any_of(events_.begin(),events_.end(),[&](auto e){return !backend_->complete(e);}))
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
