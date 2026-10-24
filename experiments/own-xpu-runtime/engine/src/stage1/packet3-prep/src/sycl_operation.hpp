#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet194-expert-diet-engine/owner_api.hpp"
#include <sycl/sycl.hpp>
namespace ownrt {
// Internal backend hook. Applications submit through Device::compute so the
// owning ledger, not a borrowed queue, controls event/allocation lifetimes.
struct SyclOperation : Operation {
  virtual sycl::event submit(sycl::queue&, std::span<void* const>,
                            const std::vector<sycl::event>&) const = 0;
};
}
