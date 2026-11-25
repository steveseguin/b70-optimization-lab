// bench_xm3: the plain joint_matrix_apply (no coordinates) on a B operand (16 x 16 bf16, packed).
//   stage 1 (read only): B loaded from local memory with element (k, n) = k * 16 + n; each lane records its
//     elements in the order apply visits them, so the order is known.
//   stage 2 (BENCH_XM3_WRITE=1): B written by apply from each lane's own 8 words of pairs (lane n = column n), in
//     that order, against B loaded from local memory: D = A x B bit for bit, and the time of both (a sub-group per
//     16 columns, 144 steps, M = 1).
// (bench_xm2's apply with coordinates on a B that was never loaded hung the card, 2026-11-25.)
//   bench_xm3 <card>
#include "../src/device.hpp"
#include <sycl/ext/oneapi/matrix/matrix.hpp>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>

using namespace ink;
namespace jm = sycl::ext::oneapi::experimental::matrix;
using bf = sycl::ext::oneapi::bfloat16;

static uint16_t f2bf(float f) {
    uint32_t u;
    std::memcpy(&u, &f, 4);
    return (uint16_t)((u + 0x7fffu + ((u >> 16) & 1u)) >> 16);
}
static float bf2f(uint16_t b) {
    uint32_t u = (uint32_t)b << 16;
    float f;
    std::memcpy(&f, &u, 4);
    return f;
}
constexpr int K = 2304, ST = K / 16;

