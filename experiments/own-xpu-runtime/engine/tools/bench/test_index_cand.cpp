// OWN_IDX_CAND: the one-token index of the layers past 20 over the layer-20 candidate rows only
// (IndexerScoreBC + TopKSelC) against the full score (IndexerScoreB) + the masked select over all rows
// (TopKSelP<false>), bit for bit, and GPU time of each, at long lengths (ratio-1 rows = tokens). TopKSelC runs
// both final walks (in steps of 1,024, and by ranges of positions: rwalk, OWN_TOPK_R).
//   part 1: random queries / keys: scores at the candidate rows and the 512-entry lists
//   part 2: crafted score arrays, select only: heavy ties, +0 / -0, candidates mostly -inf (TopKSelC's fallback)
// The mask and block list come from TopKSelP<true> (block 8, top 2048, newest pinned) as in the engine.
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/test_index_cand.cpp -o test_index_cand
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <string>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    const int MAXN = 140000;
    float *dq = sycl::malloc_device<float>(4096, q), *dw = sycl::malloc_device<float>(32, q);
    uint16_t *dk = sycl::malloc_device<uint16_t>((size_t)MAXN * 128, q);
    float *sa = sycl::malloc_device<float>(MAXN + 64, q), *sb = sycl::malloc_device<float>(MAXN + 64, q);
    uint8_t *cand = sycl::malloc_device<uint8_t>(MAXN + 64, q);
    int32_t *bl = sycl::malloc_device<int32_t>(2048 + 64, q), *la = sycl::malloc_device<int32_t>(512, q),
            *lb = sycl::malloc_device<int32_t>(512, q);
    std::mt19937 rng(11);
    std::normal_distribution<float> nd(0.f, 1.f);
    std::vector<float> hq(4096), hw(32);
    std::vector<uint16_t> hk((size_t)MAXN * 128);
    for (auto &v : hq) v = nd(rng) * 0.1f;
    for (auto &v : hw) v = nd(rng);
    for (auto &v : hk) {
        const float f = nd(rng);
        uint32_t u;
        std::memcpy(&u, &f, 4);
        v = (uint16_t)(u >> 16);
    }
    q.memcpy(dq, hq.data(), hq.size() * 4);
    q.memcpy(dw, hw.data(), hw.size() * 4);
    q.memcpy(dk, hk.data(), hk.size() * 2).wait();
    auto us = [](sycl::event &e) {
        return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
    };
    using KB = TopKSelP<true>;
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
    constexpr size_t WG = 128;
    auto score_full = [&](int len, float *out) {
        const int T_ = (len + 31) / 32 * 32;
        const IndexerScoreB<ActF32> k{len, T_};
        const size_t n = ((size_t)T_ + WG - 1) / WG * WG;
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(32 * 128 + 32, h);
            h.parallel_for(sycl::nd_range<1>(n, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                k(it, dq, dk, dw, out, &lt[0]);
            });
        });
    };
    auto score_cand = [&](int len, float *out) {
        const int T_ = (len + 31) / 32 * 32;
        const IndexerScoreBC<ActF32> k{{len, T_}};
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(32 * 128 + 32, h);
            h.parallel_for(sycl::nd_range<1>((size_t)2048 * 8, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
                k(it, dq, dk, dw, out, bl, &lt[0]);
            });
        });
    };
    // compares la / lb, and sa / sb at the mask's rows; also the block list against the mask
    long bad = 0;
    auto compare = [&](int len, bool scores, const char *what) {
        std::vector<float> a(len), b(len);
        std::vector<uint8_t> cm(len);
        std::vector<int32_t> x(512), y(512), hb(2049);
        q.memcpy(a.data(), sa, (size_t)len * 4);
        q.memcpy(b.data(), sb, (size_t)len * 4);
        q.memcpy(cm.data(), cand, len);
        q.memcpy(hb.data(), bl, 2049 * 4);
        q.memcpy(x.data(), la, 512 * 4);
        q.memcpy(y.data(), lb, 512 * 4).wait();
        long nc = 0, sd = 0;
        for (int j = 0; j < len; ++j)
            if (cm[j]) { ++nc; if (scores && std::memcmp(&a[j], &b[j], 4)) ++sd; }
        std::vector<uint8_t> m2(len, 0);
        bool bb = hb[0] < 0 || hb[0] > 2048;
        for (int i = 0; !bb && i < hb[0]; ++i) {
            if (i && hb[1 + i] <= hb[i]) bb = true;
            for (int j = hb[1 + i] * 8; j < std::min(hb[1 + i] * 8 + 8, len); ++j) m2[j] = 1;
        }
        if (m2 != cm) bb = true;
        long ld = 0, neg = 0;
        for (int i = 0; i < 512; ++i) { ld += x[i] != y[i]; neg += x[i] < 0; }
        const bool ok = !sd && !ld && !bb;
        bad += !ok;
        std::printf("    %-34s len %6d: %5ld candidate rows (%4d blocks), %ld scores differ, %ld list entries differ"
                    " (%ld empty), blocks %s -> %s\n", what, len, nc, hb[0], sd, ld, neg, bb ? "WRONG" : "ok",
                    ok ? "SAME" : "DIFFERENT");
    };
    std::printf("part 1: random queries and keys (GPU us; full = score all rows + masked select over all rows)\n");
    std::printf("  %6s %10s %10s %10s %10s %10s %10s %10s\n", "len", "score all", "blocks", "select", "cand score",
                "cand sel", "ranges sel", "saved us");
    for (int len : {16500, 17000, 24000, 34000, 69000, 95000, 130000}) {
        double t[6] = {};
        const int REP = 20;
        for (int r = 0; r < REP + 1; ++r) {
            const int nb = (len + 7) / 8;
            auto e0 = score_full(len, sa);
            auto e1 = local(KB{nb, 2048, 0, 0, 0, 8, len}, (const float *)sa, (const uint8_t *)nullptr, bl, cand);
            auto e2 = local(KR{len, 512, 128, 512, len, 0, 0}, (const float *)sa, (const uint8_t *)cand, la, (uint8_t *)nullptr);
            q.fill(sb, std::nanf(""), MAXN + 64);
            auto e3 = score_cand(len, sb);
            auto e4 = local(TopKSelC{len, 512, 128, 512, 8}, (const float *)sb, (const uint8_t *)cand, (const int32_t *)bl, lb);
            q.wait();
            if (r == REP) compare(len, true, "random");
            q.fill(lb, -5, 512);
            auto e5 = local(TopKSelC{len, 512, 128, 512, 8, true}, (const float *)sb, (const uint8_t *)cand,
                            (const int32_t *)bl, lb);
            q.wait();
            if (r) { t[0] += us(e0); t[1] += us(e1); t[2] += us(e2); t[3] += us(e3); t[4] += us(e4); t[5] += us(e5); }
        }
        for (auto &v : t) v /= REP;
        std::printf("  %6d %10.1f %10.1f %10.1f %10.1f %10.1f %10.1f %10.1f\n", len, t[0], t[1], t[2], t[3], t[4],
                    t[5], t[0] + t[2] - t[3] - std::min(t[4], t[5]));
        compare(len, true, "random, select by ranges");
    }
    std::printf("part 2: crafted scores, select only (TopKSelC on the same array as the masked select)\n");
    std::vector<float> hs(MAXN);
    auto craft = [&](int len, int kind) {
        for (int j = 0; j < len; ++j) {
            const float f = nd(rng);
            if (kind == 0) hs[j] = std::floor(f * 1.5f);           // a few values: heavy ties at the threshold
            else if (kind == 1) hs[j] = f > 0.5f ? 0.0f : -0.0f;   // +0 and -0 only (one key)
            else if (kind == 2) hs[j] = -INFINITY;                 // all -inf but a few (fallback)
            else hs[j] = f;                                        // plain
        }
        if (kind == 2)
            for (int i = 0; i < 300; ++i) hs[(size_t)(rng() % len)] = nd(rng);
        q.memcpy(sa, hs.data(), (size_t)len * 4).wait();
    };
    const char *names[4] = {"ties (few values)", "+0 / -0 only", "mostly -inf (fallback)", "plain normal"};
    for (int kind = 0; kind < 4; ++kind)
        for (int len : {16391, 40000, 120001}) {
            craft(len, kind);
            const int nb = (len + 7) / 8;
            local(KB{nb, 2048, 0, 0, 0, 8, len}, (const float *)sa, (const uint8_t *)nullptr, bl, cand);
            local(KR{len, 512, 128, 512, len, 0, 0}, (const float *)sa, (const uint8_t *)cand, la, (uint8_t *)nullptr);
            local(TopKSelC{len, 512, 128, 512, 8}, (const float *)sa, (const uint8_t *)cand, (const int32_t *)bl, lb);
            q.wait();
            compare(len, false, names[kind]);
            q.fill(lb, -5, 512);
            local(TopKSelC{len, 512, 128, 512, 8, true}, (const float *)sa, (const uint8_t *)cand, (const int32_t *)bl, lb);
            q.wait();
            compare(len, false, (std::string(names[kind]) + ", by ranges").c_str());
        }
    std::printf(bad ? "FAIL (%ld cases differ)\n" : "PASS\n", bad);
    return bad ? 1 : 0;
}
