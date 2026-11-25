// bench_xdot: accuracy of 2304-long dot products (an expert gate|up row) computed on the matrix engines with the
// inputs split into three bf16 parts (weights exactly bf16, like NVFP4's code x scale), for several orders of the sums,
// against the exact value (long double) and against the engine's FP32 order today (gemv1_rows: lane l takes chunks
// l, l+16, ..., each chunk's 32 products in order from 0.0f with fma, the lane sums in chunk order, xor butterfly).
//   bench_xdot <card> [groups]
// Layouts (8 tokens x 16 outputs per sub-group, K steps of 16):
//   0 chain: one accumulator, for each K step the three parts in turn
//   1 parts: one accumulator per part over all K, then (a1 + a2) + a3
//   2 seg16: chain within segments of 16 K steps (256 values), segment sums added in order into a total
//   3 seg9:  the same with segments of 9 K steps (144 values; 16 segments)
//   4 segp:  segments of 16 K steps, one accumulator per part in a segment, ((a1 + a2) + a3) added into the total
//   5 segr16: segments of 16 K steps, one accumulator: all third parts, then second, then first; 8 segr9 the same, 9 steps
//   6 seg8p: segp with segments of 8 K steps; 7 segp23: segments of 16, first parts alone, second + third together
#include "../src/device.hpp"
#include <sycl/ext/oneapi/matrix/matrix.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>

using namespace ink;
namespace jm = sycl::ext::oneapi::experimental::matrix;
namespace jmi = sycl::ext::intel::experimental::matrix;
using bf = sycl::ext::oneapi::bfloat16;

