// chain-bound small kernels: current form vs variants, bitwise + GPU time
#include <sycl/sycl.hpp>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

// softmax with masked terms added as +0 (sum >= +0 always, so x + 0 == x)
template <int NI> struct SoftmaxB {
    int heads;
    void operator()(sycl::nd_item<1> it, const float *sinks, const int32_t *idxs, float *score) const {
        sycl::sub_group sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id();
        const int h = (int)it.get_group_linear_id();
        if (h >= heads) return;
        constexpr int K = NI / 32;
        float *s = score + (size_t)h * NI;
        float v[K];
        int ok[K];
        const float sk = sinks[h];
        float mx = sk;
#pragma unroll
        for (int k = 0; k < K; ++k) {
            ok[k] = idxs[32 * k + lane] >= 0 ? 1 : 0;
            v[k] = s[32 * k + lane];
            if (ok[k]) mx = v[k] > mx ? v[k] : mx;
        }
        for (int w_ = 16; w_; w_ >>= 1) {
            const float o = sycl::select_from_group(sg, mx, lane ^ w_);
            mx = o > mx ? o : mx;
        }
        float sum = sycl::exp(sk - mx);
        float e0[K];
#pragma unroll
        for (int k = 0; k < K; ++k) {
            if (ok[k]) v[k] = sycl::exp(v[k] - mx);
            e0[k] = ok[k] ? v[k] : 0.0f;
        }
#pragma unroll
        for (int k = 0; k < K; ++k)
#pragma unroll
            for (int l2 = 0; l2 < 32; ++l2) sum += sycl::select_from_group(sg, e0[k], l2);
#pragma unroll
        for (int k = 0; k < K; ++k)
            if (ok[k]) s[32 * k + lane] = v[k] / sum;
    }
};
// floor: 640 dependent adds of broadcast values
struct ChainFloor {
    void operator()(sycl::nd_item<1> it, const float *x, float *y) const {
        sycl::sub_group sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id();
        float v[20];
        for (int k = 0; k < 20; ++k) v[k] = x[32 * k + lane];
        float sum = 0;
#pragma unroll
        for (int k = 0; k < 20; ++k)
#pragma unroll
            for (int l2 = 0; l2 < 32; ++l2) sum += sycl::select_from_group(sg, v[k], l2);
        if (lane == 0) y[it.get_group_linear_id()] = sum;
    }
};

int main(int argc, char **argv) {
    int card = argc > 1 ? atoi(argv[1]) : 0;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    sycl::device dev = l0.at(card);
    sycl::context ctx(dev);
    sycl::queue q(ctx, dev, sycl::property_list{sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
    std::mt19937 rng(5);
    auto U = [&](float a, float b) { return std::uniform_real_distribution<float>(a, b)(rng); };
    auto gpu_us = [&](auto submit) {
        for (int i = 0; i < 5; ++i) submit();
        q.wait();
        sycl::event a = submit();
        for (int i = 0; i < 38; ++i) submit();
        sycl::event b = submit();
        b.wait();
        return (b.get_profiling_info<sycl::info::event_profiling::command_end>() -
                a.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3 / 40;
    };
    const int H = 16, NI = 640;
    std::vector<float> sc(H * NI), sinks(H);
    std::vector<int32_t> ix(NI);
    for (auto &v : sc) v = U(-8, 8);
    for (auto &v : sinks) v = U(-2, 2);
    for (int i = 0; i < NI; ++i) ix[i] = (i % 7 == 3) ? -1 : i;
    float *dsc0 = sycl::malloc_device<float>(H * NI, q), *dsc1 = sycl::malloc_device<float>(H * NI, q), *dsk = sycl::malloc_device<float>(H, q);
    int32_t *dix = sycl::malloc_device<int32_t>(NI, q);
    float *fy = sycl::malloc_device<float>(64, q);
    q.memcpy(dsk, sinks.data(), H * 4); q.memcpy(dix, ix.data(), NI * 4); q.wait();
    auto run = [&](auto K, float *d) {
        return q.parallel_for(sycl::nd_range<1>(H * 32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { K(it, dsk, dix, d); });
    };
    // correctness: one pass each from the same input
    q.memcpy(dsc0, sc.data(), H * NI * 4); q.memcpy(dsc1, sc.data(), H * NI * 4); q.wait();
    run(SparseSoftmaxP<640>{H}, dsc0).wait(); run(SoftmaxB<640>{H}, dsc1).wait();
    std::vector<float> a(H * NI), b(H * NI);
    q.memcpy(a.data(), dsc0, H * NI * 4); q.memcpy(b.data(), dsc1, H * NI * 4); q.wait();
    size_t nd = 0; for (int i = 0; i < H * NI; ++i) nd += memcmp(&a[i], &b[i], 4) != 0;
    // timing (in place repeatedly: values change but the work is the same)
    double tA = gpu_us([&] { return run(SparseSoftmaxP<640>{H}, dsc0); });
    double tB = gpu_us([&] { return run(SoftmaxB<640>{H}, dsc1); });
    double tF = gpu_us([&] { return q.parallel_for(sycl::nd_range<1>(H * 32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { ChainFloor{}(it, dsc1, fy); }); });
    std::printf("softmax640 x%d heads: current %.2f us, masked+0 %.2f us (differ %zu of %d), add-chain floor %.2f us\n", H, tA, tB, nd, H * NI, tF);
    // rms norm 5120
    std::vector<float> x(5120), w(5120);
    for (auto &v : x) v = U(-3, 3) * (U(0, 1) < 0.1f ? 30.f : 1.f);
    for (auto &v : w) v = U(0.5, 1.5);
    float *dx = sycl::malloc_device<float>(5120, q), *dw = sycl::malloc_device<float>(5120, q), *dy = sycl::malloc_device<float>(5120, q);
    q.memcpy(dx, x.data(), 5120 * 4); q.memcpy(dw, w.data(), 5120 * 4); q.wait();
    double tN = gpu_us([&] { return q.parallel_for(sycl::nd_range<1>(128, 128), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { RmsNormPS<5120, 4>{}(it, dx, dw, dy); }); });
    double tN1 = gpu_us([&] { return q.parallel_for(sycl::nd_range<1>(32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { RmsNormPS<5120, 1>{}(it, dx, dw, dy); }); });
    double tE = gpu_us([&] { return q.single_task([=] { dy[0] = dx[0]; }); });
    std::printf("rmsnorm5120: S=4 %.2f us, S=1 %.2f us, empty kernel %.2f us\n", tN, tN1, tE);
    return nd != 0;
}
