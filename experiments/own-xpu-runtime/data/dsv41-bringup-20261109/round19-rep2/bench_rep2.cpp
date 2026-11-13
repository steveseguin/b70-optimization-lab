// bench_rep2.cpp (rep2 helper, 2026-11-13): one card. The replicated rows of the one-token step that every card reads
// in full today: the stream mixes' 25 dot rows (hc_attn_fn / hc_ffn_fn, 24 F32 rows x 20,480 + the sum of squares)
// and the router rows (ffn_gate_inp, 384 x 5,120 as 16-bit halves), against ONE card's share of them.
//   A  attention mix: SkNormDotsW<8> (production: the norm + 25 dot work-groups) vs SkNormDotsWS<8> (the norm + card
//      s's rows [r0, r1)); SkNormW<5120, 16> alone (the norm's floor).
//   B  FFN mix + router: FlNormK<5120,16,25,8,0,NoRows,FlH16Rows<160>> (production) vs FlNormKS (card s's dot rows,
//      all 384 router rows: "Bd") and FlNormKS with the router rows [64 s, 64 s + 64) too ("Bdr"); FlNormKS with no
//      dot rows ("B0": the router launch alone).
//   C  RoutePRows: the pick + the shared gate / up rows (card 0's 384 + 384 rows) with the FFN finish riding
//      (production) vs without.
//   D  FlDownComb<GemvQ8P<72>,6> / <GemvQ5KP<9>,6> (card 0's 864 shared down rows) vs FlDownCombF (+ the finish).
//   E  RowsP<HcFinishRows> alone (launch_rows, one row): the finish's own length.
//   X  XchgP2 / XchgQ2 on one card with six local "peer" buffers (flags preset): the copies land where XchgP / XchgQ
//      put theirs plus the second range, nothing else changes (indexing check; times are local, not PCIe).
// Bitwise: every share's outputs (dot-row words, norm output, router words) against the production launch's; C / D's
// outputs with and without the rider; D / E's finish outputs. Timing: kernel time per launch (profiling events), cold
// weights (NCOPY copies cycled), 400-launch warm-up, rounds alternating order, median; "max" = the slowest share.
// env: PL=layers (default: the first layer with a Q8_0 and one with a Q5_K shared expert)  NCOPY=8  REPS=40  ROUNDS=5
//      NSET=4  FORM=1 (the finish's form, OWN_HC_FIN)  NOTIME=1
#include <sycl/sycl.hpp>
#include <fcntl.h>
#include <unistd.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <map>
#include <random>
#include <string>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
#include "stage2/packet3/kernels/sycl_v41_rep2.hpp"
using namespace ops41sycl;
using Act = ActF32;

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
static double median(std::vector<double> v) {
    if (v.empty()) return 0;
    std::sort(v.begin(), v.end());
    return v[v.size() / 2];
}
static int envi(const char *n, int d) { const char *e = getenv(n); return e ? atoi(e) : d; }
static std::vector<unsigned> env_list(const char *n, std::vector<unsigned> d) {
    const char *e = getenv(n);
    if (!e) return d;
    std::vector<unsigned> v;
    for (const char *p = e; *p;) {
        v.push_back((unsigned)strtoul(p, (char **)&p, 0));
        if (*p == ',') ++p;
    }
    return v;
}
#include "gguf_part.inc"

static constexpr unsigned H = 5120, H4 = 4 * H, NC = 6, NE = 384, SHR = 384, SDR = 864, MID = 2304;
static int g_form = 1;

