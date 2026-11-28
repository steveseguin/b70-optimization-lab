// bench_xs: the one-token NVFP4 expert products (8 experts, real weights of layers 0-3, each timed launch the next
// layer so the weights come from memory) in three arithmetics / decodes, timed and checked against double:
//   V0  today's (xmx_moe.hpp XFull): the B tile holds the exact weights code x scale (bf16), per segment of 16 steps
//       c1 (input part 1) and c23 (parts 2, 3) from zero, total = total + (c1 + c23)
//   V1  the scale outside the products: the B tile holds the codes' magnitudes (x 2^-15, through halves, no multiply),
//       per step c = x3.B + x2.B + x1.B from zero, total = fma(scale x 2^15, c, total)
//   V2  V1's arithmetic with the magnitudes from a 256-entry local table (codes re-laid so byte j holds inputs 2j, 2j+1)
// V1 and V2 differ only by the exact power of two 2^15 in B and in the scale, so they must give the same bits.
// The engine's own one-token kernel (xm::full_prod, with its activation epilogue) is timed for reference.
//   bench_xs <model.gguf> <card>
#include "../../src/xmx_moe.hpp"
#include <algorithm>
#include <random>

using namespace ink;
namespace jm = sycl::ext::oneapi::experimental::matrix;
using bf = sycl::ext::oneapi::bfloat16;

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

