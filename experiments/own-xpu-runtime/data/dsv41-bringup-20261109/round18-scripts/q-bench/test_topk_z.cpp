// q2 parts: where does the top-512 select's time go (TopKSelR, one work-group of 1,024, ~100 us at 69,000 rows)? Forms of
// TopKSelR<false> that keep its algorithm (the same four radix passes, the same walk by ranges, so the same
// list), each against TopKSelP bit for bit, GPU time of each on one card:
//   R        TopKSelR<false> (the engine, OWN_TOPK_R)
//   X<U,A>   loads issued U at a time (the passes over strided positions and the walk over the item's range),
//            A: the radix passes' local-memory adds folded per sub-group for the keys whose digit equals
//            lane 0's (one ballot and one add for all of them; the other lanes add as before)
// Score arrays as test_topk_r: normal values, a few values (heavy ties), +0 / -0, mostly -inf, NaNs mixed in;
// plain select (top 512 of n, offset 128) and masked select (the block select's mask).
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/test_topk_q.cpp -o test_topk_q
//   ONEAPI_DEVICE_SELECTOR=level_zero:1 ./test_topk_q
#include <sycl/sycl.hpp>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

template <int U, bool AGG> struct SelX {
    using KP = TopKSelP<false>;
    static constexpr int WG = KP::WG, NSG = KP::NSG;
    KP p;
    void operator()(sycl::nd_item<1> it, const float *sc, const uint8_t *cand_in, int32_t *out, uint8_t *, float *lm) const {
        auto g = it.get_group();
        sycl::sub_group sg = it.get_sub_group();
        const int lid = (int)it.get_local_linear_id();
        const int sgi = (int)sg.get_group_linear_id(), lane = (int)sg.get_local_linear_id();
        uint32_t *hist = reinterpret_cast<uint32_t *>(lm), *misc = hist + NSG * 256;
        const int n = p.n;
        const bool all = p.k >= n;
        const int nm = (n + WG - 1) / WG;
        uint32_t T = 0, rem = 0;
        using LA = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::work_group,
                                    sycl::access::address_space::local_space>;
        if (!all) {
            uint32_t prefix = 0, pmask = 0;
            rem = (uint32_t)p.k;
            for (int pass = 0; pass < 4; ++pass) {
                const int shift = 24 - 8 * pass;
                for (int i = lid; i < NSG * 256; i += WG) hist[i] = 0;
                sycl::group_barrier(g);
                for (int m0 = 0; m0 < nm; m0 += U) {
                    uint32_t kk[U];
                    bool act[U];
#pragma unroll
                    for (int u = 0; u < U; ++u) {
                        const int j = lid + WG * (m0 + u);
                        act[u] = m0 + u < nm && j < n;
                        kk[u] = act[u] ? KP::okey(p.val(sc, cand_in, j)) : 0u;
                    }
#pragma unroll
                    for (int u = 0; u < U; ++u) {
                        const bool a = act[u] && (kk[u] & pmask) == prefix;
                        const uint32_t d = (kk[u] >> shift) & 255u;
                        if constexpr (AGG) {
                            const uint32_t d0 = sycl::select_from_group(sg, d, 0);
                            const bool a0 = sycl::select_from_group(sg, a ? 1 : 0, 0) != 0;
                            const bool m = a && a0 && d == d0;
                            const uint32_t c0 = (uint32_t)sycl::ext::oneapi::group_ballot(sg, m).count();
                            if (lane == 0 && c0) LA(hist[sgi * 256 + d0]).fetch_add(c0);
                            if (a && !m) LA(hist[sgi * 256 + d]).fetch_add(1u);
                        } else {
                            if (a) LA(hist[sgi * 256 + d]).fetch_add(1u);
                        }
                    }
                }
                sycl::group_barrier(g);
                uint32_t tot = 0;
                if (lid < 256)
                    for (int s2 = 0; s2 < NSG; ++s2) tot += hist[s2 * 256 + (255 - lid)];
                const uint32_t inc = sycl::inclusive_scan_over_group(g, tot, sycl::plus<uint32_t>());
                const uint32_t exc = inc - tot;
                if (lid < 256 && exc < rem && rem <= inc) {
                    misc[0] = 255u - (uint32_t)lid;
                    misc[1] = exc;
                }
                sycl::group_barrier(g);
                prefix |= misc[0] << shift;
                pmask |= 255u << shift;
                rem -= misc[1];
                sycl::group_barrier(g);
            }
            T = prefix;
        }
        const int c = nm, j0 = sycl::min(n, lid * c), j1 = sycl::min(n, j0 + c);
        uint32_t ngt = 0, neq = 0;
        for (int jb = j0; jb < j1; jb += U) {
            uint32_t kk[U];
#pragma unroll
            for (int u = 0; u < U; ++u) kk[u] = jb + u < j1 ? KP::okey(p.val(sc, cand_in, jb + u)) : 0u;
#pragma unroll
            for (int u = 0; u < U; ++u)
                if (jb + u < j1) {
                    ngt += (all || kk[u] > T) ? 1u : 0u;
                    neq += (!all && kk[u] == T) ? 1u : 0u;
                }
        }
        const uint32_t gtb = sycl::exclusive_scan_over_group(g, ngt, sycl::plus<uint32_t>());
        const uint32_t eqb = sycl::exclusive_scan_over_group(g, neq, sycl::plus<uint32_t>());
        uint32_t base = gtb + sycl::min(eqb, rem), eqs = eqb;
        for (int jb = j0; jb < j1; jb += U) {
            uint32_t kk[U];
#pragma unroll
            for (int u = 0; u < U; ++u) kk[u] = jb + u < j1 ? KP::okey(p.val(sc, cand_in, jb + u)) : 0u;
#pragma unroll
            for (int u = 0; u < U; ++u)
                if (jb + u < j1) {
                    const bool gt = all || kk[u] > T, eq = !all && kk[u] == T;
                    const bool sel = gt || (eq && eqs < rem);
                    if (eq) ++eqs;
                    if (sel) {
                        if (base < (uint32_t)p.outn) out[base] = jb + u + p.add;
                        ++base;
                    }
                }
        }
        const uint32_t tot = sycl::reduce_over_group(g, ngt, sycl::plus<uint32_t>()) +
                             sycl::min(sycl::reduce_over_group(g, neq, sycl::plus<uint32_t>()), rem);
        for (int i = (int)tot + lid; i < p.outn; i += WG) out[i] = -1;
    }
};

