// bench_xmx: the matrix engines (DPAS through joint_matrix, bf16 inputs, fp32 sums) as an exact-product device:
//   1. the matrix shapes the card offers;
//   2. what one multiply-add instruction computes: D = C + sum of 16 products per element, compared bit for bit
//      with rounding models built from the exact sum (int128 fixed point): one rounding of the whole sum, an fp32
//      chain in index order, pairs added exactly then rounded, truncation variants;
//   3. whether a row's result depends on the other rows of its tile (random rows vs zero rows);
//   4. the three-part bf16 split of fp32 values (x = x1 + x2 + x3 exactly?);
//   5. the rate of a plain bf16 product (T multiply-adds per second and pJ per multiply-add).
//   bench_xmx <card> [tests]
#include "../src/device.hpp"
#include <sycl/ext/oneapi/matrix/matrix.hpp>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>

using namespace ink;
namespace jm = sycl::ext::oneapi::experimental::matrix;
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
static uint32_t fbits(float f) { uint32_t u; std::memcpy(&u, &f, 4); return u; }

// exact sums: terms m * 2^e with |m| < 2^50, gathered at the smallest exponent in an int128
struct Exact {
    __int128 s = 0;
    int e0 = 0;
};
static void term(double v, int &e, long long &m) { // v = m * 2^e exactly (v a float or a product of two bf16)
    if (v == 0.0) { e = 0; m = 0; return; }
    int ex;
    const double fr = std::frexp(v, &ex); // v = fr * 2^ex, 0.5 <= |fr| < 1
    m = (long long)std::ldexp(fr, 26); // floats have 24 significant bits, bf16 products 16
    e = ex - 26;
}
static Exact exact_sum(const std::vector<double> &vals) {
    std::vector<int> es(vals.size());
    std::vector<long long> ms(vals.size());
    int e0 = 1 << 30;
    for (size_t i = 0; i < vals.size(); ++i) {
        term(vals[i], es[i], ms[i]);
        if (ms[i]) e0 = std::min(e0, es[i]);
    }
    Exact x;
    x.e0 = e0 == (1 << 30) ? 0 : e0;
    for (size_t i = 0; i < vals.size(); ++i)
        if (ms[i]) {
            const int sh = es[i] - x.e0;
            if (sh > 95) { std::fprintf(stderr, "exact_sum: exponent span too wide (%d)\n", sh); std::exit(2); }
            x.s += (__int128)ms[i] << sh;
        }
    return x;
}
static int hibit(unsigned __int128 a) {
    const uint64_t hi = (uint64_t)(a >> 64), lo = (uint64_t)a;
    return hi ? 64 + 63 - __builtin_clzll(hi) : 63 - __builtin_clzll(lo);
}
static float round_exact(const Exact &x, bool trunc) { // to fp32: nearest even, or toward zero
    if (x.s == 0) return 0.0f;
    const bool neg = x.s < 0;
    unsigned __int128 a = neg ? -(unsigned __int128)x.s : (unsigned __int128)x.s;
    int sh = hibit(a) - 23;
    unsigned __int128 m;
    if (sh > 0) {
        m = a >> sh;
        const unsigned __int128 rem = a & (((unsigned __int128)1 << sh) - 1), half = (unsigned __int128)1 << (sh - 1);
        if (!trunc && (rem > half || (rem == half && (m & 1)))) {
            ++m;
            if (m >> 24) { m >>= 1; ++sh; }
        }
    } else {
        m = a << (-sh);
        sh = sh;
    }
    const float f = std::ldexp((float)(uint32_t)m, sh + x.e0);
    return neg ? -f : f;
}
// terms cut (toward zero, or toward minus infinity) to multiples of 2^(emax - W), emax = the largest term's exponent
// (of its leading bit), summed exactly, rounded once to nearest even
static float aligned(const std::vector<double> &v, int W, bool floor_cut) {
    int emax = -100000;
    for (double x : v) if (x != 0) { int e; std::frexp(x, &e); emax = std::max(emax, e); }
    if (emax == -100000) return 0.0f;
    std::vector<double> c(v.size());
    for (size_t i = 0; i < v.size(); ++i) {
        const double q = std::ldexp(v[i], W - emax); // exact (power of two)
        const double t = floor_cut ? std::floor(q) : std::trunc(q);
        c[i] = std::ldexp(t, emax - W);
    }
    return round_exact(exact_sum(c), false);
}
static double ulp_err(float got, const Exact &x) { // |got - exact| in units of fp32 ulp at the exact value
    const float r = round_exact(x, false);
    if (r == 0.0f) return got == 0.0f ? 0.0 : 1e9;
    int e; std::frexp((double)r, &e);
    const double ulp = std::ldexp(1.0, e - 24);
    // exact value as a double approximation (enough for an error in ulps)
    const double xv = (double)x.s * std::ldexp(1.0, x.e0);
    return std::fabs((double)got - xv) / ulp;
}
static float rn_add(float a, double b) { // RN(a + b) for b exact in double
    return round_exact(exact_sum({(double)a, b}), false);
}
static float rz_add(float a, double b) { return round_exact(exact_sum({(double)a, b}), true); }

