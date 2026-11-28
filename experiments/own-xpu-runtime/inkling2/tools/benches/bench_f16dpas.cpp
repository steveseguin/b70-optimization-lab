// bench_f16dpas: can the matrix engines' fp16 multiply-adds give exact products for attention scores?
// (keys are fp16 in the cache, so exact as one fp16 part; a query row would be three fp16 parts, each with its own
// power-of-two scale). Questions:
//   1. subnormal fp16 operands: does one instruction use them as they are, or flush them to zero? Each test row has
//      one nonzero product, so the exact result is a single fp32 value: a subnormal x normal, normal x subnormal,
//      subnormal x subnormal (the product is a normal fp32), and normal x normal for control;
//   2. one instruction's sum of 16 random fp16 products against the exact sum rounded once (as bench_xmx for bf16);
//   3. the rate and energy of fp16 products against bf16 (same shape as bench_xmx's gemm rate).
//   bench_f16dpas <card> [tests]
#include "../../src/device.hpp"
#include <sycl/ext/oneapi/matrix/matrix.hpp>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>

using namespace ink;
namespace jm = sycl::ext::oneapi::experimental::matrix;
using bf = sycl::ext::oneapi::bfloat16;
using hf = sycl::half;

static uint16_t h_bits(float f) { hf h(f); uint16_t u; std::memcpy(&u, &h, 2); return u; }
static float h_val(uint16_t u) { hf h; std::memcpy(&h, &u, 2); return (float)h; }

// one sub-group per test: D = A B (A 8 x 16, B 16 x 16 row major, fp16; D 8 x 16 fp32)
static void mad_f16(sycl::queue &q, const uint16_t *A, const uint16_t *B, float *D, int T) {
    q.parallel_for(sycl::nd_range<1>((size_t)T * 16, 16), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
         auto sg = it.get_sub_group();
         const int t = (int)it.get_group(0);
         auto g = [](auto *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
         jm::joint_matrix<sycl::sub_group, hf, jm::use::a, 8, 16, jm::layout::row_major> a;
         jm::joint_matrix<sycl::sub_group, hf, jm::use::b, 16, 16, jm::layout::row_major> b;
         jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16> c;
         jm::joint_matrix_fill(sg, c, 0.0f);
         jm::joint_matrix_load(sg, a, g((const hf *)A + (size_t)t * 128), 16);
         jm::joint_matrix_load(sg, b, g((const hf *)B + (size_t)t * 256), 16);
         jm::joint_matrix_mad(sg, c, a, b, c);
         jm::joint_matrix_store(sg, c, g(D + (size_t)t * 128), 16, jm::layout::row_major);
     }).wait();
}