int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench_xm3 <card>\n"); return 1; }
    Device dev(std::atoi(argv[1]));
    sycl::queue &q = dev.q;
    auto gp = [](auto *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
    // stage 1
    float *dO = sycl::malloc_device<float>(16 * 16, q);
    q.memset(dO, 0, 16 * 16 * 4).wait();
    q.submit([&](sycl::handler &h) {
         sycl::local_accessor<bf, 1> bs(256, h);
         h.parallel_for(sycl::nd_range<1>(16, 16), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
             auto sg = it.get_sub_group();
             const int ln = (int)sg.get_local_linear_id();
             uint32_t *bw = reinterpret_cast<uint32_t *>(&bs[0]);
             // packed layout in memory: word jj * 16 + n holds (k = 2 jj, n) low, (k = 2 jj + 1, n) high
#pragma unroll
             for (int jj = 0; jj < 8; ++jj) {
                 const float lo = (float)((2 * jj) * 16 + ln), hi = (float)((2 * jj + 1) * 16 + ln);
                 bw[jj * 16 + ln] = (sycl::bit_cast<uint32_t>(lo) >> 16) | (sycl::bit_cast<uint32_t>(hi) & 0xFFFF0000u);
             }
             sycl::group_barrier(sg);
             jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed> b;
             jm::joint_matrix_load(sg, b, bs.template get_multi_ptr<sycl::access::decorated::no>(), 32);
             float v[16];
#pragma unroll
             for (int i = 0; i < 16; ++i) v[i] = -1.0f;
             int cnt = 0;
             jm::joint_matrix_apply(sg, b, [&](bf &x) {
                 if (cnt < 16) v[cnt] = (float)x;
                 ++cnt;
             });
#pragma unroll
             for (int i = 0; i < 16; ++i) dO[ln * 16 + i] = v[i];
             if (ln == 0) dO[255] = dO[255]; // keep
             (void)cnt;
         });
     }).wait();
    std::vector<float> O(256);
    q.memcpy(O.data(), dO, 256 * 4).wait();
    std::printf("stage 1: elements of each lane in apply order (value = k * 16 + n):\n");
    bool lane_col = true, k_order = true;
    for (int n = 0; n < 16; ++n) {
        if (n < 3 || n == 15) {
            std::printf("  lane %2d:", n);
            for (int i = 0; i < 16; ++i) std::printf(" %g", O[n * 16 + i]);
            std::printf("\n");
        }
        for (int i = 0; i < 16; ++i) {
            const int v = (int)O[n * 16 + i];
            if (v % 16 != n) lane_col = false;
            if (v / 16 != i) k_order = false;
        }
    }
    std::printf("  lane = column: %s; element i = k i: %s\n", lane_col ? "yes" : "NO", k_order ? "yes" : "NO");
    if (!std::getenv("BENCH_XM3_WRITE") || std::atoi(std::getenv("BENCH_XM3_WRITE")) == 0 || !lane_col || !k_order) return 0;

    // stage 2: G sub-groups, each 16 columns over K = 2304; B values bf16 N(0, 0.05); A one row (M = 1)
    const int G = 4096;
    std::mt19937_64 rng(7);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    std::vector<uint16_t> A((size_t)K), Bv((size_t)G * K * 16);
    for (auto &a : A) a = f2bf(nd(rng));
    for (auto &b : Bv) b = f2bf(nd(rng) * 0.05f);
    uint16_t *dA = sycl::malloc_device<uint16_t>(A.size(), q), *dB = sycl::malloc_device<uint16_t>(Bv.size(), q);
    float *dD = sycl::malloc_device<float>((size_t)G * 16 * 2, q);
    q.memcpy(dA, A.data(), A.size() * 2); q.memcpy(dB, Bv.data(), Bv.size() * 2).wait();
    auto run = [&](int how) {
        double best = 1e9;
        for (int rep = 0; rep < 5; ++rep) {
            auto t0 = std::chrono::steady_clock::now();
            q.submit([&](sycl::handler &h) {
                 sycl::local_accessor<bf, 1> bs(how == 0 ? 4 * 512 : 4 * 256, h);
                 h.parallel_for(sycl::nd_range<1>((size_t)G * 16, 64), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                     auto sg = it.get_sub_group();
                     const int g = (int)(it.get_global_id(0) / 16), ln = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id();
                     const bf *ag = reinterpret_cast<const bf *>(dA);
                     jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 1, 16> c;
                     jm::joint_matrix_fill(sg, c, 0.0f);
                     if (how == 1) { // a defined B to load before each apply: zeros in this sub-group's own area
                         uint32_t *bz = reinterpret_cast<uint32_t *>(&bs[0]) + sgi * 128;
#pragma unroll
                         for (int j = 0; j < 8; ++j) bz[j * 16 + ln] = 0u;
                         sycl::group_barrier(sg);
                     }
                     for (int k = 0; k < ST; ++k) {
                         // lane ln: its column's 16 values of step k (stored column-major per step), as 8 words of pairs
                         const uint32_t *src = reinterpret_cast<const uint32_t *>(dB + ((size_t)g * ST + k) * 256 + ln * 16);
                         uint32_t wv[8];
#pragma unroll
                         for (int j = 0; j < 8; ++j) wv[j] = src[j];
                         jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed> b;
                         if (how == 0) {
                             uint32_t *bw = reinterpret_cast<uint32_t *>(&bs[0]) + sgi * 256 + (k & 1) * 128;
#pragma unroll
                             for (int j = 0; j < 8; ++j) bw[j * 16 + ln] = wv[j];
                             sycl::group_barrier(sg);
                             jm::joint_matrix_load(sg, b, bs.template get_multi_ptr<sycl::access::decorated::no>() + sgi * 512 + (k & 1) * 256, 32);
                         } else {
                             jm::joint_matrix_load(sg, b, bs.template get_multi_ptr<sycl::access::decorated::no>() + sgi * 256, 32); // defined contents
                             int e = 0;
                             jm::joint_matrix_apply(sg, b, [&](bf &x) {
                                 const uint32_t w = wv[(e >> 1) & 7];
                                 x = sycl::bit_cast<bf>((uint16_t)(e & 1 ? w >> 16 : w & 0xFFFFu));
                                 ++e;
                             });
                         }
                         jm::joint_matrix<sycl::sub_group, bf, jm::use::a, 1, 16, jm::layout::row_major> a;
                         jm::joint_matrix_load(sg, a, gp(ag + (size_t)k * 16), K);
                         jm::joint_matrix_mad(sg, c, a, b, c);
                     }
                     jm::joint_matrix_store(sg, c, gp(dD + (size_t)how * G * 16 + (size_t)g * 16), 16, jm::layout::row_major);
                 });
             }).wait();
            best = std::min(best, std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count());
        }
        return best * 1e6;
    };
    // bit check first with a small run of how 1 (it loads a defined B before the apply)
    const double t0 = run(0), t1 = run(1);
    std::vector<float> D((size_t)G * 32);
    q.memcpy(D.data(), dD, D.size() * 4).wait();
    long diff = 0;
    for (int i = 0; i < G * 16; ++i) diff += std::memcmp(&D[i], &D[(size_t)G * 16 + i], 4) != 0;
    // and against a double reference for a few columns
    double maxrel = 0;
    for (int g = 0; g < 4; ++g)
        for (int n = 0; n < 16; ++n) {
            double s = 0, sa = 0;
            for (int k = 0; k < K; ++k) {
                const double p = (double)bf2f(A[k]) * bf2f(Bv[((size_t)g * ST + k / 16) * 256 + n * 16 + k % 16]);
                s += p; sa += std::fabs(p);
            }
            maxrel = std::max(maxrel, std::fabs(D[(size_t)g * 16 + n] - s) / sa);
        }
    std::printf("stage 2: B from local memory %.1f us, B by apply %.1f us; results %s (%ld of %d differ); max error vs double %.2e (x sum|p|)\n",
                t0, t1, diff ? "DIFFER" : "identical", diff, G * 16, maxrel);
    return 0;
}