#include "zparts.inc"
int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    const int MAXN = 140000;
    float *sc = sycl::malloc_device<float>(MAXN + 64, q);
    constexpr int NV = 6;
    int32_t *ls[NV];
    for (auto &l : ls) l = sycl::malloc_device<int32_t>(2048 + 64, q);
    using KR = TopKSelP<false>;
    constexpr size_t SLM = (size_t)KR::NSG * 256 + 8;
    auto local = [&](auto k, auto... a) {
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(SLM, h);
            h.parallel_for(sycl::nd_range<1>(1024, 1024), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                k(it, a..., &lt[0]);
            });
        });
    };
    auto us = [](sycl::event &e) {
        return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
    };
    std::mt19937 rng(5);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::vector<float> hs(MAXN);
    const char *kinds[3] = {"normal", "+0 / -0", "mostly -inf"};
    auto fill = [&](int n, int kind) {
        for (int j = 0; j < n; ++j) {
            const float f = nd(rng);
            hs[j] = kind == 1 ? (f > 0 ? 0.0f : -0.0f) : kind == 2 ? -INFINITY : f;
        }
        if (kind == 2)
            for (int i = 0; i < 300; ++i) hs[(size_t)(rng() % n)] = nd(rng);
        q.memcpy(sc, hs.data(), (size_t)n * 4).wait();
    };
    long bad = 0;
    std::printf("%-12s %7s | %8s %8s | %8s %8s | %8s %8s | walks same as P\n", "scores", "n", "P", "R", "pass noA", "pass", "walk R", "walk C");
    for (int kind = 0; kind < 3; ++kind)
        for (int n : {2300, 17000, 34000, 69000, 95000, 130000}) {
            fill(n, kind);
            const KR k{n, 512, 128, 512, 0, 0, 0};
            double t[NV] = {};
            bool sw = true, sc2 = true;
            const int REP = 10;
            for (int r = 0; r <= REP; ++r) {
                for (int v = 0; v < NV; ++v) q.fill(ls[v], -5, 2048 + 64);
                q.wait();
                auto e0 = local(k, (const float *)sc, (const uint8_t *)nullptr, ls[0], (uint8_t *)nullptr); e0.wait();
                auto e1 = local(TopKSelR<false>{k}, (const float *)sc, (const uint8_t *)nullptr, ls[1], (uint8_t *)nullptr); e1.wait();
                auto e2 = local(ZP<0>{k}, (const float *)sc, ls[2]); e2.wait();
                auto e3 = local(ZP<1>{k}, (const float *)sc, ls[3]); e3.wait();
                int32_t tr[2];
                q.memcpy(tr, ls[3], 8).wait();
                auto e4 = local(ZW{k, (uint32_t)tr[0], (uint32_t)tr[1]}, (const float *)sc, ls[4]); e4.wait();
                auto e5 = local(ZC{k, (uint32_t)tr[0], (uint32_t)tr[1]}, (const float *)sc, ls[5]); e5.wait();
                if (r) { t[0] += us(e0); t[1] += us(e1); t[2] += us(e2); t[3] += us(e3); t[4] += us(e4); t[5] += us(e5); }
                std::vector<int32_t> ref(512), o(512);
                q.memcpy(ref.data(), ls[0], 2048).wait();
                q.memcpy(o.data(), ls[4], 2048).wait(); if (o != ref) sw = false;
                q.memcpy(o.data(), ls[5], 2048).wait(); if (o != ref) sc2 = false;
            }
            bad += !sw + !sc2;
            std::printf("%-12s %7d | %8.1f %8.1f | %8.1f %8.1f | %8.1f %8.1f | %s %s\n", kinds[kind], n, t[0] / REP, t[1] / REP,
                        t[2] / REP, t[3] / REP, t[4] / REP, t[5] / REP, sw ? "y" : "NO", sc2 ? "y" : "NO");
        }
    std::printf(bad ? "FAIL (%ld differ)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
