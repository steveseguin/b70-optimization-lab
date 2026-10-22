#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/ordered_queue.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/build/checked/experiments/own-xpu-runtime/stage2/packet183-twocard-s1-micro/owner.hpp"
namespace ownrt {
// Optional capability, separate from Backend's vtable and Device's layout.
// Only a backend whose ENTIRE submission stream is one in-order queue may
// implement this. A completed terminal event proves completion of its prefix.
// No event, allocation, command or kernel is created by this query.
struct OrderedQueue {
  virtual ~OrderedQueue() = default;
  virtual bool ordered_prefix_complete(Event terminal) = 0;
};
}