struct LW {
    int L = 0;
    iq3::Type sty;                       // shared expert type (Q8_0 / Q5_K)
    std::vector<float *> fa, ff;         // hc_attn_fn / hc_ffn_fn copies (24 x 20,480)
    std::vector<uint8_t *> rt, sg, su, sd; // router (384 rows, halves), shared gate / up (384 rows), down (864 rows)
    float *anw = nullptr, *fnw = nullptr, *bias = nullptr, *fsc = nullptr, *fbs = nullptr;
    size_t rtb = 0, sgb = 0, sdb = 0;    // packed row bytes
};
static LW load_layer(sycl::queue &q, int L, int ncopy) {
    LW w;
    w.L = L;
    const std::string p = "blk." + std::to_string(L) + ".";
    w.sty = (iq3::Type)gt(p + "ffn_gate_shexp.weight").type;
    const auto fa = f32_vec(p + "hc_attn_fn.weight", (size_t)24 * H4);
    const auto ff = f32_vec(p + "hc_ffn_fn.weight", (size_t)24 * H4);
    const auto rt = packed_rows(p + "ffn_gate_inp.weight", iq3::Type::F32, H, 0, NE);
    const auto sg = packed_rows(p + "ffn_gate_shexp.weight", w.sty, H, 0, SHR);
    const auto su = packed_rows(p + "ffn_up_shexp.weight", w.sty, H, 0, SHR);
    const iq3::Type dty = (iq3::Type)gt(p + "ffn_down_shexp.weight").type;
    if (dty != w.sty) { std::printf("layer %d: down type %u != gate type %u\n", L, (unsigned)dty, (unsigned)w.sty); std::exit(2); }
    const auto sd = packed_rows(p + "ffn_down_shexp.weight", dty, MID, 0, SDR);
    w.rtb = pk41::packed_row_bytes(iq3::Type::F32, H);
    w.sgb = pk41::packed_row_bytes(w.sty, H);
    w.sdb = pk41::packed_row_bytes(dty, MID);
    for (int c = 0; c < ncopy; ++c) {
        w.fa.push_back(dcopy(q, fa)), w.ff.push_back(dcopy(q, ff)), w.rt.push_back(dcopy(q, rt));
        w.sg.push_back(dcopy(q, sg)), w.su.push_back(dcopy(q, su)), w.sd.push_back(dcopy(q, sd));
    }
    w.anw = dcopy(q, f32_vec(p + "attn_norm.weight", H));
    w.fnw = dcopy(q, f32_vec(p + "ffn_norm.weight", H));
    w.bias = dcopy(q, f32_vec(p + "exp_probs_b.bias", NE));
    {
        const GgufT &s = gt(p + "hc_ffn_scale.weight"), &b = gt(p + "hc_ffn_base.weight");
        w.fsc = dcopy(q, f32_vec(p + "hc_ffn_scale.weight", s.ne0 * s.ne1));
        w.fbs = dcopy(q, f32_vec(p + "hc_ffn_base.weight", b.ne0 * b.ne1));
        std::printf("layer %d: shared type %u; hc_ffn_scale %lu, base %lu values; router row %zu B, %d copies\n", L,
                    (unsigned)w.sty, (unsigned long)(s.ne0 * s.ne1), (unsigned long)(b.ne0 * b.ne1), w.rtb, ncopy);
    }
    return w;
}

struct Bufs {
    float *x, *y, *streams, *router, *act, *shg, *shu, *shd, *expd, *out, *pre, *post, *comb;
    double *d25;
    uint32_t *ids;
    float *prob;
};
using EvV = std::vector<sycl::event>;

template <size_t SLM, typename K, typename... A> static sycl::event wgl(sycl::queue &q, size_t groups, size_t wg, K k, A... args) {
    return q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<uint32_t, 1> lt(SLM, hh);
        hh.parallel_for(sycl::nd_range<1>(groups * wg, wg), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            k(it, args..., &lt[0]);
        });
    });
}
template <typename K> static sycl::event flk(sycl::queue &q, const K &k, size_t xsn) { // fl_norm_launch
    const size_t ng = k.groups();
    return q.submit([&](sycl::handler &hh) {
        sycl::local_accessor<uint32_t, 1> lm(64, hh);
        sycl::local_accessor<float, 1> xs(xsn ? xsn : 1, hh);
        hh.parallel_for(sycl::nd_range<1>(ng * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            k(it, &lm[0], xs.template get_multi_ptr<sycl::access::decorated::yes>());
        });
    });
}
template <typename K, typename... A> static sycl::event rows0(sycl::queue &q, size_t rows, K k, A... args) { // launch_rows<0>
    const size_t nwg = (rows + 15) / 16;
    return q.submit([&](sycl::handler &hh) {
        hh.parallel_for(sycl::nd_range<1>(nwg * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, args...); });
    });
}
static HcFinishRows fin_of(const LW &w, const Bufs &b, const double *d) {
    HcMixFinishSG k{(int)H, 8};
    k.form = g_form;
    return HcFinishRows{k, d, w.fsc, w.fbs, b.pre, b.post, b.comb};
}

