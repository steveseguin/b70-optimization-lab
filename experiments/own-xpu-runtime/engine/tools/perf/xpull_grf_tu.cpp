// Machine code of the pull exchange kernel (ops41sycl::XchgPull) as the engine launches it (a lambda; the build's
// auto register mode picks 256 registers: every exchange then costs two register-mode changes, tl85 2026-11-11) and
// as a functor pinned to 128 registers (OWN_XPULL_GRF=128). Compile with tools/perf/dump_isa.sh; nothing runs.
#include <sycl/sycl.hpp>
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>
#include "stage2/packet3/kernels/sycl_v41.hpp"
namespace syclex = sycl::ext::oneapi::experimental;
namespace syclintel = sycl::ext::intel::experimental;
struct XPull128 {
    ops41sycl::XchgPull x;
    float *p0, *p1, *p2, *p3, *p4, *p5;
    uint32_t *err;
    void operator()(sycl::nd_item<1> it) const { x(it, p0, p1, p2, p3, p4, p5, err); }
    auto get(syclex::properties_tag) const { return syclex::properties{syclintel::grf_size<128>, syclex::sub_group_size<32>}; }
};
int main() {
    sycl::queue q;
    ops41sycl::XchgPull x{};
    float *p = sycl::malloc_device<float>(64, q);
    uint32_t *e = sycl::malloc_device<uint32_t>(64, q);
    q.parallel_for(sycl::nd_range<1>(256, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
        x(it, p, p, p, p, p, p, e);
    });
    q.parallel_for(sycl::nd_range<1>(256, 256), XPull128{x, p, p, p, p, p, p, e});
    q.wait();
    return 0;
}