template <class E, bool CM = false> static double gemm_rate(sycl::queue &q, const Device &dev, int M, int N, int K, uint16_t one_a, uint16_t one_b,
                                           float expect, double &pj) {
    uint16_t *A = sycl::malloc_device<uint16_t>((size_t)M * K, q), *B = sycl::malloc_device<uint16_t>((size_t)K * N, q);
    float *Cm = sycl::malloc_device<float>((size_t)M * N, q);
    q.fill(A, one_a, (size_t)M * K).wait();
    q.fill(B, one_b, (size_t)K * N).wait();
    const int TMR = 32, TNC = 32, SGW = 8;
    const size_t nsg = (size_t)(M / TMR) * (N / TNC);
    auto go = [&] {
        q.parallel_for(sycl::nd_range<1>(nsg * 16, SGW * 16), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
            auto sg = it.get_sub_group();
            const size_t s = it.get_global_id(0) / 16;
            const int mt = (int)(s / (N / TNC)), nt = (int)(s % (N / TNC));
            auto g = [](auto *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
            jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16> acc[4][2];
#pragma unroll
            for (int i = 0; i < 4; ++i)
#pragma unroll
                for (int j = 0; j < 2; ++j) jm::joint_matrix_fill(sg, acc[i][j], 0.0f);
            for (int k = 0; k < K; k += 16) {
                jm::joint_matrix<sycl::sub_group, E, jm::use::a, 8, 16, jm::layout::row_major> a[4];
                jm::joint_matrix<sycl::sub_group, E, jm::use::b, 16, 16, CM ? jm::layout::col_major : jm::layout::ext_intel_packed> b[2];
#pragma unroll
                for (int i = 0; i < 4; ++i) jm::joint_matrix_load(sg, a[i], g((const E *)A + (size_t)(mt * TMR + 8 * i) * K + k), K);
#pragma unroll
                for (int j = 0; j < 2; ++j) {
                    if constexpr (CM) jm::joint_matrix_load(sg, b[j], g((const E *)B + (size_t)(nt * TNC + 16 * j) * K + k), K);
                    else jm::joint_matrix_load(sg, b[j], g((const E *)B + (size_t)(k / 2) * N * 2 + (size_t)(nt * TNC + 16 * j) * 2), N * 2);
                }
#pragma unroll
                for (int i = 0; i < 4; ++i)
#pragma unroll
                    for (int j = 0; j < 2; ++j) jm::joint_matrix_mad(sg, acc[i][j], a[i], b[j], acc[i][j]);
            }
#pragma unroll
            for (int i = 0; i < 4; ++i)
#pragma unroll
                for (int j = 0; j < 2; ++j)
                    jm::joint_matrix_store(sg, acc[i][j], g(Cm + (size_t)(mt * TMR + 8 * i) * N + nt * TNC + 16 * j), N, jm::layout::row_major);
        });
    };
    go(); q.wait();
    const int reps = 20;
    const double e0 = dev.energy_j(), t0 = now_s();
    for (int r = 0; r < reps; ++r) go();
    q.wait();
    const double t = (now_s() - t0) / reps, macs = (double)M * N * K;
    pj = (dev.energy_j() - e0) / reps / macs * 1e12;
    float c0 = 0;
    q.memcpy(&c0, Cm, 4).wait();
    if (std::fabs(c0 - expect) > 1e-3f * std::fabs(expect)) std::printf("  gemm check: C[0] = %g, expected %g\n", c0, (double)expect);
    sycl::free(A, q); sycl::free(B, q); sycl::free(Cm, q);
    return macs / t / 1e12;
}

// tf32: A 8 x 8, B 8 x 16 (fp32 storage, values with 10 mantissa bits), K steps of 8; same tile per sub-group as above
static double gemm_rate_tf32(sycl::queue &q, const Device &dev, int M, int N, int K, double &pj) {
    float *A = sycl::malloc_device<float>((size_t)M * K, q), *B = sycl::malloc_device<float>((size_t)K * N, q);
    float *Cm = sycl::malloc_device<float>((size_t)M * N, q);
    q.fill(A, 1.0f, (size_t)M * K).wait();
    q.fill(B, 0.0078125f, (size_t)K * N).wait();
    const int TMR = 32, TNC = 32, SGW = 8;
    const size_t nsg = (size_t)(M / TMR) * (N / TNC);
    using T32 = jm::precision::tf32;
    auto go = [&] {
        q.parallel_for(sycl::nd_range<1>(nsg * 16, SGW * 16), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
            auto sg = it.get_sub_group();
            const size_t s = it.get_global_id(0) / 16;
            const int mt = (int)(s / (N / TNC)), nt = (int)(s % (N / TNC));
            auto g = [](auto *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
            jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16> acc[4][2];
#pragma unroll
            for (int i = 0; i < 4; ++i)
#pragma unroll
                for (int j = 0; j < 2; ++j) jm::joint_matrix_fill(sg, acc[i][j], 0.0f);
            for (int k = 0; k < K; k += 8) {
                jm::joint_matrix<sycl::sub_group, T32, jm::use::a, 8, 8, jm::layout::row_major> a[4];
                jm::joint_matrix<sycl::sub_group, T32, jm::use::b, 8, 16, jm::layout::row_major> b[2];
#pragma unroll
                for (int i = 0; i < 4; ++i) jm::joint_matrix_load(sg, a[i], g(A + (size_t)(mt * TMR + 8 * i) * K + k), K);
#pragma unroll
                for (int j = 0; j < 2; ++j) jm::joint_matrix_load(sg, b[j], g(B + (size_t)k * N + nt * TNC + 16 * j), N);
#pragma unroll
                for (int i = 0; i < 4; ++i)
#pragma unroll
                    for (int j = 0; j < 2; ++j) jm::joint_matrix_mad(sg, acc[i][j], a[i], b[j], acc[i][j]);
            }
#pragma unroll
            for (int i = 0; i < 4; ++i)
#pragma unroll
                for (int j = 0; j < 2; ++j)
                    jm::joint_matrix_store(sg, acc[i][j], g(Cm + (size_t)(mt * TMR + 8 * i) * N + nt * TNC + 16 * j), N, jm::layout::row_major);
        });
    };
    go(); q.wait();
    const int reps = 10;
    const double e0 = dev.energy_j(), t0 = now_s();
    for (int r = 0; r < reps; ++r) go();
    q.wait();
    const double t = (now_s() - t0) / reps, macs = (double)M * N * K;
    pj = (dev.energy_j() - e0) / reps / macs * 1e12;
    float c0 = 0;
    q.memcpy(&c0, Cm, 4).wait();
    if (std::fabs(c0 - K / 128.0f) > 1e-3f) std::printf("  tf32 gemm check: C[0] = %g, expected %g\n", c0, K / 128.0);
    sycl::free(A, q); sycl::free(B, q); sycl::free(Cm, q);
    return macs / t / 1e12;
}

