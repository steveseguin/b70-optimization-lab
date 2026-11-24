// bench_fma: the card's FP32 multiply-add rate as kernels see it: K independent chains per lane, the multiplier
// broadcast from another lane (select_from_group with a constant index, as the tile kernels do), work-groups of WG.
//   bench_fma <card>
#include "../src/device.hpp"
#include <cstdio>

using namespace ink;

template <int K, int WG> double run(sycl::queue &q, float *out, int groups, int iters) {
    auto go = [&] {
        q.parallel_for(sycl::nd_range<1>((size_t)groups * WG, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
            auto sg = it.get_sub_group();
            const int lane = (int)sg.get_local_linear_id();
            float a[K];
#pragma unroll
            for (int k = 0; k < K; ++k) a[k] = (float)(lane + k) * 1e-3f;
            float x = 1.0f + (float)it.get_global_id(0) * 1e-9f, w = 0.999f - (float)lane * 1e-6f;
            for (int i = 0; i < iters; ++i) {
#pragma unroll
                for (int u = 0; u < 16; ++u) {
                    const float wb = sycl::select_from_group(sg, w, u);
#pragma unroll
                    for (int k = 0; k < K; ++k) a[k] = sycl::fma(wb, x, a[k]);
                }
                x = x * 0.9999f;
            }
            float s = 0.0f;
#pragma unroll
            for (int k = 0; k < K; ++k) s += a[k];
            out[it.get_global_id(0)] = s;
        });
    };
    go(); q.wait();
    const double t0 = now_s();
    for (int r = 0; r < 5; ++r) go();
    q.wait();
    const double t = (now_s() - t0) / 5;
    return (double)groups * WG * iters * 16 * K / t / 1e12; // T multiply-adds per second
}

// the tile pattern: chain k multiplies by its own weight register (wk broadcast from lane u) and the lane's input xs[u]
// (16 per lane, distinct registers), as tile_dots' rows j and values i
template <int K, int WG> double run_tile(sycl::queue &q, float *out, int groups, int iters) {
    auto go = [&] {
        q.parallel_for(sycl::nd_range<1>((size_t)groups * WG, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
            auto sg = it.get_sub_group();
            const int lane = (int)sg.get_local_linear_id();
            float a[K], w[K], xs[16];
#pragma unroll
            for (int k = 0; k < K; ++k) { a[k] = (float)(lane + k) * 1e-3f; w[k] = 0.999f - (float)(lane + 3 * k) * 1e-6f; }
#pragma unroll
            for (int u = 0; u < 16; ++u) xs[u] = 1.0f + (float)(it.get_global_id(0) + u) * 1e-9f;
            for (int i = 0; i < iters; ++i) {
#pragma unroll
                for (int u = 0; u < 16; ++u)
#pragma unroll
                    for (int k = 0; k < K; ++k) a[k] = sycl::fma(sycl::select_from_group(sg, w[k], u), xs[u], a[k]);
#pragma unroll
                for (int u = 0; u < 16; ++u) xs[u] = xs[u] * 0.9999f;
            }
            float s = 0.0f;
#pragma unroll
            for (int k = 0; k < K; ++k) s += a[k];
            out[it.get_global_id(0)] = s;
        });
    };
    go(); q.wait();
    const double t0 = now_s();
    for (int r = 0; r < 5; ++r) go();
    q.wait();
    const double t = (now_s() - t0) / 5;
    return (double)groups * WG * iters * 16 * K / t / 1e12;
}

int main(int argc, char **argv) {
    Device d(argc > 1 ? std::atoi(argv[1]) : 1);
    const int groups16 = 32 * 64 * 8, iters = 256;
    float *out = d.alloc<float>((size_t)groups16 * 16);
#define R(K) std::printf("K %2d  WG 16: %5.2f  WG 128: %5.2f  WG 256: %5.2f TMAC/s\n", K, run<K, 16>(d.q, out, groups16, iters), \
                         run<K, 128>(d.q, out, groups16 / 8, iters), run<K, 256>(d.q, out, groups16 / 16, iters));
    R(1) R(2) R(4) R(8) R(16) R(24) R(32)
#define T(K) std::printf("tile pattern K %2d  WG 16: %5.2f  WG 128: %5.2f  WG 512: %5.2f TMAC/s\n", K, run_tile<K, 16>(d.q, out, groups16, iters), \
                         run_tile<K, 128>(d.q, out, groups16 / 8, iters), run_tile<K, 512>(d.q, out, groups16 / 32, iters));
    T(2) T(4) T(8) T(12) T(16) T(24)
    return 0;
}
