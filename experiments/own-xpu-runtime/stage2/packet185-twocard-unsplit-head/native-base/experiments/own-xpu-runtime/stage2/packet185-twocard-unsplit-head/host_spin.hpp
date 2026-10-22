#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/host_spin.hpp"
#pragma once
#include <chrono>
#include <thread>
// Linked policy, sealed by the executable hash; no environment override.
namespace p56x {
extern const bool sleep20;
inline constexpr unsigned yield_iterations = 256;
inline void pause() {
#if defined(__i386__) || defined(__x86_64__)
  __builtin_ia32_pause();
#elif defined(__aarch64__)
  asm volatile("yield");
#else
  std::this_thread::yield();
#endif
}
// Preserve acquire/completion checks and cancellation/progress on every loop.
// One spin budget per invocation; sleeps are capped to the remaining deadline.
template<class Ready, class Guard>
bool wait(Ready ready, Guard guard,
          std::chrono::steady_clock::time_point deadline) {
  const auto spin_end = std::chrono::steady_clock::now() + std::chrono::microseconds(250);
  unsigned iterations = 0;
  while (!ready()) {
    guard();
    const auto now = std::chrono::steady_clock::now();
    if (now >= deadline) return false;
    if (sleep20 && now >= spin_end) {
      auto delay = std::chrono::duration_cast<std::chrono::steady_clock::duration>(std::chrono::microseconds(20));
      if (deadline - now < delay) delay = deadline - now;
      std::this_thread::sleep_for(delay);
    } else {
      pause();
      if (++iterations % yield_iterations == 0) std::this_thread::yield();
    }
  }
  return true;
}
}
