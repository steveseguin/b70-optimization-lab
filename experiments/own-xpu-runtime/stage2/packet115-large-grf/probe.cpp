#include <sycl/sycl.hpp>
// Offline compiler capability check only. This file has no executable entry.
sycl::event probe(sycl::queue& q, float* dst, const float* src) {
    return q.parallel_for<class Packet115ModuleProbe>(sycl::range<1>(256), [=](sycl::id<1> i) {
        dst[i] = src[i] * 1.125f + 0.25f;
    });
}
