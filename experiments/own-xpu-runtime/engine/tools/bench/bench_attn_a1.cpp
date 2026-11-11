// attn a1 (2026-11-11): the engine's sparse attention at its one-token and guess-check shapes against
// sycl_v41_attn.hpp, one card. Production: WindowAppendP + SparseScoreHG<512, 1> (SparseScoreP<512> at 128 slots) +
// SparseSoftmaxP<n> + SparseOutJC<512, 16, 128> (with the rope'd ry); blocks ScoreM / SoftmaxM / OutMC<JC>.
// Forms (main table, the lists given): 0 production; 1 SparseScoreT<512, 8> + SparseOutJE<512, n, 16, true>
// (the softmax in the output launch); 2 SparseScoreT<512, 16> + the same; 3 SparseOutF<512, n> (one launch, through
// SparseOutFK at FGRF registers). WIN=1: one token with the window append, production against SparseScoreT<512, 8 |
// 16, true> + SparseOutJE and against SparseOutF<512, n, true> (ring, widx, cat, weights, out, ry).
// OUT=1: the output alone, SparseOutJC against SparseOutJE<512, n, 16, false> (weights given).
// Checks: everything BITWISE against production (memcmp): out, ry, the kept slots' weights (production's softmax
// output against SparseOutJE's wout copy), the kept slots' raw scores (production's score launch alone against
// SparseScoreT's; the engine's attn_w keeps them), WIN: the ring, widx, the list; every shape and both data kinds
// (normal; peaky q * 6 with 40 early window slots and 1/8 of the chosen rows skipped), stale scores NaN / inf / huge,
// out and ry NaN before each run.
// RACE=n (attn a2): the one launch (F) the way the engine runs it, which the checks above do not: n steps per shape,
// each step two layers A and B (their own queries, sinks, lists and rings) that SHARE F's score array, so every F
// launch finds the other layer's scores there (the engine's attn_w); every launch checked on the card, bit for bit,
// against production run beside it on its own copies. One token (default; ONLY tags "rw h.. n.. p.."): consecutive
// steps p0, p0 + 1, ... on each layer's ring with the window append (each step reads the ring rows earlier steps'
// launches stored; p0 = 36 crosses the window's first wrap), the rings, widx and lists compared at the end. RACE_M=1,2,..
// (tags "rb h.. n.. M.."): blocks with fixed lists instead. SPOIL=1: before every F launch a kernel on every Xe core
// reads F's score array and the layer's ring; RFLUSH=1: the cache flush before every step; CONC=1 | 2: copy-engine
// copies | streaming kernels on a second queue during each shape. (a1's F failed in the
// engine, gate tg95, not in the checks above: they ran one launch after a fresh stale fill.)
// WA=1 (attn wa-1): blocks (MS, default 2,3,4,5,6,8; 16 / 12 / 8 heads; the 10 slot counts; block start 1000, 125, 60
// and 0; ONLY tags "wa h.. n.. M.. p..") with the window append: WindowAppendM + production against WindowAppendM +
// the engine's OWN_ATT_T form and the WA forms (F, T8 + JE, T16 + JE): out, ry, kept weights and raw scores, the whole
// ring (its block area starts stale) and the lists, bitwise; then the time of WindowAppendM alone and of the engine's
// chain without / with WA (after the flush the block's kv and q are read once, as the engine's rope launches leave
// them in L2; WA_COLD=1: not). WA_STEPS=n: n consecutive checks per shape on two layers (each its ring, lists and
// queries; the layers share each form's score array), RingCommitM after each, every launch's out / ry compared on
// the card, the rings and lists at the end; CONC as RACE (ONLY tags "ws h.. n.. M..").
// Time: GPU time per launch and the chain (first start -> last end), median of IT runs, the card's cache flushed
// before each run (the engine's rows come cold), after a 400 ms warm-up (an idle card runs ~2.5x slower at first).
// NB=128 | 256: a one-work-group kernel of that register file right before and after each form (the engine's
// neighbours are 128-register kernels: a 256-register launch between them costs two register-mode changes); the
// chain then runs from the first neighbour's start to the second's end.
// Env: ONLY=substring of the shape tag, IT (default 60), MS=1,2,4,6,8 (token counts), NOFLUSH=1, NOCHECK=1, NOTIME=1,
// WIN=1, OUT=1, FGRF=0 (the engine's register file and tile heads per shape, att_f_grf / att_f_s8; or 128 | 256 with
// SHG=16 | 8: SparseOutF's score tiles of 16 or 8 heads), NB. Build: icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31
// "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -I src.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/sycl_v41_attn.hpp"
using namespace ops41sycl;

