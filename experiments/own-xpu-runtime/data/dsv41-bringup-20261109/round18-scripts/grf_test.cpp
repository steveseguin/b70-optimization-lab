// tiny register-pressure kernel: does the AOT flag switch spilling kernels to the 256-register mode?
#include <sycl/sycl.hpp>
#include <cstdio>
int main() {
    sycl::queue q;
    float *x = sycl::malloc_device<float>(1 << 20, q), *y = sycl::malloc_device<float>(1 << 14, q);
    q.parallel_for(sycl::nd_range<1>(1 << 14, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
        const size_t i = it.get_global_id(0);
        float a[160];
#pragma unroll
        for (int k = 0; k < 160; ++k) a[k] = x[(i * 7 + k * 131) & ((1 << 20) - 1)];
        float s = 0;
#pragma unroll
        for (int r = 0; r < 4; ++r)
#pragma unroll
            for (int k = 0; k < 160; ++k) s = s + a[k] * a[(k * 17 + r) % 160];
        y[i] = s;
    }).wait();
    std::printf("ok\n");
}