// one sub-group per test: D = C + A B (A 8 x 16, B 16 x 16 row major, C / D 8 x 16)
static void mad_tests(sycl::queue &q, const uint16_t *A, const uint16_t *B, const float *C, float *D, int T) {
    q.parallel_for(sycl::nd_range<1>((size_t)T * 16, 16), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
         auto sg = it.get_sub_group();
         const int t = (int)it.get_group(0);
         auto g = [](auto *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
         jm::joint_matrix<sycl::sub_group, bf, jm::use::a, 8, 16, jm::layout::row_major> a;
         jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::row_major> b;
         jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16> c;
         jm::joint_matrix_load(sg, a, g((const bf *)A + (size_t)t * 128), 16);
         jm::joint_matrix_load(sg, b, g((const bf *)B + (size_t)t * 256), 16);
         jm::joint_matrix_load(sg, c, g(C + (size_t)t * 128), 16, jm::layout::row_major);
         jm::joint_matrix_mad(sg, c, a, b, c);
         jm::joint_matrix_store(sg, c, g(D + (size_t)t * 128), 16, jm::layout::row_major);
     }).wait();
}

// sub-group tile 32 x 32 (4 x 2 accumulators), K steps of 16; A rows x K, B K x N (row major or packed pairs)
template <bool PACKED> static double gemm_rate(sycl::queue &q, const Device &dev, int M, int N, int K, double &pj) {
    uint16_t *A = sycl::malloc_device<uint16_t>((size_t)M * K, q), *B = sycl::malloc_device<uint16_t>((size_t)K * N, q);
    float *Cm = sycl::malloc_device<float>((size_t)M * N, q);
    q.fill(A, (uint16_t)0x3f80, (size_t)M * K).wait(); // 1.0
    q.fill(B, (uint16_t)0x3c00, (size_t)K * N).wait(); // 2^-7
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
                jm::joint_matrix<sycl::sub_group, bf, jm::use::a, 8, 16, jm::layout::row_major> a[4];
                jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16,
                                 PACKED ? jm::layout::ext_intel_packed : jm::layout::row_major> b[2];
#pragma unroll
                for (int i = 0; i < 4; ++i) jm::joint_matrix_load(sg, a[i], g((const bf *)A + (size_t)(mt * TMR + 8 * i) * K + k), K);
#pragma unroll
                for (int j = 0; j < 2; ++j) {
                    if constexpr (PACKED) jm::joint_matrix_load(sg, b[j], g((const bf *)B + (size_t)(k / 2) * N * 2 + (size_t)(nt * TNC + 16 * j) * 2), N * 2);
                    else jm::joint_matrix_load(sg, b[j], g((const bf *)B + (size_t)k * N + nt * TNC + 16 * j), N);
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
    if (std::fabs(c0 - (float)K / 128.0f) > 1e-3f) std::printf("  gemm check: C[0] = %g, expected %g\n", c0, (double)K / 128.0);
    sycl::free(A, q); sycl::free(B, q); sycl::free(Cm, q);
    return macs / t / 1e12;
}

int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench_xmx <card> [tests]\n"); return 1; }
    Device dev(std::atoi(argv[1]));
    sycl::queue &q = dev.q;
    const int T = argc > 2 ? std::atoi(argv[2]) : 4096;

    // 1. shapes
    {
        namespace ex = sycl::ext::oneapi::experimental;
        auto combos = q.get_device().get_info<ex::info::device::matrix_combinations>();
        std::printf("matrix combinations (a b c d types; m n k; max m n k):\n");
        for (auto &c : combos)
            std::printf("  %d %d %d %d; %zu %zu %zu; %zu %zu %zu\n", (int)c.atype, (int)c.btype, (int)c.ctype, (int)c.dtype, c.msize,
                        c.nsize, c.ksize, c.max_msize, c.max_nsize, c.max_ksize);
    }

    // 2 + 3. one instruction's sums, two value ranges; rows 1-7 random or zero
    std::mt19937_64 rng(12345);
    for (int range : {6, 20}) {
        std::uniform_int_distribution<int> ex(-range, range);
        std::uniform_int_distribution<int> man(0, 127), sgn(0, 1);
        auto rbf = [&] { // a random bf16 with exponent in [-range, range]
            const float v = std::ldexp(1.0f + man(rng) / 128.0f, ex(rng)) * (sgn(rng) ? -1.0f : 1.0f);
            return f2bf_rn(v);
        };
        std::uniform_int_distribution<uint32_t> m24(0, (1u << 23) - 1);
        auto rf = [&] { return std::ldexp(1.0f + m24(rng) / 8388608.0f, ex(rng)) * (sgn(rng) ? -1.0f : 1.0f); };
        std::vector<uint16_t> A((size_t)T * 128), B((size_t)T * 256);
        std::vector<float> C((size_t)T * 128), D((size_t)T * 128), D0((size_t)T * 128);
        for (auto &v : A) v = rbf();
        for (auto &v : B) v = rbf();
        for (auto &v : C) v = rf();
        // a quarter of the tests: cancellation (row 0's products sum to about -C)
        uint16_t *dA = sycl::malloc_device<uint16_t>(A.size(), q), *dB = sycl::malloc_device<uint16_t>(B.size(), q);
        float *dC = sycl::malloc_device<float>(C.size(), q), *dD = sycl::malloc_device<float>(D.size(), q);
        q.memcpy(dA, A.data(), A.size() * 2); q.memcpy(dB, B.data(), B.size() * 2); q.memcpy(dC, C.data(), C.size() * 4).wait();
        mad_tests(q, dA, dB, dC, dD, T);
        q.memcpy(D.data(), dD, D.size() * 4).wait();
        // models
        const char *names[] = {"one rounding (RN of the exact sum)", "fp32 chain k = 0..15 from C", "fp32 chain, C added last",
                               "pairs exact, chain of 8 from C", "quads exact, chain of 4 from C", "products exact sum, then + C (two roundings)",
                               "toward zero, one rounding", "pairs exact, chain from C, toward zero", "fp32 chain k = 15..0 from C"};
        const int NMOD = 9;
        long match[NMOD] = {0};
        long total = 0, shown = 0;
        const int WS[] = {24, 25, 26, 27, 28, 30, 32, 36, 40};
        long amatch[2][9] = {{0}};
        double emax_eng = 0, emax_chain = 0, esum_eng = 0, esum_chain = 0;
        long hist_eng[4] = {0}, hist_chain[4] = {0};
        for (int t = 0; t < T; ++t)
            for (int r = 0; r < 8; ++r)
                for (int n = 0; n < 16; ++n) {
                    double p[16];
                    for (int k = 0; k < 16; ++k) p[k] = (double)bf2f(A[(size_t)t * 128 + r * 16 + k]) * (double)bf2f(B[(size_t)t * 256 + k * 16 + n]);
                    const float c = C[(size_t)t * 128 + r * 16 + n], d = D[(size_t)t * 128 + r * 16 + n];
                    std::vector<double> all(p, p + 16);
                    all.push_back(c);
                    float m[NMOD];
                    m[0] = round_exact(exact_sum(all), false);
                    { float a = c; for (int k = 0; k < 16; ++k) a = rn_add(a, p[k]); m[1] = a; }
                    { float a = (float)p[0]; for (int k = 1; k < 16; ++k) a = rn_add(a, p[k]); m[2] = rn_add(a, c); }
                    { float a = c; for (int k = 0; k < 16; k += 2) a = round_exact(exact_sum({(double)a, p[k], p[k + 1]}), false); m[3] = a; }
                    { float a = c; for (int k = 0; k < 16; k += 4) a = round_exact(exact_sum({(double)a, p[k], p[k + 1], p[k + 2], p[k + 3]}), false); m[4] = a; }
                    { const float sp = round_exact(exact_sum(std::vector<double>(p, p + 16)), false); m[5] = rn_add(c, sp); }
                    m[6] = round_exact(exact_sum(all), true);
                    { float a = c; for (int k = 0; k < 16; k += 2) a = round_exact(exact_sum({(double)a, p[k], p[k + 1]}), true); m[7] = a; }
                    { float a = c; for (int k = 15; k >= 0; --k) a = rn_add(a, p[k]); m[8] = a; }
                    for (int i = 0; i < NMOD; ++i) match[i] += fbits(m[i]) == fbits(d);
                    for (int fc = 0; fc < 2; ++fc)
                        for (int w = 0; w < 9; ++w) amatch[fc][w] += fbits(aligned(all, WS[w], fc != 0)) == fbits(d);
                    {
                        const Exact ex = exact_sum(all);
                        const double ee = ulp_err(d, ex), ec = ulp_err(m[1], ex);
                        emax_eng = std::max(emax_eng, ee); emax_chain = std::max(emax_chain, ec);
                        esum_eng += ee; esum_chain += ec;
                        hist_eng[ee < 0.5 ? 0 : ee < 1.0 ? 1 : ee < 2.0 ? 2 : 3]++;
                        hist_chain[ec < 0.5 ? 0 : ec < 1.0 ? 1 : ec < 2.0 ? 2 : 3]++;
                    }
                    ++total;
                    if (fbits(m[0]) != fbits(d) && fbits(m[3]) != fbits(d) && shown < 4) {
                        ++shown;
                        std::printf("  range %d test %d (%d,%d): engine %.9g, one rounding %.9g, pairs %.9g, chain %.9g\n", range, t, r, n,
                                    d, m[0], m[3], m[1]);
                    }
                }
        std::printf("one multiply-add instruction, exponents within +-%d (%ld elements):\n", range, total);
        for (int i = 0; i < NMOD; ++i) std::printf("  %-48s %ld (%.4f %%)\n", names[i], match[i], 100.0 * match[i] / total);
        for (int fc = 0; fc < 2; ++fc)
            for (int w = 0; w < 9; ++w)
                std::printf("  aligned to the largest term, %2d bits, cut %-11s %ld (%.4f %%)\n", WS[w], fc ? "down" : "toward 0",
                            amatch[fc][w], 100.0 * amatch[fc][w] / total);
        std::printf("  error against the exact sum, in ulps: engine mean %.4f max %.3f (<0.5 %ld, <1 %ld, <2 %ld, more %ld); "
                    "fp32 chain mean %.4f max %.3f (<0.5 %ld, <1 %ld, <2 %ld, more %ld)\n",
                    esum_eng / total, emax_eng, hist_eng[0], hist_eng[1], hist_eng[2], hist_eng[3], esum_chain / total, emax_chain,
                    hist_chain[0], hist_chain[1], hist_chain[2], hist_chain[3]);
        // rows 1-7 zero: row 0 unchanged?
        std::vector<uint16_t> Az = A;
        for (int t = 0; t < T; ++t)
            for (int i = 16; i < 128; ++i) Az[(size_t)t * 128 + i] = 0;
        q.memcpy(dA, Az.data(), Az.size() * 2).wait();
        mad_tests(q, dA, dB, dC, dD, T);
        q.memcpy(D0.data(), dD, D0.size() * 4).wait();
        long same = 0;
        for (int t = 0; t < T; ++t)
            for (int n = 0; n < 16; ++n) same += fbits(D0[(size_t)t * 128 + n]) == fbits(D[(size_t)t * 128 + n]);
        std::printf("  row 0 with rows 1-7 zero instead of random: %ld of %d identical\n", same, T * 16);
        // the same launch twice
        mad_tests(q, dA, dB, dC, dD, T);
        std::vector<float> D1(D.size());
        q.memcpy(D1.data(), dD, D1.size() * 4).wait();
        std::printf("  repeat: %s\n", std::memcmp(D1.data(), D0.data(), D0.size() * 4) ? "DIFFERENT" : "identical");
        sycl::free(dA, q); sycl::free(dB, q); sycl::free(dC, q); sycl::free(dD, q);
    }

    // 4. the three-part split (nearest even): x = x1 + x2 + x3 exactly?
    {
        std::normal_distribution<float> nd(0.0f, 1.0f);
        std::uniform_int_distribution<int> ex(-60, 60);
        long ok = 0, n = 0, ok2 = 0;
        double worst = 0;
        for (int i = 0; i < 2000000; ++i) {
            const float x = nd(rng) * std::ldexp(1.0f, ex(rng));
            const float x1 = bf2f(f2bf_rn(x)), r1 = x - x1, x2 = bf2f(f2bf_rn(r1)), r2 = r1 - x2, x3 = bf2f(f2bf_rn(r2));
            ok += (double)x1 + (double)x2 + (double)x3 == (double)x;
            ok2 += r2 == x3;
            if (x != 0) worst = std::max(worst, std::fabs(((double)x1 + x2 + x3 - x) / x));
            ++n;
        }
        std::printf("three-part bf16 split (exponents +-60 times N(0,1)): %ld of %ld exact (%ld with the last part exact), worst relative %.3g\n",
                    ok, n, ok2, worst);
    }

    if (std::getenv("BENCH_NO_RATE")) return 0;
    // 5. rate
    {
        double pj = 0;
        for (int rep = 0; rep < 2; ++rep) {
            const double r0 = gemm_rate<false>(q, dev, 4096, 4608, 2304, pj);
            std::printf("bf16 product 4096 x 4608 x 2304, B row major: %.1f T multiply-adds/s, %.2f pJ each\n", r0, pj);
            const double r1 = gemm_rate<true>(q, dev, 4096, 4608, 2304, pj);
            std::printf("bf16 product 4096 x 4608 x 2304, B packed:    %.1f T multiply-adds/s, %.2f pJ each\n", r1, pj);
        }
    }
    return 0;
}
