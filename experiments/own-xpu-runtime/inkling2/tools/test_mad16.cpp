// test_mad16: the card's 8x16x16 fp16 matrix instruction called directly (the OpenCL builtin
// intel_sub_group_f16_f16_matrix_mad_k16), operands from plain loads: A (8 rows x 16, row-major, 256 contiguous bytes) by
// one sub-group block load (lane = column), B as each lane's own 16 contiguous halfs (lane = column n: B[k][n] = row n of a key-major
// array, the layout of the key cache), the result as 8 floats per lane (row i, column = lane). Checks against the CPU
// (exact products: the sums of exact small integers) and against joint_matrix.   test_mad16 <card>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/matrix/matrix.hpp>

typedef short short8 __attribute__((ext_vector_type(8)));
typedef int int8v __attribute__((ext_vector_type(8)));
typedef float float8 __attribute__((ext_vector_type(8)));
SYCL_EXTERNAL float8 intel_sub_group_f16_f16_matrix_mad_k16(short8 a, int8v b, float8 acc);

namespace jm = sycl::ext::oneapi::experimental::matrix;

int main(int argc, char **argv) {
    const int card = argc > 1 ? std::atoi(argv[1]) : 3;
    auto devs = sycl::device::get_devices(sycl::info::device_type::gpu);
    sycl::queue q(devs.at(card));
    std::mt19937 rng(3);
    std::uniform_int_distribution<int> di(-8, 8);
    std::vector<sycl::half> A(8 * 16), Bk(16 * 16); // A[r][k]; Bk[n][k] (key-major)
    for (auto &x : A) x = (sycl::half)(float)di(rng);
    for (auto &x : Bk) x = (sycl::half)((float)di(rng) * 0.25f);
    std::vector<double> ref(8 * 16);
    for (int r = 0; r < 8; ++r)
        for (int n = 0; n < 16; ++n) {
            double s = 0;
            for (int k = 0; k < 16; ++k) s += (double)(float)A[r * 16 + k] * (double)(float)Bk[n * 16 + k];
            ref[r * 16 + n] = s + 0.5; // plus the accumulator's start value
        }
    sycl::half *dA = sycl::malloc_device<sycl::half>(A.size(), q), *dB = sycl::malloc_device<sycl::half>(Bk.size(), q);
    float *dC = sycl::malloc_device<float>(2 * 128, q);
    q.memcpy(dA, A.data(), A.size() * 2).wait();
    q.memcpy(dB, Bk.data(), Bk.size() * 2).wait();
    q.parallel_for(sycl::nd_range<1>(16, 16), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
         auto sg = it.get_sub_group();
         const int lane = (int)sg.get_local_linear_id();
         // A: lane w holds column w of the 8 rows (a[m] = A[m][w]: a sub-group block load of the 128 halfs)
         const short *a16 = reinterpret_cast<const short *>(dA);
         short8 a;
#pragma unroll
         for (int m = 0; m < 8; ++m) a[m] = a16[m * 16 + lane];
         int8v b;
         const int *b32 = reinterpret_cast<const int *>(dB + lane * 16);
#pragma unroll
         for (int i = 0; i < 8; ++i) b[i] = b32[i];
         float8 c;
#pragma unroll
         for (int i = 0; i < 8; ++i) c[i] = 0.5f;
         c = intel_sub_group_f16_f16_matrix_mad_k16(a, b, c);
#pragma unroll
         for (int i = 0; i < 8; ++i) dC[i * 16 + lane] = c[i];
         // the same with joint_matrix (B column-major from the key-major array)
         using JA = jm::joint_matrix<sycl::sub_group, sycl::half, jm::use::a, 8, 16, jm::layout::row_major>;
         using JB = jm::joint_matrix<sycl::sub_group, sycl::half, jm::use::b, 16, 16, jm::layout::col_major>;
         using JC = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16>;
         JA ja; JB jb; JC jc;
         jm::joint_matrix_fill(sg, jc, 0.5f);
         auto gp = [](const sycl::half *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
         jm::joint_matrix_load(sg, ja, gp(dA), 16);
         jm::joint_matrix_load(sg, jb, gp(dB), 16);
         jm::joint_matrix_mad(sg, jc, ja, jb, jc);
         jm::joint_matrix_store(sg, jc, sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(dC + 128), 16,
                                jm::layout::row_major);
     }).wait();
    std::vector<float> C(256);
    q.memcpy(C.data(), dC, 256 * 4).wait();
    int bad0 = 0, bad1 = 0;
    for (int i = 0; i < 128; ++i) {
        bad0 += (double)C[i] != ref[i];
        bad1 += (double)C[128 + i] != ref[i];
    }
    std::printf("direct builtin: %d of 128 wrong; joint_matrix: %d of 128 wrong (C[0] %g ref %g, C[17] %g ref %g)\n", bad0, bad1, C[0], ref[0], C[17],
                ref[17]);
    return bad0 || bad1;
}
