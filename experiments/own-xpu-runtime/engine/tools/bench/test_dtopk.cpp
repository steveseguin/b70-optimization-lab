// Build + run (from experiments/own-xpu-runtime/engine): icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/test_dtopk.cpp -o test_dtopk && ONEAPI_DEVICE_SELECTOR=level_zero:1 ./test_dtopk
//
// dtopk-1 (2026-11-16; /home/steve/dsv41-work/dtopk/README.md; sycl_v41.hpp "dtopk-1"): the one-token index selects of
// idxsplit-2's split layers by candidates, on one card, bit for bit against the selects the engine runs today.
// The six cards' score shares are cut as Backend41::ixd_bounds cuts them (T = the rows rounded up to 32, shares of
// ceil(T / 6) rounded up to 32 rows, in card order) and the candidate area is laid out as Backend41::dtk_geo lays it out
// (card d's chunk at d u: row values | row indices | block values | block indices). Per card, stage 1 runs over its
// share (TopKSelD1<16>; the layer-20 form also TopKSelDB1<8>, which zeroes the whole mask) into its own chunk. On one
// card the six chunks already sit where the engine's XchgPull puts them on every card (the pull copies bytes, same
// offsets), so stage 3 (TopKSelDQ / TopKSelDQB) runs over the area as every card does after the pull.
// Forms (each against the engine's select over the same rows; that reference itself against the host's partial_sort):
//   rows      plain top 512 (+128). Today: TopKSelQ<16..96> by qsel_span(n) from 4,096 rows, TopKSelR past 98,304 and
//             below 4,096 rows (dev_sel_rows with OWN_TOPK_Q / OWN_TOPK_R on, OWN_TOPK_M off: the defaults)
//   masked    the same with the layer-20 marks (the reference block select's) as the mask, cand_n = n
//   part      the same with cand_n = 3n/4 rounded down to 8 (rows past cand_n unmasked)
//   layer 20  the block select (blocks of 8, top 2048, the newest +inf; today TopKSelBQ<16/32> past 2,048 blocks or
//             TopKSelP<true>, as dev_sel_blocks) -> block list + marks, and the rows' select, both from one candidate
//             area (the geometry with blocks). The engine runs this form only past 2,048 blocks; it is checked at every
//             length here (below that every block is kept: stage 3's "all" branch).
// Score families: normal; few values (ties); all +0 / -0; ties at the threshold (a third of the rows equal, 300 above,
// the rest below); +0 / -0 at the threshold (~100 ones, ~50 minus ones, the rest +0 / -0); mostly -inf (300 + n / 1000
// finite rows: below 512 up to 211,000 rows, ties at -inf; blocks at -inf unflagged); NaNs of both signs mixed in (incl. 0xFFFFFFFF, key 0, and signalling NaNs).
// Rows [n, T + 192) hold +inf: no select may read past row n (the engine's score kernel writes -inf there; +inf
// would be taken if read). Outputs start as garbage (lists -5,
// marks 7, the candidate area 0x7f bytes) and must end equal to the reference, with nothing written past the list's
// 512 entries, the block list's 1 + count or the marks' n rows.
// Lengths: 300, 513, 600 (edges: k >= n; short and empty last shares) and 8,192, 50,000, 97,000, 194,000, 352,000,
// 705,000 rows. Times (normal scores, median of 5): today's rows / block select (one work-group over all rows; the score
// gather before them is not in this bench), dtopk's slowest card's stage 1 (rows; blocks) and the merges. The pull of
// the candidates (the engine's XchgPull) is not timed here. Env: ONLY=n (one length), NOTIME=1.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

constexpr int NC = 6;                // cards (OWN_TP=6)
constexpr int KR_ = 512, KB_ = 2048; // rows kept, blocks kept
constexpr int BS = 8;                // rows per block
using KP = TopKSelP<false>;
using KB = TopKSelP<true>;
using D1 = TopKSelD1<16>;  // Backend41::DtkR1
using DB1 = TopKSelDB1<8>; // Backend41::DtkB1
constexpr size_t SLM = (size_t)KP::NSG * 256 + 8;

