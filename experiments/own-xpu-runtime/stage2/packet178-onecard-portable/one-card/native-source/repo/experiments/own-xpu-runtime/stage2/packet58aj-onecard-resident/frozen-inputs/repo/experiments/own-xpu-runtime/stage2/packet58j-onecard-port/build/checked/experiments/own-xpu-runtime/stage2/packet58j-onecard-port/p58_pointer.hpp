#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet165-warm-prefill/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet165-warm-prefill/one-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p58_pointer.hpp"
#pragma once
#include <cstdint>
#include <cstddef>
namespace p58 {
// Publication is protected by the owned queue and the completed position fence.
// Generation is retained in each row for CPU/state receipts; no table mutation
// overlaps a kernel. Therefore an old generation cannot be consumed.
struct Pointer {uint64_t address=0,generation=0;};
inline const uint8_t* resolve(const uint8_t* bank,size_t offset,size_t expert_bytes,bool indirect){
 if(!indirect)return bank+offset;
 auto entry=reinterpret_cast<const Pointer*>(bank)[offset/expert_bytes];
 return reinterpret_cast<const uint8_t*>(entry.address)+offset%expert_bytes;
}
}
