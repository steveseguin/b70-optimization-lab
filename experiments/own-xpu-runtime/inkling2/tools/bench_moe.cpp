// bench_moe: time the grouped expert kernels of steps with several tokens (moe_group.hpp) on the model's NVFP4
// expert tensors, and check every layout against the first kernels (GroupedPair / GroupedRows) bit for bit.
//   bench_moe <model.gguf> <card> <tokens>...
// Routing: each token picks 8 distinct experts from a skewed distribution (fixed seed). Each timed launch uses the
// next of layers 0-19 (all NVFP4), so the weights come from memory. BENCH_ITERS (default 20).
#include "../src/tok_tiles.hpp"
#include <random>
#include <functional>

int main(int argc, char **argv) {
    using namespace ink;
    if (argc < 4) { std::fprintf(stderr, "usage: bench_moe <model.gguf> <card> <tokens>...\n"); return 2; }
    try {
        GGUF g(argv[1]);
        Device d(std::atoi(argv[2]));
        Weights w;
        w.upload(d, g, false);
        auto views = planarize(d, g, w, false);
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 20;
        constexpr int NL = 20, NE = 128, KU = 8, E = 2304, NFF = 1152;
        std::vector<WView> gu(NL), dn(NL);
        for (int l = 0; l < NL; ++l) {
            gu[l] = views.at("blk." + std::to_string(l) + ".ffn_gate_up_exps.weight");
            dn[l] = views.at("blk." + std::to_string(l) + ".ffn_down_exps.weight");
            if (gu[l].kind != K_NVFP4P || dn[l].kind != K_NVFP4P) throw std::runtime_error("layer " + std::to_string(l) + " is not NVFP4");
        }
        if (std::getenv("BENCH_DECODE")) { // one-token expert kernels: 8 experts from one layer vs from all 20 layers
            std::mt19937 rng(5);
            std::vector<int32_t> hid(16 * KU);
            for (int st = 0; st < 16; ++st)
                for (int k = 0; k < KU; ++k) hid[st * KU + k] = ((st * KU + k) * 37 + 11) % NE;
            int32_t *ids = d.alloc<int32_t>(hid.size());
            d.put(ids, hid.data(), hid.size());
            std::vector<float> hx(E);
            std::normal_distribution<float> nd(0.0f, 1.0f);
            for (auto &v : hx) v = nd(rng);
            float *x = d.alloc<float>(E), *hb = d.alloc<float>((size_t)KU * NFF), *y = d.alloc<float>((size_t)KU * E);
            d.put(x, hx.data(), E);
            d.q.memset(hb, 0, (size_t)KU * NFF * 4).wait();
            const size_t gub = gu[0].rb * (size_t)gu[0].t->ne[1];
            { // launch cost vs size: K slots (experts) per launch, experts from 20 layers; x has 2 rows (slots 8+ use row 1)
                float *x2 = d.alloc<float>(2 * E), *hb2 = d.alloc<float>((size_t)16 * NFF), *y2 = d.alloc<float>((size_t)16 * E);
                d.put(x2, hx.data(), E); d.put(x2 + E, hx.data(), E);
                d.q.memset(hb2, 0, (size_t)16 * NFF * 4).wait();
                int32_t *ids16 = d.alloc<int32_t>(16 * 16);
                std::vector<int32_t> h16(16 * 16);
                for (int i = 0; i < 256; ++i) h16[i] = (i * 37 + 11) % NE;
                d.put(ids16, h16.data(), h16.size());
                for (int K : {1, 2, 4, 8, 16}) {
                    const int it = 640;
                    auto g = [&](int i) {
                        const WView &v = gu[(i / 16) % 20];
                        SituOp so{nullptr, ids16 + (i % 16) * 16, 8.0f, 4.0f, hb2, NFF};
                        gemv_pair(d.q, v, v.p + (size_t)NFF * v.rb, gub, NFF, ids16 + (i % 16) * 16, K, x2, E, KU, so, 2);
                    };
                    Tune dtu{2, 2};
                    if (const char *e = std::getenv("BENCH_DT")) std::sscanf(e, "%d,%d", &dtu.R, &dtu.sgw);
                    auto dn2 = [&](int i) { gemv_routed_v(d.q, dn[(i / 16) % 20], ids16 + (i % 16) * 16, K, hb2, NFF, 1, y2, E, dtu); };
                    for (int i = 0; i < 32; ++i) { g(i); dn2(i); }
                    d.q.wait();
                    double t0 = now_s();
                    for (int i = 0; i < it; ++i) g(i);
                    d.q.wait();
                    double ug = (now_s() - t0) / it * 1e6;
                    t0 = now_s();
                    for (int i = 0; i < it; ++i) dn2(i);
                    d.q.wait();
                    double ud = (now_s() - t0) / it * 1e6;
                    std::printf("K=%2d slots: gate_up %7.2f us (%.1f GB/s), down %7.2f us (%.1f GB/s)\n", K, ug,
                                K * 23.89e6 / 8 / ug / 1e3, ud, K * 11.94e6 / 8 / ud / 1e3);
                }
            }
            for (int nl : {1, 4, 20}) {
                auto run = [&](int i) {
                    const WView &v = gu[(i / 16) % nl];
                    SituOp so{nullptr, ids + (i % 16) * KU, 8.0f, 4.0f, hb, NFF};
                    gemv_pair(d.q, v, v.p + (size_t)NFF * v.rb, gub, NFF, ids + (i % 16) * KU, KU, x, E, 1, so, 2);
                };
                auto rund = [&](int i) { gemv_routed_v(d.q, dn[(i / 16) % nl], ids + (i % 16) * KU, KU, hb, NFF, 1, y, E, Tune{2, 2}); };
                for (int pass = 0; pass < 2; ++pass) {
                    std::function<void(int)> f = pass ? std::function<void(int)>(rund) : std::function<void(int)>(run);
                    for (int i = 0; i < 32; ++i) f(i);
                    d.q.wait();
                    const int it = 640;
                    double t0 = now_s();
                    for (int i = 0; i < it; ++i) f(i);
                    d.q.wait();
                    std::printf("decode %s, experts from %2d layer(s): %7.2f us per launch\n", pass ? "down   " : "gate_up", nl, (now_s() - t0) / it * 1e6);
                }
            }
            // light load between the expert kernels: one work-group spinning about n iterations
            float *tmp = d.alloc<float>(4096);
            auto spin = [&](int n) {
                d.q.parallel_for(sycl::nd_range<1>(sycl::range<1>(16), sycl::range<1>(16)), [=](sycl::nd_item<1> it) {
                    float v = x[it.get_local_id(0)];
                    for (int k = 0; k < n; ++k) v = v * 0.999f + 0.001f;
                    tmp[it.get_local_id(0)] = v;
                });
            };
            for (int n : {20000, 100000}) {
                const int it2 = 300;
                double t0 = now_s();
                for (int i = 0; i < it2; ++i) spin(n);
                d.q.wait();
                double us_s = (now_s() - t0) / it2 * 1e6;
                for (int pass = 0; pass < 2; ++pass) {
                    t0 = now_s();
                    for (int i = 0; i < it2; ++i) {
                        spin(n);
                        const WView &v = gu[(i / 16) % 20];
                        SituOp so{nullptr, ids + (i % 16) * KU, 8.0f, 4.0f, hb, NFF};
                        if (pass == 0) gemv_pair(d.q, v, v.p + (size_t)NFF * v.rb, gub, NFF, ids + (i % 16) * KU, KU, x, E, 1, so, 2);
                        else gemv_routed_v(d.q, dn[(i / 16) % 20], ids + (i % 16) * KU, KU, hb, NFF, 1, y, E, Tune{2, 2});
                    }
                    d.q.wait();
                    double us_b = (now_s() - t0) / it2 * 1e6;
                    std::printf("light load: spin %.1f us alone; spin + %s %.1f us -> %s share %.2f us\n", us_s, pass ? "down" : "gate_up", us_b,
                                pass ? "down" : "gate_up", us_b - us_s);
                }
            }
            // context: the gate_up kernel alone vs. each launch after a small one-work-group kernel (as in the engine)
            auto tiny = [&]() {
                d.q.parallel_for(sycl::nd_range<1>(sycl::range<1>(256), sycl::range<1>(256)), [=](sycl::nd_item<1> it) {
                    float v = x[it.get_local_id(0)];
                    v = sycl::reduce_over_group(it.get_group(), v, sycl::plus<float>());
                    tmp[it.get_local_id(0)] = v;
                });
            };
            auto gu1 = [&](int i) {
                const WView &v = gu[(i / 16) % 20];
                SituOp so{nullptr, ids + (i % 16) * KU, 8.0f, 4.0f, hb, NFF};
                gemv_pair(d.q, v, v.p + (size_t)NFF * v.rb, gub, NFF, ids + (i % 16) * KU, KU, x, E, 1, so, 2);
            };
            const int it = 640;
            for (int rep = 0; rep < 2; ++rep) {
                double t0 = now_s();
                for (int i = 0; i < it; ++i) tiny();
                d.q.wait();
                double ut = (now_s() - t0) / it * 1e6;
                t0 = now_s();
                for (int i = 0; i < it; ++i) gu1(i);
                d.q.wait();
                double ug = (now_s() - t0) / it * 1e6;
                t0 = now_s();
                for (int i = 0; i < it; ++i) { tiny(); gu1(i); }
                d.q.wait();
                double ub = (now_s() - t0) / it * 1e6;
                t0 = now_s();
                for (int i = 0; i < it; ++i) { tiny(); tiny(); tiny(); tiny(); gu1(i); }
                d.q.wait();
                double u4 = (now_s() - t0) / it * 1e6;
                std::printf("context: tiny %.2f us, gate_up %.2f us, tiny+gate_up %.2f us (gate_up share %.2f), 4 tiny+gate_up %.2f (share %.2f)\n",
                            ut, ug, ub, ub - ut, u4, u4 - 4 * ut);
            }
            return 0;
        }
        for (int a = 3; a < argc; ++a) {
            const int ntok = std::atoi(argv[a]), K = ntok * KU;
            std::mt19937 rng(11 + ntok);
            std::vector<double> wexp(NE);
            for (int e = 0; e < NE; ++e) wexp[e] = 1.0 / (5.0 + (e * 53) % NE); // skewed popularity
            std::vector<int32_t> hid(K);
            for (int t = 0; t < ntok; ++t) {
                std::vector<double> ww = wexp;
                for (int k = 0; k < KU; ++k) {
                    std::discrete_distribution<int> dd(ww.begin(), ww.end());
                    int e = dd(rng);
                    ww[e] = 0.0;
                    hid[(size_t)t * KU + k] = e;
                }
            }
            std::normal_distribution<float> nd(0.0f, 1.0f);
            std::vector<float> hx((size_t)ntok * E), hh((size_t)K * NFF);
            for (auto &v : hx) v = nd(rng);
            for (auto &v : hh) v = nd(rng) * 0.1f;
            float *x = d.alloc<float>(hx.size()), *hb = d.alloc<float>(hh.size());
            float *hout0 = d.alloc<float>((size_t)K * NFF), *hout1 = d.alloc<float>((size_t)K * NFF);
            float *y0 = d.alloc<float>((size_t)K * E), *y1 = d.alloc<float>((size_t)K * E);
            int32_t *ids = d.alloc<int32_t>(K);
            d.put(x, hx.data(), hx.size());
            d.put(hb, hh.data(), hh.size());
            d.put(ids, hid.data(), hid.size());
            MoeGroups grp;
            grp.alloc(d, NE, K);
            moe_group(d.q, ids, K, NE, grp).wait();
            int na = 0;
            d.get(&na, grp.count, 1);
            const int amax = std::min(NE, K);
            const size_t gub = gu[0].rb * (size_t)gu[0].t->ne[1], dnb = dn[0].rb * (size_t)dn[0].t->ne[1];
            const double bytes_gu = (double)gub * na, bytes_dn = (double)dnb * na;
            std::printf("tokens %d: %d slots, %d experts used, gate_up %.1f MB, down %.1f MB per launch\n", ntok, K, na,
                        bytes_gu / 1e6, bytes_dn / 1e6);
            auto timeit = [&](auto &&launch) {
                for (int i = 0; i < 2; ++i) launch(i);
                d.q.wait();
                double t0 = now_s();
                for (int i = 0; i < iters; ++i) launch(i + 1);
                d.q.wait();
                double us = (now_s() - t0) / iters * 1e6;
                launch(0);
                d.q.wait();
                return us;
            };
            std::vector<float> h0((size_t)K * NFF), h1((size_t)K * NFF), z0((size_t)K * E), z1((size_t)K * E);
            auto cmp = [](const std::vector<float> &u, const std::vector<float> &v) {
                for (size_t i = 0; i < u.size(); ++i) if (std::memcmp(&u[i], &v[i], 4)) return (long)i;
                return -1L;
            };
            // gate_up + SITU
            auto pair_run = [&](GTune gt, float *hout) {
                return timeit([&](int i) {
                    const WView &v = gu[i % NL];
                    SituOp so{nullptr, ids, 8.0f, 4.0f, hout, NFF};
                    grouped_pair(d.q, v, v.p + (size_t)NFF * v.rb, gub, NFF, grp, amax, x, E, KU, so, gt.sgw, gt);
                });
            };
            double us0 = pair_run(GTune{0, 8, 2}, hout0);
            d.get(h0.data(), hout0, h0.size());
            std::printf("  gate_up  first kernel          sg2  %9.1f us  %6.1f GB/s\n", us0, bytes_gu / us0 / 1e3);
            auto gp = [&](int np, int mb, bool big, int sgw) {
                d.q.memset(hout1, 0, h1.size() * 4).wait();
                double us = pair_run(GTune{np, mb, sgw, big}, hout1);
                d.get(h1.data(), hout1, h1.size());
                long bad = cmp(h0, h1);
                std::printf("  gate_up  np%d mb%-2d %s      sg%d  %9.1f us  %6.1f GB/s  x%.2f  %s\n", np, mb, big ? "grf256" : "grf128", sgw,
                            us, bytes_gu / us / 1e3, us0 / us, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
            };
            const int tiles = MoeGroups::max_tiles(NE, K);
            int nt = 0;
            d.get(&nt, grp.ntiles, 1);
            std::printf("  %d tiles of up to 16 slots (%.0f %% of lanes used)\n", nt, 100.0 * K / (16.0 * nt));
            auto gpt = [&](int ng, bool big, int sgw) {
                d.q.memset(hout1, 0, h1.size() * 4).wait();
                GTune gt{ng, 8, sgw, big, true, tiles};
                double us = pair_run(gt, hout1);
                d.get(h1.data(), hout1, h1.size());
                long bad = cmp(h0, h1);
                std::printf("  gate_up  token-par %2d rows %s sg%d  %9.1f us  %6.1f GB/s  x%.2f  %s\n", 2 * ng, big ? "grf256" : "grf128", sgw,
                            us, bytes_gu / us / 1e3, us0 / us, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
            };
#define INK_B(NG, BIG) for (int sgw : {1, 2, 4}) gpt(NG, BIG, sgw);
            INK_TSP_COMBOS(INK_B)
#undef INK_B
            // transposed tiles
            float *Xt = d.alloc<float>((size_t)tiles * E * MOE_TS), *Ht = d.alloc<float>((size_t)tiles * NFF * MOE_TS);
            double ug = timeit([&](int) { tile_gather(d.q, grp, tiles, x, E, KU, E, Xt); });
            std::printf("  tile_gather x (%d x %d)                %9.1f us\n", tiles, E, ug);
            std::vector<int32_t> hts(tiles), htn(tiles), hsl(K);
            d.get(hts.data(), grp.tile_s0, nt); d.get(htn.data(), grp.tile_n, nt); d.get(hsl.data(), grp.slots, K);
            auto gptt = [&](int ng, bool big, bool il, int sgw) {
                TTune tt{ng, sgw, big, il};
                d.q.memset(hout1, 0, h1.size() * 4).wait();
                double us = timeit([&](int i) {
                    const WView &v = gu[i % NL];
                    SituOp so{nullptr, ids, 8.0f, 4.0f, hout1, NFF};
                    slot_pair_t(d.q, v, v.p + (size_t)NFF * v.rb, gub, NFF, grp, tiles, Xt, so, nullptr, tt);
                });
                d.get(h1.data(), hout1, h1.size());
                long bad = cmp(h0, h1);
                // the same with the activation written to the transposed tiles
                double ust = timeit([&](int i) {
                    const WView &v = gu[i % NL];
                    SituOp so{nullptr, ids, 8.0f, 4.0f, nullptr, NFF};
                    slot_pair_t(d.q, v, v.p + (size_t)NFF * v.rb, gub, NFF, grp, tiles, Xt, so, Ht, tt);
                });
                std::vector<float> ht((size_t)nt * NFF * MOE_TS);
                d.get(ht.data(), Ht, ht.size());
                long badt = -1;
                for (int t = 0; t < nt && badt < 0; ++t)
                    for (int l = 0; l < htn[t] && badt < 0; ++l) {
                        int sl = hsl[hts[t] + l];
                        for (int r = 0; r < NFF; ++r)
                            if (std::memcmp(&ht[((size_t)t * NFF + r) * MOE_TS + l], &h0[(size_t)sl * NFF + r], 4)) { badt = (long)sl * NFF + r; break; }
                    }
                std::printf("  gate_up  tiles %2d rows %s %s sg%d  %9.1f us  %6.1f GB/s  x%.2f  %s | to tiles %9.1f us  %s\n", 2 * ng,
                            big ? "grf256" : "grf128", il ? "il" : "  ", sgw, us, bytes_gu / us / 1e3, us0 / us,
                            bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str(), ust, badt < 0 ? "same" : ("DIFF at " + std::to_string(badt)).c_str());
            };
#define INK_B(NG, BIG, IL) for (int sgw : {1, 2, 4}) gptt(NG, BIG, IL, sgw);
            INK_TTP_COMBOS(INK_B)
#undef INK_B
            for (int ng : {1, 2}) { // generic tile kernels (tok_tiles.hpp)
                double us = timeit([&](int i) {
                    const WView &v = gu[i % NL];
                    SituOp so{nullptr, ids, 8.0f, 4.0f, nullptr, NFF};
                    slot_pair_g(d.q, v, v.p + (size_t)NFF * v.rb, gub, NFF, grp, tiles, Xt, so, Ht, ng);
                });
                std::vector<float> ht((size_t)nt * NFF * MOE_TS);
                d.get(ht.data(), Ht, ht.size());
                long badt = -1;
                for (int t = 0; t < nt && badt < 0; ++t)
                    for (int l = 0; l < htn[t] && badt < 0; ++l) {
                        int sl = hsl[hts[t] + l];
                        for (int r = 0; r < NFF; ++r)
                            if (std::memcmp(&ht[((size_t)t * NFF + r) * MOE_TS + l], &h0[(size_t)sl * NFF + r], 4)) { badt = (long)sl * NFF + r; break; }
                    }
                std::printf("  gate_up  generic tiles %d rows  to tiles %9.1f us  x%.2f  %s\n", 2 * ng, us, us0 / us,
                            badt < 0 ? "same" : ("DIFF at " + std::to_string(badt)).c_str());
            }
            for (int cmb = 0; cmb < 12; ++cmb) { // pairs of tiles (tok_tiles.hpp slot_pair_g2): ng x pair x big
                const int ng = cmb / 4 == 0 ? 1 : cmb / 4 == 1 ? 2 : 4;
                const bool pair = cmb & 1, big = cmb & 2;
                d.q.memset(Ht, 0, (size_t)tiles * NFF * MOE_TS * 4).wait();
                double us = timeit([&](int i) {
                    const WView &v = gu[i % NL];
                    SituOp so{nullptr, ids, 8.0f, 4.0f, nullptr, NFF};
                    slot_pair_g2(d.q, v, v.p + (size_t)NFF * v.rb, gub, NFF, grp, tiles, Xt, so, Ht, ng, pair, big);
                });
                std::vector<float> ht((size_t)nt * NFF * MOE_TS);
                d.get(ht.data(), Ht, ht.size());
                long badt = -1;
                for (int t = 0; t < nt && badt < 0; ++t)
                    for (int l = 0; l < htn[t] && badt < 0; ++l) {
                        int sl = hsl[hts[t] + l];
                        for (int r = 0; r < NFF; ++r)
                            if (std::memcmp(&ht[((size_t)t * NFF + r) * MOE_TS + l], &h0[(size_t)sl * NFF + r], 4)) { badt = (long)sl * NFF + r; break; }
                    }
                std::printf("  gate_up  %s %d rows %s to tiles %9.1f us  x%.2f  %s\n", pair ? "tile pairs" : "two tiles ", 2 * ng,
                            big ? "grf256" : "grf128", us, us0 / us,
                            badt < 0 ? "same" : ("DIFF at " + std::to_string(badt)).c_str());
            }
            if (std::getenv("BENCH_ALL")) {
#define INK_B(NP, MB, BIG) for (int sgw : {1, 2, 4}) gp(NP, MB, BIG, sgw);
            INK_GP_COMBOS(INK_B)
#undef INK_B
            }
            // down
            auto rows_run = [&](GTune gt, float *y) {
                return timeit([&](int i) { grouped_rows(d.q, dn[i % NL], grp, amax, hb, NFF, y, E, gt.sgw, gt); });
            };
            double ud0 = rows_run(GTune{0, 8, 2}, y0);
            d.get(z0.data(), y0, z0.size());
            std::printf("  down     first kernel          sg2  %9.1f us  %6.1f GB/s\n", ud0, bytes_dn / ud0 / 1e3);
            auto gr = [&](int r, int mb, bool big, int sgw) {
                d.q.memset(y1, 0, z1.size() * 4).wait();
                double us = rows_run(GTune{r, mb, sgw, big}, y1);
                d.get(z1.data(), y1, z1.size());
                long bad = cmp(z0, z1);
                std::printf("  down     R%d mb%-2d %s       sg%d  %9.1f us  %6.1f GB/s  x%.2f  %s\n", r, mb, big ? "grf256" : "grf128", sgw,
                            us, bytes_dn / us / 1e3, ud0 / us, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
            };
            auto grt = [&](int r, bool big, int sgw) {
                d.q.memset(y1, 0, z1.size() * 4).wait();
                double us = rows_run(GTune{r, 8, sgw, big, true, tiles}, y1);
                d.get(z1.data(), y1, z1.size());
                long bad = cmp(z0, z1);
                std::printf("  down     token-par %2d rows %s sg%d  %9.1f us  %6.1f GB/s  x%.2f  %s\n", r, big ? "grf256" : "grf128", sgw,
                            us, bytes_dn / us / 1e3, ud0 / us, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
            };
#define INK_B(R, BIG) for (int sgw : {1, 2, 4}) grt(R, BIG, sgw);
            INK_TSR_COMBOS(INK_B)
#undef INK_B
            tile_gather(d.q, grp, tiles, hb, NFF, 0, NFF, Ht).wait();
            auto grtt = [&](int r, bool big, bool il, int sgw) {
                d.q.memset(y1, 0, z1.size() * 4).wait();
                double us = timeit([&](int i) { slot_rows_t(d.q, dn[i % NL], grp, tiles, Ht, y1, E, TTune{r, sgw, big, il}); });
                d.get(z1.data(), y1, z1.size());
                long bad = cmp(z0, z1);
                std::printf("  down     tiles %2d rows %s %s sg%d  %9.1f us  %6.1f GB/s  x%.2f  %s\n", r, big ? "grf256" : "grf128",
                            il ? "il" : "  ", sgw, us, bytes_dn / us / 1e3, ud0 / us, bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
            };
#define INK_B(R, BIG, IL) for (int sgw : {1, 2, 4}) grtt(R, BIG, IL, sgw);
            INK_TTR_COMBOS(INK_B)
#undef INK_B
            for (int r : {1, 2}) {
                d.q.memset(y1, 0, z1.size() * 4).wait();
                double us = timeit([&](int i) { slot_rows_g(d.q, dn[i % NL], grp, tiles, Ht, y1, E, r); });
                d.get(z1.data(), y1, z1.size());
                long bad = cmp(z0, z1);
                std::printf("  down     generic tiles %d rows           %9.1f us  x%.2f  %s\n", r, us, ud0 / us,
                            bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
            }
            for (int cmb = 0; cmb < 12; ++cmb) {
                const int r = cmb / 4 == 0 ? 1 : cmb / 4 == 1 ? 2 : 4;
                const bool pair = cmb & 1, big = cmb & 2;
                d.q.memset(y1, 0, z1.size() * 4).wait();
                double us = timeit([&](int i) { slot_rows_g2(d.q, dn[i % NL], grp, tiles, Ht, y1, E, r, pair, big); });
                d.get(z1.data(), y1, z1.size());
                long bad = cmp(z0, z1);
                std::printf("  down     %s %d rows %s        %9.1f us  x%.2f  %s\n", pair ? "tile pairs" : "two tiles ", r,
                            big ? "grf256" : "grf128", us, ud0 / us,
                            bad < 0 ? "same" : ("DIFF at " + std::to_string(bad)).c_str());
            }
            // layers 20-23 (file-layout formats): first kernels vs generic tiles
            for (int l = 20; l < 24; ++l) {
                {
                    const Tensor *tg = g.find("blk." + std::to_string(l) + ".ffn_gate_up_exps.weight");
                    const Tensor *td = g.find("blk." + std::to_string(l) + ".ffn_down_exps.weight");
                    WView vg{tg, w[tg->name], tg->row_bytes(), K_RAW}, vd{td, w[td->name], td->row_bytes(), K_RAW};
                    const size_t eg = vg.rb * (size_t)tg->ne[1];
                    d.q.memset(hout0, 0, h0.size() * 4).wait();
                    double ua = timeit([&](int) { SituOp so{nullptr, ids, 8.0f, 4.0f, hout0, NFF};
                                                  grouped_pair(d.q, vg, vg.p + (size_t)NFF * vg.rb, eg, NFF, grp, amax, x, E, KU, so, 2); });
                    d.get(h0.data(), hout0, h0.size());
                    double ub = timeit([&](int) { SituOp so{nullptr, ids, 8.0f, 4.0f, nullptr, NFF};
                                                  slot_pair_g(d.q, vg, vg.p + (size_t)NFF * vg.rb, eg, NFF, grp, tiles, Xt, so, Ht, 2); });
                    std::vector<float> ht((size_t)nt * NFF * MOE_TS);
                    d.get(ht.data(), Ht, ht.size());
                    long badt = -1;
                    for (int t = 0; t < nt && badt < 0; ++t)
                        for (int ll = 0; ll < htn[t] && badt < 0; ++ll) {
                            int sl = hsl[hts[t] + ll];
                            for (int r = 0; r < NFF; ++r)
                                if (std::memcmp(&ht[((size_t)t * NFF + r) * MOE_TS + ll], &h0[(size_t)sl * NFF + r], 4)) { badt = (long)sl * NFF + r; break; }
                        }
                    d.q.memset(y0, 0, z0.size() * 4).wait();
                    double uc = timeit([&](int) { grouped_rows(d.q, vd, grp, amax, hb, NFF, y0, E, 2); });
                    d.get(z0.data(), y0, z0.size());
                    tile_gather(d.q, grp, tiles, hb, NFF, 0, NFF, Ht).wait();
                    d.q.memset(y1, 0, z1.size() * 4).wait();
                    double ud = timeit([&](int) { slot_rows_g(d.q, vd, grp, tiles, Ht, y1, E, 2); });
                    d.get(z1.data(), y1, z1.size());
                    long badd = cmp(z0, z1);
                    { // the same tiles on the decode copies (gemv2.hpp dec_repack): same bits as the file layout's
                        auto mkd = [&](const Tensor *t, const WView &v) {
                            WView o = v;
                            if (dec_kind(*t) == K_RAW) return o;
                            o.kind = dec_kind(*t); o.rb = dec_stride(*t);
                            uint8_t *b = d.alloc<uint8_t>(o.rb * (size_t)t->rows());
                            dec_repack(d.q, *t, v.p, b).wait();
                            o.p = b;
                            return o;
                        };
                        WView dg = mkd(tg, vg), dd = mkd(td, vd);
                        const size_t egd = dg.rb * (size_t)tg->ne[1];
                        std::vector<float> ht1((size_t)nt * NFF * MOE_TS);
                        double ue = timeit([&](int) { SituOp so{nullptr, ids, 8.0f, 4.0f, nullptr, NFF};
                                                      slot_pair_g(d.q, dg, dg.p + (size_t)NFF * dg.rb, egd, NFF, grp, tiles, Xt, so, Ht, 2); });
                        d.get(ht1.data(), Ht, ht1.size());
                        const bool sg_same = std::memcmp(ht1.data(), ht.data(), ht.size() * 4) == 0;
                        tile_gather(d.q, grp, tiles, hb, NFF, 0, NFF, Ht).wait();
                        std::vector<float> z2(z1.size());
                        d.q.memset(y1, 0, z1.size() * 4).wait();
                        double uf = timeit([&](int) { slot_rows_g(d.q, dd, grp, tiles, Ht, y1, E, 2); });
                        d.get(z2.data(), y1, z2.size());
                        const bool sd_same = std::memcmp(z2.data(), z1.data(), z1.size() * 4) == 0;
                        std::printf("  layer %d decode copies: gate_up tiles %9.1f us %s   down tiles %9.1f us %s\n", l, ue,
                                    sg_same ? "same" : "DIFF", uf, sd_same ? "same" : "DIFF");
                        if (dg.p != vg.p) d.release((void *)dg.p);
                        if (dd.p != vd.p) d.release((void *)dd.p);
                    }
                    std::printf("  layer %d %s/%s: gate_up %9.1f -> %9.1f us %s   down %9.1f -> %9.1f us %s\n", l, type_name(tg->type),
                                type_name(td->type), ua, ub, badt < 0 ? "same" : ("DIFF at " + std::to_string(badt)).c_str(), uc, ud,
                                badd < 0 ? "same" : ("DIFF at " + std::to_string(badd)).c_str());
                }
            }
            if (std::getenv("BENCH_ALL")) {
#define INK_B(R, MB, BIG) for (int sgw : {1, 2, 4}) gr(R, MB, BIG, sgw);
            INK_GR_COMBOS(INK_B)
#undef INK_B
            }
            for (void *p : {(void *)x, (void *)hb, (void *)hout0, (void *)hout1, (void *)y0, (void *)y1, (void *)ids, (void *)Xt, (void *)Ht}) d.release(p);
        }
    } catch (std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