static long g_cmp = 0;
static int g_fail = 0;
static std::vector<uint32_t> words(sycl::queue &q, const void *p, size_t n) {
    std::vector<uint32_t> v(n);
    q.memcpy(v.data(), p, n * 4).wait();
    return v;
}
static void check(const char *what, const std::vector<uint32_t> &a, const std::vector<uint32_t> &b, size_t lo, size_t hi) {
    size_t nd = 0, first = (size_t)-1;
    for (size_t i = lo; i < hi; ++i)
        if (a[i] != b[i]) { ++nd; if (first == (size_t)-1) first = i; }
    ++g_cmp;
    if (nd) { ++g_fail; std::printf("  DIFF %s: %zu of %zu words (first %zu)\n", what, nd, hi - lo, first); }
}

struct Var {
    std::string name;
    std::function<void(int c, unsigned s, EvV &ev)> f; // c: weight copy, s: share
    unsigned nshare;                                  // 1: one launch form; NC: per share
};
static void time_vars(sycl::queue &q, std::vector<Var> &vars, int reps, int rounds, int ncopy, const char *tag, int L) {
    struct Key { size_t v; unsigned s; };
    std::vector<Key> keys;
    for (size_t v = 0; v < vars.size(); ++v)
        for (unsigned s = 0; s < vars[v].nshare; ++s) keys.push_back({v, s});
    std::vector<std::vector<double>> t(keys.size());
    {
        EvV ev;
        for (int r = 0; r < 400; ++r) vars[0].f(r % ncopy, 0, ev);
        q.wait();
    }
    for (int warm = 0; warm < 2; ++warm)
        for (auto &k : keys) {
            EvV ev;
            for (int r = 0; r < 4; ++r) vars[k.v].f(r % ncopy, k.s, ev);
            q.wait();
        }
    for (int rd = 0; rd < rounds; ++rd)
        for (size_t kk = 0; kk < keys.size(); ++kk) {
            const size_t k = rd % 2 ? keys.size() - 1 - kk : kk;
            EvV ev;
            for (int r = 0; r < reps; ++r) vars[keys[k].v].f((r + rd) % ncopy, keys[k].s, ev);
            q.wait();
            for (int r = 1; r < reps; ++r) t[k].push_back(ev_us(ev[(size_t)r]));
        }
    std::printf("timing %s layer %d (%d rounds x %d reps, %d copies, kernel us, median):\n", tag, L, rounds, reps - 1, ncopy);
    for (size_t v = 0; v < vars.size(); ++v) {
        std::vector<double> per;
        for (size_t k = 0; k < keys.size(); ++k)
            if (keys[k].v == v) per.push_back(median(t[k]));
        std::printf("  T %-3s L%-2d %-10s", tag, L, vars[v].name.c_str());
        if (per.size() == 1) std::printf(" %7.2f\n", per[0]);
        else {
            std::printf(" max %6.2f  shares:", *std::max_element(per.begin(), per.end()));
            for (double x : per) std::printf(" %6.2f", x);
            std::printf("\n");
        }
    }
}

static void fill(sycl::queue &q, float *p, size_t n, std::mt19937 &g, float sd, float big) {
    std::normal_distribution<float> nd(0.f, sd);
    std::uniform_real_distribution<float> u(0.f, 1.f);
    std::vector<float> v(n);
    for (auto &f : v) { f = nd(g); if (u(g) < 0.002f) f *= big; }
    q.memcpy(p, v.data(), n * 4).wait();
}