static sycl::queue *gq;
template <typename K, typename... A> sycl::event lsg(size_t g, K k, A... a) {
    return gq->parallel_for(sycl::nd_range<1>(g * 32, 32),
                            [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, a...); });
}
template <size_t SLM, typename K, typename... A> sycl::event lwg(size_t g, size_t wg, K k, A... a) {
    return gq->submit([&](sycl::handler &h) {
        sycl::local_accessor<uint32_t, 1> lt(SLM, h);
        h.parallel_for(sycl::nd_range<1>(g * wg, wg),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, a..., &lt[0]); });
    });
}
template <unsigned GRF> struct NbK {
    float *p;
    void operator()(sycl::nd_item<1> it) const {
        if (it.get_global_linear_id() == 0) p[0] += 1.0f;
    }
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<GRF>,
                                                           sycl::ext::oneapi::experimental::sub_group_size<32>};
    }
};
static int g_nb = 0, g_fgrf = 0;
static float *g_nbp = nullptr;
static sycl::event nbk() {
    if (g_nb == 256) return gq->parallel_for(sycl::nd_range<1>(32, 32), NbK<256>{g_nbp});
    return gq->parallel_for(sycl::nd_range<1>(32, 32), NbK<128>{g_nbp});
}
static double evus(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
static double span_us(const sycl::event &a, const sycl::event &b) {
    return (b.get_profiling_info<sycl::info::event_profiling::command_end>() -
            a.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}

constexpr unsigned HD = 512, QH = 64;
constexpr size_t QS = (size_t)QH * HD, WS = (size_t)QH * 640;
constexpr int NVALS[] = {128, 160, 192, 288, 320, 384, 448, 512, 576, 640};
constexpr int NNV = (int)(sizeof(NVALS) / sizeof(int));

struct Bufs {
    float *q, *sinks, *w, *w2, *out, *ry, *cs, *sn;
    uint16_t *kvw, *kvc;
    int32_t *ix;
};

// ---- production
template <int NI> void softmax_prod(unsigned M, int nh, const float *sinks, const int32_t *ix, float *w, std::vector<sycl::event> &ev) {
    if (M == 1) ev.push_back(lsg(nh, SparseSoftmaxP<NI>{nh}, sinks, ix, w));
    else ev.push_back(lsg((size_t)M * nh, SoftmaxM<SparseSoftmaxP<NI>>{{nh}, (unsigned)nh, M, 640, WS}, sinks, ix, w));
}
template <int I = 0> void softmax_any(int n, unsigned M, int nh, const float *s, const int32_t *ix, float *w, std::vector<sycl::event> &ev) {
    if constexpr (I < NNV) {
        if (n == NVALS[I]) return softmax_prod<NVALS[I]>(M, nh, s, ix, w, ev);
        return softmax_any<I + 1>(n, M, nh, s, ix, w, ev);
    } else {
        std::printf("no softmax for n %d\n", n);
        std::exit(2);
    }
}
static void score_prod(int n, unsigned M, int nh, int W, const Bufs &b, std::vector<sycl::event> &ev) {
    if (n == 128) {
        if (M == 1) ev.push_back(lsg((size_t)nh * n / 32, SparseScoreP<512>{n, nh, W, (int)HD}, (const float *)b.q, (const uint16_t *)b.kvw,
                                     (const uint16_t *)b.kvc, (const int32_t *)b.ix, b.w));
        else ev.push_back(lsg((size_t)M * nh * n / 32, ScoreM<SparseScoreP<512>>{{n, nh, W, (int)HD}, (unsigned)(nh * n / 32), M, QS, 640, WS},
                              (const float *)b.q, (const uint16_t *)b.kvw, (const uint16_t *)b.kvc, (const int32_t *)b.ix, b.w));
    } else {
        const unsigned gpt = (unsigned)(nh * (n / 32));
        if (M == 1) ev.push_back(lsg(gpt, SparseScoreHG<512, 1>{n, nh, W, (int)HD}, (const float *)b.q, (const uint16_t *)b.kvw,
                                     (const uint16_t *)b.kvc, (const int32_t *)b.ix, b.w));
        else ev.push_back(lsg((size_t)M * gpt, ScoreM<SparseScoreHG<512, 1>>{{n, nh, W, (int)HD}, gpt, M, QS, 640, WS}, (const float *)b.q,
                              (const uint16_t *)b.kvw, (const uint16_t *)b.kvc, (const int32_t *)b.ix, b.w));
    }
}
static sycl::event out_jc(unsigned M, int n, int nh, int W, const Bufs &b) {
    using SC = SparseOutJC<512, 16, 128>;
    SC so{n, nh, W};
    so.ry = b.ry, so.cosb = b.cs, so.sinb = b.sn;
    const unsigned gpo = (unsigned)SC::groups(nh);
    if (M == 1) return lwg<SC::SLM>(gpo, SC::WG, so, (const uint16_t *)b.kvw, (const uint16_t *)b.kvc, (const int32_t *)b.ix, (const float *)b.w, b.out);
    return lwg<SC::SLM>((size_t)M * gpo, SC::WG, OutMC<SC>{so, gpo, M, 640, WS, QS, QS}, (const uint16_t *)b.kvw, (const uint16_t *)b.kvc,
                        (const int32_t *)b.ix, (const float *)b.w, b.out);
}

// ---- sycl_v41_attn.hpp
template <unsigned HG> sycl::event score_t(int n, unsigned M, int nh, int W, const Bufs &b) {
    using K = SparseScoreT<HD, HG>;
    K k{n, nh, W, (int)HD};
    k.m = M;
    k.qs = QS, k.is = 640, k.ss = WS;
    return lwg<K::SLM>((size_t)M * K::groups(n, nh), K::WG, k, (const float *)b.q, (const uint16_t *)b.kvw, (const uint16_t *)b.kvc,
                       (const int32_t *)b.ix, b.w);
}
template <int NI, bool SM> sycl::event out_je1(unsigned M, int n, int nh, int W, const Bufs &b) {
    using SC = SparseOutJE<HD, NI, 16, SM>;
    SC so{n, nh, W};
    so.ry = b.ry, so.cosb = b.cs, so.sinb = b.sn;
    so.sinks = b.sinks;
    so.wout = SM ? b.w2 : nullptr;
    const unsigned gpo = (unsigned)SC::groups(nh);
    if (M == 1) return lwg<SC::SLM>(gpo, SC::WG, so, (const uint16_t *)b.kvw, (const uint16_t *)b.kvc, (const int32_t *)b.ix, (const float *)b.w, b.out);
    return lwg<SC::SLM>((size_t)M * gpo, SC::WG, OutMJ<SC>{so, gpo, M, 640, WS, QS, QS}, (const uint16_t *)b.kvw, (const uint16_t *)b.kvc,
                        (const int32_t *)b.ix, (const float *)b.w, b.out);
}
template <bool SM, int I = 0> sycl::event out_je(unsigned M, int n, int nh, int W, const Bufs &b) {
    if constexpr (I < NNV) {
        if (n == NVALS[I]) return out_je1<NVALS[I], SM>(M, n, nh, W, b);
        return out_je<SM, I + 1>(M, n, nh, W, b);
    } else {
        std::printf("no output for n %d\n", n);
        std::exit(2);
    }
}

// one launch: SparseOutF (the card's counter g_cnt, the running count g_target, the error word g_err)
static uint32_t *g_cnt = nullptr, *g_err = nullptr;
static uint32_t g_target = 0;
static int g_shg = 16; // SHG=8: SparseOutF's score tiles of 8 heads
template <int NI, bool WIN, unsigned SHG, bool WA = false> sycl::event out_f2(unsigned grf, unsigned M, int nh, int W, const Bufs &b, int p,
                                                                             int nc, const float *kv, const int32_t *cidx, int32_t *widx) {
    using K = SparseOutF<HD, NI, WIN, ActF32, SHG, WA>;
    K k{nh, W, (int)HD};
    k.m = M;
    k.qs = QS, k.is = 640, k.ss = WS, k.os = QS, k.rs = QS;
    k.start_pos = p, k.nc = nc;
    g_target += M * (uint32_t)K::nst(nh);
    k.target = g_target;
    k.spin = 5000000;
    const size_t gr = K::groups(nh, M);
    return gq->submit([&](sycl::handler &h) {
        sycl::local_accessor<uint32_t, 1> lt(K::SLM, h);
        if (grf == 128)
            h.parallel_for(sycl::nd_range<1>(gr * K::WG, K::WG),
                           SparseOutFK<K, 128>{k, b.q, b.kvw, b.kvc, b.ix, kv, cidx, widx, b.w, b.out, b.ry, b.cs, b.sn, b.sinks, b.w2,
                                               g_cnt, g_err, lt});
        else
            h.parallel_for(sycl::nd_range<1>(gr * K::WG, K::WG),
                           SparseOutFK<K, 256>{k, b.q, b.kvw, b.kvc, b.ix, kv, cidx, widx, b.w, b.out, b.ry, b.cs, b.sn, b.sinks, b.w2,
                                               g_cnt, g_err, lt});
    });
}
template <int NI, bool WIN, bool WA = false> sycl::event out_f1(unsigned M, int nh, int W, const Bufs &b, int p, int nc, const float *kv,
                                                               const int32_t *cidx, int32_t *widx) {
    // FGRF=0 (default): the engine's choice (att_f_grf, att_f_s8); else FGRF and SHG as given
    const unsigned grf = g_fgrf ? (unsigned)g_fgrf : att_f_grf<NI, WIN>();
    const bool s8 = g_fgrf ? g_shg == 8 : att_f_s8(NI, WIN, M);
    if (s8) return out_f2<NI, WIN, 8, WA>(grf, M, nh, W, b, p, nc, kv, cidx, widx);
    return out_f2<NI, WIN, 16, WA>(grf, M, nh, W, b, p, nc, kv, cidx, widx);
}
template <bool WIN, int I = 0, bool WA = false>
sycl::event out_f(int n, unsigned M, int nh, int W, const Bufs &b, int p = 0, int nc = 0, const float *kv = nullptr,
                  const int32_t *cidx = nullptr, int32_t *widx = nullptr) {
    if constexpr (I < NNV) {
        if (n == NVALS[I]) return out_f1<NVALS[I], WIN, WA>(M, nh, W, b, p, nc, kv, cidx, widx);
        return out_f<WIN, I + 1, WA>(n, M, nh, W, b, p, nc, kv, cidx, widx);
    } else {
        std::printf("no one-launch form for n %d\n", n);
        std::exit(2);
    }
}

// main forms: 0 production; 1 T8 + JE (softmax in it); 2 T16 + JE; 3 F (one launch)
constexpr int NF = 4;
static const char *fname[NF] = {"prod", "T8+JE", "T16+JE", "F"};
static void run_form(int form, int n, unsigned M, int nh, int W, const Bufs &b, std::vector<sycl::event> &ev) {
    if (form == 3) {
        ev.push_back(out_f<false>(n, M, nh, W, b));
        return;
    }
    if (form == 0) {
        score_prod(n, M, nh, W, b, ev);
        softmax_any(n, M, nh, b.sinks, b.ix, b.w, ev);
        ev.push_back(out_jc(M, n, nh, W, b));
        return;
    }
    ev.push_back(form == 1 ? score_t<8>(n, M, nh, W, b) : score_t<16>(n, M, nh, W, b));
    ev.push_back(out_je<true>(M, n, nh, W, b));
}

// one token with the window append: 0 production (WindowAppendP + score + softmax + JC); 1 / 2 SparseScoreT<512, 8 /
// 16, true> + JE; 3 SparseOutF<512, n, true>
template <unsigned HG> sycl::event score_tw(int n, int nh, int p, int nc, const Bufs &b, const float *kv, const int32_t *cidx, int32_t *widx) {
    using K = SparseScoreT<HD, HG, true, ActF32>;
    K k{n, nh, 128, (int)HD};
    k.start_pos = p, k.nc = nc;
    return lwg<K::SLM>(K::groups(n, nh), K::WG, k, (const float *)b.q, b.kvw, (const uint16_t *)b.kvc, kv, cidx, widx, b.ix, b.w);
}
static void run_win(int f, int n, int nh, int p, const Bufs &b, const float *kv, const int32_t *cidx, int32_t *widx,
                    std::vector<sycl::event> &ev) {
    const int nc = n > 128 ? 512 : 0;
    const int32_t *ci = nc ? cidx : (const int32_t *)nullptr;
    if (f == 3) {
        ev.push_back(out_f<true>(n, 1, nh, 128, b, p, nc, kv, ci, widx));
        return;
    }
    if (f == 0) {
        const WindowAppendP<ActF32> wa{128, (int)HD, p, nc};
        uint16_t *ring = b.kvw;
        int32_t *cat = b.ix;
        ev.push_back(gq->parallel_for(sycl::nd_range<1>(512, 64), [=](sycl::nd_item<1> it) { wa(it, ring, kv, widx, cat, ci); }));
        score_prod(n, 1, nh, 128, b, ev);
        softmax_any(n, 1, nh, b.sinks, b.ix, b.w, ev);
        ev.push_back(out_jc(1, n, nh, 128, b));
        return;
    }
    ev.push_back(f == 1 ? score_tw<8>(n, nh, p, nc, b, kv, ci, widx) : score_tw<16>(n, nh, p, nc, b, kv, ci, widx));
    ev.push_back(out_je<true>(1, n, nh, 128, b));
}

// attn wa-1: blocks with the window append (W = 128 + 256 window rows, as the engine's MTX). 0 WindowAppendM +
// production (ScoreM + SoftmaxM + OutMC); 1 WindowAppendM + the engine's OWN_ATT_T form (att_f_on: F, else T8 + JE);
// 2 SparseOutF WA; 3 SparseScoreT<512, 8> WA + JE; 4 SparseScoreT<512, 16> WA + JE; 5 the engine's form with WA
// (OWN_ATT_WA=1: att_f_on ? 2 : 3)
constexpr int WA_W = 128 + 256;
static bool wa_f_on(int n, unsigned M) { return M <= 4 || n <= 160 || n >= 640; } // (backend att_f_on)
static sycl::event wam(unsigned M, int p, int nc, uint16_t *ring, const float *kv, int32_t *cat, const int32_t *ci) {
    const WindowAppendM<ActF32> wa{128, (int)HD, p, nc, (int)M, WA_W - 128, (size_t)HD, 512, 640};
    return gq->parallel_for(sycl::nd_range<1>((size_t)M * std::max<int>((int)HD, 128 + nc), 64),
                            [=](sycl::nd_item<1> it) { wa(it, ring, kv, cat, ci); });
}
template <unsigned HG> sycl::event score_ta(int n, unsigned M, int nh, int p, int nc, const Bufs &b, const float *kv, const int32_t *ci) {
    using K = SparseScoreT<HD, HG, false, ActF32, true>;
    K k{n, nh, WA_W, (int)HD};
    k.m = M;
    k.qs = QS, k.is = 640, k.ss = WS;
    k.start_pos = p, k.nc = nc;
    return lwg<K::SLM>((size_t)M * K::groups(n, nh), K::WG, k, (const float *)b.q, b.kvw, (const uint16_t *)b.kvc, kv, ci, b.ix, b.w);
}
static void run_wa(int f, int n, unsigned M, int nh, int p, const Bufs &b, const float *kv, const int32_t *cidx,
                   std::vector<sycl::event> &ev) {
    const int nc = n > 128 ? 512 : 0;
    const int32_t *ci = nc ? cidx : (const int32_t *)nullptr;
    if (f == 5) f = wa_f_on(n, M) ? 2 : 3;
    if (f <= 1) {
        ev.push_back(wam(M, p, nc, b.kvw, kv, b.ix, ci));
        if (f == 0) run_form(0, n, M, nh, WA_W, b, ev);
        else run_form(wa_f_on(n, M) ? 3 : 1, n, M, nh, WA_W, b, ev);
        return;
    }
    if (f == 2) {
        ev.push_back(out_f<false, 0, true>(n, M, nh, WA_W, b, p, nc, kv, ci, nullptr));
        return;
    }
    ev.push_back(f == 3 ? score_ta<8>(n, M, nh, p, nc, b, kv, ci) : score_ta<16>(n, M, nh, p, nc, b, kv, ci));
    ev.push_back(out_je<true>(M, n, nh, WA_W, b));
}

static uint16_t f2bf(float f) { // round to nearest even (finite values)
    uint32_t u;
    std::memcpy(&u, &f, 4);
    return (uint16_t)((u + 0x7fff + ((u >> 16) & 1)) >> 16);
}

int main() {
    sycl::queue q{sycl::gpu_selector_v, sycl::property_list{sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    gq = &q;
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    if (const char *e = std::getenv("FGRF")) g_fgrf = std::atoi(e);
    if (const char *e = std::getenv("NB")) g_nb = std::atoi(e);
    if (const char *e = std::getenv("SHG")) g_shg = std::atoi(e);
    g_nbp = sycl::malloc_device<float>(16, q);
    g_cnt = sycl::malloc_device<uint32_t>(16, q);
    g_err = sycl::malloc_device<uint32_t>(16, q);
    q.fill(g_nbp, 0.f, 16).wait();
    q.fill(g_cnt, 0u, 16).wait();
    q.fill(g_err, 0u, 16).wait();
    auto ferr = [&]() { // a one-launch wait that timed out
        uint32_t e = 0;
        q.memcpy(&e, g_err, 4).wait();
        if (e) std::printf("ONE-LAUNCH WAIT TIMED OUT\n");
        return e != 0;
    };
    const char *only = std::getenv("ONLY");
    const int IT = std::getenv("IT") ? std::atoi(std::getenv("IT")) : 60;
    const bool flush = !std::getenv("NOFLUSH"), check = !std::getenv("NOCHECK"), timing = !std::getenv("NOTIME");
    constexpr int MMAX = 16, WMAX = 128 + 256, CROWS = 8192;
    const size_t nq = MMAX * QS, nw = MMAX * WS, nix = MMAX * 640;
    Bufs b{};
    b.q = sycl::malloc_device<float>(nq, q);
    b.sinks = sycl::malloc_device<float>(QH, q);
    b.w = sycl::malloc_device<float>(nw, q);
    b.w2 = sycl::malloc_device<float>(nw, q);
    b.out = sycl::malloc_device<float>(nq, q);
    b.ry = sycl::malloc_device<float>(nq, q);
    b.cs = sycl::malloc_device<float>(MMAX * 32, q);
    b.sn = sycl::malloc_device<float>(MMAX * 32, q);
    b.kvw = sycl::malloc_device<uint16_t>((size_t)WMAX * HD, q);
    b.kvc = sycl::malloc_device<uint16_t>((size_t)CROWS * HD, q);
    b.ix = sycl::malloc_device<int32_t>(nix, q);
    const size_t nfl = (size_t)64 << 20; // 256 MiB of floats to push the rows out of L2
    float *fl = sycl::malloc_device<float>(nfl, q), *fo = sycl::malloc_device<float>(1024, q);
    q.fill(fl, 1.0f, nfl).wait();
    auto flush_k = [=](sycl::nd_item<1> it) {
        float s = 0;
        for (size_t i = it.get_global_linear_id(); i < nfl; i += 1024 * 32) s += fl[i];
        if (s == 12345.f) fo[0] = s;
    };
    auto warm = [&](int ms) { // keep the card busy so its clock is up (an idle card runs ~2.5x slower at first)
        const auto t0 = std::chrono::steady_clock::now();
        while (std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count() < ms) {
            for (int r = 0; r < 20; ++r) lsg(1024, flush_k);
            q.wait();
        }
    };
    warm(400);
    std::mt19937 rng(41);
    std::normal_distribution<float> nd(0.f, 1.f);
    {
        std::vector<uint16_t> kw((size_t)WMAX * HD), kc((size_t)CROWS * HD);
        for (auto &x : kw) x = f2bf(nd(rng));
        for (auto &x : kc) x = f2bf(nd(rng));
        q.memcpy(b.kvw, kw.data(), kw.size() * 2).wait();
        q.memcpy(b.kvc, kc.data(), kc.size() * 2).wait();
        std::vector<float> cs(MMAX * 32), sn(MMAX * 32);
        for (int i = 0; i < MMAX * 32; ++i) cs[i] = std::cos(0.37f * i), sn[i] = std::sin(0.37f * i);
        q.memcpy(b.cs, cs.data(), cs.size() * 4).wait();
        q.memcpy(b.sn, sn.data(), sn.size() * 4).wait();
    }
    // stale scores / weights: a pattern with NaN / inf / huge values, the same before every run
    std::vector<float> stale(nw);
    for (size_t i = 0; i < nw; ++i) {
        const uint32_t pat[4] = {0x7fc12345u, 0x7f800000u, 0xff800000u, 0x7f7fffffu};
        uint32_t u = pat[i % 4];
        std::memcpy(&stale[i], &u, 4);
    }
    struct Kind { const char *name; float qscale; int early; int skip8; };
    const Kind kinds[] = {{"normal", 1.f, 0, 0}, {"peaky q*6, early window, 1/8 skipped", 6.f, 40, 1}};
    struct Shape { int n; unsigned M; int nh; };
    std::vector<Shape> shapes;
    std::vector<unsigned> ms = {1u, 2u, 4u, 6u, 8u};
    if (const char *e = std::getenv("MS")) {
        ms.clear();
        for (const char *c = e; *c;) {
            ms.push_back((unsigned)std::atoi(c));
            while (*c && *c != ',') ++c;
            if (*c) ++c;
        }
    }
    for (int nh : {16, 12, 8}) // (12: the cards of a split head group in blocks, OWN_TP_HEADS_MIN)
        for (unsigned M : ms)
            for (int n : NVALS) shapes.push_back({n, M, nh});
    auto kept_equal = [&](const std::vector<float> &a, const std::vector<float> &c, const std::vector<int32_t> &ix, unsigned M, int nh, int n) {
        size_t bad = 0;
        for (unsigned t = 0; t < M; ++t)
            for (int h = 0; h < nh; ++h)
                for (int i = 0; i < n; ++i)
                    if (ix[t * 640 + i] >= 0) {
                        const size_t o = t * WS + (size_t)h * n + i;
                        bad += std::memcmp(&a[o], &c[o], 4) != 0;
                    }
        return bad;
    };
    auto out_equal = [&](const std::vector<float> &a, const std::vector<float> &c, unsigned M, int nh) {
        size_t bad = 0;
        for (unsigned t = 0; t < M; ++t)
            for (int h = 0; h < nh; ++h) bad += std::memcmp(&a[t * QS + (size_t)h * HD], &c[t * QS + (size_t)h * HD], HD * 4) != 0;
        return bad;
    };
    if (std::getenv("WIN")) {
        bool ok = true;
        float *kv = sycl::malloc_device<float>(HD, q);
        int32_t *cidx = sycl::malloc_device<int32_t>(512, q), *widx = sycl::malloc_device<int32_t>(128, q);
        std::vector<uint16_t> ring0((size_t)128 * HD);
        q.memcpy(ring0.data(), b.kvw, ring0.size() * 2).wait();
        std::printf("one token, window + score + softmax + output chain us (median of %d%s%s): prod, TW8 + JE, TW16 + JE, F\n", IT,
                    flush ? ", L2 flushed" : "", g_nb ? ", between neighbour kernels" : "");
        for (int nh : {16, 8})
            for (int n : NVALS)
                for (int p : {1000, 60, 127, 0}) {
                    char tag[64];
                    std::snprintf(tag, sizeof tag, "h%d n%d p%d", nh, n, p);
                    if (only && !std::strstr(tag, only)) continue;
                    std::vector<float> hq(nq), hs(QH), hk(HD);
                    for (auto &x : hq) x = nd(rng);
                    for (auto &x : hs) x = nd(rng) * 2.f;
                    for (auto &x : hk) x = nd(rng);
                    std::vector<int32_t> hc(512, -1);
                    if (n == 640) {
                        std::vector<int> pc(CROWS);
                        for (int i = 0; i < CROWS; ++i) pc[i] = i;
                        std::shuffle(pc.begin(), pc.end(), rng);
                        for (int i = 0; i < 512; ++i) hc[i] = (i % 8 == 5) ? -1 : 128 + pc[i];
                    } else if (n > 128) {
                        const int len = n - 128 - (int)(rng() % 32);
                        for (int i = 0; i < 512; ++i) hc[i] = i < len ? 128 + i : -1;
                    }
                    q.memcpy(b.q, hq.data(), nq * 4).wait();
                    q.memcpy(b.sinks, hs.data(), QH * 4).wait();
                    q.memcpy(kv, hk.data(), HD * 4).wait();
                    q.memcpy(cidx, hc.data(), 512 * 4).wait();
                    std::vector<float> rw[4], ro[4], rr[4];
                    std::vector<uint16_t> rg[4];
                    std::vector<int32_t> rc[4], rx[4];
                    auto reset = [&]() {
                        q.memcpy(b.kvw, ring0.data(), ring0.size() * 2).wait();
                        q.memcpy(b.w, stale.data(), nw * 4).wait();
                        q.memcpy(b.w2, stale.data(), nw * 4).wait();
                        q.fill(b.ix, (int32_t)-7, nix).wait();
                        q.fill(widx, (int32_t)-7, 128).wait();
                        q.fill(b.out, std::nanf(""), nq).wait();
                        q.fill(b.ry, std::nanf(""), nq).wait();
                    };
                    for (int f = 0; f < 4; ++f) {
                        reset();
                        std::vector<sycl::event> ev;
                        run_win(f, n, nh, p, b, kv, cidx, widx, ev);
                        q.wait();
                        rw[f].resize(nw), ro[f].resize(nq), rr[f].resize(nq), rg[f].resize(ring0.size()), rc[f].resize(nix), rx[f].resize(128);
                        q.memcpy(rw[f].data(), f ? b.w2 : b.w, nw * 4).wait(); // the weights: production's softmax, JE's wout
                        q.memcpy(ro[f].data(), b.out, nq * 4).wait();
                        q.memcpy(rr[f].data(), b.ry, nq * 4).wait();
                        q.memcpy(rg[f].data(), b.kvw, ring0.size() * 2).wait();
                        q.memcpy(rc[f].data(), b.ix, nix * 4).wait();
                        q.memcpy(rx[f].data(), widx, 128 * 4).wait();
                        if (f) {
                            const size_t bw = kept_equal(rw[0], rw[f], rc[0], 1, nh, n), bo = out_equal(ro[0], ro[f], 1, nh),
                                         by = out_equal(rr[0], rr[f], 1, nh);
                            const bool same = !bw && !bo && !by && rg[0] == rg[f] && rc[0] == rc[f] && rx[0] == rx[f];
                            if (!same) {
                                ok = false;
                                std::printf("  %s form %d differs (w %zu out %zu ry %zu ring %d cat %d widx %d)\n", tag, f, bw, bo, by,
                                            (int)(rg[0] != rg[f]), (int)(rc[0] != rc[f]), (int)(rx[0] != rx[f]));
                            }
                        }
                    }
                    if (!timing || p != 1000) continue;
                    double ch[4];
                    for (int f = 0; f < 4; ++f) {
                        std::vector<double> v;
                        for (int r = 0; r < IT + 3; ++r) {
                            if (flush) lsg(1024, flush_k);
                            else if (r % 8 == 0) warm(2);
                            std::vector<sycl::event> ev;
                            sycl::event e0, e1;
                            if (g_nb) e0 = nbk();
                            run_win(f, n, nh, p, b, kv, cidx, widx, ev);
                            if (g_nb) e1 = nbk();
                            q.wait();
                            if (r >= 3) v.push_back(g_nb ? span_us(e0, e1) : span_us(ev.front(), ev.back()));
                        }
                        std::sort(v.begin(), v.end());
                        ch[f] = v[v.size() / 2];
                    }
                    std::printf("%-16s %6.2f %6.2f %6.2f %6.2f\n", tag, ch[0], ch[1], ch[2], ch[3]);
                    std::fflush(stdout);
                }
        if (ferr()) ok = false;
        std::printf(ok ? "PASS\n" : "FAIL\n");
        return ok ? 0 : 1;
    }
    // attn wa-1 (see run_wa): token t's compressed list as the engine's (640 slots: 512 distinct rows, 1/8 skipped in
    // the peaky kind; 160 .. 608: CidxFill's rows 0 .. len_t - 1 with len_t within 31 of n - 128, so the trimmed
    // slot count is n; 128: none)
    auto wa_lists = [&](int n, unsigned M, int skip8, std::vector<int32_t> &hc) {
        hc.assign((size_t)MMAX * 512, -1);
        for (unsigned t = 0; t < M; ++t) {
            int32_t *c = hc.data() + (size_t)t * 512;
            if (n == 640) {
                std::vector<int> pc(CROWS);
                for (int i = 0; i < CROWS; ++i) pc[i] = i;
                std::shuffle(pc.begin(), pc.end(), rng);
                for (int i = 0; i < 512; ++i) c[i] = (skip8 && i % 8 == 5) ? -1 : 128 + pc[i];
            } else if (n > 128) {
                const int len = n - 128 - (int)(rng() % 32);
                for (int i = 0; i < 512; ++i) c[i] = i < len ? 128 + i : -1;
            }
        }
    };
    if (std::getenv("WA") || std::getenv("WA_STEPS")) {
        if (!std::getenv("MS")) ms = {2u, 3u, 4u, 5u, 6u, 8u};
        float *kv = sycl::malloc_device<float>((size_t)MMAX * HD, q);
        int32_t *cidx = sycl::malloc_device<int32_t>((size_t)MMAX * 512, q);
        const size_t nrg = (size_t)WA_W * HD;
        bool ok = true;
        auto kv_fill = [&](float *d, size_t n) {
            std::vector<float> hk(n);
            for (auto &x : hk) x = nd(rng);
            q.memcpy(d, hk.data(), n * 4).wait();
        };
        if (const char *se = std::getenv("WA_STEPS")) { // consecutive checks, as the engine runs them (see the top)
            const int N = std::max(1, std::atoi(se));
            const int conc = std::getenv("CONC") ? std::atoi(std::getenv("CONC")) : 0;
            sycl::queue q2{q.get_context(), q.get_device(), sycl::property_list{sycl::property::queue::in_order{}}};
            const size_t ncb = (size_t)32 << 20;
            float *cb0 = conc ? sycl::malloc_device<float>(ncb, q) : nullptr, *cb1 = conc ? sycl::malloc_device<float>(ncb, q) : nullptr;
            if (conc) {
                q.fill(cb0, 1.0f, ncb).wait();
                q.fill(cb1, 2.0f, ncb).wait();
            }
            uint32_t *bad = sycl::malloc_device<uint32_t>(4, q);
            float *wP = sycl::malloc_device<float>(nw, q), *wF = sycl::malloc_device<float>(nw, q);
            float *oP = sycl::malloc_device<float>(nq, q), *yP = sycl::malloc_device<float>(nq, q);
            float *oF = sycl::malloc_device<float>(nq, q), *yF = sycl::malloc_device<float>(nq, q);
            constexpr int NKV = 16; // key-row sets (M tokens each) cycled through the steps, per layer
            float *kvs = sycl::malloc_device<float>((size_t)NKV * 2 * MMAX * HD, q);
            kv_fill(kvs, (size_t)NKV * 2 * MMAX * HD);
            struct Lay { float *q, *sinks; int32_t *ixP, *ixF, *cidx; uint16_t *ringP, *ringF; };
            Lay ly[2];
            for (Lay &l : ly) {
                l.q = sycl::malloc_device<float>(nq, q);
                l.sinks = sycl::malloc_device<float>(QH, q);
                l.ixP = sycl::malloc_device<int32_t>(nix, q);
                l.ixF = sycl::malloc_device<int32_t>(nix, q);
                l.cidx = sycl::malloc_device<int32_t>((size_t)MMAX * 512, q);
                l.ringP = sycl::malloc_device<uint16_t>(nrg, q);
                l.ringF = sycl::malloc_device<uint16_t>(nrg, q);
            }
            auto cmp = [&](const float *a, const float *c, size_t n, uint32_t step) {
                q.parallel_for(sycl::range<1>(n), [=](sycl::item<1> it) {
                    const size_t i = it.get_linear_id();
                    if (sycl::bit_cast<uint32_t>(a[i]) != sycl::bit_cast<uint32_t>(c[i])) {
                        using ARu = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::device,
                                                     sycl::access::address_space::global_space>;
                        ARu(bad[0]).fetch_add(1u);
                        ARu(bad[1]).fetch_min(step);
                    }
                });
            };
            std::printf("WA_STEPS: %d consecutive checks x 2 layers per shape (window append + attention + RingCommitM; the layers "
                        "share each form's score array), production against the engine's OWN_ATT_WA form%s\n", N,
                        conc == 2 ? ", CONC=2" : conc == 1 ? ", CONC=1" : "");
            for (int nh : {16, 12, 8})
                for (int n : {128, 160, 288, 384, 640})
                    for (unsigned M : ms) {
                        char tag[64];
                        std::snprintf(tag, sizeof tag, "ws h%d n%d M%u", nh, n, M);
                        if (only && !std::strstr(tag, only)) continue;
                        const int nc = n > 128 ? 512 : 0, p0 = 100;
                        for (int L = 0; L < 2; ++L) {
                            Lay &l = ly[L];
                            std::vector<float> hq(nq), hs(QH);
                            for (auto &x : hq) x = nd(rng) * (L ? 6.f : 1.f);
                            for (auto &x : hs) x = nd(rng) * 2.f;
                            q.memcpy(l.q, hq.data(), nq * 4).wait();
                            q.memcpy(l.sinks, hs.data(), QH * 4).wait();
                            std::vector<int32_t> hc;
                            wa_lists(n, M, L, hc);
                            q.memcpy(l.cidx, hc.data(), hc.size() * 4).wait();
                            std::vector<uint16_t> rg(nrg);
                            for (auto &x : rg) x = f2bf(nd(rng));
                            q.memcpy(l.ringP, rg.data(), nrg * 2).wait();
                            q.memcpy(l.ringF, rg.data(), nrg * 2).wait();
                            q.fill(l.ixP, (int32_t)-7, nix).wait();
                            q.fill(l.ixF, (int32_t)-7, nix).wait();
                        }
                        q.memcpy(wP, stale.data(), nw * 4).wait();
                        q.memcpy(wF, stale.data(), nw * 4).wait();
                        q.fill(oP, 0.f, nq).wait();
                        q.fill(oF, 0.f, nq).wait();
                        q.fill(yP, 0.f, nq).wait();
                        q.fill(yF, 0.f, nq).wait();
                        const uint32_t init[4] = {0u, 0xffffffffu, 0u, 0u};
                        q.memcpy(bad, init, 16).wait();
                        const size_t no = (size_t)(M - 1) * QS + (size_t)nh * HD;
                        const auto t0 = std::chrono::steady_clock::now();
                        for (int r2 = 0; conc && r2 < 24; ++r2) {
                            if (conc == 1) q2.memcpy(r2 % 2 ? cb0 : cb1, r2 % 2 ? cb1 : cb0, ncb * 4);
                            else
                                q2.parallel_for(sycl::nd_range<1>(64 * 256, 256), [=](sycl::nd_item<1> it) {
                                    for (size_t i = it.get_global_linear_id(); i < ncb; i += 64 * 256) cb1[i] = cb0[i] + 1.0f;
                                });
                        }
                        for (int st = 0; st < N; ++st) {
                            const int p = p0 + st * (int)M;
                            for (int L = 0; L < 2; ++L) {
                                const Lay &l = ly[L];
                                Bufs bp{l.q, l.sinks, wP, nullptr, oP, yP, b.cs, b.sn, l.ringP, b.kvc, l.ixP};
                                Bufs bf{l.q, l.sinks, wF, nullptr, oF, yF, b.cs, b.sn, l.ringF, b.kvc, l.ixF};
                                const float *kvL = kvs + ((size_t)(st % NKV) * 2 + L) * MMAX * HD;
                                std::vector<sycl::event> ev;
                                const RingCommitM rc{128, (int)HD, p, (int)M};
                                run_wa(0, n, M, nh, p, bp, kvL, l.cidx, ev);
                                uint16_t *rP = l.ringP, *rF = l.ringF;
                                q.parallel_for(sycl::nd_range<1>((size_t)M * HD, 64), [=](sycl::nd_item<1> it) { rc(it, rP); });
                                run_wa(5, n, M, nh, p, bf, kvL, l.cidx, ev);
                                q.parallel_for(sycl::nd_range<1>((size_t)M * HD, 64), [=](sycl::nd_item<1> it) { rc(it, rF); });
                                cmp(oP, oF, no, (uint32_t)(2 * st + L));
                                cmp(yP, yF, no, (uint32_t)(2 * st + L));
                            }
                        }
                        q.wait();
                        const double msd = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
                        q2.wait();
                        uint32_t hb[4];
                        q.memcpy(hb, bad, 16).wait();
                        size_t sb = 0;
                        for (const Lay &l : ly) {
                            std::vector<uint16_t> g0(nrg), g1(nrg);
                            std::vector<int32_t> c0(nix), c1(nix);
                            q.memcpy(g0.data(), l.ringP, nrg * 2).wait();
                            q.memcpy(g1.data(), l.ringF, nrg * 2).wait();
                            q.memcpy(c0.data(), l.ixP, nix * 4).wait();
                            q.memcpy(c1.data(), l.ixF, nix * 4).wait();
                            sb += (g0 != g1) + (c0 != c1);
                        }
                        if (hb[0] || sb) ok = false;
                        std::printf("%-16s %s: %u output words differ (first at launch %d)%s  [%.0f ms]\n", tag, hb[0] || sb ? "FAIL" : "ok",
                                    hb[0], hb[0] ? (int)hb[1] : -1, sb ? ", rings / lists differ at the end" : "", msd);
                        std::fflush(stdout);
                    }
            if (ferr()) ok = false;
            std::printf(ok ? "PASS\n" : "FAIL\n");
            return ok ? 0 : 1;
        }
        std::vector<uint16_t> ring0(nrg);
        q.memcpy(ring0.data(), b.kvw, nrg * 2).wait(); // (random rows, the block area too: stale for every form)
        std::printf("blocks with the window append, bitwise against WindowAppendM + production: forms 1 (WindowAppendM + the "
                    "engine's form), 2 F WA, 3 T8 WA + JE, 4 T16 WA + JE. Time (p1000, median of %d%s%s): WindowAppendM alone, "
                    "the chain WindowAppendM + the engine's form, the engine's form with WA\n", IT, flush ? ", L2 flushed" : "",
                    g_nb ? ", chains between neighbour kernels" : "");
        for (int nh : {16, 12, 8})
            for (unsigned M : ms)
                for (int n : NVALS)
                    for (int p : {1000, 125, 60, 0}) {
                        char tag[64];
                        std::snprintf(tag, sizeof tag, "wa h%d n%d M%u p%d", nh, n, M, p);
                        if (only && !std::strstr(tag, only)) continue;
                        const int nc = n > 128 ? 512 : 0;
                        for (int kind = 0; kind < 2; ++kind) {
                            std::vector<float> hq(nq), hs(QH);
                            for (auto &x : hq) x = nd(rng) * (kind ? 6.f : 1.f);
                            for (auto &x : hs) x = nd(rng) * 2.f;
                            q.memcpy(b.q, hq.data(), nq * 4).wait();
                            q.memcpy(b.sinks, hs.data(), QH * 4).wait();
                            kv_fill(kv, (size_t)MMAX * HD);
                            std::vector<int32_t> hc;
                            wa_lists(n, M, kind, hc);
                            q.memcpy(cidx, hc.data(), hc.size() * 4).wait();
                            if (!check) break;
                            const size_t mw = (size_t)M * WS, mq = (size_t)M * QS, mx = (size_t)M * 640; // (M tokens' parts)
                            auto reset = [&]() {
                                q.memcpy(b.kvw, ring0.data(), nrg * 2);
                                q.memcpy(b.w, stale.data(), mw * 4);
                                q.memcpy(b.w2, stale.data(), mw * 4);
                                q.fill(b.ix, (int32_t)-7, mx);
                                q.fill(b.out, std::nanf(""), mq);
                                q.fill(b.ry, std::nanf(""), mq).wait();
                            };
                            std::vector<float> rs(nw), rw(nw), ro(nq), rr(nq), cs(nw), cw(nw), co(nq), cr(nq);
                            std::vector<uint16_t> rg0(nrg), rg(nrg);
                            std::vector<int32_t> rc0(nix), rc(nix);
                            std::vector<sycl::event> ev;
                            reset(); // production's raw scores (WindowAppendM, then the score launch alone)
                            ev.push_back(wam(M, p, nc, b.kvw, kv, b.ix, nc ? cidx : nullptr));
                            score_prod(n, M, nh, WA_W, b, ev);
                            q.wait();
                            q.memcpy(rs.data(), b.w, mw * 4).wait();
                            reset();
                            ev.clear();
                            run_wa(0, n, M, nh, p, b, kv, cidx, ev);
                            q.memcpy(rw.data(), b.w, mw * 4);
                            q.memcpy(ro.data(), b.out, mq * 4);
                            q.memcpy(rr.data(), b.ry, mq * 4);
                            q.memcpy(rg0.data(), b.kvw, nrg * 2);
                            q.memcpy(rc0.data(), b.ix, mx * 4).wait();
                            for (int f = 1; f <= 4; ++f) {
                                reset();
                                ev.clear();
                                run_wa(f, n, M, nh, p, b, kv, cidx, ev);
                                q.memcpy(cs.data(), b.w, mw * 4);
                                q.memcpy(cw.data(), b.w2, mw * 4);
                                q.memcpy(co.data(), b.out, mq * 4);
                                q.memcpy(cr.data(), b.ry, mq * 4);
                                q.memcpy(rg.data(), b.kvw, nrg * 2);
                                q.memcpy(rc.data(), b.ix, mx * 4).wait();
                                const size_t bs = kept_equal(rs, cs, rc0, M, nh, n), bw = kept_equal(rw, cw, rc0, M, nh, n),
                                             bo = out_equal(ro, co, M, nh), by = out_equal(rr, cr, M, nh);
                                const bool brg = rg != rg0, bcat = rc != rc0;
                                if (bs || bw || bo || by || brg || bcat) {
                                    ok = false;
                                    std::printf("  %s %s form %d: scores %zu weights %zu out heads %zu ry heads %zu differ%s%s\n", tag,
                                                kind ? "peaky" : "normal", f, bs, bw, bo, by, brg ? ", ring differs" : "",
                                                bcat ? ", lists differ" : "");
                                }
                            }
                        }
                        if (!timing || p != 1000) continue;
                        // (after the cache flush, the block's key rows and queries read once, as the engine's rope
                        // launches leave them in L2 just before; the rows, compressed rows and cidx stay cold.
                        // WA_COLD=1: kv and q cold too)
                        const bool cold = std::getenv("WA_COLD") != nullptr;
                        auto touch = [&](const float *src, size_t cnt) {
                            q.parallel_for(sycl::nd_range<1>(64 * 256, 256), [=](sycl::nd_item<1> it) {
                                float s = 0;
                                for (size_t i = it.get_global_linear_id(); i < cnt; i += 64 * 256) s += src[i];
                                if (s == 12345.f) fo[0] = s;
                            });
                        };
                        double med[3];
                        for (int k = 0; k < 3; ++k) { // WindowAppendM alone, form 1's chain, form 5's chain
                            std::vector<double> v;
                            for (int r = 0; r < IT + 3; ++r) {
                                if (flush) {
                                    lsg(1024, flush_k);
                                    if (!cold) {
                                        touch(kv, (size_t)M * HD);
                                        touch(b.q, (size_t)M * QS);
                                    }
                                } else if (r % 8 == 0) warm(2);
                                std::vector<sycl::event> ev;
                                sycl::event e0, e1;
                                if (g_nb) e0 = nbk();
                                if (k == 0) ev.push_back(wam(M, p, nc, b.kvw, kv, b.ix, nc ? cidx : nullptr));
                                else run_wa(k == 1 ? 1 : 5, n, M, nh, p, b, kv, cidx, ev);
                                if (g_nb) e1 = nbk();
                                q.wait();
                                if (r >= 3) v.push_back(k == 0 ? evus(ev[0]) : g_nb ? span_us(e0, e1) : span_us(ev.front(), ev.back()));
                            }
                            std::sort(v.begin(), v.end());
                            med[k] = v[v.size() / 2];
                        }
                        std::printf("%-22s %-2s wam %5.2f | chain %6.2f -> %6.2f (%+.2f)\n", tag, wa_f_on(n, M) ? "F" : "T", med[0], med[1],
                                    med[2], med[2] - med[1]);
                        std::fflush(stdout);
                    }
        if (ferr()) ok = false;
        std::printf(ok ? "PASS\n" : "FAIL\n");
        return ok ? 0 : 1;
    }
    auto fill_lists = [&](const Shape &sh, const Kind &kd, int W, std::vector<int32_t> &hix) {
        hix.assign(nix, -1);
        for (unsigned t = 0; t < sh.M; ++t) {
            int32_t *L = hix.data() + (size_t)t * 640;
            std::vector<int> perm(W);
            for (int i = 0; i < W; ++i) perm[i] = i;
            std::shuffle(perm.begin(), perm.end(), rng);
            for (int i = 0; i < 128; ++i) L[i] = i < kd.early ? -1 : perm[i];
            const int nc = sh.n - 128;
            if (sh.n == 640) { // 512 chosen rows (distinct), some skipped
                std::vector<int> pc(CROWS);
                for (int i = 0; i < CROWS; ++i) pc[i] = i;
                std::shuffle(pc.begin(), pc.end(), rng);
                for (int i = 0; i < nc; ++i) L[128 + i] = (kd.skip8 && i % 8 == 5) ? -1 : W + pc[i];
            } else if (nc > 0) { // a trimmed list: rows 0 .. len - 1, then -1 up to n
                const int len = nc - (int)(rng() % 32);
                for (int i = 0; i < nc; ++i) L[128 + i] = i < len ? W + i : -1;
            }
        }
    };
    if (const char *re = std::getenv("RACE")) { // (see the top)
        const int N = std::max(1, std::atoi(re));
        const bool spoil = std::getenv("SPOIL") != nullptr, rflush = std::getenv("RFLUSH") != nullptr;
        // CONC=1: copy-engine traffic (128 MiB copies) on a second queue while each shape runs; CONC=2: streaming
        // kernels on it (memory traffic beside the launches, as the engine's peer pushes and copies are)
        const int conc = std::getenv("CONC") ? std::atoi(std::getenv("CONC")) : 0;
        sycl::queue q2{q.get_context(), q.get_device(), sycl::property_list{sycl::property::queue::in_order{}}};
        const size_t ncb = (size_t)32 << 20; // floats (128 MiB) per copy buffer
        float *cb0 = conc ? sycl::malloc_device<float>(ncb, q) : nullptr, *cb1 = conc ? sycl::malloc_device<float>(ncb, q) : nullptr;
        if (conc) {
            q.fill(cb0, 1.0f, ncb).wait();
            q.fill(cb1, 2.0f, ncb).wait();
        }
        std::vector<unsigned> rms;
        if (const char *e = std::getenv("RACE_M"))
            for (const char *c = e; *c;) {
                rms.push_back((unsigned)std::atoi(c));
                while (*c && *c != ',') ++c;
                if (*c) ++c;
            }
        const bool win = rms.empty();
        uint32_t *bad = sycl::malloc_device<uint32_t>(4, q);
        float *wF = sycl::malloc_device<float>(nw, q), *wP = sycl::malloc_device<float>(nw, q);
        float *oP = sycl::malloc_device<float>(nq, q), *yP = sycl::malloc_device<float>(nq, q);
        float *oF = sycl::malloc_device<float>(nq, q), *yF = sycl::malloc_device<float>(nq, q);
        constexpr int NKV = 64; // the steps' key rows (kv), per layer
        float *kvs = sycl::malloc_device<float>((size_t)NKV * 2 * HD, q);
        {
            std::vector<float> hk((size_t)NKV * 2 * HD);
            for (auto &x : hk) x = nd(rng);
            q.memcpy(kvs, hk.data(), hk.size() * 4).wait();
        }
        struct Lay {
            float *q, *sinks;
            int32_t *ixP, *ixF, *cidx, *widxP, *widxF;
            uint16_t *ringP, *ringF;
        };
        Lay ly[2];
        for (Lay &l : ly) {
            l.q = sycl::malloc_device<float>(nq, q);
            l.sinks = sycl::malloc_device<float>(QH, q);
            l.ixP = sycl::malloc_device<int32_t>(nix, q);
            l.ixF = sycl::malloc_device<int32_t>(nix, q);
            l.cidx = sycl::malloc_device<int32_t>(512, q);
            l.widxP = sycl::malloc_device<int32_t>(128, q);
            l.widxF = sycl::malloc_device<int32_t>(128, q);
            l.ringP = sycl::malloc_device<uint16_t>((size_t)128 * HD, q);
            l.ringF = sycl::malloc_device<uint16_t>((size_t)128 * HD, q);
        }
        auto cmp = [&](const float *a, const float *c, size_t n, uint32_t step) {
            q.parallel_for(sycl::range<1>(n), [=](sycl::item<1> it) {
                const size_t i = it.get_linear_id();
                if (sycl::bit_cast<uint32_t>(a[i]) != sycl::bit_cast<uint32_t>(c[i])) {
                    using ARu = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::device,
                                                 sycl::access::address_space::global_space>;
                    ARu(bad[0]).fetch_add(1u);
                    ARu(bad[1]).fetch_min(step);
                }
            });
        };
        auto spoil_k = [&](const float *w, size_t nwf, const uint16_t *rg, size_t nrg) { // 128 work-groups: every core
            q.parallel_for(sycl::nd_range<1>(128 * 256, 256), [=](sycl::nd_item<1> it) {
                float s = 0;
                uint32_t u = 0;
                for (size_t i = it.get_local_linear_id(); i < nwf; i += 256) s += w[i];
                for (size_t i = it.get_local_linear_id(); i < nrg; i += 256) u += rg[i];
                if (s == 12345.f && u == 7u) fo[0] = s;
            });
        };
        bool ok = true;
        std::printf("RACE: %d steps x 2 layers per shape, F's score array shared by the layers%s%s; %s\n", N, spoil ? ", SPOIL" : "",
                    rflush ? ", RFLUSH" : "", win ? "one token with the window append (consecutive steps)" : "blocks");
        struct RS { int nh, n, a; };
        std::vector<RS> rs;
        for (int nh : win ? std::vector<int>{16, 8} : std::vector<int>{16, 12, 8})
            for (int n : {128, 160, 288, 640})
                if (win)
                    for (int p0 : {36, 1000}) rs.push_back({nh, n, p0});
                else
                    for (unsigned M : rms) rs.push_back({nh, n, (int)M});
        for (const RS &r : rs) {
            char tag[64];
            if (win) std::snprintf(tag, sizeof tag, "rw h%d n%d p%d", r.nh, r.n, r.a);
            else std::snprintf(tag, sizeof tag, "rb h%d n%d M%d", r.nh, r.n, r.a);
            if (only && !std::strstr(tag, only)) continue;
            const unsigned M = win ? 1u : (unsigned)r.a;
            const int W = win || M == 1 ? 128 : 128 + 256;
            const int nc = win && r.n > 128 ? 512 : 0;
            for (int L = 0; L < 2; ++L) {
                Lay &l = ly[L];
                std::vector<float> hq(nq), hs(QH);
                for (auto &x : hq) x = nd(rng) * (L ? 6.f : 1.f);
                for (auto &x : hs) x = nd(rng) * 2.f;
                q.memcpy(l.q, hq.data(), nq * 4).wait();
                q.memcpy(l.sinks, hs.data(), QH * 4).wait();
                if (win) {
                    std::vector<int32_t> hc(512, -1);
                    if (r.n == 640) {
                        std::vector<int> pc(CROWS);
                        for (int i = 0; i < CROWS; ++i) pc[i] = i;
                        std::shuffle(pc.begin(), pc.end(), rng);
                        for (int i = 0; i < 512; ++i) hc[i] = (i % 8 == 5) ? -1 : 128 + pc[i];
                    } else if (r.n > 128) {
                        const int len = r.n - 128 - (int)(rng() % 32);
                        for (int i = 0; i < 512; ++i) hc[i] = i < len ? 128 + i : -1;
                    }
                    q.memcpy(l.cidx, hc.data(), 512 * 4).wait();
                    std::vector<uint16_t> rg((size_t)128 * HD);
                    for (auto &x : rg) x = f2bf(nd(rng));
                    q.memcpy(l.ringP, rg.data(), rg.size() * 2).wait();
                    q.memcpy(l.ringF, rg.data(), rg.size() * 2).wait();
                    q.fill(l.ixP, (int32_t)-7, nix).wait();
                    q.fill(l.ixF, (int32_t)-7, nix).wait();
                    q.fill(l.widxP, (int32_t)-7, 128).wait();
                    q.fill(l.widxF, (int32_t)-7, 128).wait();
                } else {
                    std::vector<int32_t> hix;
                    fill_lists({r.n, M, r.nh}, kinds[L], W, hix);
                    q.memcpy(l.ixP, hix.data(), nix * 4).wait();
                    q.memcpy(l.ixF, hix.data(), nix * 4).wait();
                }
            }
            q.memcpy(wP, stale.data(), nw * 4).wait();
            q.memcpy(wF, stale.data(), nw * 4).wait();
            q.fill(oP, 0.f, nq).wait();
            q.fill(oF, 0.f, nq).wait();
            q.fill(yP, 0.f, nq).wait();
            q.fill(yF, 0.f, nq).wait();
            const uint32_t init[4] = {0u, 0xffffffffu, 0u, 0u};
            q.memcpy(bad, init, 16).wait();
            const size_t no = (size_t)(M - 1) * QS + (size_t)r.nh * HD; // the outputs written (token stride QS)
            const auto t0 = std::chrono::steady_clock::now();
            for (int r2 = 0; conc && r2 < 24; ++r2) {
                if (conc == 1) q2.memcpy(r2 % 2 ? cb0 : cb1, r2 % 2 ? cb1 : cb0, ncb * 4);
                else
                    q2.parallel_for(sycl::nd_range<1>(64 * 256, 256), [=](sycl::nd_item<1> it) {
                        for (size_t i = it.get_global_linear_id(); i < ncb; i += 64 * 256) cb1[i] = cb0[i] + 1.0f;
                    });
            }
            for (int s = 0; s < N; ++s) {
                if (rflush) lsg(1024, flush_k);
                for (int L = 0; L < 2; ++L) {
                    const Lay &l = ly[L];
                    Bufs bp{l.q, l.sinks, wP, nullptr, oP, yP, b.cs, b.sn, win ? l.ringP : b.kvw, b.kvc, l.ixP};
                    Bufs bf{l.q, l.sinks, wF, nullptr, oF, yF, b.cs, b.sn, win ? l.ringF : b.kvw, b.kvc, l.ixF};
                    std::vector<sycl::event> ev;
                    const float *kv = kvs + ((size_t)(s % NKV) * 2 + L) * HD;
                    if (win) run_win(0, r.n, r.nh, r.a + s, bp, kv, l.cidx, l.widxP, ev);
                    else run_form(0, r.n, M, r.nh, W, bp, ev);
                    if (spoil) spoil_k(wF, (size_t)(M - 1) * WS + (size_t)r.nh * r.n, bf.kvw, (size_t)W * HD);
                    if (win) run_win(3, r.n, r.nh, r.a + s, bf, kv, l.cidx, l.widxF, ev);
                    else run_form(3, r.n, M, r.nh, W, bf, ev);
                    cmp(oP, oF, no, (uint32_t)(2 * s + L));
                    cmp(yP, yF, no, (uint32_t)(2 * s + L));
                }
            }
            q.wait();
            const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
            q2.wait();
            uint32_t hb[4];
            q.memcpy(hb, bad, 16).wait();
            size_t sb = 0;
            if (win) // the rings, widx and lists at the end
                for (const Lay &l : ly) {
                    std::vector<uint16_t> g0((size_t)128 * HD), g1((size_t)128 * HD);
                    std::vector<int32_t> c0(640), c1(640), x0(128), x1(128);
                    q.memcpy(g0.data(), l.ringP, g0.size() * 2).wait();
                    q.memcpy(g1.data(), l.ringF, g1.size() * 2).wait();
                    q.memcpy(c0.data(), l.ixP, 640 * 4).wait();
                    q.memcpy(c1.data(), l.ixF, 640 * 4).wait();
                    q.memcpy(x0.data(), l.widxP, 128 * 4).wait();
                    q.memcpy(x1.data(), l.widxF, 128 * 4).wait();
                    sb += (g0 != g1) + (c0 != c1) + (x0 != x1);
                }
            if (hb[0] || sb) ok = false;
            std::printf("%-18s %s: %u output words differ (first at launch %d)%s  [%.0f ms]\n", tag, hb[0] || sb ? "FAIL" : "ok", hb[0],
                        hb[0] ? (int)hb[1] : -1, sb ? ", rings / lists differ at the end" : "", ms);
            std::fflush(stdout);
        }
        if (ferr()) ok = false;
        std::printf(ok ? "PASS\n" : "FAIL\n");
        return ok ? 0 : 1;
    }
    if (std::getenv("OUT")) { // the output alone (weights from production's score + softmax): JC against JE<false>
        bool ok = true;
        std::printf("output only, us per launch (median of %d%s): JC, JE\n", IT, flush ? ", L2 flushed" : "");
        for (const Shape &sh : shapes) {
            char tag[64];
            std::snprintf(tag, sizeof tag, "h%d n%d M%u", sh.nh, sh.n, sh.M);
            if (only && !std::strstr(tag, only)) continue;
            const int W = sh.M == 1 ? 128 : 128 + 256;
            for (int kind = 0; kind < 2; ++kind) {
                std::vector<float> hq(nq), hs(QH);
                for (auto &x : hq) x = nd(rng) * (kind ? 6.f : 1.f);
                for (auto &x : hs) x = nd(rng) * 2.f;
                std::vector<int32_t> hix;
                fill_lists(sh, kinds[kind], W, hix);
                q.memcpy(b.q, hq.data(), nq * 4).wait();
                q.memcpy(b.sinks, hs.data(), QH * 4).wait();
                q.memcpy(b.ix, hix.data(), nix * 4).wait();
                q.memcpy(b.w, stale.data(), nw * 4).wait();
                std::vector<sycl::event> ev;
                run_form(0, sh.n, sh.M, sh.nh, W, b, ev);
                q.wait();
                std::vector<float> r0(nq), r1(nq), y0(nq), y1(nq);
                double med[2];
                for (int f = 0; f < 2; ++f) {
                    q.fill(b.out, std::nanf(""), nq).wait();
                    q.fill(b.ry, std::nanf(""), nq).wait();
                    (f ? out_je<false>(sh.M, sh.n, sh.nh, W, b) : out_jc(sh.M, sh.n, sh.nh, W, b)).wait();
                    q.memcpy(f ? r1.data() : r0.data(), b.out, nq * 4).wait();
                    q.memcpy(f ? y1.data() : y0.data(), b.ry, nq * 4).wait();
                    if (f && (out_equal(r0, r1, sh.M, sh.nh) || out_equal(y0, y1, sh.M, sh.nh))) {
                        ok = false;
                        std::printf("  %s kind %d JE differs\n", tag, kind);
                    }
                    if (kind == 0 && timing) {
                        std::vector<double> v;
                        for (int r = 0; r < IT + 3; ++r) {
                            if (flush) {
                                lsg(1024, flush_k);
                                std::vector<sycl::event> e2;
                                score_prod(sh.n, sh.M, sh.nh, W, b, e2); // the rows warm as after the score (the engine's state)
                                softmax_any(sh.n, sh.M, sh.nh, b.sinks, b.ix, b.w, e2);
                            } else if (r % 8 == 0) warm(2);
                            sycl::event e = f ? out_je<false>(sh.M, sh.n, sh.nh, W, b) : out_jc(sh.M, sh.n, sh.nh, W, b);
                            q.wait();
                            if (r >= 3) v.push_back(evus(e));
                        }
                        std::sort(v.begin(), v.end());
                        med[f] = v[v.size() / 2];
                    }
                }
                if (kind == 0 && timing) {
                    std::printf("%-22s %6.2f %6.2f\n", tag, med[0], med[1]);
                    std::fflush(stdout);
                }
            }
        }
        std::printf(ok ? "PASS\n" : "FAIL\n");
        return ok ? 0 : 1;
    }
    bool all_ok = true;
    std::printf("us: production score + softmax + output launches and chain (first start -> last end); T8 / T16 + JE: "
                "score + output launches and chain; F: one launch (median of %d%s%s)\n", IT, flush ? ", L2 flushed" : "",
                g_nb ? ", chains between neighbour kernels" : "");
    for (const Shape &sh : shapes) {
        char tag[64];
        std::snprintf(tag, sizeof tag, "h%d n%d M%u", sh.nh, sh.n, sh.M);
        if (only && !std::strstr(tag, only)) continue;
        const int W = sh.M == 1 ? 128 : 128 + 256;
        for (const Kind &kd : kinds) {
            std::vector<float> hq(nq), hs(QH);
            for (auto &x : hq) x = nd(rng) * kd.qscale;
            for (auto &x : hs) x = nd(rng) * 2.f;
            std::vector<int32_t> hix;
            fill_lists(sh, kd, W, hix);
            q.memcpy(b.q, hq.data(), nq * 4).wait();
            q.memcpy(b.sinks, hs.data(), QH * 4).wait();
            q.memcpy(b.ix, hix.data(), nix * 4).wait();
            if (!check) continue;
            auto clear = [&]() {
                q.memcpy(b.w, stale.data(), nw * 4).wait();
                q.memcpy(b.w2, stale.data(), nw * 4).wait();
                q.fill(b.out, std::nanf(""), nq).wait();
                q.fill(b.ry, std::nanf(""), nq).wait();
            };
            std::vector<float> rs(nw), rw(nw), ro(nq), rr(nq), cs(nw), cw(nw), co(nq), cr(nq);
            std::vector<sycl::event> ev;
            clear(); // production's raw scores (the score launch alone)
            score_prod(sh.n, sh.M, sh.nh, W, b, ev);
            q.wait();
            q.memcpy(rs.data(), b.w, nw * 4).wait();
            clear();
            ev.clear();
            run_form(0, sh.n, sh.M, sh.nh, W, b, ev);
            q.wait();
            q.memcpy(rw.data(), b.w, nw * 4).wait();
            q.memcpy(ro.data(), b.out, nq * 4).wait();
            q.memcpy(rr.data(), b.ry, nq * 4).wait();
            for (int form = 1; form < NF; ++form) {
                clear();
                ev.clear();
                run_form(form, sh.n, sh.M, sh.nh, W, b, ev);
                q.wait();
                q.memcpy(cs.data(), b.w, nw * 4).wait();
                q.memcpy(cw.data(), b.w2, nw * 4).wait();
                q.memcpy(co.data(), b.out, nq * 4).wait();
                q.memcpy(cr.data(), b.ry, nq * 4).wait();
                const size_t bs = kept_equal(rs, cs, hix, sh.M, sh.nh, sh.n), bw = kept_equal(rw, cw, hix, sh.M, sh.nh, sh.n),
                             bo = out_equal(ro, co, sh.M, sh.nh), by = out_equal(rr, cr, sh.M, sh.nh);
                if (bs || bw || bo || by) {
                    all_ok = false;
                    std::printf("  %s %s form %s: scores %zu weights %zu out heads %zu ry heads %zu differ\n", tag, kd.name, fname[form], bs,
                                bw, bo, by);
                }
            }
        }
        if (timing) {
            double med[NF][3] = {}, chain[NF] = {};
            for (int form = 0; form < NF; ++form) {
                std::vector<std::vector<double>> per(3);
                std::vector<double> ch;
                for (int r = 0; r < IT + 3; ++r) {
                    if (flush) lsg(1024, flush_k);
                    else if (r % 8 == 0) warm(2);
                    std::vector<sycl::event> ev;
                    sycl::event e0, e1;
                    if (g_nb) e0 = nbk();
                    run_form(form, sh.n, sh.M, sh.nh, W, b, ev);
                    if (g_nb) e1 = nbk();
                    q.wait();
                    if (r < 3) continue;
                    for (size_t k = 0; k < ev.size(); ++k) per[k].push_back(evus(ev[k]));
                    ch.push_back(g_nb ? span_us(e0, e1) : span_us(ev.front(), ev.back()));
                }
                for (int k = 0; k < 3; ++k)
                    if (!per[k].empty()) {
                        std::sort(per[k].begin(), per[k].end());
                        med[form][k] = per[k][per[k].size() / 2];
                    }
                std::sort(ch.begin(), ch.end());
                chain[form] = ch[ch.size() / 2];
            }
            std::printf("%-14s prod %5.2f+%5.2f+%5.2f chain %6.2f | T8 %5.2f+%5.2f chain %6.2f | T16 %5.2f+%5.2f chain %6.2f | F %6.2f\n",
                        tag, med[0][0], med[0][1], med[0][2], chain[0], med[1][0], med[1][1], chain[1], med[2][0], med[2][1], chain[2],
                        chain[3]);
            std::fflush(stdout);
        }
    }
    if (ferr()) all_ok = false;
    std::printf(all_ok ? "PASS\n" : "FAIL\n");
    return all_ok ? 0 : 1;
}