static uint16_t f2bf_rn(float f) {
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

constexpr int K = 2304, NL = 9;

template <int L> static void run(sycl::queue &q, const uint16_t *X, const uint16_t *B, float *Y, int G) {
    // X: G x 3 parts x 8 rows x K (bf16); B: G x K x 16 (row major, bf16); Y: G x 8 x 16
    q.submit([&](sycl::handler &h) {
     sycl::local_accessor<float, 1> sl(256, h);
     h.parallel_for(sycl::nd_range<1>((size_t)G * 16, 16), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
         auto sg = it.get_sub_group();
         const int g = (int)it.get_group(0);
         auto gp = [](auto *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
         const bf *xg = (const bf *)X + (size_t)g * 3 * 8 * K;
         const bf *bg = (const bf *)B + (size_t)g * K * 16;
         using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, 8, 16, jm::layout::row_major>;
         using Bm = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::row_major>;
         using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16>;
         auto ld = [&](A &a, int p, int k) { jm::joint_matrix_load(sg, a, gp(xg + (size_t)p * 8 * K + k), K); };
         auto lb = [&](Bm &b, int k) { jm::joint_matrix_load(sg, b, gp(bg + (size_t)k * 16), 16); };
         C tot;
         jm::joint_matrix_fill(sg, tot, 0.0f);
         auto lp = sl.template get_multi_ptr<sycl::access::decorated::no>();
         const int ln = (int)sg.get_local_linear_id();
         auto addm = [&](C &dst, C &src) { // dst = dst + src, element by element (through local memory)
             jm::joint_matrix_store(sg, dst, lp, 16, jm::layout::row_major);
             jm::joint_matrix_store(sg, src, lp + 128, 16, jm::layout::row_major);
             sycl::group_barrier(sg);
             for (int i = ln; i < 128; i += 16) sl[i] = sl[i] + sl[128 + i];
             sycl::group_barrier(sg);
             jm::joint_matrix_load(sg, dst, lp, 16, jm::layout::row_major);
             sycl::group_barrier(sg);
         };
         if constexpr (L == 0) {
             for (int k = 0; k < K; k += 16) {
                 Bm b; lb(b, k);
                 for (int p = 0; p < 3; ++p) { A a; ld(a, p, k); jm::joint_matrix_mad(sg, tot, a, b, tot); }
             }
         } else if constexpr (L == 1) {
             C c1, c2, c3;
             jm::joint_matrix_fill(sg, c1, 0.0f); jm::joint_matrix_fill(sg, c2, 0.0f); jm::joint_matrix_fill(sg, c3, 0.0f);
             for (int k = 0; k < K; k += 16) {
                 Bm b; lb(b, k);
                 A a; ld(a, 0, k); jm::joint_matrix_mad(sg, c1, a, b, c1);
                 ld(a, 1, k); jm::joint_matrix_mad(sg, c2, a, b, c2);
                 ld(a, 2, k); jm::joint_matrix_mad(sg, c3, a, b, c3);
             }
             addm(c1, c2);
             addm(c1, c3);
             addm(tot, c1); // 0 + v = v
         } else if constexpr (L == 2 || L == 3) {
             constexpr int SEG = L == 2 ? 16 : 9;
             for (int k0 = 0; k0 < K; k0 += 16 * SEG) {
                 C s;
                 jm::joint_matrix_fill(sg, s, 0.0f);
                 for (int k = k0; k < sycl::min(K, k0 + 16 * SEG); k += 16) {
                     Bm b; lb(b, k);
                     for (int p = 0; p < 3; ++p) { A a; ld(a, p, k); jm::joint_matrix_mad(sg, s, a, b, s); }
                 }
                 addm(tot, s);
             }
         } else if constexpr (L == 5 || L == 8) { // segments: the third parts, then the second, then the first, one accumulator
             constexpr int SEG = L == 5 ? 16 : 9;
             for (int k0 = 0; k0 < K; k0 += 16 * SEG) {
                 C s;
                 jm::joint_matrix_fill(sg, s, 0.0f);
                 for (int p = 2; p >= 0; --p)
                     for (int k = k0; k < sycl::min(K, k0 + 16 * SEG); k += 16) {
                         Bm b; lb(b, k);
                         A a; ld(a, p, k); jm::joint_matrix_mad(sg, s, a, b, s);
                     }
                 addm(tot, s);
             }
         } else if constexpr (L == 7) { // segments of 16: first parts in one accumulator, second and third in another
             constexpr int SEG = 16;
             for (int k0 = 0; k0 < K; k0 += 16 * SEG) {
                 C c1, c2;
                 jm::joint_matrix_fill(sg, c1, 0.0f); jm::joint_matrix_fill(sg, c2, 0.0f);
                 for (int k = k0; k < sycl::min(K, k0 + 16 * SEG); k += 16) {
                     Bm b; lb(b, k);
                     A a; ld(a, 0, k); jm::joint_matrix_mad(sg, c1, a, b, c1);
                     ld(a, 1, k); jm::joint_matrix_mad(sg, c2, a, b, c2);
                     ld(a, 2, k); jm::joint_matrix_mad(sg, c2, a, b, c2);
                 }
                 addm(c1, c2);
                 addm(tot, c1);
             }
         } else {
             constexpr int SEG = L == 6 ? 8 : 16;
             for (int k0 = 0; k0 < K; k0 += 16 * SEG) {
                 C c1, c2, c3;
                 jm::joint_matrix_fill(sg, c1, 0.0f); jm::joint_matrix_fill(sg, c2, 0.0f); jm::joint_matrix_fill(sg, c3, 0.0f);
                 for (int k = k0; k < sycl::min(K, k0 + 16 * SEG); k += 16) {
                     Bm b; lb(b, k);
                     A a; ld(a, 0, k); jm::joint_matrix_mad(sg, c1, a, b, c1);
                     ld(a, 1, k); jm::joint_matrix_mad(sg, c2, a, b, c2);
                     ld(a, 2, k); jm::joint_matrix_mad(sg, c3, a, b, c3);
                 }
                 addm(c1, c2);
                 addm(c1, c3);
                 addm(tot, c1);
             }
         }
         jm::joint_matrix_store(sg, tot, gp(Y + (size_t)g * 128), 16, jm::layout::row_major);
     });
    }).wait();
}

int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench_xdot <card> [groups]\n"); return 1; }
    Device dev(std::atoi(argv[1]));
    sycl::queue &q = dev.q;
    const int G = argc > 2 ? std::atoi(argv[2]) : 256;
    std::mt19937_64 rng(777);
    // weights: E2M1 values x an E4M3-like scale per 16 (exact in bf16); inputs: N(0,1), 1 in 64 times 20
    const float e2m1[8] = {0.0f, 0.5f, 1.0f, 1.5f, 2.0f, 3.0f, 4.0f, 6.0f};
    std::uniform_int_distribution<int> code(0, 15), sexp(-10, -5), smant(0, 7), out(0, 63);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    std::vector<uint16_t> X((size_t)G * 3 * 8 * K), B((size_t)G * K * 16);
    std::vector<float> xf((size_t)G * 8 * K), wf((size_t)G * 16 * K);
    for (int g = 0; g < G; ++g) {
        for (int n = 0; n < 16; ++n)
            for (int k0 = 0; k0 < K; k0 += 16) {
                const float sc = std::ldexp(1.0f + smant(rng) / 8.0f, sexp(rng));
                for (int k = k0; k < k0 + 16; ++k) {
                    const int c = code(rng);
                    const float w = (c & 8 ? -1.0f : 1.0f) * e2m1[c & 7] * sc;
                    wf[((size_t)g * 16 + n) * K + k] = w;
                    B[((size_t)g * K + k) * 16 + n] = f2bf_rn(w);
                    if (bf2f(f2bf_rn(w)) != w) { std::fprintf(stderr, "weight not exact in bf16\n"); return 2; }
                }
            }
        for (int r = 0; r < 8; ++r)
            for (int k = 0; k < K; ++k) {
                float x = nd(rng);
                if (out(rng) == 0) x *= 20.0f;
                xf[((size_t)g * 8 + r) * K + k] = x;
                const float x1 = bf2f(f2bf_rn(x)), r1 = x - x1, x2 = bf2f(f2bf_rn(r1)), x3 = bf2f(f2bf_rn(r1 - x2));
                X[(((size_t)g * 3 + 0) * 8 + r) * K + k] = f2bf_rn(x1);
                X[(((size_t)g * 3 + 1) * 8 + r) * K + k] = f2bf_rn(x2);
                X[(((size_t)g * 3 + 2) * 8 + r) * K + k] = f2bf_rn(x3);
                if ((double)x1 + x2 + x3 != (double)x) { std::fprintf(stderr, "split not exact\n"); return 2; }
            }
    }
    uint16_t *dX = sycl::malloc_device<uint16_t>(X.size(), q), *dB = sycl::malloc_device<uint16_t>(B.size(), q);
    float *dY = sycl::malloc_device<float>((size_t)G * 128, q);
    q.memcpy(dX, X.data(), X.size() * 2); q.memcpy(dB, B.data(), B.size() * 2).wait();
    std::vector<std::vector<float>> Y(NL, std::vector<float>((size_t)G * 128));
    auto get = [&](int l) { q.memcpy(Y[l].data(), dY, (size_t)G * 128 * 4).wait(); };
    run<0>(q, dX, dB, dY, G); get(0);
    run<1>(q, dX, dB, dY, G); get(1);
    run<2>(q, dX, dB, dY, G); get(2);
    run<3>(q, dX, dB, dY, G); get(3);
    run<4>(q, dX, dB, dY, G); get(4);
    run<5>(q, dX, dB, dY, G); get(5);
    run<6>(q, dX, dB, dY, G); get(6);
    run<7>(q, dX, dB, dY, G); get(7);
    run<8>(q, dX, dB, dY, G); get(8);
    // the same run again (determinism) and with the 8 token rows of one group cut to 1 (row 0 only)
    std::vector<float> Yr((size_t)G * 128);
    run<2>(q, dX, dB, dY, G);
    q.memcpy(Yr.data(), dY, Yr.size() * 4).wait();
    std::printf("seg16 repeat: %s\n", std::memcmp(Yr.data(), Y[2].data(), Yr.size() * 4) ? "DIFFERENT" : "identical");
    const char *names[NL + 1] = {"chain", "parts", "seg16", "seg9", "segp", "segr16", "seg8p", "segp23", "segr9", "fp32 today"};
    double esum[NL + 1] = {0}, emax[NL + 1] = {0}, rsum[NL + 1] = {0}, rmax[NL + 1] = {0};
    long n = 0, worse[NL + 1] = {0};
    std::vector<double> ev[NL + 1];
    for (int g = 0; g < G; ++g)
        for (int r = 0; r < 8; ++r)
            for (int o = 0; o < 16; ++o) {
                const float *x = &xf[((size_t)g * 8 + r) * K];
                const float *w = &wf[((size_t)g * 16 + o) * K];
                long double ex = 0, l1 = 0;
                for (int k = 0; k < K; ++k) { ex += (long double)x[k] * w[k]; l1 += std::fabs((long double)x[k] * w[k]); }
                // today's FP32 order
                float acc[16] = {0};
                for (int l = 0; l < 16; ++l)
                    for (int c = l; c < K / 32; c += 16) {
                        float s = 0.0f;
                        for (int i = 0; i < 32; ++i) s = std::fmaf(w[32 * c + i], x[32 * c + i], s);
                        acc[l] += s;
                    }
                for (int m = 8; m >= 1; m >>= 1) {
                    float t[16];
                    for (int l = 0; l < 16; ++l) t[l] = acc[l] + acc[l ^ m];
                    std::memcpy(acc, t, sizeof t);
                }
                int e;
                std::frexp((double)ex, &e);
                const double ulp = std::ldexp(1.0, e - 24), eps = std::ldexp(1.0, -24);
                for (int l = 0; l <= NL; ++l) {
                    const float y = l < NL ? Y[l][(size_t)g * 128 + r * 16 + o] : acc[0];
                    const double err = std::fabs((double)((long double)y - ex));
                    const double eu = err / ulp, er = err / (eps * (double)l1);
                    esum[l] += eu; emax[l] = std::max(emax[l], eu); rsum[l] += er; rmax[l] = std::max(rmax[l], er);
                    ev[l].push_back(eu);
                }
                ++n;
            }
    std::printf("%ld dot products of %d (8 tokens x 16 outputs x %d groups); error in ulps of the exact value, and relative to "
                "2^-24 x sum |w x|:\n", n, K, G);
    for (int l = 0; l <= NL; ++l) {
        std::sort(ev[l].begin(), ev[l].end());
        std::printf("  %-11s ulps: mean %7.3f median %6.3f p99 %8.3f max %10.3f | rel to sum|wx|: mean %.4f max %.4f\n", names[l],
                    esum[l] / n, ev[l][n / 2], ev[l][(size_t)(n * 0.99)], emax[l], rsum[l] / n, rmax[l]);
    }
    return 0;
}