// one sub-group per (expert, 16-row block) over all inputs; work-group = 2 sub-groups (MODE 0: the gate and up blocks
// gi and nff/16 + gi, as XFull; MODE 1: blocks 2 gi, 2 gi + 1). Raw sums to Y[expert slot][row].
template <int V, int MODE, int PF = 4, int PD = 8> struct XS {
    const uint8_t *W; size_t estride; int cols, nff;
    const int32_t *ex; const uint16_t *P; size_t pp; float *Y; int ldy;
    const uint32_t *gtab;
    sycl::local_accessor<bf, 1> zb;
    sycl::local_accessor<uint32_t, 1> tab;
    sycl::local_accessor<float, 1> st;
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const {
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 1, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, 1, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        const auto sg = it.get_sub_group();
        const int t = (int)it.get_group(0), gi = (int)it.get_group(1);
        const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id(), lid = (int)it.get_local_linear_id();
        const int steps = cols / 16;
        const int blk = MODE == 0 ? sgi * (nff / 16) + gi : gi * 2 + sgi;
        const uint8_t *w = W + (size_t)ex[t] * estride + (size_t)blk * steps * xm::TB;
        if (lid < 128) reinterpret_cast<uint32_t *>(&zb[0])[lid] = 0u;
        if constexpr (V == 2)
            for (int i = lid; i < 256; i += 32) tab[i] = gtab[i];
        sycl::group_barrier(it.get_group());
        xm::Raw r[PF];
#pragma unroll
        for (int i = 0; i < PF; ++i) r[i] = xm::fetch16t(w + (size_t)i * xm::TB, ln);
        C tot, c1, c23, zc;
        jm::joint_matrix_fill(sg, tot, 0.0f);
        jm::joint_matrix_fill(sg, zc, 0.0f);
        B rb;
        jm::joint_matrix_load(sg, rb, zb.template get_multi_ptr<sycl::access::decorated::no>(), 32);
        const bf *pa = reinterpret_cast<const bf *>(P);
        for (int k0 = 0; k0 < steps; k0 += xm::SEG) {
            const int ns = sycl::min(xm::SEG, steps - k0);
            if constexpr (V == 0) {
                jm::joint_matrix_fill(sg, c1, 0.0f);
                jm::joint_matrix_fill(sg, c23, 0.0f);
            }
            for (int b = 0; b < ns; b += PF) {
                const int kb = k0 + b, kn = sycl::min(kb + PF, steps - PF);
                xm::Raw n[PF];
#pragma unroll
                for (int i = 0; i < PF; ++i) n[i] = xm::fetch16t(w + (size_t)(kn + i) * xm::TB, ln);
                if constexpr (PD > 0) {
                    namespace sx = sycl::ext::oneapi::experimental;
                    const int kp = sycl::min(kb + PD, steps - PF);
                    const uint8_t *pp8 = w + (size_t)kp * xm::TB + (size_t)sycl::min(ln, PF * xm::TB / 64) * 64;
                    sx::prefetch((void *)pp8, 64, sx::properties{sx::prefetch_hint_L1});
                }
#pragma unroll
                for (int i = 0; i < PF; ++i) {
                    float s = 0.0f;
                    if constexpr (V == 0) {
                        float v[16];
                        xm::decode_vals(r[i], v);
                        int e = 0;
                        jm::joint_matrix_apply(sg, rb, [&](bf &x) { x = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v[e]) >> 16)); ++e; });
                    } else if constexpr (V == 1) {
                        float v[16];
                        const uint32_t cw[2] = {(uint32_t)r[i].cw, (uint32_t)(r[i].cw >> 32)};
#pragma unroll
                        for (int hh = 0; hh < 2; ++hh) {
                            const uint32_t x = cw[hh];
                            const int j0 = 4 * hh;
                            pl::NVFP4P::pair(x, 9, 1.0f, v[j0 + 0], v[j0 + 2]);
                            pl::NVFP4P::pair(x, 5, 1.0f, v[8 + j0 + 0], v[8 + j0 + 2]);
                            pl::NVFP4P::pair(x, 1, 1.0f, v[j0 + 1], v[j0 + 3]);
                            pl::NVFP4P::pair(x, -3, 1.0f, v[8 + j0 + 1], v[8 + j0 + 3]);
                        }
                        int e = 0;
                        jm::joint_matrix_apply(sg, rb, [&](bf &x) { x = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v[e]) >> 16)); ++e; });
                        s = pl::ue4m3_bits((uint8_t)r[i].sc) * 32768.0f;
                    } else {
                        uint32_t wd[8];
#pragma unroll
                        for (int j = 0; j < 8; ++j) wd[j] = tab[(uint32_t)(r[i].cw >> (8 * j)) & 0xFFu];
                        int e = 0;
                        jm::joint_matrix_apply(sg, rb, [&](bf &x) { x = sycl::bit_cast<bf>((uint16_t)(wd[e >> 1] >> ((e & 1) * 16))); ++e; });
                        s = pl::ue4m3_bits((uint8_t)r[i].sc);
                    }
                    A x0, x1, x2;
                    const bf *pk = pa + (size_t)(kb + i) * 16;
                    jm::joint_matrix_load(sg, x0, gp(pk), cols);
                    jm::joint_matrix_load(sg, x1, gp(pk + pp), cols);
                    jm::joint_matrix_load(sg, x2, gp(pk + 2 * pp), cols);
                    if constexpr (V == 0) {
                        jm::joint_matrix_mad(sg, c1, x0, rb, c1);
                        jm::joint_matrix_mad(sg, c23, x1, rb, c23);
                        jm::joint_matrix_mad(sg, c23, x2, rb, c23);
                    } else {
                        C c;
                        jm::joint_matrix_mad(sg, c, x2, rb, zc);
                        jm::joint_matrix_mad(sg, c, x1, rb, c);
                        jm::joint_matrix_mad(sg, c, x0, rb, c);
                        jm::joint_matrix_apply(sg, tot, c, [&](float &u, float &cv) { u = sycl::fma(s, cv, u); });
                    }
                }
#pragma unroll
                for (int i = 0; i < PF; ++i) r[i] = n[i];
            }
            if constexpr (V == 0) {
                jm::joint_matrix_apply(sg, c1, c23, [](float &u, float &v) { u = u + v; });
                jm::joint_matrix_apply(sg, tot, c1, [](float &u, float &v) { u = u + v; });
            }
        }
        jm::joint_matrix_store(sg, tot, st.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)sgi * 16, 16, jm::layout::row_major);
        sycl::group_barrier(sg);
        Y[(size_t)t * ldy + blk * 16 + ln] = st[(size_t)sgi * 16 + ln];
    }
};
template <int V, int MODE>
static sycl::event xs(sycl::queue &q, const uint8_t *W, size_t estride, int cols, int nff, int rows, const int32_t *ex, int nex,
                      const uint16_t *P, size_t pp, float *Y, int ldy, const uint32_t *gtab) {
    const int ngr = MODE == 0 ? nff / 16 : rows / 32;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<bf, 1> zb(256, h);
        sycl::local_accessor<uint32_t, 1> tab(V == 2 ? 256 : 1, h);
        sycl::local_accessor<float, 1> st(32, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nex, (size_t)ngr * 32), sycl::range<2>(1, 32)),
                       XS<V, MODE>{W, estride, cols, nff, ex, P, pp, Y, ldy, gtab, zb, tab, st});
    });
}

