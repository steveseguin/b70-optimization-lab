// Build + run (from experiments/own-xpu-runtime/engine): icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/test_topk_shard.cpp -o test_topk_shard && ONEAPI_DEVICE_SELECTOR=level_zero:1 ./test_topk_shard
//
// kvshard step 0 (2026-11-16; /home/steve/dsv41-work/kvshard/STUDY.md 5.0 and README.md): the index's top-k selects
// over rows split by owner, bit for bit against the whole-array selects, on one card. The rows are owned the way
// kvshard stores them (ops41sycl::kvs_owner / kvs_local: chunks of R rows round robin over 6 owners); each owner's
// rows form a compact local array. Per owner, stage 1 of topk-m (TopKSelM1<16> rows, TopKSelMB1<8> blocks) runs over
// its local array; the candidates are compacted (pads dropped, local positions mapped to global ones: TkCompact) and
// merged by global position (TkMerge: rank = own index + the other owners' candidates below it, by binary search)
// into one ascending array padded with key 0 / position -1; stage 2 (TopKSelQ2 / TopKSelQB2) runs over it unchanged.
// Exact: one total order (order key descending, position ascending), so every member of the global top k is in its
// group's top k on its owner; the merged array is in ascending global position, so the ties taken and the output
// order are TopKSelP's (sycl_v41.hpp "topk-m"). The block select's newest block is +inf on the owner of the global
// newest block only: the other owners run TopKSelMB1 over one dummy block more (their own last block is then not
// +inf; the dummy, +inf, takes one of the group's k slots and is dropped by the compaction: the global top k holds
// the newest block, so at most k - 1 others share a group with the dummy). kvshard-2 replaces the dummy with a
// "newest block" parameter and moves TkCompact / TkMerge into sycl_v41.hpp.
// Arms (each against the whole-array TopKSelP: lists, block lists and marks memcmp'd):
//   1card   the engine's own two launches over the whole array (topk_mr / topk_mb: M1 + Q2, MB1 + QB2): topk-m's
//           first bitwise record
//   R2048   the shard with chunks of 2,048 rows (OWN_KV_SHARD_R default)
//   R16384  ... of 16,384 rows
// Selects: plain (top 512 rows, +128), masked (the same with the reference block select's marks: masked rows count
// as -inf), block (blocks of 8 rows, top 2048, the newest +inf; list + row marks). Score families as test_topk_q
// (normal, few values, +0 / -0, mostly -inf, NaNs mixed in); lengths up to 3,000,000 rows (stage 2's register reach:
// at most 96 x 1,024 candidates). Time (normal scores, median of 5): the reference, the 1-card form, the shard's
// slowest owner's stage 1 + compaction + merge + stage 2. Env: ONLY=n (one length), NOTIME=1.
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

constexpr int NC = 6;                  // owners (cards)
constexpr int KR_ = 512, KB_ = 2048;   // rows kept, blocks kept
constexpr int BS = 8;                  // rows per block

// global row of owner d's local row l (the inverse of kvs_owner / kvs_local)
inline long kvs_global(long l, int d, unsigned R, unsigned N) { return ((l / (long)R) * (long)N + d) * (long)R + l % (long)R; }

