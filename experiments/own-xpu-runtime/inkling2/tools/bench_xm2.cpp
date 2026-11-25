// bench_xm2: can a B operand (16 x 16 bf16, packed) be built from each lane's own registers (lane n = column n,
// values k = 0..15) instead of local memory? D = A x B with B loaded from local memory vs B written element by element
// with joint_matrix_apply (coordinates), and the time of both (a sub-group per 16 columns, 144 steps, M = 1 and 8).
//   bench_xm2 <card>
#include "../src/device.hpp"
#include <sycl/ext/oneapi/matrix/matrix.hpp>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>

using namespace ink;
namespace jm = sycl::ext::oneapi::experimental::matrix;
namespace jmi = sycl::ext::intel::experimental::matrix;
using bf = sycl::ext::oneapi::bfloat16;

static uint16_t f2bf_rn(float f) { uint32_t u; std::memcpy(&u, &f, 4); return (uint16_t)((u + 0x7fffu + ((u >> 16) & 1u)) >> 16); }
constexpr int K = 2304, ST = K / 16;
static int G = 256;

// Bv[g][k][n] bf16 values; lane n of group g reads its 16 values of step k (a column) from global memory
template <int M, int HOW> static double run(sycl::queue &q, const uint16_t *A, const uint16_t *Bv, float *D, int reps) {
    double best = 1e30;
    const int G = ::G;
    for (int r = 0; r < reps; ++r) {
        auto t0 = std::chrono::steady_clock::now();
        q.submit([&](sycl::handler &h) {
            sycl::local_accessor<bf, 1> bs(HOW == 0 ? 256 * 4 : 2, h);
            h.parallel_for(sycl::nd_range<1>((size_t)G * 16, 64), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                auto sg = it.get_sub_group();
                const int g = (int)(it.get_global_id(0) / 16), ln = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id();
                auto gp = [](auto *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
                const bf *ag = (const bf *)A + (size_t)(g % 64) * 8 * K;
                jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, M, 16> c;
                jm::joint_matrix_fill(sg, c, 0.0f);
                for (int k = 0; k < ST; ++k) {
                    // lane ln: its column's 16 values of step k, as 8 words of pairs
                    const uint32_t *src = reinterpret_cast<const uint32_t *>(Bv + ((size_t)g * K + (size_t)k * 16) * 16 + ln * 16);
                    uint32_t wv[8];
#pragma unroll
                    for (int j = 0; j < 8; ++j) wv[j] = src[j];
                    jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed> b;
                    if constexpr (HOW == 0) {
                        uint32_t *bw = reinterpret_cast<uint32_t *>(&bs[0]) + sgi * 128;
#pragma unroll
                        for (int j = 0; j < 8; ++j) bw[j * 16 + ln] = wv[j];
                        sycl::group_barrier(sg);
                        jm::joint_matrix_load(sg, b, bs.template get_multi_ptr<sycl::access::decorated::no>() + sgi * 256, 32);
                    } else {
                        jmi::joint_matrix_apply(sg, b, [&](bf &x, size_t row, size_t col) {
                            const uint32_t w = wv[row / 2];
                            x = sycl::bit_cast<bf>((uint16_t)(row & 1 ? w >> 16 : w & 0xFFFF));
                        });
                    }
                    jm::joint_matrix<sycl::sub_group, bf, jm::use::a, M, 16, jm::layout::row_major> a;
                    jm::joint_matrix_load(sg, a, gp(ag + (size_t)k * 16), K);
                    jm::joint_matrix_mad(sg, c, a, b, c);
                    if constexpr (HOW == 0) sycl::group_barrier(sg);
                }
                jm::joint_matrix_store(sg, c, gp(D + (size_t)g * 128), 16, jm::layout::row_major);
            });
        }).wait();
        best = std::min(best, std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count());
    }
    return best;
}

int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench_xm2 <card>\n"); return 1; }
    Device dev(std::atoi(argv[1]));
    if (argc > 2) G = std::atoi(argv[2]);
    sycl::queue &q = dev.q;
    std::mt19937_64 rng(5);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    std::vector<uint16_t> A((size_t)64 * 8 * K), Bv((size_t)G * K * 16);
    for (auto &v : A) v = f2bf_rn(nd(rng));
    for (auto &v : Bv) v = f2bf_rn(nd(rng) * 0.05f);
    uint16_t *dA = sycl::malloc_device<uint16_t>(A.size(), q), *dB = sycl::malloc_device<uint16_t>(Bv.size(), q);
    float *d0 = sycl::malloc_device<float>((size_t)G * 128, q), *d1 = sycl::malloc_device<float>((size_t)G * 128, q);
    q.memcpy(dA, A.data(), A.size() * 2); q.memcpy(dB, Bv.data(), Bv.size() * 2).wait();
    std::vector<float> h0((size_t)G * 128), h1((size_t)G * 128);
    auto cmp = [&](int M) {
        long same = 0, n = 0;
        for (int g = 0; g < G; ++g) for (int r = 0; r < M; ++r) for (int c = 0; c < 16; ++c) {
            same += std::memcmp(&h0[(size_t)g * 128 + r * 16 + c], &h1[(size_t)g * 128 + r * 16 + c], 4) == 0; ++n; }
        return std::to_string(same) + " of " + std::to_string(n);
    };
    double t0 = run<8, 0>(q, dA, dB, d0, 3);
    std::printf("local memory M = 8: %.1f us\n", t0 * 1e6); std::fflush(stdout);
    double t1 = run<8, 1>(q, dA, dB, d1, 1);
    q.memcpy(h0.data(), d0, h0.size() * 4); q.memcpy(h1.data(), d1, h1.size() * 4).wait();
    std::printf("M = 8: local memory %.1f us, registers %.1f us, identical %s\n", t0 * 1e6, t1 * 1e6, cmp(8).c_str());
    t0 = run<1, 0>(q, dA, dB, d0, 3); t1 = run<1, 1>(q, dA, dB, d1, 3);
    q.memcpy(h0.data(), d0, h0.size() * 4); q.memcpy(h1.data(), d1, h1.size() * 4).wait();
    std::printf("M = 1: local memory %.1f us, registers %.1f us, identical %s\n", t0 * 1e6, t1 * 1e6, cmp(1).c_str());
    return 0;
}
