#pragma once
#include "owner.hpp"
#include <optional>

namespace ownrt {
// Test before subtracting unsigned backend timestamps. Zero means unavailable.
inline std::optional<std::uint64_t> event_duration(EventTiming t) {
  if(t.start_ns == 0 || t.end_ns <= t.start_ns) return std::nullopt;
  return t.end_ns-t.start_ns;
}
}