int main(int argc, char **argv) {
    if (argc < 3) { std::fprintf(stderr, "usage: bench_xs <model.gguf> <card>\n"); return 2; }
    try {
        GGUF gf(argv[1]);
        Device d(std::atoi(argv[2]));
        Weights w;
        w.upload(d, gf, false);
        auto views = planarize(d, gf, w, false);
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 200;
        // BENCH_NL layers in turn (1-20; 20 spreads the reads over ~11 GB of weights), BENCH_SETS expert sets in turn
        const int NL = std::getenv("BENCH_NL") ? std::atoi(std::getenv("BENCH_NL")) : 4;
        const int NSETS = std::getenv("BENCH_SETS") ? std::atoi(std::getenv("BENCH_SETS")) : 1;
        const bool only_engine = std::getenv("BENCH_ENGINE_ONLY") != nullptr;
        constexpr int NE = 128, KU = 8, E = 2304, NFF = 1152;
        if (NL < 1 || NL > 20 || NSETS < 1) throw std::runtime_error("BENCH_NL 1-20, BENCH_SETS >= 1");
        std::vector<WView> gu(NL), dn(NL);
        for (int l = 0; l < NL; ++l) {
            gu[l] = views.at("blk." + std::to_string(l) + ".ffn_gate_up_exps.weight");
            dn[l] = views.at("blk." + std::to_string(l) + ".ffn_down_exps.weight");
            if (gu[l].kind != K_NVFP4P || dn[l].kind != K_NVFP4P) throw std::runtime_error("layer " + std::to_string(l) + " is not NVFP4");
        }
        const size_t gub = gu[0].rb * (size_t)gu[0].t->ne[1], dnb = dn[0].rb * (size_t)dn[0].t->ne[1];
        std::mt19937 rng(11);
        std::vector<int32_t> hex((size_t)KU * NSETS);
        for (int st = 0; st < NSETS; ++st) {
            std::vector<int> pool(NE);
            for (int e = 0; e < NE; ++e) pool[e] = e;
            if (st == 0) for (int k = 0; k < KU; ++k) hex[k] = (int)((k * 37 + 5) % NE);
            else {
                std::shuffle(pool.begin(), pool.end(), rng);
                for (int k = 0; k < KU; ++k) hex[(size_t)st * KU + k] = pool[k];
            }
        }
        std::normal_distribution<float> nd(0.0f, 1.0f);
        std::vector<float> hx(E), hh(NFF);
        for (auto &v : hx) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
        for (auto &v : hh) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
        auto parts = [](const std::vector<float> &x) {
            std::vector<uint16_t> p(3 * x.size());
            for (size_t i = 0; i < x.size(); ++i) {
                uint16_t a, b, c;
                split3(x[i], a, b, c);
                p[i] = a; p[x.size() + i] = b; p[2 * x.size() + i] = c;
            }
            return p;
        };
        const std::vector<uint16_t> px = parts(hx), ph = parts(hh);
        uint16_t *Px = d.alloc<uint16_t>(px.size()), *Ph = d.alloc<uint16_t>(ph.size());
        d.put(Px, px.data(), px.size());
        d.put(Ph, ph.data(), ph.size());
        int32_t *ex = d.alloc<int32_t>(hex.size());
        d.put(ex, hex.data(), hex.size());
        // host rows of layer 0's chosen experts (planar, before the tile layout) for the check against double
        std::vector<uint8_t> rg((size_t)KU * 2 * NFF * gu[0].rb), rd((size_t)KU * E * dn[0].rb);
        for (int k = 0; k < KU; ++k) {
            d.get(rg.data() + (size_t)k * 2 * NFF * gu[0].rb, gu[0].p + (size_t)hex[k] * gub, 2 * NFF * gu[0].rb);
            d.get(rd.data() + (size_t)k * E * dn[0].rb, dn[0].p + (size_t)hex[k] * dnb, E * dn[0].rb);
        }
        // the tile layout (today's), in place; and V2's copies with the codes re-laid (byte j: inputs 2j, 2j+1)
        std::vector<uint8_t *> gu2(NL), dn2(NL);
        {
            uint8_t *tmp = d.alloc<uint8_t>(std::max(gub, dnb));
            for (int l = 0; l < NL; ++l) {
                xm::repack_tiles(d.q, const_cast<uint8_t *>(gu[l].p), gu[l].rb, 2 * NFF, E, NE, tmp);
                xm::repack_tiles(d.q, const_cast<uint8_t *>(dn[l].p), dn[l].rb, E, NFF, NE, tmp);
            }
            sycl::free(tmp, d.q);
            auto relay = [&](const uint8_t *src, size_t bytes) {
                uint8_t *o = d.alloc<uint8_t>(bytes);
                const size_t nt = bytes / xm::TB;
                d.q.parallel_for(sycl::range<2>(nt, 16), [=](sycl::id<2> id) {
                    const uint8_t *tp = src + id[0] * xm::TB;
                    uint8_t *op = o + id[0] * xm::TB;
                    const int n = (int)id[1];
                    auto nib = [&](int k) { return k < 8 ? (tp[8 * n + k] & 0xF) : (tp[8 * n + k - 8] >> 4); };
                    for (int j = 0; j < 8; ++j) op[8 * n + j] = (uint8_t)(nib(2 * j) | (nib(2 * j + 1) << 4));
                    op[128 + n] = tp[128 + n];
                }).wait();
                return o;
            };
            for (int l = 0; l < (only_engine ? 0 : NL); ++l) { gu2[l] = relay(gu[l].p, NE * gub); dn2[l] = relay(dn[l].p, NE * dnb); } // (every expert)
        }
        std::vector<uint32_t> htab(256);
        for (int v = 0; v < 256; ++v) {
            auto bfmag = [](int c) -> uint32_t {
                static const float mag[8] = {0, 1, 2, 3, 4, 6, 8, 12};
                float f = mag[c & 7];
                uint32_t u;
                std::memcpy(&u, &f, 4);
                return (u >> 16) | ((c & 8) ? 0x8000u : 0u);
            };
            htab[v] = bfmag(v & 0xF) | (bfmag(v >> 4) << 16);
        }
        uint32_t *gtab = d.alloc<uint32_t>(256);
        d.put(gtab, htab.data(), 256);
        float *Y = d.alloc<float>((size_t)KU * E);
        const double macs_gu = (double)KU * 2 * NFF * E, macs_dn = (double)KU * E * NFF;
        auto timeit = [&](auto &&launch) {
            for (int i = 0; i < 8; ++i) launch(i);
            d.q.wait();
            const double e0 = d.energy_j(), t0 = now_s();
            for (int i = 0; i < iters; ++i) launch(i);
            d.q.wait();
            const double us = (now_s() - t0) / iters * 1e6, ej = (d.energy_j() - e0) / iters;
            return std::pair<double, double>(us, ej);
        };
        // the sums of layer 0 against double: mean and max error in units of 2^-24 x sum |w x|
        auto check = [&](int mode, std::vector<float> &out) {
            const int rows = mode == 0 ? 2 * NFF : E, cols = mode == 0 ? E : NFF;
            const std::vector<float> &x = mode == 0 ? hx : hh;
            const std::vector<uint8_t> &R = mode == 0 ? rg : rd;
            const size_t rb = mode == 0 ? gu[0].rb : dn[0].rb;
            out.resize((size_t)KU * rows);
            d.get(out.data(), Y, out.size());
            double sm = 0, mx = 0;
            int n = 0;
            for (int k = 0; k < KU; ++k)
                for (int r = 0; r < rows; r += 7) {
                    const uint8_t *row = R.data() + ((size_t)k * rows + r) * rb;
                    double s = 0, a = 0;
                    for (int i = 0; i < cols; ++i) { const double p = host_nvfp4(row, cols, i) * (double)x[i]; s += p; a += std::fabs(p); }
                    const double err = std::fabs((double)out[(size_t)k * rows + r] - s) / (a * 0x1p-24 + 1e-300);
                    sm += err; mx = std::max(mx, err); ++n;
                }
            return std::pair<double, double>(sm / n, mx);
        };
        std::printf("one token, 8 experts, layers 0-%d in turn, %d launches each\n", NL - 1, iters);
        std::vector<float> o0, o1, o2;
        for (int mode = 0; mode < (only_engine ? 0 : 2); ++mode) {
            const char *nm = mode == 0 ? "gate|up" : "down";
            const int cols = mode == 0 ? E : NFF, rows = mode == 0 ? 2 * NFF : E;
            const uint16_t *P = mode == 0 ? Px : Ph;
            const size_t pp = cols, eb = mode == 0 ? gub : dnb;
            const double macs = mode == 0 ? macs_gu : macs_dn;
            auto L = [&](int l) { return mode == 0 ? gu[l].p : dn[l].p; };
            auto L2 = [&](int l) { return mode == 0 ? gu2[l] : dn2[l]; };
            auto run = [&](int v, int i) {
                const int l = i % NL;
                if (mode == 0) {
                    if (v == 0) xs<0, 0>(d.q, L(l), eb, cols, NFF, rows, ex, KU, P, pp, Y, rows, gtab);
                    else if (v == 1) xs<1, 0>(d.q, L(l), eb, cols, NFF, rows, ex, KU, P, pp, Y, rows, gtab);
                    else xs<2, 0>(d.q, L2(l), eb, cols, NFF, rows, ex, KU, P, pp, Y, rows, gtab);
                } else {
                    if (v == 0) xs<0, 1>(d.q, L(l), eb, cols, NFF, rows, ex, KU, P, pp, Y, rows, gtab);
                    else if (v == 1) xs<1, 1>(d.q, L(l), eb, cols, NFF, rows, ex, KU, P, pp, Y, rows, gtab);
                    else xs<2, 1>(d.q, L2(l), eb, cols, NFF, rows, ex, KU, P, pp, Y, rows, gtab);
                }
            };
            for (int rep = 0; rep < 2; ++rep)
                for (int v = 0; v < 3; ++v) {
                    const auto [us, ej] = timeit([&](int i) { run(v, i); });
                    run(v, 0);
                    d.q.wait();
                    std::vector<float> &o = v == 0 ? o0 : (v == 1 ? o1 : o2);
                    const auto [em, ex2] = check(mode, o);
                    std::printf("  %-8s V%d  %7.2f us  %6.1f GB/s  %6.1f pJ/MAC  error mean %.4f max %.4f\n", nm, v, us,
                                (double)KU * eb / us / 1e3, ej / macs * 1e12, em, ex2);
                }
            std::printf("  %-8s V1 vs V2: %s; V0 vs V1: %s\n", nm, std::memcmp(o1.data(), o2.data(), o1.size() * 4) ? "DIFFER" : "same bits",
                        std::memcmp(o0.data(), o1.data(), o0.size() * 4) ? "differ (another arithmetic)" : "same bits");
        }
        { // the engine's kernel, for reference (its epilogue too)
            std::vector<MoeGroups> grps(NSETS);
            for (int st = 0; st < NSETS; ++st) {
                grps[st].alloc(d, NE, KU);
                moe_group(d.q, ex + (size_t)st * KU, KU, NE, grps[st]).wait();
            }
            const int tiles = MoeGroups::max_tiles(NE, KU);
            uint16_t *Hp = d.alloc<uint16_t>((size_t)3 * NFF * 16);
            float *Y2 = d.alloc<float>((size_t)KU * E);
            const xm::ActOp op{nullptr, 8.0f, 4.0f};
            double us, ej;
            std::tie(us, ej) = timeit([&](int i) {
                xm::full_prod<1, 0, 4, 2, 128, 8, 1>(d.q, gu[i % NL].p, gub, E, NFF, 2 * NFF, grps[(i / NL) % NSETS], tiles, Px, (size_t)E, true, op, Hp, NFF, nullptr, 0);
            });
            std::printf("  (%d layers, %d expert sets in turn)\n", NL, NSETS);
            std::printf("  engine full_prod gate|up %7.2f us  %6.1f pJ/MAC\n", us, ej / macs_gu * 1e12);
            std::tie(us, ej) = timeit([&](int i) {
                xm::full_prod<1, 1, 4, 2, 128, 8, 1>(d.q, dn[i % NL].p, dnb, NFF, NFF, E, grps[(i / NL) % NSETS], tiles, Ph, (size_t)NFF, true, op, nullptr, 0, Y2, E);
            });
            std::printf("  engine full_prod down    %7.2f us  %6.1f pJ/MAC\n", us, ej / macs_dn * 1e12);
        }
    } catch (std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