// owner d's stage-1 candidates (keys ck, positions ci at soff[d], S[d] slots; each group's pads, key 0 / position -1,
// at the end of its k slots) -> the valid ones (local position < lim[d]) in order at soff[d] of ok / oi, positions
// global (blocks: local block -> global block, R a multiple of 8), their count in cnt[d]. One work-group per owner.
struct TkCompact {
    static constexpr int WG = 1024;
    unsigned R, N;
    int blocks;
    int S[NC], lim[NC];
    size_t soff[NC];
    void operator()(sycl::nd_item<1> it, const uint32_t *ck, const int32_t *ci, uint32_t *ok, int32_t *oi, int32_t *cnt) const {
        auto g = it.get_group();
        const int d = (int)it.get_group_linear_id(), lid = (int)it.get_local_linear_id();
        if (d >= NC) return; // (whole work-group)
        const uint32_t *k = ck + soff[d];
        const int32_t *p = ci + soff[d];
        uint32_t *dk = ok + soff[d];
        int32_t *dp = oi + soff[d];
        int base = 0;
        for (int s0 = 0; s0 < S[d]; s0 += WG) {
            const int s = s0 + lid;
            const int32_t l = s < S[d] ? p[s] : -1;
            const int v = (l >= 0 && l < lim[d]) ? 1 : 0;
            const int x = sycl::exclusive_scan_over_group(g, v, sycl::plus<int>());
            if (v) {
                const long gp = blocks ? kvs_global((long)l * BS, d, R, N) / BS : kvs_global(l, d, R, N);
                dk[base + x] = k[s];
                dp[base + x] = (int32_t)gp;
            }
            base += sycl::reduce_over_group(g, v, sycl::plus<int>());
        }
        if (lid == 0) cnt[d] = base;
    }
};
// every owner's compacted candidates into one array in ascending global position: candidate i of owner d goes to
// rank i + (per other owner: its candidates with a lower position). One item per slot (soff[d] .. soff[d + 1]).
struct TkMerge {
    size_t soff[NC + 1];
    void operator()(sycl::nd_item<1> it, const uint32_t *ok, const int32_t *oi, const int32_t *cnt, uint32_t *mk,
                    int32_t *mi) const {
        const size_t gid = it.get_global_linear_id();
        if (gid >= soff[NC]) return;
        int d = 0;
        while (d + 1 < NC && gid >= soff[d + 1]) ++d;
        const int i = (int)(gid - soff[d]);
        if (i >= cnt[d]) return;
        const int32_t pos = oi[soff[d] + i];
        long rank = i;
        for (int e = 0; e < NC; ++e) {
            if (e == d) continue;
            const int32_t *a = oi + soff[e];
            int lo = 0, hi = cnt[e]; // first index with a[x] >= pos
            while (lo < hi) {
                const int mid = (lo + hi) / 2;
                if (a[mid] < pos) lo = mid + 1;
                else hi = mid;
            }
            rank += lo;
        }
        mk[rank] = ok[soff[d] + i];
        mi[rank] = pos;
    }
};

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    const bool timing = !std::getenv("NOTIME");
    const long only = std::getenv("ONLY") ? std::atol(std::getenv("ONLY")) : 0;
    const int MAXN = 3000000;
    using KP = TopKSelP<false>;
    using KB = TopKSelP<true>;
    using M1 = TopKSelM1<16>;
    using MB1 = TopKSelMB1<8>;
    constexpr size_t SLM = (size_t)KP::NSG * 256 + 8;
    static_assert((size_t)M1::NSG * 256 + 8 == SLM && (size_t)MB1::NSG * 256 + 8 == SLM);
    // one work-group of 1024 (the selects) or G of them (stage 1), SLM floats of local memory last
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
    // stage 2 by its register span (as the engine's topk_mr / topk_mb)
    auto q2 = [&](const KP &k, const uint32_t *ck, const int32_t *ci, int32_t *out) -> sycl::event {
        const int c = qsel_span(k.n);
        if (c <= 16) return local_g(1, TopKSelQ2<16>{k}, ck, ci, out);
        if (c <= 32) return local_g(1, TopKSelQ2<32>{k}, ck, ci, out);
        if (c <= 64) return local_g(1, TopKSelQ2<64>{k}, ck, ci, out);
        if (c <= 96) return local_g(1, TopKSelQ2<96>{k}, ck, ci, out);
        std::printf("stage 2: %d candidates beyond one group\n", k.n);
        std::exit(2);
    };
    auto qb2 = [&](const KB &k, const uint32_t *ck, const int32_t *ci, int32_t *out, uint8_t *marks) -> sycl::event {
        const int c = qsel_span(k.n);
        if (c <= 16) return local_g(1, TopKSelQB2<16>{k}, ck, ci, out, marks);
        if (c <= 32) return local_g(1, TopKSelQB2<32>{k}, ck, ci, out, marks);
        if (c <= 64) return local_g(1, TopKSelQB2<64>{k}, ck, ci, out, marks);
        if (c <= 96) return local_g(1, TopKSelQB2<96>{k}, ck, ci, out, marks);
        std::printf("block stage 2: %d candidates beyond one group\n", k.n);
        std::exit(2);
    };
    // buffers: the whole array, its marks, the lists; per owner the local scores and marks; the candidates
    float *sc = sycl::malloc_device<float>(MAXN + 64, q);
    uint8_t *mref = sycl::malloc_device<uint8_t>(MAXN + 64, q), *mout = sycl::malloc_device<uint8_t>(MAXN + 64, q);
    int32_t *lref = sycl::malloc_device<int32_t>(KB_ + 64, q), *lout = sycl::malloc_device<int32_t>(KB_ + 64, q);
    const size_t LMAX = (size_t)MAXN / NC + 16384 + 64;
    float *lsc[NC];
    uint8_t *lmk[NC], *lbm[NC]; // per owner: the masked select's mask, the block stage 1's zeroed rows
    for (int d = 0; d < NC; ++d) {
        lsc[d] = sycl::malloc_device<float>(LMAX, q);
        lmk[d] = sycl::malloc_device<uint8_t>(LMAX, q);
        lbm[d] = sycl::malloc_device<uint8_t>(LMAX, q);
    }
    const size_t CMAX = (size_t)98304 + (size_t)NC * KB_ + 64; // candidate slots (stage 2's reach + an extra group per owner)
    uint32_t *ck = sycl::malloc_device<uint32_t>(CMAX, q), *ok = sycl::malloc_device<uint32_t>(CMAX, q),
             *mk = sycl::malloc_device<uint32_t>(CMAX, q);
    int32_t *ci = sycl::malloc_device<int32_t>(CMAX, q), *oi = sycl::malloc_device<int32_t>(CMAX, q),
            *mi = sycl::malloc_device<int32_t>(CMAX, q), *cnt = sycl::malloc_device<int32_t>(64, q);
    std::mt19937 rng(7);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::vector<float> hs(MAXN);
    const char *kinds[5] = {"normal", "few values (ties)", "+0 / -0", "mostly -inf", "with NaNs"};
    long bad = 0;
    std::printf("%-18s %8s %-7s | plain  masked block(list marks) | time us: plain  masked  block\n", "scores", "n", "arm");
    for (int kind = 0; kind < 5; ++kind)
        for (int n : {600, 4700, 17000, 69000, 139000, 400000, 1000000, 3000000}) {
            if (only && n != only) continue;
            for (int j = 0; j < n; ++j) {
                const float f = nd(rng);
                hs[j] = kind == 1 ? std::floor(f * 1.5f) : kind == 2 ? (f > 0 ? 0.0f : -0.0f) : kind == 3 ? -INFINITY : f;
            }
            if (kind == 3)
                for (int i = 0; i < 300 + n / 1000; ++i) hs[(size_t)(rng() % n)] = nd(rng);
            if (kind == 4)
                for (int i = 0; i < 64; ++i) hs[(size_t)(rng() % n)] = (i & 1) ? std::nanf("") : -std::nanf("");
            q.memcpy(sc, hs.data(), (size_t)n * 4).wait();
            const int nb = (n + BS - 1) / BS;
            const KB kb{nb, KB_, 0, 0, 0, BS, n};
            const KP kp{n, KR_, 128, KR_, 0, 0, 0}, km{n, KR_, 128, KR_, n, 0, 0};
            const int REP = timing && kind == 0 ? 5 : 1;
            // reference: TopKSelP over the whole array (block select first: its marks are the masked select's mask)
            std::vector<int32_t> rp(KR_), rm(KR_), rb(KB_ + 1);
            std::vector<uint8_t> rmk(n);
            double tref[3] = {};
            {
                std::vector<double> t3[3];
                for (int r = 0; r < REP; ++r) {
                    q.fill(mref, (uint8_t)7, (size_t)n + 64);
                    q.fill(lref, -5, KB_ + 64).wait();
                    auto e2 = local_g(1, kb, (const float *)sc, (const uint8_t *)nullptr, lref, mref);
                    e2.wait();
                    t3[2].push_back(us(e2));
                    q.memcpy(rb.data(), lref, (KB_ + 1) * 4);
                    q.memcpy(rmk.data(), mref, (size_t)n).wait();
                    q.fill(lref, -5, KB_ + 64).wait();
                    auto e0 = local_g(1, kp, (const float *)sc, (const uint8_t *)nullptr, lref, (uint8_t *)nullptr);
                    e0.wait();
                    t3[0].push_back(us(e0));
                    q.memcpy(rp.data(), lref, KR_ * 4).wait();
                    q.fill(lref, -5, KB_ + 64).wait();
                    auto e1 = local_g(1, km, (const float *)sc, (const uint8_t *)mref, lref, (uint8_t *)nullptr);
                    e1.wait();
                    t3[1].push_back(us(e1));
                    q.memcpy(rm.data(), lref, KR_ * 4).wait();
                }
                for (int s = 0; s < 3; ++s) {
                    std::sort(t3[s].begin(), t3[s].end());
                    tref[s] = t3[s][t3[s].size() / 2];
                }
            }
            std::printf("%-18s %8d %-7s | %-6s %-6s %-17s | %8.1f %7.1f %7.1f\n", kinds[kind], n, "ref P", "-", "-", "-", tref[0],
                        tref[1], tref[2]);
            auto cmp_list = [&](const std::vector<int32_t> &ref, const int32_t *dev, size_t m) {
                std::vector<int32_t> x(m);
                q.memcpy(x.data(), dev, m * 4).wait();
                return x == ref;
            };
            auto cmp_marks = [&](const uint8_t *dev) {
                std::vector<uint8_t> x(n);
                q.memcpy(x.data(), dev, (size_t)n).wait();
                return x == rmk;
            };
            // arm 0: the engine's own two launches over the whole array (topk_mr / topk_mb)
            {
                bool okp = true, okm = true, okbl = true, okbm = true;
                std::vector<double> t3[3];
                for (int r = 0; r < REP; ++r) {
                    for (int sel = 0; sel < 2; ++sel) {
                        const KP &k = sel ? km : kp;
                        const int G = (k.n + M1::R - 1) / M1::R;
                        KP k2 = k;
                        k2.n = G * k.k, k2.cand_n = 0;
                        q.fill(lout, -5, KB_ + 64).wait();
                        auto a = local_g((size_t)G, M1{k}, (const float *)sc, sel ? (const uint8_t *)mref : (const uint8_t *)nullptr, ck, ci);
                        auto b = q2(k2, ck, ci, lout);
                        b.wait();
                        t3[sel].push_back(us(a) + us(b));
                        (sel ? okm : okp) = (sel ? okm : okp) && cmp_list(sel ? rm : rp, lout, KR_);
                    }
                    const int G = (kb.n + MB1::R - 1) / MB1::R;
                    KB k2 = kb;
                    k2.n = G * kb.k;
                    q.fill(mout, (uint8_t)7, (size_t)n + 64);
                    q.fill(lout, -5, KB_ + 64).wait();
                    auto a = local_g((size_t)G, MB1{kb}, (const float *)sc, ck, ci, mout);
                    auto b = qb2(k2, ck, ci, lout, mout);
                    b.wait();
                    t3[2].push_back(us(a) + us(b));
                    okbl = okbl && cmp_list(rb, lout, KB_ + 1);
                    okbm = okbm && cmp_marks(mout);
                }
                double t[3];
                for (int s = 0; s < 3; ++s) {
                    std::sort(t3[s].begin(), t3[s].end());
                    t[s] = t3[s][t3[s].size() / 2];
                }
                bad += !okp + !okm + !okbl + !okbm;
                std::printf("%-18s %8d %-7s | %-6s %-6s %-8s %-8s | %8.1f %7.1f %7.1f\n", kinds[kind], n, "1card", okp ? "y" : "NO",
                            okm ? "y" : "NO", okbl ? "y" : "NO", okbm ? "y" : "NO", t[0], t[1], t[2]);
            }
            // arms 1, 2: the shard
            for (unsigned R : {2048u, 16384u}) {
                // the owners' local arrays (scores; the reference marks as each owner's mask)
                long nl[NC] = {};
                for (int d = 0; d < NC; ++d) {
                    std::vector<float> ls;
                    std::vector<uint8_t> lm;
                    for (long l = 0;; ++l) {
                        const long r = kvs_global(l, d, R, NC);
                        if (r >= n) {
                            if (l % R == 0) break; // (a whole chunk past the end: no more rows of d)
                            l = (l / R + 1) * R - 1; // (the rest of this chunk is past the end)
                            continue;
                        }
                        ls.push_back(hs[r]);
                        lm.push_back(rmk[r]);
                    }
                    nl[d] = (long)ls.size();
                    if (nl[d]) {
                        q.memcpy(lsc[d], ls.data(), ls.size() * 4);
                        q.memcpy(lmk[d], lm.data(), lm.size()).wait();
                    }
                }
                long tot = 0;
                for (int d = 0; d < NC; ++d) tot += nl[d];
                if (tot != n) {
                    std::printf("ownership: %ld rows of %d\n", tot, n);
                    return 2;
                }
                const int dnew = (int)kvs_owner((long)(nb - 1) * BS, R, NC); // the owner of the global newest block
                bool okp = true, okm = true, okbl = true, okbm = true, ok0 = true;
                std::vector<double> t3[3];
                for (int r = 0; r < REP; ++r) {
                    // rows: plain and masked
                    for (int sel = 0; sel < 2; ++sel) {
                        TkCompact tc{R, (unsigned)NC, 0, {}, {}, {}};
                        TkMerge tm{};
                        size_t off = 0;
                        double s1 = 0; // the slowest owner's stage 1 (the cards run theirs at once)
                        for (int d = 0; d < NC; ++d) {
                            const int G = (int)((nl[d] + M1::R - 1) / M1::R);
                            tc.S[d] = G * KR_, tc.lim[d] = (int)nl[d], tc.soff[d] = tm.soff[d] = off;
                            if (G) {
                                const KP k{(int)nl[d], KR_, 128, KR_, sel ? (int)nl[d] : 0, 0, 0};
                                auto a = local_g((size_t)G, M1{k}, (const float *)lsc[d],
                                                 sel ? (const uint8_t *)lmk[d] : (const uint8_t *)nullptr, ck + off, ci + off);
                                a.wait();
                                s1 = std::max(s1, us(a));
                            }
                            off += (size_t)G * KR_;
                        }
                        tm.soff[NC] = off;
                        q.fill(mk, 0u, off);
                        q.fill(mi, -1, off).wait();
                        auto e1 = q.submit([&](sycl::handler &h) {
                            h.parallel_for(sycl::nd_range<1>((size_t)NC * TkCompact::WG, TkCompact::WG),
                                           [=](sycl::nd_item<1> it) { tc(it, ck, ci, ok, oi, cnt); });
                        });
                        auto e2 = q.submit([&](sycl::handler &h) {
                            h.parallel_for(sycl::nd_range<1>((off + 255) / 256 * 256, 256),
                                           [=](sycl::nd_item<1> it) { tm(it, ok, oi, cnt, mk, mi); });
                        });
                        const KP k2{(int)off, KR_, 128, KR_, 0, 0, 0};
                        q.fill(lout, -5, KB_ + 64).wait();
                        auto e3 = q2(k2, mk, mi, lout);
                        e3.wait();
                        t3[sel].push_back(s1 + us(e1) + us(e2) + us(e3));
                        (sel ? okm : okp) = (sel ? okm : okp) && cmp_list(sel ? rm : rp, lout, KR_);
                    }
                    // blocks (the dummy +inf block on every owner but the newest block's)
                    {
                        TkCompact tc{R, (unsigned)NC, 1, {}, {}, {}};
                        TkMerge tm{};
                        size_t off = 0;
                        double s1 = 0;
                        for (int d = 0; d < NC; ++d) {
                            q.fill(lbm[d], (uint8_t)7, (size_t)nl[d] + 64).wait();
                            const int nbl = (int)((nl[d] + BS - 1) / BS), nbk = nl[d] ? nbl + (d == dnew ? 0 : 1) : 0;
                            const int G = (nbk + MB1::R - 1) / MB1::R;
                            tc.S[d] = G * KB_, tc.lim[d] = nbl, tc.soff[d] = tm.soff[d] = off;
                            if (G) {
                                const KB k{nbk, KB_, 0, 0, 0, BS, (int)nl[d]};
                                auto a = local_g((size_t)G, MB1{k}, (const float *)lsc[d], ck + off, ci + off, lbm[d]);
                                a.wait();
                                s1 = std::max(s1, us(a));
                                std::vector<uint8_t> z(nl[d]);
                                q.memcpy(z.data(), lbm[d], (size_t)nl[d]).wait();
                                for (uint8_t v : z) ok0 = ok0 && v == 0; // (stage 1 zeroes the owner's rows)
                            }
                            off += (size_t)G * KB_;
                        }
                        tm.soff[NC] = off;
                        q.fill(mk, 0u, off);
                        q.fill(mi, -1, off).wait();
                        auto e1 = q.submit([&](sycl::handler &h) {
                            h.parallel_for(sycl::nd_range<1>((size_t)NC * TkCompact::WG, TkCompact::WG),
                                           [=](sycl::nd_item<1> it) { tc(it, ck, ci, ok, oi, cnt); });
                        });
                        auto e2 = q.submit([&](sycl::handler &h) {
                            h.parallel_for(sycl::nd_range<1>((off + 255) / 256 * 256, 256),
                                           [=](sycl::nd_item<1> it) { tm(it, ok, oi, cnt, mk, mi); });
                        });
                        const KB k2{(int)off, KB_, 0, 0, 0, BS, n};
                        q.fill(mout, (uint8_t)0, (size_t)n + 64); // (stage 2 flags the kept rows; the rest stay 0)
                        q.fill(lout, -5, KB_ + 64).wait();
                        auto e3 = qb2(k2, mk, mi, lout, mout);
                        e3.wait();
                        t3[2].push_back(s1 + us(e1) + us(e2) + us(e3));
                        okbl = okbl && cmp_list(rb, lout, KB_ + 1);
                        okbm = okbm && cmp_marks(mout);
                    }
                }
                double t[3];
                for (int s = 0; s < 3; ++s) {
                    std::sort(t3[s].begin(), t3[s].end());
                    t[s] = t3[s][t3[s].size() / 2];
                }
                bad += !okp + !okm + !okbl + !okbm + !ok0;
                char arm[16];
                std::snprintf(arm, sizeof arm, "R%u", R);
                std::printf("%-18s %8d %-7s | %-6s %-6s %-8s %-8s | %8.1f %7.1f %7.1f%s\n", kinds[kind], n, arm, okp ? "y" : "NO",
                            okm ? "y" : "NO", okbl ? "y" : "NO", okbm ? "y" : "NO", t[0], t[1], t[2],
                            ok0 ? "" : "  (stage 1 left local marks set)");
            }
            std::fflush(stdout);
        }
    std::printf(bad ? "FAIL (%ld differ)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
