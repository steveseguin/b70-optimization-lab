// bench_xa: the plain joint_matrix_apply (no coordinates) on an A operand (MR x 16 bf16, row major), MR = 1, 2, 4, 8.
//   stage 1: A loaded from local memory with element (r, k) = r * 16 + k; each lane records its elements in the order
//     apply visits them (lane, e) -> (r, k).
//   stage 2: A written by apply from values each lane computes by that map, against A loaded from memory: D = A x B
//     bit for bit (random A and B).
//   bench_xa <card>
#include "../../src/device.hpp"
#include <sycl/ext/oneapi/matrix/matrix.hpp>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>

using namespace ink;
namespace jm = sycl::ext::oneapi::experimental::matrix;
using bf = sycl::ext::oneapi::bfloat16;

template <int MR> static bool probe(sycl::queue &q) {
    constexpr int NE = MR; // elements per lane (MR x 16 / 16)
    float *dO = sycl::malloc_device<float>(16 * 16, q);
    q.memset(dO, 0xff, 16 * 16 * 4).wait();
    q.submit([&](sycl::handler &h) {
         sycl::local_accessor<bf, 1> as(MR * 16, h);
         h.parallel_for(sycl::nd_range<1>(16, 16), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
             auto sg = it.get_sub_group();
             const int ln = (int)sg.get_local_linear_id();
             for (int r = 0; r < MR; ++r) as[r * 16 + ln] = bf((float)(r * 16 + ln));
             sycl::group_barrier(sg);
             jm::joint_matrix<sycl::sub_group, bf, jm::use::a, MR, 16, jm::layout::row_major> a;
             jm::joint_matrix_load(sg, a, as.template get_multi_ptr<sycl::access::decorated::no>(), 16);
             float v[16];
             for (int i = 0; i < 16; ++i) v[i] = -1.0f;
             int e = 0;
             jm::joint_matrix_apply(sg, a, [&](bf &x) { if (e < 16) v[e] = (float)x; ++e; });
             for (int i = 0; i < 16; ++i) dO[ln * 16 + i] = v[i];
             if (ln == 0) dO[255] = (float)e;
         });
     }).wait();
    std::vector<float> o(256);
    q.memcpy(o.data(), dO, 256 * 4).wait();
    sycl::free(dO, q);
    std::printf("MR %d: apply visits %d elements per lane\n", MR, (int)o[255]);
    bool rowmap = true; // lane n holds column n, element e = row e
    for (int ln = 0; ln < 16; ++ln) {
        std::printf("  lane %2d:", ln);
        for (int e = 0; e < NE; ++e) {
            const int v = (int)o[ln * 16 + e];
            std::printf(" (%d,%d)", v / 16, v % 16);
            if (v != e * 16 + ln) rowmap = false;
        }
        std::printf("\n");
    }
    std::printf("  map 'lane n = column n, element e = row e': %s\n", rowmap ? "yes" : "no");
    return rowmap;
}

// stage 2: lane n builds column n of A (rows in order) from the values, D against the loaded A
template <int MR> static void write_check(sycl::queue &q) {
    std::mt19937 rng(5);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    std::vector<uint16_t> ha(MR * 16), hb(256);
    auto f2bf = [](float f) { uint32_t u; std::memcpy(&u, &f, 4); return (uint16_t)((u + 0x7fffu + ((u >> 16) & 1u)) >> 16); };
    for (auto &x : ha) x = f2bf(nd(rng));
    for (auto &x : hb) x = f2bf(nd(rng));
    uint16_t *dA = sycl::malloc_device<uint16_t>(MR * 16, q), *dB = sycl::malloc_device<uint16_t>(256, q);
    float *dD = sycl::malloc_device<float>(2 * MR * 16, q);
    q.memcpy(dA, ha.data(), ha.size() * 2).wait();
    q.memcpy(dB, hb.data(), hb.size() * 2).wait();
    q.submit([&](sycl::handler &h) {
         h.parallel_for(sycl::nd_range<1>(16, 16), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
             auto sg = it.get_sub_group();
             const int ln = (int)sg.get_local_linear_id();
             auto gp = [](auto *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
             jm::joint_matrix<sycl::sub_group, bf, jm::use::a, MR, 16, jm::layout::row_major> a0, a1;
             jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed> b;
             jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, MR, 16> c0, c1;
             jm::joint_matrix_load(sg, a0, gp(reinterpret_cast<bf *>(dA)), 16);
             jm::joint_matrix_load(sg, a1, gp(reinterpret_cast<bf *>(dA)), 16); // defined, then overwritten by apply
             jm::joint_matrix_load(sg, b, gp(reinterpret_cast<bf *>(dB)), 32);
             uint16_t mine[MR];
             for (int r = 0; r < MR; ++r) mine[r] = dA[r * 16 + ln] ^ 0; // column ln
             // scramble a1 first so a pass-through would be caught
             jm::joint_matrix_apply(sg, a1, [](bf &x) { x = bf(7.0f); });
             int e = 0;
             jm::joint_matrix_apply(sg, a1, [&](bf &x) { x = sycl::bit_cast<bf>(mine[e]); ++e; });
             jm::joint_matrix_fill(sg, c0, 0.0f);
             jm::joint_matrix_fill(sg, c1, 0.0f);
             jm::joint_matrix_mad(sg, c0, a0, b, c0);
             jm::joint_matrix_mad(sg, c1, a1, b, c1);
             jm::joint_matrix_store(sg, c0, gp(dD), 16, jm::layout::row_major);
             jm::joint_matrix_store(sg, c1, gp(dD + MR * 16), 16, jm::layout::row_major);
         });
     }).wait();
    std::vector<float> hd(2 * MR * 16);
    q.memcpy(hd.data(), dD, hd.size() * 4).wait();
    const bool same = !std::memcmp(hd.data(), hd.data() + MR * 16, MR * 16 * 4);
    std::printf("  stage 2 MR %d: A built by apply (lane n = column n) %s the loaded A\n", MR, same ? "gives the same D as" : "DIFFERS from");
    sycl::free(dA, q); sycl::free(dB, q); sycl::free(dD, q);
}

int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench_xa <card>\n"); return 1; }
    Device dev(std::atoi(argv[1]));
    sycl::queue &q = dev.q;
    const bool m1 = probe<1>(q), m2 = probe<2>(q), m4 = probe<4>(q), m8 = probe<8>(q);
    if (m1) write_check<1>(q);
    if (m2) write_check<2>(q);
    if (m4) write_check<4>(q);
    if (m8) write_check<8>(q);
    return 0;
}
