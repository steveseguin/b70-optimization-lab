// test_idxfilt (idxfilt-1, 2026-11-17): the matrix-engine pre-filter (sycl_v41_idxfilt.hpp) on one card.
// For m tokens (BENCH_M, default 43 = one card's share of a prompt half; 2-6 = a check) over len0 rows
// (BENCH_LENS; layer 20 ratio 1: token t sees len0 + t rows; ratio 2: len0 / 2 + t / 2):
//  1. exact scores by IndexerScoreBM (today's order) and the filter's LO / row norms / bound factors;
//  2. the bound on every row: LO <= exact <= LO + 2 E (E = ac[t] * n2[row]), counted (must be 0 misses);
//  3. rows the exact scorer would still score: HI >= the 512th largest LO (per token: mean / max), and at ratio 1
//     the rows of blocks of 8 whose largest HI reaches the 2048th largest block LO key;
//  4. GPU time (min of 5): IndexerScoreBM, IndexerScoreBMS<2> rmaj (today's fastest), the filter with 1 / 2 / 4
//     row tiles per sub-group, two BF16 passes, and with one pass (hi only, C1: more rows left);
//  5. end to end as the engine (OWN_IDX_FILT, idxfilt-2): the selects (TopKSelM<true> blocks at ratio 1,
//     TopKSelM<false> rows) on the exact scores, against: the filter (with its per-8-row maxima), IdxFiltT (thresholds),
//     IdxFiltX2 (exact scores where they can matter; 1 / 4 / 2 blocks per item, timed), the selects once; every row's
//     bits after X2 (each the exact score or its LO, never anything else), every list, block list and mark compared.
// BENCH_DUMP=file (an OWN_IDX_DUMP file): its query, weights and key rows instead of random ones (every token the
// dump's, len0 = its rows, ratio 1 only). Last line "PASS (N cases)" or "FAIL (...)". Build as test_index_score_px.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/sycl_v41_idxfilt.hpp"
using namespace ops41sycl;

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("device: %s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    constexpr int MM = 43;
    const int M = std::clamp(std::getenv("BENCH_M") ? std::atoi(std::getenv("BENCH_M")) : MM, 1, MM);
    std::vector<long> L0{95000L, 352000L, 993000L};
    if (const char *e = std::getenv("BENCH_LENS")) {
        L0.clear();
        for (const char *p = e; *p;) {
            L0.push_back(std::atol(p));
            while (*p && *p != ',') ++p;
            if (*p) ++p;
        }
    }
    // the dump (optional)
    std::vector<float> dq0, dw0;
    std::vector<uint16_t> dk0;
    long dlen = 0;
    if (const char *fn = std::getenv("BENCH_DUMP")) {
        FILE *f = std::fopen(fn, "rb");
        int64_t h[3] = {};
        if (!f || std::fread(h, 8, 3, f) != 3 || h[2] != 4) {
            std::printf("FAIL (cannot read the dump %s)\n", fn);
            return 2;
        }
        dlen = h[1];
        dq0.resize(4096), dw0.resize(32), dk0.resize((size_t)dlen * 128);
        const bool ok = std::fread(dq0.data(), 4, 4096, f) == 4096 && std::fread(dw0.data(), 4, 32, f) == 32 &&
                        std::fread(dk0.data(), 2, dk0.size(), f) == dk0.size();
        std::fclose(f);
        if (!ok) {
            std::printf("FAIL (short dump %s)\n", fn);
            return 2;
        }
        L0 = {dlen};
        std::printf("dump %s: layer %lld, %ld rows\n", fn, (long long)h[0], dlen);
    }
    constexpr size_t WG = 128;
    const long MAXN = *std::max_element(L0.begin(), L0.end()) + MM + 64;
    const size_t SS = (size_t)MAXN + 64;
    float *dq = sycl::malloc_device<float>((size_t)M * 4096, q), *dw = sycl::malloc_device<float>((size_t)M * 32, q);
    uint16_t *dk = sycl::malloc_device<uint16_t>((size_t)MAXN * 128, q);
    float *sa = sycl::malloc_device<float>((size_t)M * SS, q), *sb = sycl::malloc_device<float>((size_t)M * SS, q);
    float *n2 = sycl::malloc_device<float>((size_t)MAXN, q), *ac = sycl::malloc_device<float>(M, q);
    uint16_t *bh = sycl::malloc_device<uint16_t>((size_t)M * 4096, q), *bl = sycl::malloc_device<uint16_t>((size_t)M * 4096, q);
    int *dl = sycl::malloc_device<int>(M, q);
    const size_t CMS = (size_t)MAXN / 8 + 64;
    float *cm = sycl::malloc_device<float>((size_t)M * CMS, q), *thr = sycl::malloc_device<float>((size_t)M * 2 + 8, q);
    constexpr size_t BLS = 2048 + 64;
    int32_t *oa = sycl::malloc_device<int32_t>((size_t)M * 512, q), *ob = sycl::malloc_device<int32_t>((size_t)M * 512, q);
    int32_t *ba = sycl::malloc_device<int32_t>((size_t)M * BLS, q), *bb = sycl::malloc_device<int32_t>((size_t)M * BLS, q);
    uint8_t *ca = sycl::malloc_device<uint8_t>((size_t)M * SS, q), *cb = sycl::malloc_device<uint8_t>((size_t)M * SS, q);
    // idxfilt-3: TopKSelF's outputs (the survivors-only selects), compared with the full selects' on the same scores
    int32_t *of = sycl::malloc_device<int32_t>((size_t)M * 512, q), *bf = sycl::malloc_device<int32_t>((size_t)M * BLS, q);
    uint8_t *cf = sycl::malloc_device<uint8_t>((size_t)M * SS, q);
    // idxfilt-4: the candidate layers' scores (IndexerScoreBCM / the filter) and lists over the block lists bb
    float *sc1 = sycl::malloc_device<float>((size_t)M * SS, q), *sc2 = sycl::malloc_device<float>((size_t)M * SS, q);
    int32_t *oc1 = sycl::malloc_device<int32_t>((size_t)M * 512, q), *oc2 = sycl::malloc_device<int32_t>((size_t)M * 512, q);
    uint32_t *cnt4 = sycl::malloc_device<uint32_t>(64, q);
    if (!of || !bf || !cf || !sc1 || !sc2 || !oc1 || !oc2 || !cnt4) {
        std::printf("FAIL (device allocation, idxfilt-3 / -4)\n");
        return 2;
    }
    if (!dq || !dw || !dk || !sa || !sb || !n2 || !ac || !bh || !bl || !dl || !oa || !ob || !ba || !bb || !ca || !cb || !cm || !thr) {
        std::printf("FAIL (device allocation)\n");
        return 2;
    }
    std::mt19937 rng(11);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::vector<float> hq((size_t)M * 4096), hw((size_t)M * 32);
    if (dlen) {
        for (int t = 0; t < M; ++t) {
            std::copy(dq0.begin(), dq0.end(), hq.begin() + (size_t)t * 4096);
            std::copy(dw0.begin(), dw0.end(), hw.begin() + (size_t)t * 32);
        }
        q.memcpy(dk, dk0.data(), dk0.size() * 2).wait();
    } else {
        for (auto &v : hq) v = nd(rng) * 0.1f;
        for (auto &v : hw) v = nd(rng);
        std::vector<uint16_t> hk((size_t)1 << 20);
        for (long r0 = 0; r0 < MAXN * 128; r0 += (long)hk.size()) {
            const long n = std::min<long>((long)hk.size(), MAXN * 128 - r0);
            for (long i = 0; i < n; ++i) {
                const float f = nd(rng);
                uint32_t u;
                std::memcpy(&u, &f, 4);
                hk[i] = (uint16_t)(u >> 16);
            }
            q.memcpy(dk + r0, hk.data(), (size_t)n * 2).wait();
        }
    }
    q.memcpy(dq, hq.data(), hq.size() * 4);
    q.memcpy(dw, hw.data(), hw.size() * 4).wait();
    auto ms = [](sycl::event &e) {
        return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-6;
    };
    int lens[MM] = {};
    long lmax = 0;
    auto runBM = [&](float *out) {
        IndexerScoreBM<ActF32> k{};
        k.lens.p = dl;
        k.m = (unsigned)M;
        k.gpt = (unsigned)((((lmax + 31) / 32 * 32) + WG - 1) / WG);
        k.qs = 4096, k.ws = 32, k.ss = SS;
        k.rmaj = 0;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(32 * 128 + 32, h);
            h.parallel_for(sycl::nd_range<1>((size_t)M * k.gpt * WG, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                k(it, dq, dk, dw, out, &lt[0]);
            });
        });
    };
    auto runS2 = [&](float *out) {
        IndexerScoreBMS<ActF32, 2> k{};
        k.lens.p = dl;
        k.m = (unsigned)M;
        k.gpt = (unsigned)((((lmax + 31) / 32 * 32) + WG * 2 - 1) / (WG * 2));
        k.qs = 4096, k.ws = 32, k.ss = SS;
        k.rmaj = 1;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(32 * 128 + 32, h);
            h.parallel_for(sycl::nd_range<1>((size_t)M * k.gpt * WG, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                k(it, dq, dk, dw, out, &lt[0]);
            });
        });
    };
    // the filter: Q (one launch) + S (one launch); returns the two events
    auto runF = [&](auto rtc, bool two, float *out, sycl::event &eq) {
        constexpr unsigned RT = decltype(rtc)::value;
        IdxFiltQ<ActF32> kq{};
        kq.two = two;
        eq = q.submit([&](sycl::handler &h) {
            h.parallel_for(sycl::nd_range<1>((size_t)M * IdxFiltQ<ActF32>::WG, IdxFiltQ<ActF32>::WG),
                           [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] { kq(it, dq, dw, bh, bl, ac); });
        });
        using KS = IdxFiltS<ActF32, RT>;
        KS ks{};
        ks.m = (unsigned)M;
        ks.nr = (unsigned)((lmax + 31) / 32 * 32);
        ks.ss = SS;
        ks.two = two;
        ks.lens.p = dl;
        ks.cm = cm, ks.cms = CMS;
        const size_t ng = (ks.nr + KS::ROWS - 1) / KS::ROWS;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(KS::SLM, h);
            h.parallel_for(sycl::nd_range<1>(ng * KS::WG, KS::WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                ks(it, dk, bh, bl, ac, dw, out, n2, &lt[0]);
            });
        });
    };
    constexpr size_t SLMSEL = (size_t)TopKSelP<false>::NSG * 256 + 8;
    auto sel = [&](auto k, const float *sc, uint8_t *cd, int32_t *out) {
        k.lens.p = dl;
        k.m = (unsigned)M;
        k.ss = SS;
        k.cs = SS;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(SLMSEL, h);
            h.parallel_for(sycl::nd_range<1>((size_t)M * TopKSelP<false>::WG, TopKSelP<false>::WG),
                           [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, sc, cd, out, &lt[0]); });
        });
    };
    auto selB = [&](const float *sc, uint8_t *cd, int32_t *bo) {
        TopKSelM<true> k{};
        k.bls = BLS;
        return sel(k, sc, cd, bo);
    };
    auto selR = [&](const float *sc, uint8_t *cd, int32_t *out) {
        TopKSelM<false> k{};
        k.mask = false;
        return sel(k, sc, cd, out);
    };
    auto runT = [&](bool blk) {
        IdxFiltT<> k{};
        k.lens.p = dl;
        k.m = (unsigned)M;
        k.cms = CMS;
        k.blk = blk;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(IdxFiltT<>::SLM, h);
            h.parallel_for(sycl::nd_range<1>((size_t)M * IdxFiltT<>::WG, IdxFiltT<>::WG),
                           [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, cm, thr, &lt[0]); });
        });
    };
    auto selF = [&](auto kf, const float *sc, uint8_t *cd, int32_t *out) {
        using KF = decltype(kf);
        kf.lens.p = dl;
        kf.m = (unsigned)M;
        kf.ss = SS;
        kf.cs = SS;
        kf.bls = BLS;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(KF::SLM, h);
            h.parallel_for(sycl::nd_range<1>((size_t)M * KF::WG, KF::WG),
                           [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kf(it, sc, thr, cd, out, &lt[0]); });
        });
    };
    // idxfilt-4: IndexerScoreBCM over the candidate rows of bl0 (token t's list at bl0 + t * BLS), the candidate select
    auto runBCM = [&](float *out, const int32_t *bl0) {
        IndexerScoreBCM<ActF32> k{};
        k.lens.p = dl;
        k.m = (unsigned)M;
        k.gpt = (unsigned)(2048 * 8 / WG);
        k.qs = 4096, k.ws = 32, k.ss = SS, k.bls = BLS;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(32 * 128 + 32, h);
            h.parallel_for(sycl::nd_range<1>((size_t)M * k.gpt * WG, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                k(it, dq, dk, dw, out, bl0, &lt[0]);
            });
        });
    };
    auto selC = [&](const float *sc, const uint8_t *cd, const int32_t *bl0, int32_t *out) {
        TopKSelMC k{};
        k.lens.p = dl;
        k.m = (unsigned)M;
        k.ss = SS, k.cs = SS, k.bls = BLS;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt((size_t)TopKSelC::NSG * 256 + 8, h);
            h.parallel_for(sycl::nd_range<1>((size_t)M * TopKSelC::WG, TopKSelC::WG),
                           [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, sc, cd, bl0, out, &lt[0]); });
        });
    };
    auto runQ2 = [&]() {
        IdxFiltQ<ActF32> kq{};
        kq.two = true;
        return q.submit([&](sycl::handler &h) {
            h.parallel_for(sycl::nd_range<1>((size_t)M * IdxFiltQ<ActF32>::WG, IdxFiltQ<ActF32>::WG),
                           [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] { kq(it, dq, dw, bh, bl, ac); });
        });
    };
    auto runSC = [&](auto rtc, float *out, const int32_t *bl0) {
        using KS = IdxFiltSC<ActF32, decltype(rtc)::value>;
        KS k{};
        k.lens.p = dl;
        k.m = (unsigned)M;
        k.gpt = (2048 + KS::BPG - 1) / KS::BPG;
        k.ss = SS, k.ws = 32, k.bls = BLS;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(KS::SLM, h);
            h.parallel_for(sycl::nd_range<1>((size_t)M * k.gpt * KS::WG, KS::WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                k(it, dk, bh, bl, ac, dw, bl0, out, n2, &lt[0]);
            });
        });
    };
    auto runTC = [&](const float *sc, const int32_t *bl0) {
        IdxFiltTC<> k{};
        k.lens.p = dl;
        k.m = (unsigned)M;
        k.ss = SS, k.bls = BLS;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(IdxFiltTC<>::SLM, h);
            h.parallel_for(sycl::nd_range<1>((size_t)M * IdxFiltTC<>::WG, IdxFiltTC<>::WG),
                           [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, sc, bl0, thr, &lt[0]); });
        });
    };
    auto runXC = [&](float *sc, const int32_t *bl0) {
        using KX = IdxFiltXC<ActF32, 2>;
        KX k{};
        k.lens.p = dl;
        k.m = (unsigned)M;
        k.ns = (2048 + KX::SB - 1) / KX::SB;
        k.ss = SS, k.bls = BLS;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(KX::SLM, h);
            h.parallel_for(sycl::nd_range<1>((size_t)M * k.ns * KX::WG, KX::WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                k(it, dq, dk, dw, ac, n2, thr, bl0, sc, &lt[0]);
            });
        });
    };
    auto runX2 = [&](auto bpc, float *sc) {
        using KX = IdxFiltX2<ActF32, decltype(bpc)::value>;
        KX k{};
        k.lens.p = dl;
        k.m = (unsigned)M;
        k.ns = (unsigned)((lmax + KX::SR - 1) / KX::SR);
        k.ss = SS;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(KX::SLM, h);
            h.parallel_for(sycl::nd_range<1>((size_t)M * k.ns * KX::WG, KX::WG),
                           [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] { k(it, dq, dk, dw, ac, n2, thr, sc, &lt[0]); });
        });
    };
    long e2e_bad = 0;
    std::printf("%-5s %8s | %8s %8s | %8s %8s %8s %8s | %10s %8s %9s %9s | %s\n", "ratio", "len0", "BM", "S2rmaj",
                "F2 rt1", "F2 rt2", "F2 rt4", "F1 rt2", "misses", "|x-mid|/E", "rows2 mean", "rows2 max",
                "rows1 mean / blocks2 rows | e2e");
    int cases = 0, bad = 0;
    for (int ratio : dlen ? std::vector<int>{1} : std::vector<int>{1, 2}) {
        for (long n0 : L0) {
            lmax = 0;
            for (int t = 0; t < M; ++t) {
                lens[t] = dlen ? (int)dlen : ratio == 1 ? (int)(n0 + t) : (int)(n0 / 2 + t / 2);
                lmax = std::max<long>(lmax, lens[t]);
            }
            q.memcpy(dl, lens, sizeof(int) * M).wait();
            double tb = 1e30, ts = 1e30, tf[4] = {1e30, 1e30, 1e30, 1e30};
            for (int rep = 0; rep < 5; ++rep) {
                auto e1 = runBM(sa);
                e1.wait();
                tb = std::min(tb, ms(e1));
                auto e2 = runS2(sb);
                e2.wait();
                ts = std::min(ts, ms(e2));
                sycl::event eq;
                auto f0 = runF(std::integral_constant<unsigned, 1>{}, true, sb, eq);
                f0.wait();
                tf[0] = std::min(tf[0], ms(eq) + ms(f0));
                auto f2 = runF(std::integral_constant<unsigned, 4>{}, true, sb, eq);
                f2.wait();
                tf[2] = std::min(tf[2], ms(eq) + ms(f2));
                auto f3 = runF(std::integral_constant<unsigned, 2>{}, false, sb, eq);
                f3.wait();
                tf[3] = std::min(tf[3], ms(eq) + ms(f3));
                auto f1 = runF(std::integral_constant<unsigned, 2>{}, true, sb, eq); // (last: its outputs are checked)
                f1.wait();
                tf[1] = std::min(tf[1], ms(eq) + ms(f1));
            }
            // check the two-pass rt2 outputs, then the one-pass's rows (run again) from its own LO
            std::vector<float> hx((size_t)M * SS), hl((size_t)M * SS), hn((size_t)lmax + 64), ha(M);
            q.memcpy(hx.data(), sa, hx.size() * 4);
            q.memcpy(hl.data(), sb, hl.size() * 4);
            q.memcpy(hn.data(), n2, (size_t)lmax * 4);
            q.memcpy(ha.data(), ac, (size_t)M * 4).wait();
            long misses = 0;
            double worst = 0, rows_sum = 0, blk_sum = 0;
            long rows_max = 0;
            auto count = [&](const std::vector<float> &lo, const std::vector<float> &a, double &mean, long &mx, double *blk) {
                mean = 0, mx = 0;
                for (int t = 0; t < M; ++t) {
                    const long n = lens[t];
                    std::vector<double> l(n);
                    for (long r = 0; r < n; ++r) l[r] = lo[(size_t)t * SS + r];
                    std::vector<double> s = l;
                    long c = n;
                    if (n > 512) {
                        std::nth_element(s.begin(), s.begin() + (n - 512), s.end());
                        const double L = s[n - 512];
                        c = 0;
                        for (long r = 0; r < n; ++r) c += l[r] + 2.0 * ((double)a[t] * hn[r] + 1e-30) >= L;
                    }
                    mean += (double)c / M, mx = std::max(mx, c);
                    if (blk && ratio == 1 && n / 8 > 2048) {
                        const long nb = n / 8;
                        std::vector<double> lb(nb), ub(nb);
                        for (long b = 0; b < nb; ++b) {
                            lb[b] = -INFINITY, ub[b] = -INFINITY;
                            for (int j = 0; j < 8; ++j) {
                                lb[b] = std::max(lb[b], l[8 * b + j]);
                                ub[b] = std::max(ub[b], l[8 * b + j] + 2.0 * (double)a[t] * hn[8 * b + j]);
                            }
                        }
                        std::vector<double> sb2 = lb;
                        std::nth_element(sb2.begin(), sb2.begin() + (nb - 2048), sb2.end());
                        const double Lb = sb2[nb - 2048];
                        long cb = 0;
                        for (long b = 0; b < nb; ++b) cb += ub[b] >= Lb;
                        *blk += 8.0 * (double)cb / M;
                    }
                }
            };
            for (int t = 0; t < M; ++t)
                for (long r = 0; r < lens[t]; ++r) {
                    const double x = hx[(size_t)t * SS + r], lo = hl[(size_t)t * SS + r], E = (double)ha[t] * hn[r] + 1e-30;
                    if (!(x >= lo && x <= lo + 2.0 * E)) ++misses;
                    if (E > 0) worst = std::max(worst, std::fabs(x - (lo + E)) / E);
                }
            double m2 = 0, m1 = 0;
            long x2 = 0, x1 = 0;
            count(hl, ha, m2, x2, &blk_sum);
            // 5. end to end (idxfilt-2): the filter (two passes, rt2) into sb, T, X2, the selects once
            double tsel = 0, tt = 1e30, tx2[3] = {1e30, 1e30, 1e30}, rows_ex = 0;
            long ldiff = 0, bdiff = 0, cdiff = 0, rows_bad = 0, rows_exmax = 0;
            {
                const bool B = ratio == 1;
                if (B) selB(sa, ca, ba).wait();
                selR(sa, ca, oa).wait();
                for (int rep = 0; rep < 3; ++rep)
                    for (int v = 0; v < 3; ++v) { // blocks per item 1, 4, 2 (2 last: its outputs are checked)
                        sycl::event eq;
                        runF(std::integral_constant<unsigned, 2>{}, true, sb, eq).wait();
                        auto e1 = runT(B);
                        e1.wait();
                        tt = std::min(tt, ms(e1));
                        sycl::event e2 = v == 0   ? runX2(std::integral_constant<unsigned, 1>{}, sb)
                                         : v == 1 ? runX2(std::integral_constant<unsigned, 4>{}, sb)
                                                  : runX2(std::integral_constant<unsigned, 2>{}, sb);
                        e2.wait();
                        tx2[v] = std::min(tx2[v], ms(e2));
                    }
                {
                    std::vector<float> hy((size_t)M * SS);
                    q.memcpy(hy.data(), sb, hy.size() * 4).wait();
                    for (int t = 0; t < M; ++t) {
                        long c = 0;
                        for (long r = 0; r < lens[t]; ++r) {
                            const size_t i = (size_t)t * SS + r;
                            uint32_t y, x, l;
                            std::memcpy(&y, &hy[i], 4), std::memcpy(&x, &hx[i], 4), std::memcpy(&l, &hl[i], 4);
                            if (y != l) {
                                ++c;
                                rows_bad += y != x;
                            }
                        }
                        rows_ex += (double)c / M, rows_exmax = std::max(rows_exmax, c);
                    }
                }
                sycl::event e;
                if (B) { e = selB(sb, cb, bb); e.wait(); tsel += ms(e); }
                e = selR(sb, cb, ob); e.wait(); tsel += ms(e);
                std::vector<int32_t> h1((size_t)M * 512), h2((size_t)M * 512), g1((size_t)M * BLS), g2((size_t)M * BLS);
                std::vector<uint8_t> k1((size_t)M * SS), k2((size_t)M * SS);
                q.memcpy(h1.data(), oa, h1.size() * 4);
                q.memcpy(h2.data(), ob, h2.size() * 4);
                if (B) {
                    q.memcpy(g1.data(), ba, g1.size() * 4);
                    q.memcpy(g2.data(), bb, g2.size() * 4);
                    q.memcpy(k1.data(), ca, k1.size());
                    q.memcpy(k2.data(), cb, k2.size());
                }
                q.wait();
                for (int t = 0; t < M; ++t) {
                    ldiff += std::memcmp(&h1[(size_t)t * 512], &h2[(size_t)t * 512], 512 * 4) != 0;
                    if (B) {
                        const int nb = std::clamp(g1[(size_t)t * BLS], 0, 2048);
                        bdiff += g1[(size_t)t * BLS] != g2[(size_t)t * BLS] ||
                                 std::memcmp(&g1[(size_t)t * BLS + 1], &g2[(size_t)t * BLS + 1], (size_t)nb * 4) != 0;
                        cdiff += std::memcmp(&k1[(size_t)t * SS], &k2[(size_t)t * SS], (size_t)lens[t]) != 0;
                    }
                }
                e2e_bad += ldiff + bdiff + cdiff + rows_bad;
                // idxfilt-3: the survivors-only selects on the same scores (sb, thr), outputs pre-filled with junk
                double tf3b = 1e30, tf3r = 1e30;
                long fl = 0, fb = 0, fc = 0;
                for (int rep = 0; rep < 3; ++rep) {
                    q.memset(of, 0x5a, (size_t)M * 512 * 4);
                    q.memset(bf, 0x5a, (size_t)M * BLS * 4);
                    q.memset(cf, 0x5a, (size_t)M * SS).wait();
                    if (B) { e = selF(TopKSelF<true>{}, sb, cf, bf); e.wait(); tf3b = std::min(tf3b, ms(e)); }
                    e = selF(TopKSelF<false>{}, sb, cf, of); e.wait(); tf3r = std::min(tf3r, ms(e));
                }
                {
                    std::vector<int32_t> f1((size_t)M * 512), fg((size_t)M * BLS);
                    std::vector<uint8_t> fk((size_t)M * SS);
                    q.memcpy(f1.data(), of, f1.size() * 4);
                    if (B) {
                        q.memcpy(fg.data(), bf, fg.size() * 4);
                        q.memcpy(fk.data(), cf, fk.size());
                        q.memcpy(g2.data(), bb, g2.size() * 4);
                        q.memcpy(k2.data(), cb, k2.size());
                    }
                    q.wait();
                    for (int t = 0; t < M; ++t) {
                        fl += std::memcmp(&f1[(size_t)t * 512], &h2[(size_t)t * 512], 512 * 4) != 0;
                        if (B) {
                            const int nb = std::clamp(g2[(size_t)t * BLS], 0, 2048);
                            fb += fg[(size_t)t * BLS] != g2[(size_t)t * BLS] ||
                                  std::memcmp(&fg[(size_t)t * BLS + 1], &g2[(size_t)t * BLS + 1], (size_t)nb * 4) != 0;
                            fc += std::memcmp(&fk[(size_t)t * SS], &k2[(size_t)t * SS], (size_t)lens[t]) != 0;
                        }
                    }
                }
                // idxfilt-4 (layer 20's shape: the block lists bb exist): the candidate layers, BCM vs the filter
                if (B) {
                    double tb = 1e30, tq = 1e30, tsc[2] = {1e30, 1e30}, ttc = 1e30, txc = 1e30, tsl = 1e30;
                    long cl = 0;
                    for (int rep = 0; rep < 3; ++rep) {
                        e = runBCM(sc1, bb); e.wait(); tb = std::min(tb, ms(e));
                        e = selC(sc1, cb, bb, oc1); e.wait(); tsl = std::min(tsl, ms(e));
                        for (int v = 0; v < 2; ++v) { // RT 2, then 1 (1 last: its outputs are checked)
                            q.memset(oc2, 0x5a, (size_t)M * 512 * 4).wait();
                            e = runQ2(); e.wait(); tq = std::min(tq, ms(e));
                            e = v == 0 ? runSC(std::integral_constant<unsigned, 2>{}, sc2, bb) : runSC(std::integral_constant<unsigned, 1>{}, sc2, bb);
                            e.wait(); tsc[v] = std::min(tsc[v], ms(e));
                            e = runTC(sc2, bb); e.wait(); ttc = std::min(ttc, ms(e));
                            e = runXC(sc2, bb); e.wait(); txc = std::min(txc, ms(e));
                        }
                        selC(sc2, cb, bb, oc2).wait();
                    }
                    // the candidate rows whose stored value is the exact one (counted on the card), and the lists
                    q.memset(cnt4, 0, 64 * 4).wait();
                    {
                        const float *x1 = sc1, *x2 = sc2;
                        const int32_t *b0 = bb;
                        const int *lp = dl;
                        uint32_t *cp = cnt4;
                        const size_t ssv = SS, blsv = BLS;
                        q.parallel_for(sycl::range<1>((size_t)M * 2048 * 8), [=](sycl::id<1> id) {
                             const size_t i = id[0], t = i / (2048 * 8), p = i % (2048 * 8);
                             const int32_t *b = b0 + t * blsv;
                             if ((int)(p / 8) >= b[0]) return;
                             const int r = b[1 + p / 8] * 8 + (int)(p % 8);
                             if (r >= lp[t]) return;
                             sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::device,
                                              sycl::access::address_space::global_space>(cp[0]).fetch_add(1u);
                             if (x1[t * ssv + r] == x2[t * ssv + r])
                                 sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::device,
                                                  sycl::access::address_space::global_space>(cp[1]).fetch_add(1u);
                         }).wait();
                    }
                    uint32_t hc[2] = {};
                    q.memcpy(hc, cnt4, 8).wait();
                    std::vector<int32_t> c1((size_t)M * 512), c2((size_t)M * 512);
                    q.memcpy(c1.data(), oc1, c1.size() * 4);
                    q.memcpy(c2.data(), oc2, c2.size() * 4).wait();
                    for (int t = 0; t < M; ++t) cl += std::memcmp(&c1[(size_t)t * 512], &c2[(size_t)t * 512], 512 * 4) != 0;
                    std::printf("bcf %-5d %8ld: lists %ld differ (of %d tokens); candidate rows %u, exact after the filter %u "
                                "(%.1f per token); BCM %.3f ms vs filter Q %.3f + SC %.3f (RT2 %.3f) + TC %.3f + XC %.3f = %.3f ms; "
                                "candidate select %.3f ms\n",
                                ratio, n0, cl, M, hc[0], hc[1], (double)hc[1] / M, tb, tq, tsc[1], tsc[0], ttc, txc,
                                tq + std::min(tsc[0], tsc[1]) + ttc + txc, tsl);
                    e2e_bad += cl;
                    ldiff += cl;
                }
                std::printf("selF %-5d %8ld: lists %ld, block lists %ld, marks %ld differ (of %d tokens); survivors-only "
                            "selects %.3f ms (blocks %.3f + rows %.3f) vs the full selects %.3f ms\n",
                            ratio, n0, fl, fb, fc, M, (B ? tf3b : 0.0) + tf3r, B ? tf3b : 0.0, tf3r, tsel);
                e2e_bad += fl + fb + fc;
                ldiff += fl, bdiff += fb, cdiff += fc;
            }
            {
                sycl::event eq;
                runF(std::integral_constant<unsigned, 2>{}, false, sb, eq).wait();
                std::vector<float> h1((size_t)M * SS), a1(M);
                q.memcpy(h1.data(), sb, h1.size() * 4);
                q.memcpy(a1.data(), ac, (size_t)M * 4).wait();
                count(h1, a1, m1, x1, nullptr);
            }
            (void)rows_sum, (void)rows_max;
            ++cases;
            bad += misses != 0 || ldiff + bdiff + cdiff + rows_bad != 0;
            const double txb = std::min({tx2[0], tx2[1], tx2[2]});
            std::printf("%-5d %8ld | %8.3f %8.3f | %8.3f %8.3f %8.3f %8.3f | %10ld %8.4f %9.1f %9ld | %.1f / %.0f | "
                        "e2e: lists %ld, block lists %ld, marks %ld differ (of %d tokens); rows exact %.1f mean %ld max, %ld bad; "
                        "T %.3f ms, X2 %.3f / %.3f / %.3f ms (1 / 2 / 4 blocks per item), sel %.3f ms; "
                        "exact + sel %.3f ms, filter + T + X2 + sel %.3f ms\n",
                        ratio, n0, tb, ts, tf[0], tf[1], tf[2], tf[3], misses, worst, m2, x2, m1, blk_sum, ldiff, bdiff, cdiff,
                        M, rows_ex, rows_exmax, rows_bad, tt, tx2[0], tx2[2], tx2[1], tsel, ts + tsel, tf[1] + tt + txb + tsel);
        }
    }
    if (bad) std::printf("FAIL (%d of %d cases with rows outside the bound or lists that differ; %ld list differences)\n", bad, cases, e2e_bad);
    else std::printf("PASS (%d cases)\n", cases);
    return bad ? 1 : 0;
}
