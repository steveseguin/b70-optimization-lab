// bench_xq: the experts of layers 20-23 on the matrix engines (xmx_q.hpp) on the model's weights: the prompt kernel
// (prod) and the 1-8 token kernel (full) bit for bit on the same slots, the sums' error against double (units of
// 2^-24 x sum |w x|; the weights as planar.hpp's decoders give them, i.e. llama.cpp's fp32 values), time and card
// energy per launch.
//   bench_xq <model.gguf> <card> <tokens>     BENCH_X=<f32 rows of 2,304>: real hidden states as inputs (unit RMS)
#include "../src/tok_tiles.hpp"
#include "../src/xmx_q.hpp"
#include <random>

using namespace ink;

// the one-token FP32 kernels' order (GemvRoutedR): lane c % 16 adds chunk c's fma chain to its total, then the
// butterfly of sg_sum
static float today_dot(const float *w, const float *x, int cols) {
    float acc[16] = {};
    for (int c = 0; c < cols / 32; ++c) {
        float s = 0.0f;
        for (int i = 0; i < 32; ++i) s = std::fma(w[32 * c + i], x[32 * c + i], s);
        acc[c % 16] += s;
    }
    for (int o = 8; o > 0; o >>= 1) {
        float n[16];
        for (int l = 0; l < 16; ++l) n[l] = acc[l] + acc[l ^ o];
        std::copy(n, n + 16, acc);
    }
    return acc[0];
}
static void host_decode(const WView &v, const uint8_t *row, int cols, float *o) { // planar row -> fp32 weights
    for (int c = 0; c < cols / 32; ++c) {
        switch (v.kind) {
        case K_Q5_0P: pl::Q5_0P::decode32(row, cols, c, o + 32 * c); break;
        case K_IQ4_NLP: pl::IQ4_NLP::decode32(row, cols, c, o + 32 * c); break;
        case K_IQ4_XSP: pl::IQ4_XSP::decode32(row, cols, c, o + 32 * c); break;
        case K_Q4_KP: pl::Q4_KP::decode32(row, cols, c, o + 32 * c); break;
        case K_Q5_KP: pl::Q5_KP::decode32(row, cols, c, o + 32 * c); break;
        default: throw std::runtime_error("host_decode: kind");
        }
    }
}