static void run_layer(sycl::queue &q, const LW &w, Bufs &b, int nset, int reps, int rounds, int ncopy, bool notime) {
    std::printf("\n== layer %d (shared type %u), finish form %d ==\n", w.L, (unsigned)w.sty, g_form);
    unsigned R0[NC], R1[NC];
    for (unsigned s = 0; s < NC; ++s) rep2_rows((int)NC, (int)s, R0[s], R1[s]);
    // ---- the launches
    auto A_full = [&](int c, unsigned, EvV &ev) {
        ev.push_back(wgl<64>(q, 26, 512, SkNormDotsW<8>{}, (const float *)b.x, (const float *)w.anw, b.y,
                             (const float *)b.streams, (const float *)w.fa[c], b.d25));
    };
    auto A_share = [&](int c, unsigned s, EvV &ev) {
        ev.push_back(wgl<64>(q, 1 + (R1[s] - R0[s]), 512, SkNormDotsWS<8>{R0[s], R1[s] - R0[s]}, (const float *)b.x,
                             (const float *)w.anw, b.y, (const float *)b.streams, (const float *)w.fa[c], b.d25));
    };
    auto A_norm = [&](int, unsigned, EvV &ev) {
        ev.push_back(wgl<32>(q, 1, 512, SkNormW<5120, 16>{}, (const float *)b.x, (const float *)w.anw, b.y));
    };
    using FR = FlH16Rows<160>;
    auto B_full = [&](int c, unsigned, EvV &ev) {
        using K = FlNormK<5120, 16, 25, 8, 0, NoRows, FR>;
        ev.push_back(flk(q, K{b.x, w.fnw, b.y, b.streams, w.ff[c], b.d25, NoRows{}, FR{NE, w.rt[c], b.router}}, 5120));
    };
    using KS = FlNormKS<5120, 16, 8, 0, NoRows, FR>;
    auto B_d = [&](int c, unsigned s, EvV &ev) {
        ev.push_back(flk(q, KS{b.x, w.fnw, b.y, b.streams, w.ff[c], b.d25, NoRows{}, FR{NE, w.rt[c], b.router}, R0[s], R1[s] - R0[s]}, 5120));
    };
    auto B_dr = [&](int c, unsigned s, EvV &ev) {
        const unsigned e0 = NE * s / NC, e1 = NE * (s + 1) / NC;
        ev.push_back(flk(q, KS{b.x, w.fnw, b.y, b.streams, w.ff[c], b.d25, NoRows{},
                              FR{e1 - e0, w.rt[c] + (size_t)e0 * w.rtb, b.router + e0}, R0[s], R1[s] - R0[s]}, 5120));
    };
    auto B_0 = [&](int c, unsigned, EvV &ev) {
        ev.push_back(flk(q, KS{b.x, w.fnw, b.y, b.streams, w.ff[c], b.d25, NoRows{}, FR{NE, w.rt[c], b.router}, 0u, 0u}, 5120));
    };
    auto C_launch = [&](int c, bool with_fin, EvV &ev) {
        auto go = [&](auto dk) {
            using DK = decltype(dk);
            using R1t = DenseRows<DK>;
            using RR = RowsPair<R1t, R1t>;
            const RR rr{R1t{dk, w.sg[c], b.y, b.shg}, R1t{dk, w.su[c], b.y, b.shu}};
            auto sub = [&](auto rx) {
                using RX = decltype(rx);
                using K = RoutePRows<RX>;
                K k{RouteP{(int)NE, 6}, rx};
                const size_t ng = 1 + (rx.n() + 15) / 16;
                const float *logits = b.router, *bias = w.bias;
                uint32_t *ids = b.ids;
                float *prob = b.prob;
                ev.push_back(q.submit([&](sycl::handler &hh) {
                    sycl::local_accessor<float, 1> lt(2 * 1024 + 6, hh);
                    hh.parallel_for(sycl::nd_range<1>(ng * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                        k(it, logits, bias, ids, prob, &lt[0]);
                    });
                }));
            };
            if (with_fin) sub(RowsPair<HcFinishRows, RR>{fin_of(w, b, b.d25), rr});
            else sub(rr);
        };
        if (w.sty == iq3::Type::Q8_0) go(GemvQ8P<160, Act>{SHR, 0});
        else go(GemvQ5KP<20, Act>{SHR, 0});
    };
    auto D_launch = [&](int c, bool with_fin, EvV &ev) {
        auto go = [&](auto dk) {
            using DK = decltype(dk);
            if (with_fin)
                ev.push_back(rows0(q, SDR + 1, FlDownCombF<DK, 6>{dk, fin_of(w, b, b.d25)}, (const uint8_t *)w.sd[c],
                                   (const float *)b.act, b.shd, (const float *)b.expd, b.out));
            else
                ev.push_back(rows0(q, SDR, FlDownComb<DK, 6>{dk}, (const uint8_t *)w.sd[c], (const float *)b.act, b.shd,
                                   (const float *)b.expd, b.out));
        };
        if (w.sty == iq3::Type::Q8_0) go(GemvQ8P<72, Act>{SDR, 0});
        else go(GemvQ5KP<9, Act>{SDR, 0});
    };
    auto E_launch = [&](EvV &ev) { ev.push_back(rows0(q, 1, RowsP<HcFinishRows>{fin_of(w, b, b.d25)})); };

    // ---- bitwise
    std::mt19937 g(9000u + (unsigned)w.L);
    long fb_rows = 0, all_rows = 0;
    for (int si = 0; si < nset; ++si) {
        const float sd = si == nset - 1 ? 1.0f : 0.6f;
        fill(q, b.x, H, g, si % 2 ? 1.0f : 0.5f, 30.f);
        fill(q, b.streams, H4, g, sd, 30.f);
        fill(q, b.router, NE, g, 1.0f, 3.f);
        fill(q, b.act, 7 * MID, g, 0.3f, 10.f);
        fill(q, b.expd, 6 * SDR, g, 0.2f, 10.f);
        // A: production, then the six shares into a cleared region
        q.memset(b.y, 0xff, H * 4), q.memset(b.d25, 0xff, 200 * 8), q.wait();
        { EvV ev; A_full(0, 0, ev); q.wait(); }
        const auto ay = words(q, b.y, H), ad = words(q, b.d25, 400);
        for (unsigned r = 0; r < 25; ++r) {
            ++all_rows;
            bool prod = false;
            for (unsigned k = 1; k < 8; ++k) prod |= (ad[(size_t)2 * (8 * r + k)] | ad[(size_t)2 * (8 * r + k) + 1]) != 0;
            fb_rows += prod;
        }
        q.memset(b.d25, 0xff, 200 * 8), q.wait();
        for (unsigned s = 0; s < NC; ++s) {
            q.memset(b.y, 0xff, H * 4).wait();
            EvV ev;
            A_share(0, s, ev);
            q.wait();
            check("A share y", ay, words(q, b.y, H), 0, H);
        }
        check("A shares d25", ad, words(q, b.d25, 400), 0, 400);
        // B: production, then dots-only shares (full router), then dots + router shares
        q.memset(b.y, 0xff, H * 4), q.memset(b.d25, 0xff, 200 * 8), q.memset(b.router, 0xff, NE * 4), q.wait();
        { EvV ev; B_full(0, 0, ev); q.wait(); }
        const auto by = words(q, b.y, H), bd = words(q, b.d25, 400), br = words(q, b.router, NE);
        for (int form = 0; form < 2; ++form) {
            q.memset(b.d25, 0xff, 200 * 8), q.memset(b.router, 0xff, NE * 4), q.wait();
            for (unsigned s = 0; s < NC; ++s) {
                q.memset(b.y, 0xff, H * 4).wait();
                if (form == 0) q.memset(b.router, 0xff, NE * 4).wait();
                EvV ev;
                if (form == 0) B_d(0, s, ev);
                else B_dr(0, s, ev);
                q.wait();
                check(form ? "Bdr share y" : "Bd share y", by, words(q, b.y, H), 0, H);
                if (form == 0) check("Bd share router", br, words(q, b.router, NE), 0, NE);
            }
            check(form ? "Bdr shares d25" : "Bd shares d25", bd, words(q, b.d25, 400), 0, 400);
            if (form == 1) check("Bdr shares router", br, words(q, b.router, NE), 0, NE);
        }
        { // B0: no dot rows, the same router and y
            q.memset(b.y, 0xff, H * 4), q.memset(b.router, 0xff, NE * 4), q.wait();
            EvV ev;
            B_0(0, 0, ev);
            q.wait();
            check("B0 y", by, words(q, b.y, H), 0, H);
            check("B0 router", br, words(q, b.router, NE), 0, NE);
        }
        // C / D / E on B's outputs (y = the FFN norm output, router logits, d25 = the FFN mix's partials)
        q.memcpy(b.d25, bd.data(), 400 * 4), q.memcpy(b.y, by.data(), H * 4), q.memcpy(b.router, br.data(), NE * 4), q.wait();
        auto fin_words = [&]() {
            auto a = words(q, b.pre, 4), p = words(q, b.post, 4), cm = words(q, b.comb, 16);
            a.insert(a.end(), p.begin(), p.end());
            a.insert(a.end(), cm.begin(), cm.end());
            return a;
        };
        auto clear_fin = [&]() { q.memset(b.pre, 0xff, 16), q.memset(b.post, 0xff, 16), q.memset(b.comb, 0xff, 64), q.wait(); };
        clear_fin();
        { EvV ev; E_launch(ev); q.wait(); }
        const auto ef = fin_words();
        std::vector<uint32_t> cw[2];
        for (int wf = 1; wf >= 0; --wf) {
            clear_fin();
            q.memset(b.ids, 0xff, 32), q.memset(b.prob, 0xff, 32), q.memset(b.shg, 0xff, SHR * 4), q.memset(b.shu, 0xff, SHR * 4), q.wait();
            EvV ev;
            C_launch(0, wf != 0, ev);
            q.wait();
            auto v = words(q, b.ids, 6), pr = words(q, b.prob, 6), gg = words(q, b.shg, SHR), uu = words(q, b.shu, SHR);
            v.insert(v.end(), pr.begin(), pr.end());
            v.insert(v.end(), gg.begin(), gg.end());
            v.insert(v.end(), uu.begin(), uu.end());
            cw[wf] = v;
            if (wf) check("C finish vs E", ef, fin_words(), 0, 24);
        }
        check("C with vs without finish", cw[1], cw[0], 0, cw[0].size());
        std::vector<uint32_t> dw[2];
        for (int wf = 0; wf < 2; ++wf) {
            clear_fin();
            q.memset(b.shd, 0xff, SDR * 4), q.memset(b.out, 0xff, SDR * 4), q.wait();
            EvV ev;
            D_launch(0, wf != 0, ev);
            q.wait();
            auto v = words(q, b.shd, SDR), o = words(q, b.out, SDR);
            v.insert(v.end(), o.begin(), o.end());
            dw[wf] = v;
            if (wf) check("D finish vs E", ef, fin_words(), 0, 24);
        }
        check("D with vs without finish", dw[0], dw[1], 0, dw[0].size());
    }
    std::printf("bitwise layer %d: %d sets; rows with production partials (SkDotsFF fallback) %ld of %ld\n", w.L, nset, fb_rows,
                all_rows);
    if (notime) return;
    {
        std::vector<Var> v{{"full", A_full, 1}, {"share", A_share, NC}, {"norm", A_norm, 1}};
        time_vars(q, v, reps, rounds, ncopy, "A", w.L);
    }
    {
        std::vector<Var> v{{"full", B_full, 1}, {"Bd", B_d, NC}, {"Bdr", B_dr, NC}, {"B0", B_0, 1}};
        time_vars(q, v, reps, rounds, ncopy, "B", w.L);
    }
    {
        std::vector<Var> v{{"withfin", [&](int c, unsigned, EvV &ev) { C_launch(c, true, ev); }, 1},
                           {"nofin", [&](int c, unsigned, EvV &ev) { C_launch(c, false, ev); }, 1}};
        time_vars(q, v, reps, rounds, ncopy, "C", w.L);
    }
    {
        std::vector<Var> v{{"plain", [&](int c, unsigned, EvV &ev) { D_launch(c, false, ev); }, 1},
                           {"withfin", [&](int c, unsigned, EvV &ev) { D_launch(c, true, ev); }, 1},
                           {"finalone", [&](int, unsigned, EvV &ev) { E_launch(ev); }, 1}};
        time_vars(q, v, reps, rounds, ncopy, "D", w.L);
    }
}

