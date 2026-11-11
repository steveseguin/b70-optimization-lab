// The one-token step's attention score and softmax at the six-card shapes (12 or 16 heads of 512 per card), one card:
//   score   SparseScoreHG<512, HG> for HG = 4 (production: (heads / 4) * (n / 32) sub-groups), 2 and 1 (more
//           sub-groups, each with fewer heads; every (head, slot) sum keeps the same serial j order and operations)
//   softmax SparseSoftmaxPN<640> (the trimmed lists' kernel, 256 registers; "repo") against a copy of it (SoftmaxPNOld;
//           a bit-mask form tried 2026-11-11 also built at 256 registers and ran slower: dropped), a lean form
//           (SoftmaxPNLean: runtime slot loops, no arrays, exp recomputed in the store pass; 128 registers) and
//           SparseSoftmaxP<n> (the 640-slot kernel's form built for the slot count; 128 registers; OWN_ATT_PK)
// Result (card 3, 2026-11-11, ad4-card3.txt): all PASS; n = 160 score + softmax 13.8 us (HG 4 + PN) -> 6.1 us
// (HG 1 + P<160>); n = 640 13.1 us (HG 4 + P<640>, production) -> 10.8-11.0 us (HG 1).
// Every candidate BITWISE against production (score array memcmp). n = 160 (prompt 1's 128 window slots + 32) and
// 640 (128 + 512 chosen rows), 1 in 8 compressed slots skipped (-1) for n = 640; trimmed lists (n < 640) keep every
// slot. Time: mean of 200 launches each (events), after warm-up; also a back-to-back chain score -> softmax timed by
// the host clock (no profiling) for HG = 4 / old softmax against HG = 1 / new softmax.
//   cd engine; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_attn_dec.cpp -o $S/bench_attn_dec
//   ONEAPI_DEVICE_SELECTOR=level_zero:N $S/bench_attn_dec      (exit 1 on any difference)
#include <sycl/sycl.hpp>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

// the softmax as it was before 2026-11-11 (sycl_v41.hpp SparseSoftmaxPN, ok[K] / e0[K] arrays)
template <int NI> struct SoftmaxPNOld {
    int heads, n;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *sinks, const int32_t *idxs, float *score) const {
        sycl::sub_group sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id();
        const int h = (int)it.get_group_linear_id();
        if (h >= heads) return;
        constexpr int K = NI / 32;
        const int kn = n / 32;
        float *s = score + (size_t)h * n;
        float v[K];
        int ok[K];
        const float sk = sinks[h];
        float mx = sk;
#pragma unroll
        for (int k = 0; k < K; ++k) {
            ok[k] = 0;
            v[k] = 0;
            if (k < kn) {
                ok[k] = idxs[32 * k + lane] >= 0 ? 1 : 0;
                v[k] = s[32 * k + lane];
            }
            if (ok[k]) mx = v[k] > mx ? v[k] : mx;
        }
        for (int w_ = 16; w_; w_ >>= 1) {
            const float o = sycl::select_from_group(sg, mx, lane ^ w_);
            mx = o > mx ? o : mx;
        }
        float sum = sycl::exp(sk - mx);
        float e0[K];
#pragma unroll
        for (int k = 0; k < K; ++k) {
            if (ok[k]) v[k] = sycl::exp(v[k] - mx);
            e0[k] = ok[k] ? v[k] : 0.0f;
        }
#pragma unroll
        for (int k = 0; k < K; ++k)
            if (k < kn)
#pragma unroll
                for (int l2 = 0; l2 < 32; ++l2) sum += sycl::select_from_group(sg, e0[k], l2);
#pragma unroll
        for (int k = 0; k < K; ++k)
            if (ok[k]) s[32 * k + lane] = v[k] / sum;
    }
};

// lean form: no per-slot arrays (runtime loops over the kn slot words, the exp terms recomputed in the store pass:
// the same exp of the same argument, so the same bits), meant to build at 128 registers
template <int UNR> struct SoftmaxPNLean {
    int heads, n;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *sinks, const int32_t *idxs, float *score) const {
        sycl::sub_group sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id();
        const int h = (int)it.get_group_linear_id();
        if (h >= heads) return;
        const int kn = n / 32;
        float *s = score + (size_t)h * n;
        const float sk = sinks[h];
        float mx = sk;
#pragma unroll UNR
        for (int k = 0; k < kn; ++k) {
            const float x = s[32 * k + lane];
            if (idxs[32 * k + lane] >= 0) mx = x > mx ? x : mx;
        }
        for (int w_ = 16; w_; w_ >>= 1) {
            const float o = sycl::select_from_group(sg, mx, lane ^ w_);
            mx = o > mx ? o : mx;
        }
        float sum = sycl::exp(sk - mx);
#pragma unroll UNR
        for (int k = 0; k < kn; ++k) {
            const float e0 = idxs[32 * k + lane] >= 0 ? sycl::exp(s[32 * k + lane] - mx) : 0.0f;
#pragma unroll
            for (int l2 = 0; l2 < 32; ++l2) sum += sycl::select_from_group(sg, e0, l2);
        }
#pragma unroll UNR
        for (int k = 0; k < kn; ++k)
            if (idxs[32 * k + lane] >= 0) s[32 * k + lane] = sycl::exp(s[32 * k + lane] - mx) / sum;
    }
};

