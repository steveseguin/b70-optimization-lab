#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aq-onecard-split/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aq-onecard-split/frozen-inputs/repo/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58aq-onecard-split/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/owner_api.hpp"
#include <sycl/sycl.hpp>
namespace ownrt {
// Internal backend hook. Applications submit through Device::compute so the
// owning ledger, not a borrowed queue, controls event/allocation lifetimes.
struct SyclOperation : Operation {
  virtual sycl::event submit(sycl::queue&, std::span<void* const>,
                            const std::vector<sycl::event>&) const = 0;
};
}
