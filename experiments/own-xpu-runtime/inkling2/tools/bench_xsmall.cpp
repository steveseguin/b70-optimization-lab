// bench_xsmall: the experts of steps of 1-8 tokens on the matrix engines (xmx_moe.hpp XSmall + small_fold) against
// today's kernels for those steps (one token: gemv_pair + gemv_routed_v, lane order; 2-8 tokens: moe_group +
// grouped_pair_t + grouped_rows_t), on the model's weights of layers 0-19 (each timed launch uses the next layer), and
// bit for bit against the prompt kernel (XProd2) on the same routing: the gate|up sums and the down outputs.
//   bench_xsmall <model.gguf> <card> [tokens...]   (default 1 2 4 8)
#include "../src/tok_tiles.hpp"
#include "../src/xmx_moe.hpp"
#include <random>

using namespace ink;

int main(int argc, char **argv) {
    if (argc < 3) { std::fprintf(stderr, "usage: bench_xsmall <model.gguf> <card> [tokens...]\n"); return 2; }
    try {
        GGUF gf(argv[1]);
        Device d(std::atoi(argv[2]));
        Weights w;
        w.upload(d, gf, false);
        auto views = planarize(d, gf, w, false);
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 200;
        constexpr int NL = 20, NE = 128, KU = 8, E = 2304, NFF = 1152;
        std::vector<WView> gu(NL), dn(NL);
        for (int l = 0; l < NL; ++l) {
            gu[l] = views.at("blk." + std::to_string(l) + ".ffn_gate_up_exps.weight");
            dn[l] = views.at("blk." + std::to_string(l) + ".ffn_down_exps.weight");
        }
        const size_t gub = gu[0].rb * (size_t)gu[0].t->ne[1], dnb = dn[0].rb * (size_t)dn[0].t->ne[1];
        std::vector<int> toks;
        for (int i = 3; i < argc; ++i) toks.push_back(std::atoi(argv[i]));
        if (toks.empty()) toks = {1, 2, 4, 8};
        const int NT = 8, KM = NT * KU, XLE = (int)xlane_floats(E), XLF = (int)xlane_floats(NFF);
        auto timeit = [&](auto &&launch) {
            for (int i = 0; i < 3; ++i) launch(i);
            d.q.wait();
            const double t0 = now_s();
            for (int i = 0; i < iters; ++i) launch(i + 1);
            d.q.wait();
            const double us = (now_s() - t0) / iters * 1e6;
            launch(0);
            d.q.wait();
            return us;
        };
        // routing and inputs per step size
        struct Case { int ntok; std::vector<int32_t> ids; std::vector<float> x; double today_gu = 0, today_dn = 0; };
        std::vector<Case> cases;
        std::mt19937 rng(11);
        std::normal_distribution<float> nd(0.0f, 1.0f);
        for (int nt : toks) {
            Case c;
            c.ntok = nt;
            for (int t = 0; t < nt; ++t) {
                std::vector<int> pick;
                while ((int)pick.size() < KU) {
                    const int e = (int)(rng() % NE);
                    if (std::find(pick.begin(), pick.end(), e) == pick.end()) pick.push_back(e);
                }
                for (int e : pick) c.ids.push_back(e);
            }
            c.x.resize((size_t)nt * E);
            for (auto &v : c.x) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
            cases.push_back(c);
        }
        int32_t *ids = d.alloc<int32_t>(KM);
        float *x = d.alloc<float>((size_t)NT * E), *xl = d.alloc<float>((size_t)NT * XLE);
        float *hb = d.alloc<float>((size_t)KM * XLF), *y = d.alloc<float>((size_t)KM * E);
        MoeGroups grp;
        grp.alloc(d, NE, KM);
        auto load_case = [&](const Case &c) {
            d.put(ids, c.ids.data(), c.ids.size());
            d.put(x, c.x.data(), c.x.size());
            std::vector<float> l((size_t)c.ntok * XLE, 0.0f);
            for (int t = 0; t < c.ntok; ++t)
                for (int i = 0; i < E; ++i) l[(size_t)t * XLE + xlane_at(i)] = c.x[(size_t)t * E + i];
            d.put(xl, l.data(), l.size());
            moe_group(d.q, ids, c.ntok * KU, NE, grp).wait();
        };
        std::printf("today's kernels (us per launch, layers rotating):\n");
        for (auto &c : cases) {
            load_case(c);
            const int K = c.ntok * KU, amax = std::min(NE, K);
            SituOp sl{nullptr, ids, 8.0f, 4.0f, hb, NFF};
            sl.ldo = XLF;
            if (c.ntok == 1) {
                c.today_gu = timeit([&](int i) { const WView &v = gu[i % NL];
                    gemv_pair(d.q, v, v.p + (size_t)NFF * v.rb, gub, NFF, ids, K, xl, XLE, KU, sl, 1, true); });
                c.today_dn = timeit([&](int i) { gemv_routed_v(d.q, dn[i % NL], ids, K, hb, XLF, 1, y, E, Tune{1, 1}, true); });
            } else {
                c.today_gu = timeit([&](int i) { const WView &v = gu[i % NL];
                    grouped_pair_t(d.q, v, v.p + (size_t)NFF * v.rb, gub, NFF, grp, amax, xl, XLE, KU, sl, c.ntok, 1, 1); });
                c.today_dn = timeit([&](int i) { grouped_rows_t(d.q, dn[i % NL], grp, amax, hb, XLF, y, E, c.ntok, 2, 1); });
                const double ug = timeit([&](int) { moe_group(d.q, ids, K, NE, grp); });
                std::printf("  %d tokens: moe_group %.1f\n", c.ntok, ug);
            }
            std::printf("  %d tokens: gate|up %.1f  down %.1f  (sum %.1f)\n", c.ntok, c.today_gu, c.today_dn, c.today_gu + c.today_dn);
        }
        { // the tile layout, in place
            uint8_t *tmp = d.alloc<uint8_t>(std::max(gub, dnb));
            for (int l = 0; l < NL; ++l) {
                xm::repack_tiles(d.q, const_cast<uint8_t *>(gu[l].p), gu[l].rb, 2 * NFF, E, NE, tmp);
                xm::repack_tiles(d.q, const_cast<uint8_t *>(dn[l].p), dn[l].rb, E, NFF, NE, tmp);
            }
            sycl::free(tmp, d.q);
        }
        // one token: tile k = slot k (no grouping)
        MoeGroups one = grp;
        {
            std::vector<int32_t> iota(KM), ones(KM, 1);
            for (int i = 0; i < KM; ++i) iota[i] = i;
            one.slots = d.alloc<int32_t>(KM); one.tile_s0 = d.alloc<int32_t>(KM); one.tile_n = d.alloc<int32_t>(KM); one.ntiles = d.alloc<int32_t>(1);
            d.put(one.slots, iota.data(), KM); d.put(one.tile_s0, iota.data(), KM); d.put(one.tile_n, ones.data(), KM);
            const int n8 = KU;
            d.put(one.ntiles, &n8, 1);
            one.tile_exp = ids;
        }
        const int tiles = MoeGroups::max_tiles(NE, KM), ngu = (E / 16 + 15) / 16, ndn = (NFF / 16 + 15) / 16;
        uint16_t *P = d.alloc<uint16_t>((size_t)tiles * 3 * 16 * E), *Hp = d.alloc<uint16_t>((size_t)tiles * 3 * 16 * NFF);
        uint16_t *Hp16 = d.alloc<uint16_t>((size_t)tiles * 3 * 16 * NFF);
        float *S = d.alloc<float>((size_t)tiles * ngu * 8 * 2 * NFF), *S2 = d.alloc<float>((size_t)tiles * ndn * 8 * E);
        float *R = d.alloc<float>((size_t)KM * 2 * NFF), *R2 = d.alloc<float>((size_t)KM * 2 * NFF), *Y2 = d.alloc<float>((size_t)KM * E);
        const xm::ActOp op{nullptr, 8.0f, 4.0f};
        const size_t pcp = (size_t)(KM + 8) * E, hcp = (size_t)(KM + 8) * NFF;
        uint16_t *Pc = d.alloc<uint16_t>(3 * pcp), *Hc = d.alloc<uint16_t>(3 * hcp);
        d.q.memset(Pc, 0, 3 * pcp * 2); d.q.memset(Hc, 0, 3 * hcp * 2).wait();
        int32_t *ctr = d.alloc<int32_t>(4096), *ctr2 = d.alloc<int32_t>(4096);
        d.q.memset(ctr, 0, 4096 * 4); d.q.memset(ctr2, 0, 4096 * 4).wait();
        xm::Super st;
        st.alloc(d, NE, KM, 4);
        const int stb = xm::Super::bound(NE, KM, 4);
        std::printf("matrix engines (us per launch):\n");
        for (auto &c : cases) {
            load_case(c);
            const int K = c.ntok * KU, M = c.ntok <= 1 ? 1 : c.ntok <= 2 ? 2 : c.ntok <= 4 ? 4 : 8;
            const MoeGroups &gg = c.ntok == 1 ? one : grp;
            const size_t pt = c.ntok == 1 ? 0 : (size_t)3 * 16 * E, pp = c.ntok == 1 ? (size_t)E : (size_t)16 * E;
            auto disp = [&]<int MODE>(const uint8_t *W, size_t es, int cols, int ncol, int nrb, const uint16_t *Pin, size_t ptt, size_t ppp, float *So) {
                if (M == 1) xm::small_prod<1, MODE>(d.q, W, es, cols, NFF, ncol, nrb, gg, KM, Pin, ptt, ppp, So);
                else if (M == 2) xm::small_prod<2, MODE>(d.q, W, es, cols, NFF, ncol, nrb, gg, KM, Pin, ptt, ppp, So);
                else if (M == 4) xm::small_prod<4, MODE>(d.q, W, es, cols, NFF, ncol, nrb, gg, KM, Pin, ptt, ppp, So);
                else xm::small_prod<8, MODE>(d.q, W, es, cols, NFF, ncol, nrb, gg, KM, Pin, ptt, ppp, So);
            };
            const double us_split = timeit([&](int) {
                if (c.ntok == 1) xm::split_row(d.q, x, E, P);
                else xm::split_gather8(d.q, grp, KM, x, E, KU, E, P);
            });
            const double us_gu = timeit([&](int i) { disp.template operator()<0>(gu[i % NL].p, gub, E, 2 * NFF, NFF / 16, P, pt, pp, S); });
            const double us_fa = timeit([&](int) { xm::small_fold_act(d.q, gg, KM, ngu, M, S, NFF, op, M, Hp); });
            const size_t hpt = (size_t)3 * M * NFF, hpp = (size_t)M * NFF;
            const double us_dn = timeit([&](int i) { disp.template operator()<1>(dn[i % NL].p, dnb, NFF, E, E / 32, Hp, hpt, hpp, S2); });
            const double us_fo = timeit([&](int) { xm::small_fold_out(d.q, gg, KM, ndn, M, S2, E, y, E); });
            std::printf("  %d tokens: split %.1f  gate|up %.1f  fold %.1f  down %.1f  fold %.1f  (sum %.1f; today %.1f)\n", c.ntok, us_split, us_gu,
                        us_fa, us_dn, us_fo, us_split + us_gu + us_fa + us_dn + us_fo, c.today_gu + c.today_dn);
            // bits against the prompt kernel on the same routing (layer 0)
            if (c.ntok == 1) xm::split_row(d.q, x, E, P);
            else xm::split_gather8(d.q, grp, KM, x, E, KU, E, P);
            disp.template operator()<0>(gu[0].p, gub, E, 2 * NFF, NFF / 16, P, pt, pp, S);
            xm::small_fold_act(d.q, gg, KM, ngu, M, S, NFF, op, M, Hp);
            disp.template operator()<1>(dn[0].p, dnb, NFF, E, E / 32, Hp, hpt, hpp, S2);
            xm::small_fold_out(d.q, gg, KM, ndn, M, S2, E, y, E);
            disp.template operator()<2>(gu[0].p, gub, E, 2 * NFF, NFF / 16, P, pt, pp, S);
            xm::small_fold_out(d.q, gg, KM, ngu, M, S, 2 * NFF, R, 2 * NFF).wait();
            xm::split_gather8(d.q, grp, KM, x, E, KU, E, P);
            xm::super_tiles(d.q, grp, NE, st);
            xm::prod2<4, 4, 4, 2>(d.q, gu[0].p, gub, E, NFF, NFF / 16, grp, st, stb, P, op, nullptr, R2, 2 * NFF);
            xm::prod2<4, 4, 4, 0>(d.q, gu[0].p, gub, E, NFF, NFF / 16, grp, st, stb, P, op, Hp16, nullptr, 0);
            xm::prod2<4, 4, 4, 1>(d.q, dn[0].p, dnb, NFF, NFF, E / 32, grp, st, stb, Hp16, op, nullptr, Y2, E).wait();
            std::vector<float> a((size_t)K * 2 * NFF), b(a.size()), ya((size_t)K * E), yb(ya.size());
            d.get(a.data(), R, a.size()); d.get(b.data(), R2, b.size()); d.get(ya.data(), y, ya.size()); d.get(yb.data(), Y2, yb.size());
            long da = 0, dy = 0;
            for (size_t i = 0; i < a.size(); ++i) da += std::memcmp(&a[i], &b[i], 4) != 0;
            for (size_t i = 0; i < ya.size(); ++i) dy += std::memcmp(&ya[i], &yb[i], 4) != 0;
            std::printf("    vs the prompt kernel: gate|up sums %s (%ld of %zu differ), down %s (%ld of %zu differ)\n", da ? "DIFF" : "same", da, a.size(),
                        dy ? "DIFF" : "same", dy, ya.size());
            // second form (XSmall2): in-kernel split (one token) or compact gather, rows per tile by count, in-group fold
            const int tl = c.ntok == 1 ? KU : K;
            auto v2 = [&]<int PF, int GRF, int ABL = 0>(const char *name) {
                auto gather = [&]() { if (c.ntok > 1) xm::split_gather_c(d.q, grp, K, x, E, KU, E, Pc, pcp); };
                auto gup = [&](int l) {
                    if (c.ntok == 1) xm::small2<1, 0, true, PF, GRF, ABL>(d.q, gu[l].p, gub, E, NFF, NFF / 16, one, tl, nullptr, 0, xl, true, op, Hc, hcp, nullptr, 0);
                    else xm::small2<8, 0, false, PF, GRF, ABL>(d.q, gu[l].p, gub, E, NFF, NFF / 16, grp, tl, Pc, pcp, nullptr, false, op, Hc, hcp, nullptr, 0);
                };
                auto dnp = [&](int l) {
                    if (c.ntok == 1) xm::small2<1, 1, false, PF, GRF, ABL>(d.q, dn[l].p, dnb, NFF, NFF, E / 32, one, tl, Hc, hcp, nullptr, false, op, nullptr, 0, y, E);
                    else xm::small2<8, 1, false, PF, GRF, ABL>(d.q, dn[l].p, dnb, NFF, NFF, E / 32, grp, tl, Hc, hcp, nullptr, false, op, nullptr, 0, y, E);
                };
                const double tg = c.ntok > 1 ? timeit([&](int) { gather(); }) : 0.0;
                const double t1 = timeit([&](int i) { gup(i % NL); });
                const double t2 = timeit([&](int i) { dnp(i % NL); });
                d.q.memset(y, 0xff, (size_t)KM * E * 4).wait();
                gather(); gup(0); dnp(0);
                d.q.wait();
                std::vector<float> yc((size_t)K * E);
                d.get(yc.data(), y, yc.size());
                long dd = 0;
                for (size_t i = 0; i < yc.size(); ++i) dd += std::memcmp(&yc[i], &yb[i], 4) != 0;
                std::printf("  %d tokens, XSmall2 %-12s gather %.1f  gate|up %.1f  down %.1f  (sum %.1f; today %.1f)  down vs the prompt kernel: %s (%ld of %zu differ)\n",
                            c.ntok, name, tg, t1, t2, tg + t1 + t2, c.today_gu + c.today_dn, dd ? "DIFF" : "same", dd, yc.size());
            };
            v2.template operator()<2, 128>("PF2");
            // third form (XSmall3): XSmall's groups + passes + rows by count + compact rows, separate in-order folds
            auto v3 = [&]<int SR, int PF>(const char *name) {
                constexpr int MX = 8;
                const bool one1 = c.ntok == 1;
                const MoeGroups &g3 = one1 ? one : grp;
                const uint16_t *Pin = one1 ? P : Pc;
                const size_t ppi = one1 ? (size_t)E : pcp;
                auto split = [&]() { if (one1) xm::split_row(d.q, x, E, P); else xm::split_gather_c(d.q, grp, K, x, E, KU, E, Pc, pcp); };
                auto gup = [&](int l) {
                    if (one1) xm::small3<1, 0, SR, PF>(d.q, gu[l].p, gub, E, NFF, 2 * NFF, NFF / 16, g3, tl, Pin, ppi, true, S);
                    else xm::small3<MX, 0, SR, PF>(d.q, gu[l].p, gub, E, NFF, 2 * NFF, NFF / 16, g3, tl, Pin, ppi, false, S);
                };
                const int mm = one1 ? 1 : MX;
                auto fa = [&]() { xm::small_fold_act_c(d.q, g3, tl, ngu, mm, S, NFF, op, Hc, hcp); };
                auto dnp = [&](int l) {
                    if (one1) xm::small3<1, 1, SR, PF>(d.q, dn[l].p, dnb, NFF, NFF, E, E / 32, g3, tl, Hc, hcp, false, S2);
                    else xm::small3<MX, 1, SR, PF>(d.q, dn[l].p, dnb, NFF, NFF, E, E / 32, g3, tl, Hc, hcp, false, S2);
                };
                auto fo = [&]() { xm::small_fold_out_c(d.q, g3, tl, ndn, mm, S2, E, y, E); };
                const double t0 = timeit([&](int) { split(); });
                const double t1 = timeit([&](int i) { gup(i % NL); });
                const double t2 = timeit([&](int) { fa(); });
                const double t3 = timeit([&](int i) { dnp(i % NL); });
                const double t4 = timeit([&](int) { fo(); });
                d.q.memset(y, 0xff, (size_t)KM * E * 4).wait();
                split(); gup(0); fa(); dnp(0); fo();
                d.q.wait();
                std::vector<float> yc((size_t)K * E);
                d.get(yc.data(), y, yc.size());
                long dd = 0;
                for (size_t i = 0; i < yc.size(); ++i) dd += std::memcmp(&yc[i], &yb[i], 4) != 0;
                std::printf("  %d tokens, XSmall3 %-8s split %.1f  gate|up %.1f  fold %.1f  down %.1f  fold %.1f  (sum %.1f; today %.1f)  down vs the prompt kernel: %s (%ld of %zu differ)\n",
                            c.ntok, name, t0, t1, t2, t3, t4, t0 + t1 + t2 + t3 + t4, c.today_gu + c.today_dn, dd ? "DIFF" : "same", dd, yc.size());
            };
            v3.template operator()<4, 1>("SR4 PF1");
            // decode variant and the gate|up fold inside the down kernel (no fold launch)
            auto v4 = [&]<int DV, bool HIN, int SRD>(const char *name) {
                constexpr int MX = 8;
                const bool one1 = c.ntok == 1;
                const MoeGroups &g3 = one1 ? one : grp;
                const uint16_t *Pin = one1 ? P : Pc;
                const size_t ppi = one1 ? (size_t)E : pcp;
                const int mm = one1 ? 1 : MX;
                auto split = [&]() { if (one1) xm::split_row(d.q, x, E, P); else xm::split_gather_c(d.q, grp, K, x, E, KU, E, Pc, pcp); };
                auto gup = [&](int l) {
                    if (one1) xm::small3<1, 0, 4, 1, 0, DV>(d.q, gu[l].p, gub, E, NFF, 2 * NFF, NFF / 16, g3, tl, Pin, ppi, true, S);
                    else xm::small3<MX, 0, 4, 1, 0, DV>(d.q, gu[l].p, gub, E, NFF, 2 * NFF, NFF / 16, g3, tl, Pin, ppi, false, S);
                };
                auto fa = [&]() { if (!HIN) xm::small_fold_act_c(d.q, g3, tl, ngu, mm, S, NFF, op, Hc, hcp); };
                auto dnp = [&](int l) {
                    if (one1) xm::small3<1, 1, SRD, 1, 0, DV, HIN>(d.q, dn[l].p, dnb, NFF, NFF, E, E / 32, g3, tl, Hc, hcp, false, S2, nullptr, op, nullptr, 0, nullptr, 0, S, ngu);
                    else xm::small3<MX, 1, SRD, 1, 0, DV, HIN>(d.q, dn[l].p, dnb, NFF, NFF, E, E / 32, g3, tl, Hc, hcp, false, S2, nullptr, op, nullptr, 0, nullptr, 0, S, ngu);
                };
                auto fo = [&]() { xm::small_fold_out_c(d.q, g3, tl, ndn, mm, S2, E, y, E); };
                const double t1 = timeit([&](int i) { gup(i % NL); });
                const double t2 = HIN ? 0.0 : timeit([&](int) { fa(); });
                if (HIN) gup(0);
                const double t3 = timeit([&](int i) { dnp(i % NL); });
                d.q.memset(y, 0xff, (size_t)KM * E * 4).wait();
                split(); gup(0); fa(); dnp(0); fo();
                d.q.wait();
                std::vector<float> yc((size_t)K * E);
                d.get(yc.data(), y, yc.size());
                long dd = 0;
                for (size_t i = 0; i < yc.size(); ++i) dd += std::memcmp(&yc[i], &yb[i], 4) != 0;
                std::printf("  %d tokens, XSmall3 %-14s gate|up %.1f  fold %.1f  down %.1f  (gate|up + fold + down %.1f)  down vs the prompt kernel: %s (%ld differ)\n",
                            c.ntok, name, t1, t2, t3, t1 + t2 + t3, dd ? "DIFF" : "same", dd);
            };
            v4.template operator()<2, false, 4>("regB SR4");
            // fourth form: all inputs per sub-group, no folds (ffn_tail reads y as today)
            auto v5 = [&]<int PF, int SRF, int GRF, int PD = 0, int HL = 1, bool SWAP = false>(const char *name) {
                constexpr int MX = 8;
                const bool one1 = c.ntok == 1;
                const MoeGroups &g3 = one1 ? one : grp;
                const uint16_t *Pin = one1 ? P : Pc;
                const size_t ppi = one1 ? (size_t)E : pcp;
                auto split = [&]() { if (one1) xm::split_row(d.q, x, E, P); else xm::split_gather_c(d.q, grp, K, x, E, KU, E, Pc, pcp); };
                auto gup = [&](int l) {
                    if (one1) xm::full_prod<1, 0, PF, SRF, GRF, PD, HL, SWAP>(d.q, gu[l].p, gub, E, NFF, 2 * NFF, g3, tl, Pin, ppi, true, op, Hc, hcp, nullptr, 0);
                    else xm::full_prod<MX, 0, PF, SRF, GRF, PD, HL, SWAP>(d.q, gu[l].p, gub, E, NFF, 2 * NFF, g3, tl, Pin, ppi, false, op, Hc, hcp, nullptr, 0);
                };
                auto dnp = [&](int l) {
                    if (one1) xm::full_prod<1, 1, PF, SRF, GRF, PD, HL, SWAP>(d.q, dn[l].p, dnb, NFF, NFF, E, g3, tl, Hc, hcp, false, op, nullptr, 0, y, E);
                    else xm::full_prod<MX, 1, PF, SRF, GRF, PD, HL, SWAP>(d.q, dn[l].p, dnb, NFF, NFF, E, g3, tl, Hc, hcp, false, op, nullptr, 0, y, E);
                };
                const double t1 = timeit([&](int i) { gup(i % NL); });
                const double t3 = timeit([&](int i) { dnp(i % NL); });
                d.q.memset(y, 0xff, (size_t)KM * E * 4).wait();
                split(); gup(0); dnp(0);
                d.q.wait();
                std::vector<float> yc((size_t)K * E);
                d.get(yc.data(), y, yc.size());
                long dd = 0;
                for (size_t i = 0; i < yc.size(); ++i) dd += std::memcmp(&yc[i], &yb[i], 4) != 0;
                std::printf("  %d tokens, XFull %-14s gate|up %.1f  down %.1f  (sum %.1f)  down vs the prompt kernel: %s (%ld differ)\n",
                            c.ntok, name, t1, t3, t1 + t3, dd ? "DIFF" : "same", dd);
            };
            v5.template operator()<4, 2, 128>("PF4 SRF2");
            v5.template operator()<4, 2, 128, 0, 1, true>("PF4 SRF2 swap");
            v5.template operator()<4, 2, 128, 8, 1>("PD8 L1");
            v5.template operator()<4, 2, 128, 16, 1>("PD16 L1");
            v5.template operator()<4, 2, 128, 32, 1>("PD32 L1");
            v5.template operator()<4, 2, 128, 16, 3>("PD16 L3");
            v5.template operator()<4, 2, 128, 32, 3>("PD32 L3");
            v5.template operator()<4, 2, 128, 64, 3>("PD64 L3");
            auto v6 = [&]<int PF, int SRF, int KS>(const char *name) {
                constexpr int MX = 8;
                const bool one1 = c.ntok == 1;
                const MoeGroups &g3 = one1 ? one : grp;
                const uint16_t *Pin = one1 ? P : Pc;
                const size_t ppi = one1 ? (size_t)E : pcp;
                auto split = [&]() { if (one1) xm::split_row(d.q, x, E, P); else xm::split_gather_c(d.q, grp, K, x, E, KU, E, Pc, pcp); };
                auto gup = [&](int l) {
                    if (one1) xm::full_prodk<1, 0, PF, SRF, KS>(d.q, gu[l].p, gub, E, NFF, 2 * NFF, g3, tl, Pin, ppi, true, op, Hc, hcp, nullptr, 0);
                    else xm::full_prodk<MX, 0, PF, SRF, KS>(d.q, gu[l].p, gub, E, NFF, 2 * NFF, g3, tl, Pin, ppi, false, op, Hc, hcp, nullptr, 0);
                };
                auto dnp = [&](int l) {
                    if (one1) xm::full_prodk<1, 1, PF, SRF, KS>(d.q, dn[l].p, dnb, NFF, NFF, E, g3, tl, Hc, hcp, false, op, nullptr, 0, y, E);
                    else xm::full_prodk<MX, 1, PF, SRF, KS>(d.q, dn[l].p, dnb, NFF, NFF, E, g3, tl, Hc, hcp, false, op, nullptr, 0, y, E);
                };
                const double t1 = timeit([&](int i) { gup(i % NL); });
                const double t3 = timeit([&](int i) { dnp(i % NL); });
                d.q.memset(y, 0xff, (size_t)KM * E * 4).wait();
                split(); gup(0); dnp(0);
                d.q.wait();
                std::vector<float> yc((size_t)K * E);
                d.get(yc.data(), y, yc.size());
                long dd = 0;
                for (size_t i = 0; i < yc.size(); ++i) dd += std::memcmp(&yc[i], &yb[i], 4) != 0;
                std::printf("  %d tokens, XFullK %-13s gate|up %.1f  down %.1f  (sum %.1f)  down vs the prompt kernel: %s (%ld differ)\n",
                            c.ntok, name, t1, t3, t1 + t3, dd ? "DIFF" : "same", dd);
            };
            v6.template operator()<4, 2, 3>("KS3");
        }
    } catch (const std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
