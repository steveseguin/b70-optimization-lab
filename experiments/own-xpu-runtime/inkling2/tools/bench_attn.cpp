// bench_attn: time the attention P*V kernels (fused.hpp) on random data at a given position and window, and check
// every variant against attn_pv_gate2 bit for bit.   bench_attn <card> [pos] [win (0 = full)] [ntok]
#include <cmath>
#include "../src/engine.hpp"
#include <random>
#include <functional>

int main(int argc, char **argv) {
    using namespace ink;
    if (argc < 2) { std::fprintf(stderr, "usage: bench_attn <card> [pos] [win] [ntok]\n"); return 2; }
    try {
        Device d(std::atoi(argv[1]));
        const int pos = argc > 2 ? std::atoi(argv[2]) : 3134, win = argc > 3 ? std::atoi(argv[3]) : 1024;
        const int ntok = argc > 4 ? std::atoi(argv[4]) : 1;
        const int nh = 24, nkvh = 8, hd = 128, kd = nkvh * hd, cap = pos + ntok + 64, ldp = cap;
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 200;
        const int ncopy = 16; // V caches cycled so reads come from memory
        std::mt19937 rng(3);
        std::normal_distribution<float> nd(0.0f, 1.0f);
        std::uniform_real_distribution<float> ud(0.0f, 1.0f);
        std::vector<float> hp((size_t)ntok * nh * ldp), hg((size_t)ntok * nh * hd);
        for (auto &v : hp) v = ud(rng) / 512.0f;
        for (auto &v : hg) v = nd(rng);
        std::vector<sycl::half> hv((size_t)cap * kd);
        for (auto &v : hv) v = (sycl::half)nd(rng);
        float *P = d.alloc<float>(hp.size()), *G = d.alloc<float>(hg.size());
        d.put(P, hp.data(), hp.size()); d.put(G, hg.data(), hg.size());
        std::vector<sycl::half *> V;
        for (int c = 0; c < ncopy; ++c) { V.push_back(d.alloc<sycl::half>(hv.size())); d.put(V.back(), hv.data(), hv.size()); }
        float *o0 = d.alloc<float>(hg.size()), *o1 = d.alloc<float>(hg.size());
        std::vector<float> h0(hg.size()), h1(hg.size());
        using Fn = sycl::event (*)(sycl::queue &, const float *, int, const sycl::half *, int, int, int, int, int, int, const float *, float *);
        const int pos0 = pos;
        auto timeit = [&](Fn f, float *o) {
            for (int i = 0; i < 4; ++i) f(d.q, P, ldp, V[i % ncopy], pos0, ntok, nh, nkvh, hd, win, G, o);
            d.q.wait();
            double t0 = now_s();
            for (int i = 0; i < iters; ++i) f(d.q, P, ldp, V[(i + 1) % ncopy], pos0, ntok, nh, nkvh, hd, win, G, o);
            d.q.wait();
            double us = (now_s() - t0) / iters * 1e6;
            f(d.q, P, ldp, V[0], pos0, ntok, nh, nkvh, hd, win, G, o);
            d.q.wait();
            return us;
        };
        const int keys = win > 0 ? std::min(win, pos + 1) : pos + 1;
        const double mb = (double)keys * kd * 2 / 1e6;
        double u0 = timeit(fz::attn_pv_gate2, o0);
        d.get(h0.data(), o0, h0.size());
        std::printf("pos %d win %d keys %d ntok %d: V %.2f MB per token\n", pos, win, keys, ntok, mb);
        std::printf("  %-22s %8.2f us %7.1f GB/s\n", "pv_gate2 (U16)", u0, mb * ntok / u0 * 1e3);
        auto run = [&](const char *name, Fn f) {
            d.q.memset(o1, 0, h1.size() * 4).wait();
            double us = timeit(f, o1);
            d.get(h1.data(), o1, h1.size());
            long bad = -1;
            for (size_t r = 0; r < h1.size(); ++r) if (std::memcmp(&h0[r], &h1[r], 4)) { bad = (long)r; break; }
            std::printf("  %-22s %8.2f us %7.1f GB/s  %s\n", name, us, mb * ntok / us * 1e3, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
        };
        { // the transposed cache
            const int vld = (cap + 15) / 16 * 16;
            std::vector<sycl::half> ht((size_t)kd * vld);
            for (int j = 0; j < cap; ++j) for (int c = 0; c < kd; ++c) ht[(size_t)c * vld + j] = hv[(size_t)j * kd + c];
            std::vector<sycl::half *> Vt;
            for (int c = 0; c < ncopy; ++c) { Vt.push_back(d.alloc<sycl::half>(ht.size())); d.put(Vt.back(), ht.data(), ht.size()); }
            auto runt = [&](const char *name, auto f) {
                d.q.memset(o1, 0, h1.size() * 4).wait();
                auto go = [&](int i, float *o) { f(d.q, P, ldp, Vt[i % ncopy], vld, pos0, ntok, nh, nkvh, hd, win, G, o); };
                for (int i = 0; i < 4; ++i) go(i, o1);
                d.q.wait();
                double t0 = now_s();
                for (int i = 0; i < iters; ++i) go(i + 1, o1);
                d.q.wait();
                double us = (now_s() - t0) / iters * 1e6;
                go(0, o1);
                d.q.wait();
                d.get(h1.data(), o1, h1.size());
                long bad = -1;
                for (size_t r = 0; r < h1.size(); ++r) if (std::memcmp(&h0[r], &h1[r], 4)) { bad = (long)r; break; }
                std::printf("  %-22s %8.2f us %7.1f GB/s  %s\n", name, us, mb * ntok / us * 1e3, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
            };
            runt("t<16>", fz::attn_pv_t<16>);
            runt("t<32>", fz::attn_pv_t<32>);
            runt("t<64>", fz::attn_pv_t<64>);
            runt("t<128>", fz::attn_pv_t<128>);
        }
        run("blk<16>", fz::attn_pv_blk<16>);
        run("blk<32>", fz::attn_pv_blk<32>);
        run("blk<64>", fz::attn_pv_blk<64>);
        run("blk<128>", fz::attn_pv_blk<128>);
        run("pv_u<32>", fz::attn_pv_gate_u<32>);
        run("pv_u<64>", fz::attn_pv_gate_u<64>);
        run("pv_u<128>", fz::attn_pv_gate_u<128>);
        run("wide<2,32>", fz::attn_pv_wide<2, 32>);
        run("wide<2,64>", fz::attn_pv_wide<2, 64>);
        run("wide<4,16>", fz::attn_pv_wide<4, 16>);
        run("wide<4,32>", fz::attn_pv_wide<4, 32>);
        run("wide<4,64>", fz::attn_pv_wide<4, 64>);
        run("wide<8,16>", fz::attn_pv_wide<8, 16>);
        run("wide<8,32>", fz::attn_pv_wide<8, 32>);
    } catch (std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
