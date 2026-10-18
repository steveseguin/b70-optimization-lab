#pragma once
#include <sycl/sycl.hpp>
#include <span>
#include <vector>
namespace p115_image {
using Submit = sycl::event (*)(unsigned, bool, sycl::queue&, std::span<void*const>, const std::vector<sycl::event>&, unsigned, unsigned, unsigned);
sycl::event normal(unsigned, bool, sycl::queue&, std::span<void*const>, const std::vector<sycl::event>&, unsigned=640, unsigned=10, unsigned=512);
sycl::event large(unsigned, bool, sycl::queue&, std::span<void*const>, const std::vector<sycl::event>&, unsigned=640, unsigned=10, unsigned=512);
}