// Backend41::ixd_bounds + Backend41::dtk_geo with tp = 6
struct Geo {
    unsigned b0[NC], b1[NC], per = 0;
    int gr = 0, gb = 0;
    unsigned nr = 0, nb = 0, u = 0;
};
static Geo geo(unsigned T, bool blocks) {
    Geo q{};
    const unsigned per = ((T + (unsigned)NC - 1) / (unsigned)NC + 31u) / 32u * 32u;
    for (int d = 0; d < NC; ++d) {
        q.b0[d] = std::min(T, (unsigned)d * per);
        q.b1[d] = std::min(T, (unsigned)(d + 1) * per);
        q.per = std::max(q.per, q.b1[d] - q.b0[d]);
    }
    q.gr = std::max(1, (int)((q.per + D1::R - 1) / D1::R));
    q.nr = (unsigned)q.gr * KR_;
    if (blocks) {
        const unsigned pb = (q.per + 7) / 8;
        q.gb = std::max(1, (int)((pb + DB1::R - 1) / DB1::R));
        q.nb = (unsigned)q.gb * KB_;
    }
    q.u = 2 * q.nr + 2 * q.nb;
    return q;
}

// TopKSelP's order key on the host
static uint32_t hkey(float f) {
    uint32_t u;
    std::memcpy(&u, &f, 4);
    if (u == 0x80000000u) u = 0u;
    return (u & 0x80000000u) ? ~u : (u | 0x80000000u);
}
// TopKSelP<false>'s list on the host: keys (rows j < cand_n with mask[j] == 0: -inf), the k largest keys with the lower
// row first among equal keys, in ascending row order + 128, then -1 up to 512
static std::vector<int32_t> host_rows(const std::vector<float> &hs, int n, const std::vector<uint8_t> *mask, int cand_n) {
    const uint32_t KNEG = hkey(-INFINITY);
    std::vector<uint32_t> key(n);
    for (int j = 0; j < n; ++j) key[j] = (mask && j < cand_n && !(*mask)[j]) ? KNEG : hkey(hs[j]);
    std::vector<int32_t> ord(n);
    for (int j = 0; j < n; ++j) ord[j] = j;
    const int tk = std::min(KR_, n);
    std::partial_sort(ord.begin(), ord.begin() + tk, ord.end(),
                      [&](int32_t a, int32_t b) { return key[a] > key[b] || (key[a] == key[b] && a < b); });
    std::sort(ord.begin(), ord.begin() + tk);
    std::vector<int32_t> out(KR_, -1);
    for (int i = 0; i < tk; ++i) out[i] = ord[i] + 128;
    return out;
}
// TopKSelP<true> on the host: block keys (each block's largest score over its rows below n, folded in row order; the
// newest +inf), the top 2048 as above; marks: the rows of the kept blocks whose key is above -inf; the list: their
// count, then those blocks ascending
static void host_blocks(const std::vector<float> &hs, int n, std::vector<int32_t> &bl, std::vector<uint8_t> &mk) {
    const int nb = (n + BS - 1) / BS;
    const uint32_t KNEG = hkey(-INFINITY);
    std::vector<uint32_t> key(nb);
    for (int j = 0; j < nb; ++j) {
        float m = -INFINITY;
        if (j == nb - 1) m = INFINITY;
        else
            for (int r = j * BS; r < std::min(j * BS + BS, n); ++r) {
                const float v = hs[r];
                m = m < v ? v : m;
            }
        key[j] = hkey(m);
    }
    std::vector<int32_t> ord(nb);
    for (int j = 0; j < nb; ++j) ord[j] = j;
    const int tk = std::min(KB_, nb);
    std::partial_sort(ord.begin(), ord.begin() + tk, ord.end(),
                      [&](int32_t a, int32_t b) { return key[a] > key[b] || (key[a] == key[b] && a < b); });
    std::sort(ord.begin(), ord.begin() + tk);
    mk.assign(n, 0);
    bl.assign(1, 0);
    for (int i = 0; i < tk; ++i) {
        const int j = ord[i];
        if (key[j] <= KNEG) continue;
        bl.push_back(j);
        for (int r = j * BS; r < std::min(j * BS + BS, n); ++r) mk[r] = 1;
    }
    bl[0] = (int32_t)bl.size() - 1;
}

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    const bool timing = !std::getenv("NOTIME");
    const long only = std::getenv("ONLY") ? std::atol(std::getenv("ONLY")) : 0;
    const int MAXN = 705000;
    const size_t SROWS = (size_t)MAXN + 64 + 192; // scores (+ the +inf rows past n), marks
    const size_t LN = (size_t)KB_ + 64;           // lists / block lists (+ the untouched tail checked)
    float *sc = sycl::malloc_device<float>(SROWS, q);
    uint8_t *mref = sycl::malloc_device<uint8_t>(SROWS, q), *mout = sycl::malloc_device<uint8_t>(SROWS, q);
    int32_t *lref[3], *lout[4], *blref = sycl::malloc_device<int32_t>(LN, q), *blout = sycl::malloc_device<int32_t>(LN, q);
    for (auto &p : lref) p = sycl::malloc_device<int32_t>(LN, q);
    for (auto &p : lout) p = sycl::malloc_device<int32_t>(LN, q);
    const Geo gmax = geo((unsigned)((MAXN + 31) / 32 * 32), true);
    const size_t AREA = (size_t)NC * gmax.u + 64;
    float *area = sycl::malloc_device<float>(AREA, q);
    if (!sc || !mref || !mout || !blref || !blout || !area) {
        std::printf("allocation failed\n");
        return 2;
    }
    auto local_g = [&](size_t G, auto k, auto... a) {
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(SLM, h);
            h.parallel_for(sycl::nd_range<1>(G * 1024, 1024), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                k(it, a..., &lt[0]);
            });
        });
    };
    auto us = [](const sycl::event &e) {
        return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
    };
    // today's selects, as dev_sel_rows / dev_sel_blocks dispatch them (OWN_TOPK_Q, OWN_TOPK_R on; OWN_TOPK_M off)
    auto rows_today = [&](const KP &k, const uint8_t *cand, int32_t *out) -> sycl::event {
        const int c = k.n >= 4096 ? qsel_span(k.n) : 0;
        if (c && c <= 16) return local_g(1, TopKSelQ<16>{k}, (const float *)sc, cand, out, (uint8_t *)nullptr);
        if (c && c <= 32) return local_g(1, TopKSelQ<32>{k}, (const float *)sc, cand, out, (uint8_t *)nullptr);
        if (c && c <= 64) return local_g(1, TopKSelQ<64>{k}, (const float *)sc, cand, out, (uint8_t *)nullptr);
        if (c && c <= 96) return local_g(1, TopKSelQ<96>{k}, (const float *)sc, cand, out, (uint8_t *)nullptr);
        return local_g(1, TopKSelR<false>{k}, (const float *)sc, cand, out, (uint8_t *)nullptr);
    };
    auto blocks_today = [&](const KB &k, int32_t *out, uint8_t *marks) -> sycl::event {
        if (k.n > 2048 && qsel_span(k.n) <= 16)
            return local_g(1, TopKSelBQ<16>{k}, (const float *)sc, (const uint8_t *)nullptr, out, marks);
        if (k.n > 2048 && qsel_span(k.n) <= 32)
            return local_g(1, TopKSelBQ<32>{k}, (const float *)sc, (const uint8_t *)nullptr, out, marks);
        return local_g(1, k, (const float *)sc, (const uint8_t *)nullptr, out, marks);
    };
    // dtopk stage 1 on every card in turn (rows; the cards would run theirs at once: the slowest one's time)
    auto stage1_rows = [&](const Geo &g, int n, const uint8_t *mask, int cand_n) {
        double tmax = 0;
        for (int d = 0; d < NC; ++d) {
            const unsigned r0 = g.b0[d], r1 = g.b1[d];
            const int lp = (int)std::clamp<long>((long)n - (long)r0, 0, (long)(r1 - r0));
            const int cn = mask ? (int)std::clamp<long>((long)cand_n - (long)r0, 0, lp) : 0;
            float *mine = area + (size_t)d * g.u;
            auto e = local_g((size_t)g.gr, D1{{lp, KR_, 0, 0, cn, 0, 0}, (int)r0}, (const float *)(sc + r0),
                             mask ? (const uint8_t *)(mask + r0) : (const uint8_t *)nullptr, mine, mine + g.nr);
            e.wait();
            tmax = std::max(tmax, us(e));
        }
        return tmax;
    };
    // ... blocks (layer 20; every card's launch zeroes the whole mask [0, n), here the same buffer six times)
    auto stage1_blocks = [&](const Geo &g, int n, uint8_t *marks) {
        double tmax = 0;
        const int last = (n + 7) / 8 - 1;
        for (int d = 0; d < NC; ++d) {
            const unsigned r0 = g.b0[d], r1 = g.b1[d];
            const int lp = (int)std::clamp<long>((long)n - (long)r0, 0, (long)(r1 - r0));
            const int nbl = (lp + 7) / 8, bb0 = (int)(r0 / 8);
            const int newest = last >= bb0 && last < bb0 + nbl ? last - bb0 : -1;
            float *mine = area + (size_t)d * g.u;
            auto e = local_g((size_t)g.gb, DB1{{nbl, KB_, 0, 0, 0, BS, lp}, bb0, newest, n}, (const float *)(sc + r0),
                             mine + 2 * g.nr, mine + 2 * g.nr + g.nb, marks);
            e.wait();
            tmax = std::max(tmax, us(e));
        }
        return tmax;
    };
    // dtopk stage 3 (every card after the pull)
    auto merge_rows = [&](const Geo &g, int32_t *out) -> sycl::event {
        const int n = NC * (int)g.nr, c = qsel_span(n);
        const float *cv = area, *ci = area + g.nr;
        if (c <= 16) return local_g(1, TopKSelDQ<16>{n, (int)g.nr, g.u, KR_, 128, KR_}, cv, ci, out);
        if (c <= 32) return local_g(1, TopKSelDQ<32>{n, (int)g.nr, g.u, KR_, 128, KR_}, cv, ci, out);
        if (c <= 64) return local_g(1, TopKSelDQ<64>{n, (int)g.nr, g.u, KR_, 128, KR_}, cv, ci, out);
        if (c <= 96) return local_g(1, TopKSelDQ<96>{n, (int)g.nr, g.u, KR_, 128, KR_}, cv, ci, out);
        std::printf("merge: %d row candidates beyond one work-group\n", n);
        std::exit(2);
    };
    auto merge_blocks = [&](const Geo &g, int rows, int32_t *out, uint8_t *marks) -> sycl::event {
        const int n = NC * (int)g.nb, c = qsel_span(n);
        const float *cv = area + 2 * g.nr, *ci = area + 2 * g.nr + g.nb;
        if (c <= 16) return local_g(1, TopKSelDQB<16>{n, (int)g.nb, g.u, KB_, rows}, cv, ci, out, marks);
        if (c <= 32) return local_g(1, TopKSelDQB<32>{n, (int)g.nb, g.u, KB_, rows}, cv, ci, out, marks);
        if (c <= 64) return local_g(1, TopKSelDQB<64>{n, (int)g.nb, g.u, KB_, rows}, cv, ci, out, marks);
        if (c <= 96) return local_g(1, TopKSelDQB<96>{n, (int)g.nb, g.u, KB_, rows}, cv, ci, out, marks);
        std::printf("merge: %d block candidates beyond one work-group\n", n);
        std::exit(2);
    };
    auto get_i = [&](const int32_t *p, size_t m) {
        std::vector<int32_t> x(m);
        q.memcpy(x.data(), p, m * 4).wait();
        return x;
    };
    auto get_b = [&](const uint8_t *p, size_t m) {
        std::vector<uint8_t> x(m);
        q.memcpy(x.data(), p, m).wait();
        return x;
    };
    // a list: the reference's 512 entries, the 64 after them untouched (-5)
    auto list_ok = [&](const int32_t *dev, const std::vector<int32_t> &ref) {
        const auto x = get_i(dev, (size_t)KR_ + 64);
        for (int i = 0; i < KR_ + 64; ++i)
            if (x[i] != (i < KR_ ? ref[i] : -5)) return false;
        return true;
    };
    // a block list: count + blocks as the reference, everything after them untouched (-5)
    auto blist_ok = [&](const int32_t *dev, const std::vector<int32_t> &ref) {
        const auto x = get_i(dev, LN);
        for (size_t i = 0; i < LN; ++i)
            if (x[i] != (i < ref.size() ? ref[i] : -5)) return false;
        return true;
    };
    // marks: rows [0, n) as the reference, the 64 after them untouched (7)
    auto marks_ok = [&](const uint8_t *dev, const std::vector<uint8_t> &ref, int n) {
        const auto x = get_b(dev, (size_t)n + 64);
        for (int i = 0; i < n + 64; ++i)
            if (x[i] != (i < n ? ref[i] : 7)) return false;
        return true;
    };
    auto med = [](std::vector<double> &v) {
        if (v.empty()) return 0.0;
        std::sort(v.begin(), v.end());
        return v[v.size() / 2];
    };
    std::mt19937 rng(11);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::vector<float> hs(SROWS);
    const char *kinds[7] = {"normal", "few values (ties)", "all +0 / -0", "ties at threshold", "+-0 at threshold",
                            "mostly -inf", "with NaNs"};
    long bad = 0, cases = 0;
    std::printf("%-18s %7s | rows masked part | l20: rows blist marks | host | us: today rows blocks | dtopk s1 rows merge, "
                "s1 blocks merge\n", "scores", "n");
    for (int n : {300, 513, 600, 8192, 50000, 97000, 194000, 352000, 705000}) {
        if (only && n != only) continue;
        const unsigned T = (unsigned)((n + 31) / 32 * 32);
        const Geo gr = geo(T, false), gl = geo(T, true);
        std::printf("n %d: T %u, shares of %u rows (last [%u, %u)); rows: %d groups/card, %u pairs/card, merge over %d "
                    "(span %d); layer 20: + %d block groups/card, %u pairs/card, merge over %d (span %d), chunk %u floats\n",
                    n, T, gr.per, gr.b0[NC - 1], gr.b1[NC - 1], gr.gr, gr.nr, NC * (int)gr.nr, qsel_span(NC * (int)gr.nr),
                    gl.gb, gl.nb, NC * (int)gl.nb, qsel_span(NC * (int)gl.nb), gl.u);
        for (int kind = 0; kind < 7; ++kind) {
            for (int j = 0; j < n; ++j) {
                const float f = nd(rng);
                switch (kind) {
                case 0: hs[j] = f; break;
                case 1: hs[j] = std::floor(f * 1.5f); break;
                case 2: hs[j] = f > 0 ? 0.0f : -0.0f; break;
                case 3: hs[j] = rng() % 3 == 0 ? 1.0f : -1.0f - std::fabs(f); break;
                case 4: hs[j] = f > 0 ? 0.0f : -0.0f; break;
                case 5: hs[j] = -INFINITY; break;
                default: hs[j] = f; break;
                }
            }
            if (kind == 3)
                for (int i = 0; i < 300; ++i) hs[(size_t)(rng() % n)] = 5.0f;
            if (kind == 4) {
                for (int i = 0; i < 100; ++i) hs[(size_t)(rng() % n)] = 1.0f;
                for (int i = 0; i < 50; ++i) hs[(size_t)(rng() % n)] = -1.0f;
            }
            if (kind == 5)
                for (int i = 0; i < 300 + n / 1000; ++i) hs[(size_t)(rng() % n)] = nd(rng);
            if (kind == 6) { // quiet NaNs of both signs, and the edge patterns: 0xFFFFFFFF (order key 0, the key stage 3's
                             // empty slots also get), 0x7FFFFFFF (the largest key), signalling NaNs of both signs
                for (int i = 0; i < 64; ++i) hs[(size_t)(rng() % n)] = (i & 1) ? std::nanf("") : -std::nanf("");
                const uint32_t eb[4] = {0xFFFFFFFFu, 0x7FFFFFFFu, 0xFF800001u, 0x7F800001u};
                for (int i = 0; i < 16; ++i) std::memcpy(&hs[(size_t)(rng() % n)], &eb[i & 3], 4);
            }
            for (size_t j = (size_t)n; j < (size_t)T + 192; ++j) hs[j] = INFINITY; // (never read)
            q.memcpy(sc, hs.data(), ((size_t)T + 192) * 4).wait();
            const int nb = (n + BS - 1) / BS, cpart = (n * 3 / 4) / 8 * 8;
            const KB kb{nb, KB_, 0, 0, 0, BS, n};
            const KP kp{n, KR_, 128, KR_, 0, 0, 0}, km{n, KR_, 128, KR_, n, 0, 0}, kq{n, KR_, 128, KR_, cpart, 0, 0};
            // host references
            std::vector<int32_t> hbl, hp, hm, hq;
            std::vector<uint8_t> hmk;
            host_blocks(hs, n, hbl, hmk);
            hp = host_rows(hs, n, nullptr, 0);
            hm = host_rows(hs, n, &hmk, n);
            hq = host_rows(hs, n, &hmk, cpart);
            const int REP = timing && kind == 0 ? 5 : 1;
            bool ok_ref = true, ok[6] = {true, true, true, true, true, true}; // rows, masked, part, l20 rows, blist, marks
            std::vector<double> t_rows, t_blk, t_s1r, t_mr, t_s1b, t_mb;
            for (int r = 0; r < REP; ++r) {
                // today: the block select first (its marks are the masked selects' mask), then the three row selects
                q.fill(mref, (uint8_t)7, SROWS);
                q.fill(blref, -5, LN);
                for (auto p : lref) q.fill(p, -5, LN);
                q.wait();
                auto eb = blocks_today(kb, blref, mref);
                eb.wait();
                auto er = rows_today(kp, nullptr, lref[0]);
                er.wait();
                rows_today(km, mref, lref[1]).wait();
                rows_today(kq, mref, lref[2]).wait();
                t_blk.push_back(us(eb));
                t_rows.push_back(us(er));
                ok_ref = ok_ref && blist_ok(blref, hbl) && marks_ok(mref, hmk, n) && list_ok(lref[0], hp) &&
                         list_ok(lref[1], hm) && list_ok(lref[2], hq);
                auto rb = get_i(blref, LN); // (the device reference's own count: 1 + rb[0] entries)
                rb.resize((size_t)1 + (size_t)std::clamp(rb[0], 0, KB_));
                const auto rmk = get_b(mref, (size_t)n);
                const auto rp = get_i(lref[0], KR_), rm = get_i(lref[1], KR_), rq = get_i(lref[2], KR_);
                // dtopk, rows (the geometry without blocks): plain, masked, part-masked
                for (int f = 0; f < 3; ++f) {
                    q.memset(area, 0x7f, AREA * 4);
                    q.fill(lout[f], -5, LN).wait();
                    const double s1 = stage1_rows(gr, n, f ? mref : nullptr, f == 2 ? cpart : n);
                    auto e = merge_rows(gr, lout[f]);
                    e.wait();
                    if (f == 0) t_s1r.push_back(s1), t_mr.push_back(us(e));
                    ok[f] = ok[f] && list_ok(lout[f], f == 0 ? rp : f == 1 ? rm : rq);
                }
                // dtopk, layer 20 (the geometry with blocks): rows and blocks into one area, then the two merges
                q.memset(area, 0x7f, AREA * 4);
                q.fill(lout[3], -5, LN);
                q.fill(blout, -5, LN);
                q.fill(mout, (uint8_t)7, SROWS).wait();
                stage1_rows(gl, n, nullptr, 0);
                const double s1b = stage1_blocks(gl, n, mout);
                auto e1 = merge_blocks(gl, n, blout, mout);
                e1.wait();
                merge_rows(gl, lout[3]).wait();
                t_s1b.push_back(s1b);
                t_mb.push_back(us(e1));
                ok[3] = ok[3] && list_ok(lout[3], rp);
                ok[4] = ok[4] && blist_ok(blout, rb);
                ok[5] = ok[5] && marks_ok(mout, rmk, n);
            }
            cases += 7; // (the reference against the host, and six dtopk results against the reference)
            bad += !ok_ref;
            for (bool x : ok) bad += !x;
            auto yn = [](bool x) { return x ? "y" : "NO"; };
            std::printf("%-18s %7d | %-4s %-6s %-4s | %-4s %-5s %-5s | %-4s", kinds[kind], n, yn(ok[0]), yn(ok[1]), yn(ok[2]),
                        yn(ok[3]), yn(ok[4]), yn(ok[5]), yn(ok_ref));
            if (kind == 0 && timing)
                std::printf(" | %8.1f %7.1f | %7.1f %6.1f, %7.1f %6.1f", med(t_rows), med(t_blk), med(t_s1r), med(t_mr),
                            med(t_s1b), med(t_mb));
            std::printf("\n");
            std::fflush(stdout);
        }
    }
    if (bad) std::printf("FAIL (%ld of %ld cases differ)\n", bad, cases);
    else std::printf("PASS (%ld cases)\n", cases);
    return bad ? 1 : 0;
}
