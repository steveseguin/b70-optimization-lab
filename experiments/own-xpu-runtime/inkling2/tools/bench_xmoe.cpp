// bench_xmoe: the NVFP4 experts on the matrix engines (xmx_moe.hpp) against today's tile kernels (slot_pair_g2 /
// slot_rows_g2, the engine's defaults), on the model's weights of layers 0-19 (each timed launch uses the next layer):
// time and card energy per launch, every configuration bit for bit against the first, and the sums' error against
// double on a sample, in units of 2^-24 x sum |w x| (README "Matrix engines with exact products").
//   bench_xmoe <model.gguf> <card> <tokens>
#include "../src/tok_tiles.hpp"
#include "../src/xmx_moe.hpp"
#include <functional>
#include <random>

using namespace ink;

static float host_ue4m3(uint8_t x) {
    const int e = (x >> 3) & 0xF, m = x & 0x7;
    if (x == 0x7F) return 0.0f;
    return e ? std::ldexp((float)(8 + m), e - 11) : (float)m * 0x1p-10f;
}
static double host_nvfp4(const uint8_t *row, int cols, int i) { // value i of a planar NVFP4 row
    const int blk = i / 16, w = i % 16;
    const uint8_t byte = row[blk * 8 + (w % 8)];
    const int nib = w < 8 ? (byte & 0xF) : (byte >> 4);
    static const int mag[8] = {0, 1, 2, 3, 4, 6, 8, 12};
    const double v = mag[nib & 7] * (double)host_ue4m3(row[cols / 2 + blk]);
    return (nib & 8) ? -v : v;
}

