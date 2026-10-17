#pragma once
#include <chrono>
#include <thread>

// Host scheduling only. Poll publication/completion with its existing acquire
// semantics, for at most 250 us per wait invocation, then use the old sleep.
namespace p56w {
inline constexpr int spin_microseconds = 250;
inline void pause() {
#if defined(__i386__) || defined(__x86_64__)
  __builtin_ia32_pause();
#elif defined(__aarch64__)
  asm volatile("yield");
#else
  std::this_thread::yield();
#endif
}
template<class Ready, class Guard>
bool spin(Ready ready, Guard guard,
          std::chrono::steady_clock::time_point deadline) {
  auto end = std::chrono::steady_clock::now() +
             std::chrono::microseconds(spin_microseconds);
  if (deadline < end) end = deadline;
  while (!ready()) {
    guard();
    if (std::chrono::steady_clock::now() >= end) return false;
    // Amortize clock/stop-channel checks, but acquire-check each publication.
    for (int i = 0; i < 32; ++i) {
      pause();
      if (ready()) return true;
    }
  }
  return true;
}
}