// X: XchgP2 / XchgQ2 indexing on one card. Six local buffers stand for the six arenas; card `me`'s flags from every
// peer preset to seq in its own buffer, so the wait passes. After the launch every other buffer must hold `me`'s
// words at [off + slot * stride + r0, .. + r1) and [off2 + s0, off2 + s1), its flag word 16 me = seq, and nothing else
// changed; `me`'s own buffer must be unchanged except nothing (the kernel only reads it).
static void run_x(sycl::queue &q, int reps) {
    const size_t NW = 8192;
    float *buf[6];
    uint32_t *err = sycl::malloc_device<uint32_t>(4, q), *cnt = sycl::malloc_device<uint32_t>(32, q);
    q.memset(err, 0, 16), q.memset(cnt, 0, 128), q.wait();
    for (int d = 0; d < 6; ++d) buf[d] = sycl::malloc_device<float>(NW, q);
    std::mt19937 g(5);
    struct Case { int kind; unsigned off, stride, nslot, r0, r1, off2, s0, s1; };
    const std::vector<Case> cases = {
        {0, 1024, 1792, 1, 288, 592, 2880, 64, 128},   // QKV (card 1) + attention rows 4..8
        {0, 1024, 1792, 1, 1488, 1792, 2880, 320, 400}, // QKV (card 5) + rows 20..25
        {1, 1024, 400, 7, 64, 128, 3840, 64, 128},     // act-like (7 slots) + rows
        {1, 1024, 384, 7, 320, 384, 3840, 320, 400},
    };
    int bad = 0;
    for (const auto &cs : cases) {
        for (int me = 0; me < 6; ++me) {
            std::vector<std::vector<float>> h(6, std::vector<float>(NW));
            for (int d = 0; d < 6; ++d) {
                for (auto &f : h[d]) f = std::uniform_real_distribution<float>(-1.f, 1.f)(g);
                for (int k = 0; k < 1024; ++k) h[d][k] = 0.f; // flag block
            }
            const uint32_t seq = 7;
            for (int t = 0; t < 6; ++t) {
                uint32_t s = seq;
                std::memcpy(&h[me][16 * t], &s, 4);
            }
            for (int d = 0; d < 6; ++d) q.memcpy(buf[d], h[d].data(), NW * 4);
            q.wait();
            if (cs.kind == 0) {
                const XchgP2 k{XchgP{6, me, cs.off, cs.stride, cs.nslot, cs.r0, cs.r1, seq, 1000000L, 0}, cs.off2, cs.s0, cs.s1};
                float *p0 = buf[0], *p1 = buf[1], *p2 = buf[2], *p3 = buf[3], *p4 = buf[4], *p5 = buf[5];
                uint32_t *e = err;
                q.parallel_for(sycl::nd_range<1>(256, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                    k(it, p0, p1, p2, p3, p4, p5, e);
                }).wait();
            } else {
                const size_t tot = (size_t)cs.nslot * ((cs.r1 - cs.r0) / 4) + (cs.s1 - cs.s0) / 4;
                const XchgQ2 k{XchgQ{6, me, cs.off, cs.stride, cs.nslot, cs.r0, cs.r1, seq, 1000000L, tot > 4 * 256 ? 1u : 0u},
                               cs.off2, cs.s0, cs.s1};
                float *p0 = buf[0], *p1 = buf[1], *p2 = buf[2], *p3 = buf[3], *p4 = buf[4], *p5 = buf[5];
                uint32_t *e = err, *cn = cnt;
                q.parallel_for(sycl::nd_range<1>(4 * 256, 256), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                    k(it, p0, p1, p2, p3, p4, p5, cn, e);
                }).wait();
            }
            for (int d = 0; d < 6; ++d) {
                std::vector<float> o(NW);
                q.memcpy(o.data(), buf[d], NW * 4).wait();
                std::vector<float> want = h[d];
                if (d != me) {
                    for (unsigned sl = 0; sl < cs.nslot; ++sl)
                        for (unsigned r = cs.r0; r < cs.r1; ++r) want[cs.off + sl * cs.stride + r] = h[me][cs.off + sl * cs.stride + r];
                    for (unsigned r = cs.s0; r < cs.s1; ++r) want[cs.off2 + r] = h[me][cs.off2 + r];
                    uint32_t s = seq;
                    std::memcpy(&want[16 * me], &s, 4);
                }
                ++g_cmp;
                if (std::memcmp(o.data(), want.data(), NW * 4)) {
                    ++bad, ++g_fail;
                    size_t i = 0;
                    while (i < NW && std::memcmp(&o[i], &want[i], 4) == 0) ++i;
                    std::printf("  X kind %d me %d buffer %d differs at word %zu\n", cs.kind, me, d, i);
                }
            }
        }
    }
    uint32_t e0 = 0;
    q.memcpy(&e0, err, 4).wait();
    std::printf("X: XchgP2 / XchgQ2 indexing, %zu cases x 6 cards x 6 buffers: %d differ; err word %u\n", cases.size(), bad, e0);
    (void)reps;
    for (int d = 0; d < 6; ++d) sycl::free(buf[d], q);
    sycl::free(err, q), sycl::free(cnt, q);
}