int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench_f16dpas <card> [tests]\n"); return 1; }
    Device dev(std::atoi(argv[1]));
    sycl::queue &q = dev.q;
    const int T = argc > 2 ? std::atoi(argv[2]) : 4096;
    std::mt19937_64 rng(777);
    uint16_t *dA = sycl::malloc_device<uint16_t>((size_t)T * 128, q), *dB = sycl::malloc_device<uint16_t>((size_t)T * 256, q);
    float *dD = sycl::malloc_device<float>((size_t)T * 128, q);
    std::vector<uint16_t> A((size_t)T * 128), B((size_t)T * 256);
    std::vector<float> D((size_t)T * 128);
    // 1. one nonzero product per row: row r of test t uses A[r][k] and B[k][n] for n = 0..15 (other A entries zero)
    std::uniform_int_distribution<int> kd(0, 15), sgn(0, 1);
    std::uniform_int_distribution<int> sub(1, 1023), mant(0, 1023), en(-14, 15);
    auto subn = [&] { return (uint16_t)(sub(rng) | (sgn(rng) << 15)); };                       // fp16 subnormal bits
    auto norm = [&] { return h_bits(std::ldexp(1.0f + mant(rng) / 1024.0f, en(rng)) * (sgn(rng) ? -1.0f : 1.0f)); };
    const char *names[4] = {"subnormal x normal", "normal x subnormal", "subnormal x subnormal", "normal x normal"};
    for (int kind = 0; kind < 4; ++kind) {
        std::vector<int> kk((size_t)T * 8);
        std::fill(A.begin(), A.end(), 0);
        for (int t = 0; t < T; ++t) {
            for (int r = 0; r < 8; ++r) {
                const int k = kd(rng);
                kk[(size_t)t * 8 + r] = k;
                A[(size_t)t * 128 + r * 16 + k] = (kind == 0 || kind == 2) ? subn() : norm();
            }
            for (int i = 0; i < 256; ++i) B[(size_t)t * 256 + i] = (kind == 1 || kind == 2) ? subn() : norm();
        }
        q.memcpy(dA, A.data(), A.size() * 2).wait();
        q.memcpy(dB, B.data(), B.size() * 2).wait();
        mad_f16(q, dA, dB, dD, T);
        q.memcpy(D.data(), dD, D.size() * 4).wait();
        long same = 0, zero = 0, other = 0;
        for (int t = 0; t < T; ++t)
            for (int r = 0; r < 8; ++r) {
                const int k = kk[(size_t)t * 8 + r];
                const double a = h_val(A[(size_t)t * 128 + r * 16 + k]);
                for (int n = 0; n < 16; ++n) {
                    const double b = h_val(B[(size_t)t * 256 + k * 16 + n]);
                    const float ex = (float)(a * b), got = D[(size_t)t * 128 + r * 16 + n]; // a b exact in fp32
                    if (got == ex) ++same;
                    else if (got == 0.0f) ++zero;
                    else ++other;
                }
            }
        std::printf("1. %-22s: %ld exact, %ld zero (flushed), %ld other, of %ld\n", names[kind], same, zero, other, (long)T * 128);
    }
    // 2. 16 random products per element (exponents -14..15, subnormals mixed in at 1 in 8): one rounding of the exact sum?
    {
        std::uniform_int_distribution<int> one8(0, 7);
        for (auto &v : A) v = one8(rng) ? norm() : subn();
        for (auto &v : B) v = one8(rng) ? norm() : subn();
        q.memcpy(dA, A.data(), A.size() * 2).wait();
        q.memcpy(dB, B.data(), B.size() * 2).wait();
        mad_f16(q, dA, dB, dD, T);
        q.memcpy(D.data(), dD, D.size() * 4).wait();
        long once = 0, nz = 0;
        double err = 0, errc = 0;
        for (int t = 0; t < T; ++t)
            for (int r = 0; r < 8; ++r)
                for (int n = 0; n < 16; ++n) {
                    double s = 0, sa = 0; // exact: products have <= 22 bits and exponents within 2^-48..2^32: double holds the sum
                    float chain = 0.0f;
                    for (int k = 0; k < 16; ++k) {
                        const double p = (double)h_val(A[(size_t)t * 128 + r * 16 + k]) * h_val(B[(size_t)t * 256 + k * 16 + n]);
                        s += p; sa += std::fabs(p);
                        chain = std::fma(h_val(A[(size_t)t * 128 + r * 16 + k]), h_val(B[(size_t)t * 256 + k * 16 + n]), chain);
                    }
                    const float got = D[(size_t)t * 128 + r * 16 + n];
                    if (got == (float)s) ++once;
                    if (sa > 0) { err += std::fabs((double)got - s) / (sa * 0x1p-24); errc += std::fabs((double)chain - s) / (sa * 0x1p-24); ++nz; }
                }
        std::printf("2. 16 products: %.1f %% equal the exact sum rounded once; error (2^-24 x sum |p|) mean %.3f, fp32 fma chain %.3f\n",
                    100.0 * once / ((double)T * 128), err / nz, errc / nz);
    }
    sycl::free(dA, q); sycl::free(dB, q); sycl::free(dD, q);
    // 3. rates
    for (int rep = 0; rep < 2; ++rep) {
        double pjh = 0, pjb = 0;
        const double rh = gemm_rate<hf>(q, dev, 4096, 4608, 2304, 0x3c00, 0x2000, 2304.0f / 128.0f, pjh); // 1.0 x 2^-7
        const double rb = gemm_rate<bf>(q, dev, 4096, 4608, 2304, 0x3f80, 0x3c00, 2304.0f / 128.0f, pjb); // 1.0 x 2^-7
        std::printf("3. 4096 x 4608 x 2304: fp16 %.1f T multiply-adds/s (%.2f pJ each), bf16 %.1f T/s (%.2f pJ)\n", rh, pjh, rb, pjb);
        double pjc = 0;
        const double rc = gemm_rate<hf, true>(q, dev, 4096, 4608, 2304, 0x3c00, 0x2000, 2304.0f / 128.0f, pjc);
        std::printf("   fp16, B column-major (keys as rows of the cache): %.1f T/s (%.2f pJ)\n", rc, pjc);
        double pjt = 0;
        const double rt = gemm_rate_tf32(q, dev, 4096, 4608, 2304, pjt);
        std::printf("   tf32 %.1f T multiply-adds/s (%.2f pJ each)\n", rt, pjt);
    }
    return 0;
}