template <typename K, typename... A> static sycl::event lsg(sycl::queue &q, size_t groups, K k, A... a) {
    return q.parallel_for(sycl::nd_range<1>(groups * 32, 32), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, a...); });
}
static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}

int main() {
    sycl::queue q{sycl::gpu_selector_v, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    sycl::queue qn{q.get_context(), q.get_device(), {sycl::property::queue::in_order{}}};
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    constexpr unsigned HD = 512, WIN = 128, NC = 4096, NMAX = 640, HMAX = 16;
    std::mt19937 rng(11);
    std::normal_distribution<float> nd(0.f, 1.f);
    auto bf = [](float f) { uint32_t u; std::memcpy(&u, &f, 4); return (uint16_t)((u + 0x7fff + ((u >> 16) & 1)) >> 16); };
    std::vector<uint16_t> hkw((size_t)WIN * HD), hkc((size_t)NC * HD);
    for (auto &v : hkw) v = bf(nd(rng));
    for (auto &v : hkc) v = bf(nd(rng));
    std::vector<float> hq((size_t)HMAX * HD), hs(HMAX);
    for (auto &v : hq) v = 0.3f * nd(rng);
    for (auto &v : hs) v = nd(rng);
    uint16_t *kw = sycl::malloc_device<uint16_t>(hkw.size(), q), *kc = sycl::malloc_device<uint16_t>(hkc.size(), q);
    float *qd = sycl::malloc_device<float>(hq.size(), q), *sk = sycl::malloc_device<float>(HMAX, q);
    int32_t *ix = sycl::malloc_device<int32_t>(NMAX, q);
    float *sa = sycl::malloc_device<float>((size_t)HMAX * NMAX, q), *sb = sycl::malloc_device<float>((size_t)HMAX * NMAX, q);
    q.memcpy(kw, hkw.data(), hkw.size() * 2);
    q.memcpy(kc, hkc.data(), hkc.size() * 2);
    q.memcpy(qd, hq.data(), hq.size() * 4);
    q.memcpy(sk, hs.data(), HMAX * 4).wait();
    int fail = 0;
    { // warm the card's clock (an idle card runs its first kernels slower)
        std::vector<int32_t> hix(640);
        for (unsigned i = 0; i < 640; ++i) hix[i] = (int)i;
        q.memcpy(ix, hix.data(), 640 * 4).wait();
        const auto t0 = std::chrono::steady_clock::now();
        while (std::chrono::steady_clock::now() - t0 < std::chrono::milliseconds(300)) {
            for (int i = 0; i < 50; ++i) lsg(qn, 80, SparseScoreHG<512, 4>{640, 16, (int)WIN, (int)HD}, (const float *)qd, (const uint16_t *)kw, (const uint16_t *)kc, (const int32_t *)ix, sa);
            qn.wait();
        }
    }
    for (unsigned n : {160u, 640u}) {
        std::vector<int32_t> hix(n);
        for (unsigned i = 0; i < n; ++i) hix[i] = i < WIN ? (int)i : (n == 640 && rng() % 8 == 0 ? -1 : (int)(WIN + rng() % NC));
        q.memcpy(ix, hix.data(), n * 4).wait();
        for (int nh : {12, 16}) {
            const size_t ns = (size_t)nh * n;
            auto score = [&](sycl::queue &qq, int hg, float *dst) -> sycl::event {
                const size_t gb = (size_t)(nh / hg) * (n / 32);
                if (hg == 4) return lsg(qq, gb, SparseScoreHG<512, 4>{(int)n, nh, (int)WIN, (int)HD}, (const float *)qd, (const uint16_t *)kw, (const uint16_t *)kc, (const int32_t *)ix, dst);
                if (hg == 2) return lsg(qq, gb, SparseScoreHG<512, 2>{(int)n, nh, (int)WIN, (int)HD}, (const float *)qd, (const uint16_t *)kw, (const uint16_t *)kc, (const int32_t *)ix, dst);
                return lsg(qq, gb, SparseScoreHG<512, 1>{(int)n, nh, (int)WIN, (int)HD}, (const float *)qd, (const uint16_t *)kw, (const uint16_t *)kc, (const int32_t *)ix, dst);
            };
            // form 0 old (copy), 1 repo PN, 2 lean, 3 lean unrolled by 2, 4 lean unrolled by 4
            auto smax = [&](sycl::queue &qq, int form, float *dst) -> sycl::event {
                switch (form) {
                case 1: return lsg(qq, (size_t)nh, SparseSoftmaxPN<640>{nh, (int)n}, (const float *)sk, (const int32_t *)ix, dst);
                case 2: return lsg(qq, (size_t)nh, SoftmaxPNLean<1>{nh, (int)n}, (const float *)sk, (const int32_t *)ix, dst);
                case 3: return lsg(qq, (size_t)nh, SoftmaxPNLean<2>{nh, (int)n}, (const float *)sk, (const int32_t *)ix, dst);
                case 4: return lsg(qq, (size_t)nh, SoftmaxPNLean<4>{nh, (int)n}, (const float *)sk, (const int32_t *)ix, dst);
                case 5: // SparseSoftmaxP<n>: the production 640-slot kernel's form at a compile-time n (stride n)
                    if (n == 160) return lsg(qq, (size_t)nh, SparseSoftmaxP<160>{nh}, (const float *)sk, (const int32_t *)ix, dst);
                    return lsg(qq, (size_t)nh, SparseSoftmaxP<640>{nh}, (const float *)sk, (const int32_t *)ix, dst);
                default: return lsg(qq, (size_t)nh, SoftmaxPNOld<640>{nh, (int)n}, (const float *)sk, (const int32_t *)ix, dst);
                }
            };
            static const char *smn[6] = {"old", "repo", "lean", "lean u2", "lean u4", "P<n>"};
            auto same = [&](const char *what) {
                std::vector<float> a(ns), b(ns);
                q.memcpy(a.data(), sa, ns * 4);
                q.memcpy(b.data(), sb, ns * 4).wait();
                size_t bad = 0;
                for (size_t i = 0; i < ns; ++i) bad += std::memcmp(&a[i], &b[i], 4) != 0;
                std::printf("    %-34s %s (%zu of %zu differ)\n", what, bad ? "FAIL" : "PASS", bad, ns);
                fail += bad != 0;
            };
            std::printf("n = %u slots, %d heads\n", n, nh);
            for (int hg : {2, 1}) {
                q.memset(sa, 0xff, (size_t)HMAX * NMAX * 4);
                q.memset(sb, 0xff, (size_t)HMAX * NMAX * 4).wait();
                score(q, 4, sa);
                score(q, hg, sb).wait();
                char t[64];
                std::snprintf(t, sizeof t, "score HG = %d vs HG = 4", hg);
                same(t);
            }
            for (int f = 1; f < 6; ++f) {
                score(q, 4, sa);
                score(q, 4, sb);
                smax(q, 0, sa);
                smax(q, f, sb).wait();
                char t[64];
                std::snprintf(t, sizeof t, "softmax %s vs old", smn[f]);
                same(t);
            }
            // times
            for (int hg : {4, 2, 1}) {
                double t = 0;
                for (int r = 0; r < 220; ++r) {
                    auto e = score(q, hg, sa);
                    e.wait();
                    if (r >= 20) t += ev_us(e);
                }
                std::printf("    score HG = %d: %6.2f us (%zu sub-groups)\n", hg, t / 200, (size_t)(nh / hg) * (n / 32));
            }
            for (int f = 0; f < 6; ++f) {
                double t = 0;
                for (int r = 0; r < 220; ++r) {
                    score(q, 4, sa);
                    auto e = smax(q, f, sa);
                    e.wait();
                    if (r >= 20) t += ev_us(e);
                }
                std::printf("    softmax %-8s %6.2f us\n", smn[f], t / 200);
            }
            // host-clock chains: 100 x (score, softmax), production vs candidate, no profiling
            const int fhg[10] = {4, 4, 2, 1, 4, 2, 1, 4, 2, 1};
            const int fsl[10] = {0, 1, 1, 0, 2, 2, 2, 5, 5, 5};
            for (int form = 0; form < 10; ++form) {
                std::vector<double> v;
                for (int rep = 0; rep < 9; ++rep) {
                    qn.wait();
                    const auto t0 = std::chrono::steady_clock::now();
                    for (int i = 0; i < 100; ++i) {
                        score(qn, fhg[form], sa);
                        smax(qn, fsl[form], sa);
                    }
                    qn.wait();
                    if (rep >= 2) v.push_back(std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - t0).count() / 100);
                }
                std::sort(v.begin(), v.end());
                std::printf("    chain score + softmax, HG = %d + %-5s %6.2f us per pair (host clock)\n", fhg[form],
                            smn[fsl[form]], v[v.size() / 2]);
            }
        }
    }
    std::printf("%s\n", fail ? "FAIL" : "PASS");
    return fail ? 1 : 0;
}
