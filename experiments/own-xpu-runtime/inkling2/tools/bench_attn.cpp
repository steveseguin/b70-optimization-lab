// bench_attn: time the attention P*V kernels (fused.hpp) on random data at a given position and window, and check
// every variant against attn_pv_gate2 bit for bit.   bench_attn <card> [pos] [win (0 = full)] [ntok]
#include <cmath>
#include "../src/engine.hpp"
#include "../src/attn_tiles.hpp"
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
        if (std::getenv("BENCH_TILE")) { // prompt steps: attn_scores (+ table) vs attn_scores_tile, attn_pv_t vs attn_pv_tile
            const int nr = 16, ext = 1024, G = nh / nkvh, it2 = std::getenv("BENCH_ITERS") ? iters : 10;
            const float scale = 1.0f / std::sqrt((float)hd);
            std::mt19937 rng(7);
            std::normal_distribution<float> nd(0.0f, 1.0f);
            auto rnd = [&](size_t n, float sc) { std::vector<float> v(n); for (auto &x : v) x = nd(rng) * sc; return v; };
            auto hq = rnd((size_t)ntok * nh * hd, 0.3f), hrc = rnd((size_t)ntok * nh * nr, 0.5f), hrb = rnd((size_t)ext * nr, 0.5f);
            auto hs = rnd((size_t)ntok * nh, 1.0f), hg = rnd((size_t)ntok * nh * hd, 1.0f);
            std::vector<sycl::half> hk((size_t)cap * kd), hv((size_t)cap * kd);
            for (auto &x : hk) x = (sycl::half)nd(rng);
            for (auto &x : hv) x = (sycl::half)nd(rng);
            const int vld = (cap + 15) / 16 * 16;
            std::vector<sycl::half> ht((size_t)kd * vld, (sycl::half)0.0f);
            for (int j = 0; j < cap; ++j) for (int c = 0; c < kd; ++c) ht[(size_t)c * vld + j] = hv[(size_t)j * kd + c];
            float *Q = d.alloc<float>(hq.size()), *Rc = d.alloc<float>(hrc.size()), *Rb = d.alloc<float>(hrb.size());
            float *Sk = d.alloc<float>(hs.size()), *Gt = d.alloc<float>(hg.size()), *tab = d.alloc<float>((size_t)ntok * nh * ext);
            sycl::half *K = d.alloc<sycl::half>(hk.size()), *Vt = d.alloc<sycl::half>(ht.size());
            d.put(Q, hq.data(), hq.size()); d.put(Rc, hrc.data(), hrc.size()); d.put(Rb, hrb.data(), hrb.size());
            d.put(Sk, hs.data(), hs.size()); d.put(Gt, hg.data(), hg.size()); d.put(K, hk.data(), hk.size()); d.put(Vt, ht.data(), ht.size());
            // the table as attn_prep builds it
            d.q.parallel_for(sycl::range<2>((size_t)ntok * nh, ext), [=](sycl::id<2> i) {
                const float *b = Rb + i[1] * nr, *r = Rc + i[0] * nr;
                float s = 0.0f;
                for (int k = 0; k < nr; ++k) s += b[k] * r[k];
                tab[i[0] * ext + i[1]] = s;
            }).wait();
            const size_t np = (size_t)ntok * nh * ldp;
            float *P0 = d.alloc<float>(np), *P1 = d.alloc<float>(np);
            float *o0 = d.alloc<float>(hg.size()), *o1 = d.alloc<float>(hg.size());
            auto tm = [&](auto f) {
                f(); d.q.wait();
                double t0 = now_s();
                for (int i = 0; i < it2; ++i) f();
                d.q.wait();
                return (now_s() - t0) / it2 * 1e6;
            };
            auto same = [&](float *a, float *b, size_t n) {
                std::vector<float> x(n), y(n);
                d.get(x.data(), a, n); d.get(y.data(), b, n);
                for (size_t i = 0; i < n; ++i) if (std::memcmp(&x[i], &y[i], 4)) return std::string("DIFF at ") + std::to_string(i);
                return std::string("same");
            };
            const int pl = pos + ntok - 1;
            const double keys = win > 0 ? (double)std::min(win, pl + 1) : (pos + ntok / 2.0);
            const double gmac = (double)ntok * nh * keys * hd / 1e9;
            std::printf("pos %d win %d ntok %d: ~%.0f keys per query, %.2f GMAC per kernel\n", pos, win, ntok, keys, gmac);
            d.q.memset(P0, 0x7f, np * 4).wait();
            double us0 = tm([&] { fz::attn_scores(d.q, Q, K, tab, pos, ntok, nh, nkvh, hd, ext, win, scale, P0, ldp); });
            std::printf("  scores (table)         %9.1f us %6.2f TMAC/s\n", us0, gmac / us0 * 1e3);
            auto sct = [&](const char *name, auto f) {
                d.q.memset(P1, 0x7f, np * 4).wait();
                double us = tm([&] { f(d.q, Q, K, Rc, Rb, nr, pos, ntok, nh, nkvh, hd, ext, win, scale, P1, ldp); });
                std::printf("  %-22s %9.1f us %6.2f TMAC/s  %s\n", name, us, gmac / us * 1e3, same(P0, P1, np).c_str());
            };
            sct("scores_tile<4,3,4>", fz::attn_scores_tile<4, 3, 4>);
            sct("scores_tile<8,3,4>", fz::attn_scores_tile<8, 3, 4>);
            sct("scores_tile<8,3,8>", fz::attn_scores_tile<8, 3, 8>);
            sct("scores_tile<16,3,4>", fz::attn_scores_tile<16, 3, 4>);
            fz::attn_softmax_norm(d.q, Sk, pos, ntok, nh, win, P0, ldp).wait();
            auto pv0 = (win > 0 ? std::min(win, pl + 1) : pl + 1) >= 1024 ? fz::attn_pv_t<64> : fz::attn_pv_t<32>;
            double u1 = tm([&] { pv0(d.q, P0, ldp, Vt, vld, pos, ntok, nh, nkvh, hd, win, Gt, o0); });
            std::printf("  pv_t                   %9.1f us %6.2f TMAC/s\n", u1, gmac / u1 * 1e3);
            auto pvt = [&](const char *name, auto f) {
                d.q.memset(o1, 0, hg.size() * 4).wait();
                double us = tm([&] { f(d.q, P0, ldp, Vt, vld, pos, ntok, nh, nkvh, hd, win, Gt, o1); });
                std::printf("  %-22s %9.1f us %6.2f TMAC/s  %s\n", name, us, gmac / us * 1e3, same(o0, o1, hg.size()).c_str());
            };
            pvt("pv_tile<4,3>", fz::attn_pv_tile<4, 3>);
            pvt("pv_tile<8,3>", fz::attn_pv_tile<8, 3>);
            pvt("pv_tile<16,3>", fz::attn_pv_tile<16, 3>);
            (void)G;
            return 0;
        }
        const int ncopy = std::getenv("BENCH_NCOPY") ? std::atoi(std::getenv("BENCH_NCOPY")) : 16; // V caches cycled so reads come from memory
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
            runt("tp<16>", fz::attn_pv_tp<16>);
            runt("tp<32>", fz::attn_pv_tp<32>);
            runt("tp<64>", fz::attn_pv_tp<64>);
            runt("t2", fz::attn_pv_t2);
            { // block order (different sums: timing only)
                const int lo0 = win > 0 ? std::max(0, pos0 - win + 1) : 0, nblk = (pos0 + ntok - 1) / fz::PVB - lo0 / fz::PVB + 1;
                float *part = d.alloc<float>((size_t)ntok * nh * nblk * hd);
                runt("block order (new sums)", [&](sycl::queue &qq, const float *P_, int ldp_, const sycl::half *Vt_, int vld_, int p0, int nt, int nh_,
                                     int nkvh_, int hd_, int win_, const float *G_, float *o_) {
                    fz::attn_pv_bo_part<3>(qq, P_, ldp_, Vt_, vld_, p0, nt, nh_, nkvh_, hd_, win_, part, nblk);
                    return fz::attn_pv_bo_sum(qq, part, nblk, p0, nt, nh_, hd_, win_, G_, o_);
                });
                d.release(part);
            }
        }
        { // one-token scores: attn_scores vs attn_scores_g<3> (K cycled over the 16 copies, table random)
            const int ext = 1024;
            std::vector<float> hq((size_t)ntok * nh * hd), htb((size_t)ntok * nh * ext);
            for (auto &v : hq) v = nd(rng) * 0.3f;
            for (auto &v : htb) v = nd(rng);
            float *Qd = d.alloc<float>(hq.size()), *Tb = d.alloc<float>(htb.size());
            d.put(Qd, hq.data(), hq.size()); d.put(Tb, htb.data(), htb.size());
            const size_t np = (size_t)ntok * nh * ldp;
            float *S0 = d.alloc<float>(np), *S1 = d.alloc<float>(np);
            d.q.memset(S0, 0, np * 4).wait(); d.q.memset(S1, 0, np * 4).wait();
            const float scale = 1.0f / std::sqrt((float)hd);
            auto ts = [&](auto f, float *S) {
                for (int i = 0; i < 4; ++i) f(i, S);
                d.q.wait();
                double t0 = now_s();
                for (int i = 0; i < iters; ++i) f(i + 1, S);
                d.q.wait();
                return (now_s() - t0) / iters * 1e6;
            };
            double a0 = ts([&](int i, float *S) { fz::attn_scores(d.q, Qd, V[i % ncopy], Tb, pos0, ntok, nh, nkvh, hd, ext, win, scale, S, ldp); }, S0);
            double a1 = ts([&](int i, float *S) { fz::attn_scores_g<3>(d.q, Qd, V[i % ncopy], Tb, pos0, ntok, nh, nkvh, hd, ext, win, scale, S, ldp); }, S1);
            fz::attn_scores(d.q, Qd, V[0], Tb, pos0, ntok, nh, nkvh, hd, ext, win, scale, S0, ldp);
            fz::attn_scores_g<3>(d.q, Qd, V[0], Tb, pos0, ntok, nh, nkvh, hd, ext, win, scale, S1, ldp);
            d.q.wait();
            std::vector<float> x(np), y(np);
            d.get(x.data(), S0, np); d.get(y.data(), S1, np);
            long bad = -1;
            for (size_t i = 0; i < np; ++i) if (std::memcmp(&x[i], &y[i], 4)) { bad = (long)i; break; }
            std::printf("  scores                 %8.2f us\n  scores_g<3>            %8.2f us  %s\n", a0, a1, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
        }
        if (std::getenv("BENCH_T_ONLY")) return 0;
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