int main(int argc, char **argv) {
    if (argc < 4) { std::fprintf(stderr, "usage: bench_xmoe <model.gguf> <card> <tokens>\n"); return 2; }
    try {
        GGUF gf(argv[1]);
        Device d(std::atoi(argv[2]));
        Weights w;
        w.upload(d, gf, false);
        auto views = planarize(d, gf, w, false);
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 20;
        constexpr int NL = 20, NE = 128, KU = 8, E = 2304, NFF = 1152;
        std::vector<WView> gu(NL), dn(NL);
        for (int l = 0; l < NL; ++l) {
            gu[l] = views.at("blk." + std::to_string(l) + ".ffn_gate_up_exps.weight");
            dn[l] = views.at("blk." + std::to_string(l) + ".ffn_down_exps.weight");
            if (gu[l].kind != K_NVFP4P || dn[l].kind != K_NVFP4P) throw std::runtime_error("layer " + std::to_string(l) + " is not NVFP4");
        }
        const int ntok = std::atoi(argv[3]), K = ntok * KU;
        std::mt19937 rng(7);
        std::vector<double> wexp(NE);
        for (int e = 0; e < NE; ++e) wexp[e] = 1.0 / (5.0 + (e * 53) % NE); // skewed popularity (bench_moe)
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
        float *x = d.alloc<float>(hx.size());
        int32_t *ids = d.alloc<int32_t>(K);
        d.put(x, hx.data(), hx.size());
        d.put(ids, hid.data(), hid.size());
        MoeGroups grp;
        grp.alloc(d, NE, K);
        moe_group(d.q, ids, K, NE, grp).wait();
        const int tiles = MoeGroups::max_tiles(NE, K);
        int nt = 0, na = 0;
        d.get(&nt, grp.ntiles, 1);
        d.get(&na, grp.count, 1);
        const size_t gub = gu[0].rb * (size_t)gu[0].t->ne[1], dnb = dn[0].rb * (size_t)dn[0].t->ne[1];
        const double mac_gu = (double)K * 2 * NFF * E, mac_dn = (double)K * E * NFF;
        std::printf("tokens %d: %d slots, %d experts, %d tiles (%.0f %% of rows used)\n", ntok, K, na, nt, 100.0 * K / (16.0 * nt));
        double ej = 0.0;
        auto timeit = [&](auto &&launch) {
            for (int i = 0; i < 2; ++i) launch(i);
            d.q.wait();
            const double e0 = d.energy_j(), t0 = now_s();
            for (int i = 0; i < iters; ++i) launch(i + 1);
            d.q.wait();
            const double us = (now_s() - t0) / iters * 1e6;
            ej = (d.energy_j() - e0) / iters;
            launch(0);
            d.q.wait();
            return us;
        };
        auto line = [&](const char *what, double us, double macs) {
            std::printf("  %-34s %9.1f us  %5.2f T exact MAC/s  %5.1f pJ/MAC  %4.0f W\n", what, us, macs / us / 1e6, ej / macs * 1e12, ej / us * 1e6);
        };
        // today's tile kernels
        float *Xt = d.alloc<float>((size_t)tiles * E * MOE_TS), *Ht = d.alloc<float>((size_t)tiles * NFF * MOE_TS);
        float *ybase = d.alloc<float>((size_t)K * E);
        {
            double us = timeit([&](int) { tile_gather_l(d.q, grp, tiles, x, E, KU, E, Xt, tile_gather_sgw()); });
            std::printf("  %-34s %9.1f us\n", "today: tile_gather_l", us);
            us = timeit([&](int i) {
                const WView &v = gu[i % NL];
                SituOp so{nullptr, ids, 8.0f, 4.0f, nullptr, NFF};
                slot_pair_g2(d.q, v, v.p + (size_t)NFF * v.rb, gub, NFF, grp, tiles, Xt, so, Ht, 2, false, false);
            });
            line("today: gate|up slot_pair_g2", us, mac_gu);
            us = timeit([&](int i) { slot_rows_g2(d.q, dn[i % NL], grp, tiles, Ht, ybase, E, 4, false, false, tile_lut); });
            line("today: down slot_rows_g2", us, mac_dn);
        }
        // the matrix engines
        uint16_t *P = d.alloc<uint16_t>((size_t)tiles * 3 * 16 * E), *Hp = d.alloc<uint16_t>((size_t)tiles * 3 * 16 * NFF);
        float *R = d.alloc<float>((size_t)K * 2 * NFF), *Y = d.alloc<float>((size_t)K * E);
        std::vector<float> R0, Y0, Rc((size_t)K * 2 * NFF), Yc((size_t)K * E);
        std::vector<uint16_t> H0, Hc((size_t)tiles * 3 * 16 * NFF);
        {
            const double us = timeit([&](int) { xm::split_gather(d.q, grp, tiles, x, E, KU, E, P); });
            std::printf("  %-34s %9.1f us\n", "xmx: split_gather", us);
            std::vector<uint16_t> p1((size_t)nt * 3 * 16 * E), p2(p1.size());
            d.get(p1.data(), P, p1.size());
            const double us8 = timeit([&](int) { xm::split_gather8(d.q, grp, tiles, x, E, KU, E, P); });
            d.get(p2.data(), P, p2.size());
            std::printf("  %-34s %9.1f us  %s\n", "xmx: split_gather8", us8, p1 == p2 ? "same" : "DIFF");
        }
        const xm::ActOp op{nullptr, 8.0f, 4.0f};
        auto cmpv = [](const auto &u, const auto &v) {
            for (size_t i = 0; i < u.size(); ++i) if (std::memcmp(&u[i], &v[i], sizeof(u[0]))) return (long)i;
            return -1L;
        };
        auto run2 = [&]<int SM, int SR, int KC>() { // XProd2 (tile layout)
            xm::Super st;
            st.alloc(d, NE, K, SM);
            const int stb = xm::Super::bound(NE, K, SM);
            xm::super_tiles(d.q, grp, NE, st).wait();
            char nm[96];
            d.q.memset(R, 0, (size_t)K * 2 * NFF * 4).wait();
            xm::prod2<SM, SR, KC, 2>(d.q, gu[0].p, gub, E, NFF, NFF / 16, grp, st, stb, P, op, nullptr, R, 2 * NFF).wait();
            d.get(Rc.data(), R, Rc.size());
            std::snprintf(nm, sizeof nm, "xmx2 SM%d SR%d KC%d gate|up", SM, SR, KC);
            const double us = timeit([&](int i) {
                xm::prod2<SM, SR, KC, 0>(d.q, gu[i % NL].p, gub, E, NFF, NFF / 16, grp, st, stb, P, op, Hp, nullptr, 0);
            });
            line(nm, us, mac_gu);
            d.get(Hc.data(), Hp, Hc.size());
            std::snprintf(nm, sizeof nm, "xmx2 SM%d SR%d KC%d down", SM, SR, KC);
            const double usd = timeit([&](int i) {
                xm::prod2<SM, SR, KC, 1>(d.q, dn[i % NL].p, dnb, NFF, NFF, E / 32, grp, st, stb, Hp, op, nullptr, Y, E);
            });
            line(nm, usd, mac_dn);
            d.get(Yc.data(), Y, Yc.size());
            const long a = cmpv(R0, Rc), b = cmpv(H0, Hc), c = cmpv(Y0, Yc);
            std::printf("    vs the first: sums %s, H %s, down %s\n", a < 0 ? "same" : "DIFF", b < 0 ? "same" : "DIFF", c < 0 ? "same" : "DIFF");
            sycl::free(st.t0, d.q); sycl::free(st.n, d.q); sycl::free(st.count, d.q);
        };
        auto run = [&]<int SM, int SR, int KC, bool TL = false>() {
            xm::Super st;
            st.alloc(d, NE, K, SM);
            const int stb = xm::Super::bound(NE, K, SM);
            xm::super_tiles(d.q, grp, NE, st).wait();
            char nm[96];
            // gate|up sums of layer 0 (tests), then gate|up + act timed, then down timed
            d.q.memset(R, 0, (size_t)K * 2 * NFF * 4).wait();
            xm::prod<SM, SR, KC, 2, 0, TL>(d.q, gu[0].p, gu[0].rb, gub, E, NFF, NFF / 16, grp, st, stb, P, op, nullptr, R, 2 * NFF).wait();
            d.get(Rc.data(), R, Rc.size());
            std::snprintf(nm, sizeof nm, "xmx SM%d SR%d KC%d%s gate|up", SM, SR, KC, TL ? " tiles" : "");
            const double us = timeit([&](int i) {
                const WView &v = gu[i % NL];
                xm::prod<SM, SR, KC, 0, 0, TL>(d.q, v.p, v.rb, gub, E, NFF, NFF / 16, grp, st, stb, P, op, Hp, nullptr, 0);
            });
            line(nm, us, mac_gu);
            d.get(Hc.data(), Hp, Hc.size()); // layer 0 (the last launch)
            std::snprintf(nm, sizeof nm, "xmx SM%d SR%d KC%d%s down", SM, SR, KC, TL ? " tiles" : "");
            const double usd = timeit([&](int i) {
                const WView &v = dn[i % NL];
                xm::prod<SM, SR, KC, 1, 0, TL>(d.q, v.p, v.rb, dnb, NFF, NFF, E / 32, grp, st, stb, Hp, op, nullptr, Y, E);
            });
            line(nm, usd, mac_dn);
            d.get(Yc.data(), Y, Yc.size());
            if (R0.empty()) { R0 = Rc; H0 = Hc; Y0 = Yc; }
            else {
                const long a = cmpv(R0, Rc), b = cmpv(H0, Hc), c = cmpv(Y0, Yc);
                std::printf("    vs the first: sums %s, H %s, down %s\n", a < 0 ? "same" : "DIFF", b < 0 ? "same" : "DIFF", c < 0 ? "same" : "DIFF");
            }
            sycl::free(st.t0, d.q); sycl::free(st.n, d.q); sycl::free(st.count, d.q);
        };
        run.template operator()<4, 4, 4>();
        if (std::getenv("BENCH_ABL_OFF")) { // energy by part (wrong values): SM4 SR4 KC4 gate|up
            xm::Super st;
            st.alloc(d, NE, K, 4);
            const int stb = xm::Super::bound(NE, K, 4);
            xm::super_tiles(d.q, grp, NE, st).wait();
            auto ab = [&]<int ABL>(const char *what) {
                const double us = timeit([&](int i) {
                    const WView &v = gu[i % NL];
                    xm::prod<4, 4, 4, 0, ABL>(d.q, v.p, v.rb, gub, E, NFF, NFF / 16, grp, st, stb, P, op, Hp, nullptr, 0);
                });
                line(what, us, mac_gu);
            };
            ab.template operator()<0>("all");
            ab.template operator()<1>("no decode");
            ab.template operator()<2>("inputs once per chunk");
            ab.template operator()<4>("no DPAS");
            ab.template operator()<3>("no decode, inputs once");
            ab.template operator()<7>("no decode, inputs once, no DPAS");
        }
        // the rows of the accuracy samples (layer 0), read before the weights change layout
        constexpr int NS = 3000;
        std::mt19937 rs(3);
        std::vector<int> smp_slot(NS), smp_rg(NS), smp_rd(NS);
        std::vector<uint8_t> rows_g((size_t)NS * gu[0].rb), rows_d((size_t)NS * dn[0].rb);
        for (int i = 0; i < NS; ++i) {
            smp_slot[i] = (int)(rs() % K); smp_rg[i] = (int)(rs() % (2 * NFF)); smp_rd[i] = (int)(rs() % E);
            const int e = hid[smp_slot[i]];
            d.get(rows_g.data() + (size_t)i * gu[0].rb, gu[0].p + (size_t)e * gub + (size_t)smp_rg[i] * gu[0].rb, gu[0].rb);
            d.get(rows_d.data() + (size_t)i * dn[0].rb, dn[0].p + (size_t)e * dnb + (size_t)smp_rd[i] * dn[0].rb, dn[0].rb);
        }
        { // the tile layout, in place (today's kernels cannot read it): the same values, so the same bits
            uint8_t *tmp = d.alloc<uint8_t>(std::max(gub, dnb));
            const double t0 = now_s();
            for (int l = 0; l < NL; ++l) {
                xm::repack_tiles(d.q, const_cast<uint8_t *>(gu[l].p), gu[l].rb, 2 * NFF, E, NE, tmp);
                xm::repack_tiles(d.q, const_cast<uint8_t *>(dn[l].p), dn[l].rb, E, NFF, NE, tmp);
            }
            std::printf("  tile layout of %d layers: %.2f s\n", NL, now_s() - t0);
            sycl::free(tmp, d.q);
        }
        run.template operator()<4, 4, 4, true>();
        run2.template operator()<4, 4, 4>();
        run2.template operator()<2, 4, 4>();
        run2.template operator()<1, 4, 4>();
        run2.template operator()<4, 2, 4>();
        run2.template operator()<4, 4, 8>();
        run2.template operator()<2, 4, 8>();
        // accuracy of the first configuration's sums against double (layer 0): gate|up from x, down from H
        {
            std::vector<int32_t> hs0(nt), htn(nt), hsl(K), hte(nt);
            d.get(hs0.data(), grp.tile_s0, nt); d.get(htn.data(), grp.tile_n, nt); d.get(hsl.data(), grp.slots, K); d.get(hte.data(), grp.tile_exp, nt);
            std::vector<int> stile(K), srow(K);
            for (int t = 0; t < nt; ++t) for (int r = 0; r < htn[t]; ++r) { stile[hsl[hs0[t] + r]] = t; srow[hsl[hs0[t] + r]] = r; }
            double sg = 0, mg = 0, sd = 0, md = 0;
            for (int i = 0; i < NS; ++i) {
                const int slot = smp_slot[i], tok = slot / KU;
                { // gate|up
                    const int r = smp_rg[i];
                    const uint8_t *row = rows_g.data() + (size_t)i * gu[0].rb;
                    double ref = 0, ab = 0;
                    for (int c = 0; c < E; ++c) { const double p = host_nvfp4(row, E, c) * hx[(size_t)tok * E + c]; ref += p; ab += std::fabs(p); }
                    const double err = ab > 0 ? std::fabs(R0[(size_t)slot * 2 * NFF + r] - ref) / (std::ldexp(1.0, -24) * ab) : 0.0;
                    sg += err; mg = std::max(mg, err);
                }
                { // down
                    const int r = smp_rd[i], t = stile[slot], sr = srow[slot];
                    const uint8_t *row = rows_d.data() + (size_t)i * dn[0].rb;
                    double ref = 0, ab = 0;
                    const size_t ph = (size_t)16 * NFF;
                    for (int c = 0; c < NFF; ++c) {
                        const size_t o = (size_t)t * 3 * ph + (size_t)sr * NFF + c;
                        const double h = (double)xm::bf_f(H0[o]) + (double)xm::bf_f(H0[o + ph]) + (double)xm::bf_f(H0[o + 2 * ph]);
                        const double p = host_nvfp4(row, NFF, c) * h;
                        ref += p; ab += std::fabs(p);
                    }
                    const double err = ab > 0 ? std::fabs(Y0[(size_t)slot * E + r] - ref) / (std::ldexp(1.0, -24) * ab) : 0.0;
                    sd += err; md = std::max(md, err);
                }
            }
            std::printf("error vs double (2^-24 x sum |w x|), %d samples: gate|up mean %.4f max %.4f, down mean %.4f max %.4f\n", NS, sg / NS, mg,
                        sd / NS, md);
        }
    } catch (const std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