int main(int argc, char **argv) {
    if (argc < 4) { std::fprintf(stderr, "usage: bench_xq <model.gguf> <card> <tokens>\n"); return 2; }
    std::setvbuf(stdout, nullptr, _IOLBF, 0);
    try {
        GGUF gf(argv[1]);
        Device d(std::atoi(argv[2]));
        Weights w;
        w.upload(d, gf, false);
        auto views = planarize(d, gf, w, false);
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 10;
        constexpr int NE = 128, KU = 8, E = 2304, NFF = 1152, SM = 4;
        const int ntok = std::atoi(argv[3]), K = ntok * KU;
        std::printf("local memory %zu bytes\n", d.q.get_device().get_info<sycl::info::device::local_mem_size>());
        std::mt19937 rng(7);
        std::vector<double> wexp(NE);
        for (int e = 0; e < NE; ++e) wexp[e] = 1.0 / (5.0 + (e * 53) % NE);
        std::vector<int32_t> hid(K);
        for (int t = 0; t < ntok; ++t) {
            std::vector<double> ww = wexp;
            for (int k = 0; k < KU; ++k) {
                std::discrete_distribution<int> dd(ww.begin(), ww.end());
                const int e = dd(rng);
                ww[e] = 0.0;
                hid[(size_t)t * KU + k] = e;
            }
        }
        std::normal_distribution<float> nd(0.0f, 1.0f);
        std::vector<float> hx((size_t)ntok * E);
        for (auto &v : hx) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
        if (const char *xf = std::getenv("BENCH_X")) {
            std::FILE *f = std::fopen(xf, "rb");
            if (!f) throw std::runtime_error("bench_xq: cannot open BENCH_X");
            std::vector<float> r;
            float buf[E];
            while (std::fread(buf, 4, E, f) == (size_t)E) r.insert(r.end(), buf, buf + E);
            std::fclose(f);
            const size_t nr = r.size() / E;
            if (!nr) throw std::runtime_error("bench_xq: BENCH_X has no rows");
            for (int t = 0; t < ntok; ++t) {
                const float *src = r.data() + (size_t)(t % nr) * E;
                double ss = 0;
                for (int c = 0; c < E; ++c) ss += (double)src[c] * src[c];
                const float sc = (float)(1.0 / std::sqrt(ss / E + 1e-6));
                for (int c = 0; c < E; ++c) hx[(size_t)t * E + c] = src[c] * sc;
            }
            std::printf("inputs: %zu real rows from %s, unit RMS\n", nr, xf);
        }
        float *x = d.alloc<float>(hx.size());
        int32_t *ids = d.alloc<int32_t>(K);
        d.put(x, hx.data(), hx.size());
        d.put(ids, hid.data(), hid.size());
        MoeGroups grp;
        grp.alloc(d, NE, K);
        moe_group(d.q, ids, K, NE, grp).wait();
        const int tiles = MoeGroups::max_tiles(NE, K);
        int nt = 0;
        d.get(&nt, grp.ntiles, 1);
        xm::Super st;
        st.alloc(d, NE, K, SM);
        const int stb = xm::Super::bound(NE, K, SM);
        xm::super_tiles(d.q, grp, NE, st).wait();
        std::vector<int32_t> hs0(nt), htn(nt), hsl(K);
        d.get(hs0.data(), grp.tile_s0, nt); d.get(htn.data(), grp.tile_n, nt); d.get(hsl.data(), grp.slots, K);
        std::vector<int> stile(K), srow(K);
        for (int t = 0; t < nt; ++t) for (int r = 0; r < htn[t]; ++r) { stile[hsl[hs0[t] + r]] = t; srow[hsl[hs0[t] + r]] = r; }
        // the first SMALL tokens through the small-step kernel: their own groups
        const int ns = std::min(ntok, 8), Ks = ns * KU;
        MoeGroups gs;
        gs.alloc(d, NE, Ks);
        moe_group(d.q, ids, Ks, NE, gs).wait();
        const int tiles_s = MoeGroups::max_tiles(NE, Ks);
        MoeGroups g1; // one token: tile k = slot k (the engine's x1)
        g1.alloc(d, NE, KU);
        {
            std::vector<int32_t> s(KU), one(KU, 1), ntl(1, KU);
            for (int k = 0; k < KU; ++k) s[k] = k;
            d.put(g1.tile_exp, hid.data(), KU); d.put(g1.tile_s0, s.data(), KU); d.put(g1.slots, s.data(), KU);
            d.put(g1.tile_n, one.data(), KU); d.put(g1.ntiles, ntl.data(), 1);
        }
        uint16_t *P = d.alloc<uint16_t>((size_t)tiles * 3 * 16 * E), *Hp = d.alloc<uint16_t>((size_t)tiles * 3 * 16 * NFF);
        const size_t pps = (size_t)(Ks + 8) * E, hps = (size_t)(Ks + 8) * NFF;
        uint16_t *Ps = d.alloc<uint16_t>(3 * pps), *Hs = d.alloc<uint16_t>(3 * hps), *P1 = d.alloc<uint16_t>(3 * (size_t)E);
        float *X = d.alloc<float>((size_t)ntok * (E / 32)), *X1 = d.alloc<float>(E / 32), *XG = d.alloc<float>((size_t)tiles * (E / 32) * 16);
        float *R = d.alloc<float>((size_t)K * 2 * NFF), *Y = d.alloc<float>((size_t)K * E);
        float *Rs = d.alloc<float>((size_t)Ks * 2 * NFF), *Ys = d.alloc<float>((size_t)Ks * E);
        xm::split_gather8(d.q, grp, tiles, x, E, KU, E, P).wait();
        d.q.memset(Ps, 0, 3 * pps * 2).wait();
        xm::split_gather_c(d.q, gs, Ks, x, E, KU, E, Ps, pps).wait();
        xm::split_row(d.q, x, E, P1).wait();
        xq::xsum(d.q, x, E, nullptr, 0, ntok, E, X).wait();
        xq::xgather(d.q, grp, tiles, X, KU, E / 32, XG).wait();
        { // the block sums from the parts give the same bits
            std::vector<float> a(E / 32), b(E / 32);
            xq::xsum(d.q, nullptr, 0, P1, E, 1, E, X1).wait();
            d.get(a.data(), X, E / 32); d.get(b.data(), X1, E / 32);
            std::printf("block sums from parts: %s\n", std::memcmp(a.data(), b.data(), a.size() * 4) ? "DIFF" : "same");
        }
        const xm::ActOp op{nullptr, 8.0f, 4.0f};
        double ej = 0.0;
        auto timeit = [&](auto &&launch) {
            for (int i = 0; i < 2; ++i) launch();
            d.q.wait();
            const double e0 = d.energy_j(), t0 = now_s();
            for (int i = 0; i < iters; ++i) launch();
            d.q.wait();
            const double us = (now_s() - t0) / iters * 1e6;
            ej = (d.energy_j() - e0) / iters;
            return us;
        };
        auto line = [&](const char *what, double us, double macs) {
            std::printf("  %-30s %9.1f us  %5.2f T exact MAC/s  %5.1f pJ/MAC  %4.0f W\n", what, us, macs / us / 1e6, ej / macs * 1e12, ej / us * 1e6);
        };
        uint8_t *tmp = nullptr;
        size_t tmpb = 0;
        for (int L = 20; L <= 23; ++L) {
            auto dec = [&](WView v) { // the engine's planar decode copy (engine.hpp gu_dec / dn_dec)
                if (v.kind != K_RAW) return v;
                if (!v.p) throw std::runtime_error("bench_xq: tensor not on the card");
                v.kind = dec_kind(*v.t);
                v.rb = dec_stride(*v.t);
                uint8_t *b = d.alloc<uint8_t>(v.rb * (size_t)v.t->rows());
                dec_repack(d.q, *v.t, v.p, b).wait();
                v.p = b;
                return v;
            };
            const WView gu = dec(views.at("blk." + std::to_string(L) + ".ffn_gate_up_exps.weight"));
            const WView dn = dec(views.at("blk." + std::to_string(L) + ".ffn_down_exps.weight"));
            const int fg = xq::fmt_of(gu.t->type), fd = xq::fmt_of(dn.t->type);
            const size_t gub = gu.rb * (size_t)(2 * NFF), dnb = dn.rb * (size_t)E;
            std::printf("layer %d: gate|up %s (kind %d), down %s (kind %d)\n", L, type_name(gu.t->type), gu.kind, type_name(dn.t->type), dn.kind);
            // accuracy samples: rows read (and decoded) before the layout changes
            constexpr int NS = 2000;
            std::mt19937 rs(3 + L);
            std::vector<int> smp_slot(NS), smp_rg(NS), smp_rd(NS);
            std::vector<float> wg((size_t)NS * E), wd((size_t)NS * NFF);
            {
                std::vector<uint8_t> row(std::max(gu.rb, dn.rb));
                for (int i = 0; i < NS; ++i) {
                    smp_slot[i] = (int)(rs() % K); smp_rg[i] = (int)(rs() % (2 * NFF)); smp_rd[i] = (int)(rs() % E);
                    const int e = hid[smp_slot[i]];
                    d.get(row.data(), gu.p + (size_t)e * gub + (size_t)smp_rg[i] * gu.rb, gu.rb);
                    host_decode(gu, row.data(), E, wg.data() + (size_t)i * E);
                    d.get(row.data(), dn.p + (size_t)e * dnb + (size_t)smp_rd[i] * dn.rb, dn.rb);
                    host_decode(dn, row.data(), NFF, wd.data() + (size_t)i * NFF);
                }
            }
            if (std::max(gub, dnb) > tmpb) { if (tmp) d.release(tmp); tmpb = std::max(gub, dnb); tmp = d.alloc<uint8_t>(tmpb); }
            const double t0 = now_s();
            xq::repack(d.q, fg, const_cast<uint8_t *>(gu.p), gu.rb, 2 * NFF, E, NE, tmp);
            xq::repack(d.q, fd, const_cast<uint8_t *>(dn.p), dn.rb, E, NFF, NE, tmp);
            std::printf("  layout: %.2f s\n", now_s() - t0);
            // prompt kernel: sums (tests), gate|up + act, down
            d.q.memset(R, 0, (size_t)K * 2 * NFF * 4).wait();
            xq::prod<2>(d.q, fg, gu.p, gub, E, NFF, NFF / 16, grp, st, stb, P, XG, op, nullptr, R, 2 * NFF).wait();
            const double mac_gu = (double)K * 2 * NFF * E, mac_dn = (double)K * E * NFF;
            double us = timeit([&] { xq::prod<0>(d.q, fg, gu.p, gub, E, NFF, NFF / 16, grp, st, stb, P, XG, op, Hp, nullptr, 0); });
            line("prompt gate|up", us, mac_gu);
            us = timeit([&] { xq::prod<1>(d.q, fd, dn.p, dnb, NFF, NFF, E / 32, grp, st, stb, Hp, nullptr, op, nullptr, Y, E); });
            line("prompt down", us, mac_dn);
            std::vector<float> R0((size_t)K * 2 * NFF), Y0((size_t)K * E);
            std::vector<uint16_t> H0((size_t)nt * 3 * 16 * NFF);
            d.get(R0.data(), R, R0.size()); d.get(Y0.data(), Y, Y0.size()); d.get(H0.data(), Hp, H0.size());
            // small steps: the first ns tokens (MMAX 8) and token 0 alone (one), against the prompt kernel's slots
            d.q.memset(Rs, 0, (size_t)Ks * 2 * NFF * 4).wait();
            xq::full<8, 2>(d.q, fg, gu.p, gub, E, NFF, 2 * NFF, gs, tiles_s, Ps, pps, false, X, KU, op, nullptr, 0, Rs, 2 * NFF).wait();
            xq::full<8, 0>(d.q, fg, gu.p, gub, E, NFF, 2 * NFF, gs, tiles_s, Ps, pps, false, X, KU, op, Hs, hps, nullptr, 0).wait();
            xq::full<8, 1>(d.q, fd, dn.p, dnb, NFF, NFF, E, gs, tiles_s, Hs, hps, false, nullptr, KU, op, nullptr, 0, Ys, E).wait();
            std::vector<float> Rsh((size_t)Ks * 2 * NFF), Ysh((size_t)Ks * E);
            d.get(Rsh.data(), Rs, Rsh.size()); d.get(Ysh.data(), Ys, Ysh.size());
            const bool same_r = !std::memcmp(Rsh.data(), R0.data(), Rsh.size() * 4), same_y = !std::memcmp(Ysh.data(), Y0.data(), Ysh.size() * 4);
            // one token
            xq::xsum(d.q, nullptr, 0, P1, E, 1, E, X1).wait();
            xq::full<1, 2>(d.q, fg, gu.p, gub, E, NFF, 2 * NFF, g1, KU, P1, E, true, X1, KU, op, nullptr, 0, Rs, 2 * NFF).wait();
            xq::full<1, 0>(d.q, fg, gu.p, gub, E, NFF, 2 * NFF, g1, KU, P1, E, true, X1, KU, op, Hs, hps, nullptr, 0).wait();
            xq::full<1, 1>(d.q, fd, dn.p, dnb, NFF, NFF, E, g1, KU, Hs, hps, false, nullptr, KU, op, nullptr, 0, Ys, E).wait();
            d.get(Rsh.data(), Rs, (size_t)KU * 2 * NFF); d.get(Ysh.data(), Ys, (size_t)KU * E);
            const bool same_r1 = !std::memcmp(Rsh.data(), R0.data(), (size_t)KU * 2 * NFF * 4), same_y1 = !std::memcmp(Ysh.data(), Y0.data(), (size_t)KU * E * 4);
            std::printf("  vs the prompt kernel: %d tokens sums %s, down %s; 1 token sums %s, down %s\n", ns, same_r ? "same" : "DIFF", same_y ? "same" : "DIFF",
                        same_r1 ? "same" : "DIFF", same_y1 ? "same" : "DIFF");
            us = timeit([&] {
                xq::full<1, 0>(d.q, fg, gu.p, gub, E, NFF, 2 * NFF, g1, KU, P1, E, true, X1, KU, op, Hs, hps, nullptr, 0);
            });
            line("1 token gate|up", us, (double)KU * 2 * NFF * E);
            us = timeit([&] { xq::full<1, 1>(d.q, fd, dn.p, dnb, NFF, NFF, E, g1, KU, Hs, hps, false, nullptr, KU, op, nullptr, 0, Ys, E); });
            line("1 token down", us, (double)KU * E * NFF);
            us = timeit([&] { xq::full<8, 0>(d.q, fg, gu.p, gub, E, NFF, 2 * NFF, gs, tiles_s, Ps, pps, false, X, KU, op, Hs, hps, nullptr, 0); });
            line("8 tokens gate|up", us, (double)Ks * 2 * NFF * E);
            // accuracy against double
            double sg = 0, mg = 0, sd = 0, md = 0, tg = 0, tgm = 0, td = 0, tdm = 0;
            const size_t ph = (size_t)16 * NFF;
            for (int i = 0; i < NS; ++i) {
                const int slot = smp_slot[i], tok = slot / KU;
                {
                    double ref = 0, ab = 0;
                    for (int c = 0; c < E; ++c) { const double p = (double)wg[(size_t)i * E + c] * hx[(size_t)tok * E + c]; ref += p; ab += std::fabs(p); }
                    const double err = ab > 0 ? std::fabs(R0[(size_t)slot * 2 * NFF + smp_rg[i]] - ref) / (std::ldexp(1.0, -24) * ab) : 0.0;
                    sg += err; mg = std::max(mg, err);
                    const double et = ab > 0 ? std::fabs(today_dot(wg.data() + (size_t)i * E, hx.data() + (size_t)tok * E, E) - ref) / (std::ldexp(1.0, -24) * ab) : 0.0;
                    tg += et; tgm = std::max(tgm, et);
                }
                {
                    const int t = stile[slot], sr = srow[slot];
                    double ref = 0, ab = 0;
                    float hf[NFF];
                    for (int c = 0; c < NFF; ++c) {
                        const size_t o = (size_t)t * 3 * ph + (size_t)sr * NFF + c;
                        const double h = (double)bf_f(H0[o]) + (double)bf_f(H0[o + ph]) + (double)bf_f(H0[o + 2 * ph]);
                        hf[c] = (float)h;
                        const double p = (double)wd[(size_t)i * NFF + c] * h;
                        ref += p; ab += std::fabs(p);
                    }
                    const double err = ab > 0 ? std::fabs(Y0[(size_t)slot * E + smp_rd[i]] - ref) / (std::ldexp(1.0, -24) * ab) : 0.0;
                    sd += err; md = std::max(md, err);
                    const double et = ab > 0 ? std::fabs(today_dot(wd.data() + (size_t)i * NFF, hf, NFF) - ref) / (std::ldexp(1.0, -24) * ab) : 0.0;
                    td += et; tdm = std::max(tdm, et);
                }
            }
            std::printf("  error vs double, %d samples: gate|up mean %.4f max %.4f, down mean %.4f max %.4f\n", NS, sg / NS, mg, sd / NS, md);
            std::printf("  today's FP32 order (host):        gate|up mean %.4f max %.4f, down mean %.4f max %.4f\n", tg / NS, tgm, td / NS, tdm);
            d.release(const_cast<uint8_t *>(gu.p));
            d.release(const_cast<uint8_t *>(dn.p));
        }
    } catch (const std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
