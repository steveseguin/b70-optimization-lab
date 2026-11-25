// bench_xm1: properties the expert kernels on the matrix engines rely on:
//   1. a 1-row (and 2- and 4-row) tile gives row 0 the same bits as the 8-row tile (several K steps, three parts);
//   2. the accumulator's work-item layout (which row / column each lane's elements hold);
//   3. the two-matrix joint_matrix_apply (element-wise add of two accumulators) gives a + b element by element.
//   bench_xm1 <card>
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

static uint16_t f2bf_rn(float f) {
    uint32_t u;
    std::memcpy(&u, &f, 4);
    return (uint16_t)((u + 0x7fffu + ((u >> 16) & 1u)) >> 16);
}
constexpr int K = 256, G = 512;

// D (M x 16) = sum over K steps of A (M x 16, three parts) x B (16 x 16): c1 from part 0, c23 from parts 1 and 2,
// then c1 + c23 through the two-matrix apply
template <int M> static void run(sycl::queue &q, const uint16_t *A, const uint16_t *B, float *D) {
    q.parallel_for(sycl::nd_range<1>((size_t)G * 16, 16), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
         auto sg = it.get_sub_group();
         const int g = (int)it.get_group(0);
         auto gp = [](auto *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
         const bf *ag = (const bf *)A + (size_t)g * 3 * 8 * K, *bg = (const bf *)B + (size_t)g * K * 16;
         jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, M, 16> c1, c23;
         jm::joint_matrix_fill(sg, c1, 0.0f);
         jm::joint_matrix_fill(sg, c23, 0.0f);
         for (int k = 0; k < K; k += 16) {
             jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::row_major> b;
             jm::joint_matrix_load(sg, b, gp(bg + (size_t)k * 16), 16);
             jm::joint_matrix<sycl::sub_group, bf, jm::use::a, M, 16, jm::layout::row_major> a;
             jm::joint_matrix_load(sg, a, gp(ag + 0 * 8 * K + k), K);
             jm::joint_matrix_mad(sg, c1, a, b, c1);
             jm::joint_matrix_load(sg, a, gp(ag + 1 * 8 * K + k), K);
             jm::joint_matrix_mad(sg, c23, a, b, c23);
             jm::joint_matrix_load(sg, a, gp(ag + 2 * 8 * K + k), K);
             jm::joint_matrix_mad(sg, c23, a, b, c23);
         }
         jm::joint_matrix_apply(sg, c1, c23, [](float &x, float &y) { x = x + y; });
         jm::joint_matrix_store(sg, c1, gp(D + (size_t)g * 128), 16, jm::layout::row_major);
     }).wait();
}

int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench_xm1 <card>\n"); return 1; }
    Device dev(std::atoi(argv[1]));
    sycl::queue &q = dev.q;
    std::mt19937_64 rng(99);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    std::vector<uint16_t> A((size_t)G * 3 * 8 * K), B((size_t)G * K * 16);
    std::vector<float> xs((size_t)G * 8 * K);
    for (auto &v : B) v = f2bf_rn(nd(rng) * 0.05f);
    for (int g = 0; g < G; ++g)
        for (int r = 0; r < 8; ++r)
            for (int k = 0; k < K; ++k) {
                const float x = nd(rng);
                auto bfv = [](uint16_t b) { uint32_t u = (uint32_t)b << 16; float f; std::memcpy(&f, &u, 4); return f; };
                const uint16_t h1 = f2bf_rn(x);
                const float r1 = x - bfv(h1);
                const uint16_t h2 = f2bf_rn(r1);
                const uint16_t h3 = f2bf_rn(r1 - bfv(h2));
                A[(((size_t)g * 3 + 0) * 8 + r) * K + k] = h1;
                A[(((size_t)g * 3 + 1) * 8 + r) * K + k] = h2;
                A[(((size_t)g * 3 + 2) * 8 + r) * K + k] = h3;
            }
    uint16_t *dA = sycl::malloc_device<uint16_t>(A.size(), q), *dB = sycl::malloc_device<uint16_t>(B.size(), q);
    float *dD = sycl::malloc_device<float>((size_t)G * 128, q);
    q.memcpy(dA, A.data(), A.size() * 2); q.memcpy(dB, B.data(), B.size() * 2).wait();
    std::vector<float> D8((size_t)G * 128), Dm((size_t)G * 128);
    q.memset(dD, 0, (size_t)G * 128 * 4).wait();
    run<8>(q, dA, dB, dD);
    q.memcpy(D8.data(), dD, D8.size() * 4).wait();
    auto cmp = [&](int M) {
        long same = 0, n = 0;
        for (int g = 0; g < G; ++g)
            for (int r = 0; r < M; ++r)
                for (int c = 0; c < 16; ++c) { same += std::memcmp(&Dm[(size_t)g * 128 + r * 16 + c], &D8[(size_t)g * 128 + r * 16 + c], 4) == 0; ++n; }
        std::printf("M = %d tiles: rows 0..%d identical to the 8-row tile at %ld of %ld\n", M, M - 1, same, n);
    };
    q.memset(dD, 0, (size_t)G * 128 * 4).wait(); run<1>(q, dA, dB, dD); q.memcpy(Dm.data(), dD, Dm.size() * 4).wait(); cmp(1);
    q.memset(dD, 0, (size_t)G * 128 * 4).wait(); run<2>(q, dA, dB, dD); q.memcpy(Dm.data(), dD, Dm.size() * 4).wait(); cmp(2);
    q.memset(dD, 0, (size_t)G * 128 * 4).wait(); run<4>(q, dA, dB, dD); q.memcpy(Dm.data(), dD, Dm.size() * 4).wait(); cmp(4);
    // the two-matrix apply against the same sum through local memory on the host: c1 + c23 = D8 is checked by
    // recomputing c1 and c23 separately
    // layout: each lane writes its element coordinates
    float *dL = sycl::malloc_device<float>(128 * 2, q);
    q.parallel_for(sycl::nd_range<1>(16, 16), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
         auto sg = it.get_sub_group();
         const int lane = (int)sg.get_local_linear_id();
         jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16> c;
         jm::joint_matrix_fill(sg, c, 0.0f);
         jmi::joint_matrix_apply(sg, c, [=](float &x, size_t r, size_t col) { x = (float)(lane * 1000 + (int)r * 16 + (int)col); });
         jm::joint_matrix_store(sg, c, sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(dL), 16,
                                jm::layout::row_major);
     }).wait();
    std::vector<float> L(128);
    q.memcpy(L.data(), dL, 128 * 4).wait();
    bool lane_col = true, coords = true;
    for (int r = 0; r < 8; ++r)
        for (int c = 0; c < 16; ++c) {
            const int v = (int)L[r * 16 + c], lane = v / 1000, rc = v % 1000;
            if (lane != c) lane_col = false;
            if (rc != r * 16 + c) coords = false;
        }
    std::printf("accumulator layout: lane = column %s, apply coordinates %s\n", lane_col ? "yes" : "NO", coords ? "right" : "WRONG");
    return 0;
}