int main() {
    const int nset = envi("NSET", 4), reps = envi("REPS", 40), rounds = envi("ROUNDS", 5), ncopy = envi("NCOPY", 8);
    const bool notime = getenv("NOTIME") != nullptr;
    g_form = envi("FORM", 1);
    sycl::queue q{sycl::gpu_selector_v, sycl::property_list{sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    const auto dev = q.get_device();
    std::printf("device %s, %u compute units\n", dev.get_info<sycl::info::device::name>().c_str(),
                dev.get_info<sycl::info::device::max_compute_units>());
    if (dev.has(sycl::aspect::ext_intel_free_memory)) {
        const size_t fm = dev.get_info<sycl::ext::intel::info::device::free_memory>();
        std::printf("free card memory %.2f GiB\n", fm / 1073741824.0);
        if (fm < ((size_t)2 << 30)) { std::printf("not enough free card memory\n"); return 3; }
    } else {
        std::printf("free memory query unavailable (ZES_ENABLE_SYSMAN=1)\n");
        return 3;
    }
    std::printf("dot rows per card:");
    for (unsigned s = 0; s < NC; ++s) { unsigned a, b; rep2_rows((int)NC, (int)s, a, b); std::printf(" [%u, %u)", a, b); }
    std::printf("\n");
    run_x(q, reps);
    Bufs b;
    b.x = sycl::malloc_device<float>(H, q);
    b.y = sycl::malloc_device<float>(H, q);
    b.streams = sycl::malloc_device<float>(H4, q);
    b.router = sycl::malloc_device<float>(NE, q);
    b.act = sycl::malloc_device<float>(7 * MID, q);
    b.shg = sycl::malloc_device<float>(SHR, q);
    b.shu = sycl::malloc_device<float>(SHR, q);
    b.shd = sycl::malloc_device<float>(SDR, q);
    b.expd = sycl::malloc_device<float>(6 * SDR, q);
    b.out = sycl::malloc_device<float>(SDR, q);
    b.pre = sycl::malloc_device<float>(4, q);
    b.post = sycl::malloc_device<float>(4, q);
    b.comb = sycl::malloc_device<float>(16, q);
    b.d25 = sycl::malloc_device<double>(200 + 8, q);
    b.ids = sycl::malloc_device<uint32_t>(8, q);
    b.prob = sycl::malloc_device<float>(8, q);
    std::vector<unsigned> pls = env_list("PL", {});
    if (pls.empty()) {
        int q8 = -1, q5 = -1;
        (void)gt("blk.2.ffn_gate_shexp.weight");
        for (int L = 0; L < 64 && (q8 < 0 || q5 < 0); ++L) {
            const std::string n = "blk." + std::to_string(L) + ".ffn_gate_shexp.weight";
            if (!g_idx.count(n) || !g_idx.count("blk." + std::to_string(L) + ".ffn_gate_inp.weight")) continue;
            const uint32_t ty = gt(n).type;
            if (ty == 8 && q8 < 0) q8 = L;
            if (ty == 13 && q5 < 0) q5 = L;
        }
        if (q8 >= 0) pls.push_back((unsigned)q8);
        if (q5 >= 0) pls.push_back((unsigned)q5);
    }
    for (unsigned L : pls) {
        const LW w = load_layer(q, (int)L, ncopy);
        if (w.sty != iq3::Type::Q8_0 && w.sty != iq3::Type::Q5_K) { std::printf("layer %u: shared type %u not benched\n", L, (unsigned)w.sty); continue; }
        run_layer(q, w, b, nset, reps, rounds, ncopy, notime);
        for (int c = 0; c < ncopy; ++c)
            sycl::free(w.fa[c], q), sycl::free(w.ff[c], q), sycl::free(w.rt[c], q), sycl::free(w.sg[c], q), sycl::free(w.su[c], q),
                sycl::free(w.sd[c], q);
        sycl::free(w.anw, q), sycl::free(w.fnw, q), sycl::free(w.bias, q), sycl::free(w.fsc, q), sycl::free(w.fbs, q);
    }
    std::printf("\nALL: %ld comparisons, %d failing -> %s\n", g_cmp, g_fail, g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
