// bench_simd: the NVFP4 expert tile's inner pattern (per 32-value chunk: the 32 inputs of each lane's token, per row a
// code byte and a scale byte read, table lookups in local memory, the value = code x scale, then 32 multiply-adds per
// row with the weight broadcast from the lane that decoded it) with 16 or 32 lanes per sub-group (one token per lane).
// Synthetic: measures TMAC/s, not engine values. bench_simd <card>
#include "../src/device.hpp"
#include <cstdio>

using namespace ink;

template <int SGS, int NR>
double run(sycl::queue &q, const uint8_t *W, const float *X, float *out, int ntiles, int nchunks, int rows) {
    constexpr int WG = 128;
    const int ngr = rows / (NR * (WG / SGS));
    auto go = [&] {
        q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lut(272, h);
            h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)ntiles, (size_t)ngr * WG), sycl::range<2>(1, WG)),
                           [=](sycl::nd_item<2> it) [[sycl::reqd_sub_group_size(SGS)]] {
                auto sg = it.get_sub_group();
                const int lane = (int)sg.get_local_linear_id(), sgi = (int)sg.get_group_linear_id(), li = (int)it.get_local_id(1);
                for (int i = li; i < 272; i += WG) lut[i] = (float)(i % 16) * 0.5f - 3.0f + (float)(i / 16) * 0.01f;
                sycl::group_barrier(it.get_group());
                const int t = (int)it.get_group(0), r0 = ((int)it.get_group(1) * (WG / SGS) + sgi) * NR;
                const size_t rb = (size_t)nchunks * 18;
                float acc[NR];
#pragma unroll
                for (int j = 0; j < NR; ++j) acc[j] = 0.0f;
                for (int c = 0; c < nchunks; ++c) {
                    float xs[32];
                    const float *xc = X + ((size_t)t * nchunks + c) * 32 * SGS;
#pragma unroll
                    for (int qd = 0; qd < 32 / 8; ++qd) {
                        auto mp = sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::yes>(
                            const_cast<float *>(xc + 8 * SGS * qd));
                        sycl::vec<float, 8> v8 = sg.load<8>(mp);
#pragma unroll
                        for (int k = 0; k < 8; ++k) xs[8 * qd + k] = v8[k];
                    }
                    float w0[NR], w1[NR];
#pragma unroll
                    for (int j = 0; j < NR; ++j) {
                        const uint8_t *row = W + (size_t)(r0 + j) * rb + (size_t)c * 18;
                        if constexpr (SGS == 16) { // lane l: byte l -> values l (low code) and 16 + l (high code)
                            const unsigned b = row[2 + lane], sb = row[lane >> 3];
                            const float sc = lut[256 + (sb & 15)];
                            w0[j] = lut[b & 15] * sc;
                            w1[j] = lut[b >> 4] * sc;
                        } else { // lane l: value l (byte l & 15, its low or high code)
                            const unsigned b = row[2 + (lane & 15)], sb = row[(lane >> 3) & 1];
                            const float sc = lut[256 + (sb & 15)];
                            w0[j] = lut[lane < 16 ? (b & 15) : (b >> 4)] * sc;
                        }
                    }
#pragma unroll
                    for (int j = 0; j < NR; ++j) {
                        float s = 0.0f;
#pragma unroll
                        for (int i = 0; i < 32; ++i) {
                            float w;
                            if constexpr (SGS == 16) w = sycl::select_from_group(sg, i < 16 ? w0[j] : w1[j], i & 15);
                            else w = sycl::select_from_group(sg, w0[j], i);
                            s = sycl::fma(w, xs[i], s);
                        }
                        acc[j] += s;
                    }
                }
#pragma unroll
                for (int j = 0; j < NR; ++j) out[((size_t)t * rows + r0 + j) * SGS + lane] = acc[j];
            });
        });
    };
    go(); q.wait();
    const int reps = 10;
    const double t0 = now_s();
    for (int r = 0; r < reps; ++r) go();
    q.wait();
    const double t = (now_s() - t0) / reps;
    return (double)ntiles * SGS * rows * nchunks * 32 / t / 1e12;
}

int main(int argc, char **argv) {
    Device d(argc > 1 ? std::atoi(argv[1]) : 1);
    const int rows = 2304, nchunks = 72, tokens = 8192;
    uint8_t *W = d.alloc<uint8_t>((size_t)rows * nchunks * 18);
    d.q.memset(W, 0x5a, (size_t)rows * nchunks * 18).wait();
    float *X = d.alloc<float>((size_t)tokens * nchunks * 32), *out = d.alloc<float>((size_t)tokens * rows);
    d.q.fill(X, 0.25f, (size_t)tokens * nchunks * 32).wait();
    for (int rep = 0; rep < 2; ++rep) {
        std::printf("16 lanes, 4 rows: %.2f TMAC/s\n", run<16, 4>(d.q, W, X, out, tokens / 16, nchunks, rows));
        std::printf("32 lanes, 4 rows: %.2f TMAC/s\n", run<32, 4>(d.q, W, X, out, tokens / 32, nchunks, rows));
        std::printf("16 lanes, 8 rows: %.2f TMAC/s\n", run<16, 8>(d.q, W, X, out, tokens / 16, nchunks, rows));
        std::printf("32 lanes, 8 rows: %.2f TMAC/s\n", run<32, 8>(d.q, W, X, out, tokens / 32, nchunks, rows));
        std::printf("32 lanes, 6 rows: %.2f TMAC/s\n", run<32, 6>(d.q, W, X, out, tokens / 32, nchunks, rows - 0));
    }
    return 0;
}
