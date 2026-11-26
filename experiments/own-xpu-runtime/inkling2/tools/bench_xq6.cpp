// bench_xq6: the Q6_K attention matrices on the matrix engines in the Q6E layout (xmx_esimd.hpp; INK_XMX_Q6):
// the prompt kernel (xd::dense Q6) against the one-token and 2-8 token ESIMD kernels (xd::dgroupej, kind EK_Q6) bit for
// bit, a mixed job list (Q8E + Q6E) against the jobs alone, the sums' error against double (units 2^-24 x sum |w x|)
// next to today's FP32 tiles (dense_t on the Q6_KU copy), and the times.
//   bench_xq6 <model.gguf> <card> <tokens>
#include "../src/tok_tiles.hpp"
#include "../src/xmx_esimd.hpp"
#include <random>
using namespace ink;
int main(int argc, char **argv) {
    if (argc < 4) { std::fprintf(stderr, "usage: bench_xq6 <model.gguf> <card> <tokens>\n"); return 2; }
    try {
        GGUF gf(argv[1]);
        Device d(std::atoi(argv[2]));
        Weights w;
        w.upload(d, gf, false);
        auto views = planarize(d, gf, w, false);
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 50;
        const int M = std::atoi(argv[3]), Mpad = (M + 63) / 64 * 64;
        constexpr int CMAX = 3072, RMAX = 3072;
        std::mt19937 rng(7);
        std::normal_distribution<float> nd(0.0f, 1.0f);
        std::vector<float> hx((size_t)Mpad * CMAX);
        for (auto &v : hx) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
        // BENCH_X=<f32 file of rows of 2,304> (e.g. a dump's l_out-41): real hidden states as the inputs, each row scaled
        // to unit RMS (an RMS norm without its weights), repeated to M rows
        if (const char *xf = std::getenv("BENCH_X")) {
            std::FILE *f = std::fopen(xf, "rb");
            if (!f) throw std::runtime_error("bench_xq6: cannot open BENCH_X");
            std::vector<float> r;
            float buf[2304];
            while (std::fread(buf, 4, 2304, f) == 2304) r.insert(r.end(), buf, buf + 2304);
            std::fclose(f);
            const size_t nr = r.size() / 2304;
            if (!nr) throw std::runtime_error("bench_xq6: BENCH_X has no rows");
            for (int t = 0; t < Mpad; ++t) {
                const float *src = r.data() + (size_t)(t % nr) * 2304;
                double ss = 0;
                for (int c = 0; c < 2304; ++c) ss += (double)src[c] * src[c];
                const float sc = (float)(1.0 / std::sqrt(ss / 2304 + 1e-6));
                for (int c = 0; c < 2304; ++c) hx[(size_t)t * 2304 + c] = src[c] * sc; // the kernels read rows of cols = 2,304
            }
            std::printf("inputs: %zu real rows from %s, unit RMS\n", nr, xf);
        }
        float *x = d.alloc<float>(hx.size());
        d.put(x, hx.data(), hx.size());
        float *Xd = d.alloc<float>((size_t)Mpad * CMAX), *Y = d.alloc<float>((size_t)Mpad * RMAX), *Y1 = d.alloc<float>((size_t)8 * RMAX),
              *Y2 = d.alloc<float>((size_t)8 * RMAX);
        uint16_t *P = d.alloc<uint16_t>((size_t)3 * Mpad * CMAX), *Pe = d.alloc<uint16_t>((size_t)3 * 8 * CMAX);
        auto timeit = [&](auto &&launch) {
            for (int i = 0; i < 2; ++i) launch();
            d.q.wait();
            const double t0 = now_s();
            for (int i = 0; i < iters; ++i) launch();
            d.q.wait();
            return (now_s() - t0) / iters * 1e6;
        };
        // a Q8_0 matrix in Q8E for the mixed job list
        const WView q8 = views.at("blk.6.attn_q.weight");
        if (q8.kind != K_Q8_0P) throw std::runtime_error("bench_xq6: blk.6.attn_q is not Q8_0");
        const int q8rows = (int)q8.t->rows();
        uint8_t *q8e = d.alloc<uint8_t>(q8.rb * q8rows);
        {
            uint8_t *t = d.alloc<uint8_t>(q8.rb * q8rows);
            d.q.memcpy(t, q8.p, q8.rb * q8rows).wait();
            xd::repack_q8e(d.q, t, q8.rb, q8rows, (int)q8.t->ne[0], q8e);
        }
        int fails = 0;
        for (const char *nm : {"blk.18.attn_q", "blk.20.attn_gate", "blk.20.attn_k", "blk.2.attn_rel"}) {
            const WView v = views.at(std::string(nm) + ".weight");
            if (v.kind != K_Q6_KP) { std::printf("%s: not Q6_K, skipped\n", nm); continue; }
            const int cols = (int)v.t->ne[0], rows = (int)v.t->rows(), ng = cols / 256;
            const double macs = (double)M * rows * cols;
            // the Q6_KU copy (codes and float scales) and the Q6E layout made from it
            const size_t urb = pl::Q6_KU::stride(cols);
            uint8_t *u = d.alloc<uint8_t>(urb * rows);
            pl::q6ku_from_p(d.q, v.p, v.rb, u, urb, cols, rows).wait();
            const WView vu{v.t, u, urb, K_Q6_KU};
            uint8_t *e6 = d.alloc<uint8_t>((size_t)(rows / 16) * ng * xd::TG6);
            xd::repack_q6e(d.q, u, urb, rows, cols, e6);
            std::vector<uint8_t> hu(urb * rows);
            d.get(hu.data(), u, hu.size());
            std::printf("%s: %d x %d, %d tokens\n", nm, cols, rows, M);
            // today's FP32 tiles
            dense_gather(d.q, x, cols, M, cols, Xd).wait();
            const double ut = timeit([&] { dense_t(d.q, vu, M, Xd, Y, rows, DTune{4, 32}); });
            std::vector<float> yt((size_t)M * rows);
            d.get(yt.data(), Y, yt.size());
            const double u1 = timeit([&] { gemv_v(d.q, v, x, cols, Y1, rows, 1, Tune{2, 2, false, 8, true}); });
            std::printf("  today: dense_t %.1f us (%.2f T MAC/s), one token gemv_v %.2f us\n", ut, macs / ut / 1e6, u1);
            // the error against double on samples
            constexpr int NS = 2000;
            std::mt19937 rs(3);
            std::vector<int> st(NS), sr(NS);
            for (int i = 0; i < NS; ++i) { st[i] = (int)(rs() % M); sr[i] = (int)(rs() % rows); }
            auto err_of = [&](const std::vector<float> &y) {
                double s = 0, mx = 0;
                for (int i = 0; i < NS; ++i) {
                    const uint8_t *row = hu.data() + (size_t)sr[i] * urb;
                    const float *sc = reinterpret_cast<const float *>(row + cols);
                    double ref = 0, ab = 0;
                    for (int c = 0; c < cols; ++c) {
                        const double p = (double)sc[c / 16] * (double)(int8_t)row[c] * hx[(size_t)st[i] * cols + c];
                        ref += p; ab += std::fabs(p);
                    }
                    const double e = ab > 0 ? std::fabs(y[(size_t)st[i] * rows + sr[i]] - ref) / (std::ldexp(1.0, -24) * ab) : 0;
                    s += e; mx = std::max(mx, e);
                }
                char b[64];
                std::snprintf(b, sizeof b, "mean %.4f max %.4f", s / NS, mx);
                return std::string(b);
            };
            std::printf("  today's error vs double: %s\n", err_of(yt).c_str());
            // prompt kernel
            const double us_s = timeit([&] { xd::split(d.q, x, cols, M, Mpad, cols, P, (size_t)Mpad * cols); });
            d.q.memset(Y, 0, (size_t)M * rows * 4).wait();
            if (rows % 128) { std::printf("  rows %% 128: no prompt kernel\n"); continue; }
            const double ud = timeit([&] { xd::dense<4, 4, 2, 2, 4, false, 8, false, true, false, true>(d.q, e6, rows, cols, P, (size_t)Mpad * cols, Mpad, M, Y, rows); });
            std::vector<float> y0((size_t)M * rows);
            d.get(y0.data(), Y, y0.size());
            std::printf("  Q6E prompt: split %.1f us + dense %.1f us (%.2f T exact MAC/s)\n    error vs double: %s\n", us_s, ud, macs / ud / 1e6,
                        err_of(y0).c_str());
            // the same rows again (deterministic)
            xd::dense<4, 4, 2, 2, 4, false, 8, false, true, false, true>(d.q, e6, rows, cols, P, (size_t)Mpad * cols, Mpad, M, Y, rows).wait();
            {
                std::vector<float> y((size_t)M * rows);
                d.get(y.data(), Y, y.size());
                const bool same = !std::memcmp(y.data(), y0.data(), y.size() * 4);
                std::printf("    again: %s\n", same ? "same bits" : "DIFF");
                fails += !same;
            }
            // one token (fp32 input, split inside) and 2-8 tokens (parts)
            for (int r : {1, 2, 3, 4, 5, 8}) {
                if (r > M) continue;
                xd::EJobs jb;
                double us;
                if (r == 1) {
                    xd::ejob_add(jb, e6, rows, reinterpret_cast<const uint16_t *>(x), Y1, rows, xd::EK_Q6);
                    us = timeit([&] { xd::dgroupej<1, 128, true, true>(d.q, jb, cols, 1); });
                } else {
                    auto sp = [&]<int MP>() { xd::splite<MP>(d.q, x, cols, r, cols, Pe).wait(); };
                    if (r == 2) sp.template operator()<2>(); else if (r <= 4) sp.template operator()<4>(); else sp.template operator()<8>();
                    xd::ejob_add(jb, e6, rows, Pe, Y1, rows, xd::EK_Q6);
                    us = timeit([&] {
                        if (r == 2) xd::dgroupej<2>(d.q, jb, cols, r);
                        else if (r <= 4) xd::dgroupej<4>(d.q, jb, cols, r);
                        else xd::dgroupej<8>(d.q, jb, cols, r);
                    });
                }
                std::vector<float> y((size_t)r * rows);
                d.get(y.data(), Y1, y.size());
                const bool same = !std::memcmp(y.data(), y0.data(), y.size() * 4);
                std::printf("  ESIMD Q6E, %d tokens: %7.2f us (%.0f GB/s of Q6_K bytes)  %s\n", r, us, (double)v.rb * rows / us / 1e3,
                            same ? "same bits as the prompt kernel" : "DIFF");
                fails += !same;
            }
            // mixed: [Q8E blk.6.attn_q, this Q6E] in one launch, one token, against each alone
            if (cols == (int)q8.t->ne[0]) {
                xd::EJobs a, b, m;
                xd::ejob_add(a, q8e, q8rows, reinterpret_cast<const uint16_t *>(x), Y2, q8rows, xd::EK_Q8);
                xd::dgroupej<1, 128, true, true>(d.q, a, cols, 1).wait();
                std::vector<float> ya(q8rows), yb(rows), ma(q8rows), mb(rows);
                d.get(ya.data(), Y2, q8rows);
                xd::ejob_add(b, e6, rows, reinterpret_cast<const uint16_t *>(x), Y1, rows, xd::EK_Q6);
                xd::dgroupej<1, 128, true, true>(d.q, b, cols, 1).wait();
                d.get(yb.data(), Y1, rows);
                d.q.memset(Y1, 0, rows * 4).wait();
                d.q.memset(Y2, 0, q8rows * 4).wait();
                xd::ejob_add(m, q8e, q8rows, reinterpret_cast<const uint16_t *>(x), Y2, q8rows, xd::EK_Q8);
                xd::ejob_add(m, e6, rows, reinterpret_cast<const uint16_t *>(x), Y1, rows, xd::EK_Q6);
                const double um = timeit([&] { xd::dgroupej<1, 128, true, true>(d.q, m, cols, 1); });
                d.get(ma.data(), Y2, q8rows);
                d.get(mb.data(), Y1, rows);
                const bool same = !std::memcmp(ya.data(), ma.data(), q8rows * 4) && !std::memcmp(yb.data(), mb.data(), rows * 4);
                std::printf("  mixed Q8E + Q6E, one token: %.2f us  %s\n", um, same ? "same bits as alone" : "DIFF");
                fails += !same;
            }
        }
        std::printf("%s\n", fails ? "FAILURES" : "all same bits");
        return fails ? 1 : 0;
    } catch (const std::exception &e) {
        std::fprintf(stderr, "bench_xq6: %s\n", e.what());
        return 1;
    }
}
