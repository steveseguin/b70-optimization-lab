#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/build/checked/experiments/own-xpu-runtime/stage2/packet56-draft-prefix/owner_api.hpp"
#include <sycl/sycl.hpp>
namespace ownrt {
// Internal backend hook. Applications submit through Device::compute so the
// owning ledger, not a borrowed queue, controls event/allocation lifetimes.
struct SyclOperation : Operation {
  virtual sycl::event submit(sycl::queue&, std::span<void* const>,
                            const std::vector<sycl::event>&) const = 0;
};
}
