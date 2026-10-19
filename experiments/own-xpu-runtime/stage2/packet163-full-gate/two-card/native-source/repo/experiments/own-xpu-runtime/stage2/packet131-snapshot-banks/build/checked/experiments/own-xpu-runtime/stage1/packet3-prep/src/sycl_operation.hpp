#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet163-full-gate/two-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet163-full-gate/two-card/native-source/repo/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet163-full-gate/two-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/build/checked/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/owner_api.hpp"
#include <sycl/sycl.hpp>
namespace ownrt {
// Internal backend hook. Applications submit through Device::compute so the
// owning ledger, not a borrowed queue, controls event/allocation lifetimes.
struct SyclOperation : Operation {
  virtual sycl::event submit(sycl::queue&, std::span<void* const>,
                            const std::vector<sycl::event>&) const = 0;
};
}
