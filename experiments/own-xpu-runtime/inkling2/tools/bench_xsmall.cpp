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
        }
    } catch (const std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
