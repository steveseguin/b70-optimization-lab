#pragma once
#include "owner.hpp"
#include <sycl/sycl.hpp>
namespace ownrt {
// Internal backend hook. Applications submit through Device::compute so the
// owning ledger, not a borrowed queue, controls event/allocation lifetimes.
struct SyclOperation : Operation {
  virtual sycl::event submit(sycl::queue&, std::span<void* const>,
                            const std::vector<sycl::event>&) const = 0;
};
}
