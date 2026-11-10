// TopKSelP (the on-card index top-k) against the host index()'s selection,
// bit for bit, on random cases: ties, -0/+0, -inf, candidate masks, and
// lengths around the 512 / 2048-block edges. Also times one call per length.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

// host reference: backend_sycl_v41.hpp index(), long path
static void host_cand(const std::vector<float> &hs, long len, std::vector<uint8_t> &cand) {
    const int bs = 8, tb = 2048;
    const int nb = (int)((len + bs - 1) / bs);
    std::vector<float> bsc(nb, -INFINITY);
    for (long j = 0; j < len; ++j) bsc[j / bs] = std::max(bsc[j / bs], hs[j]);
    bsc[(len - 1) / bs] = INFINITY;
    std::vector<int> ord(nb);
    for (int i = 0; i < nb; ++i) ord[i] = i;
    const int tk = std::min(tb, nb);
    std::partial_sort(ord.begin(), ord.begin() + tk, ord.end(),
                      [&](int a, int b) { return bsc[a] > bsc[b] || (bsc[a] == bsc[b] && a < b); });
    cand.assign(len, 0);
    for (int i = 0; i < tk; ++i)
        if (bsc[ord[i]] > -INFINITY)
            for (long j = (long)ord[i] * bs; j < std::min<long>((long)(ord[i] + 1) * bs, len); ++j) cand[j] = 1;
}
static std::vector<int32_t> host_sel(std::vector<float> hs, long len, const std::vector<uint8_t> *cand) {
    if (cand)
        for (long j = 0; j < len && j < (long)cand->size(); ++j)
            if (!(*cand)[j]) hs[j] = -INFINITY;
    std::vector<int32_t> sel(512, -1);
    const int nk = (int)std::min<long>(512, len);
    std::vector<int32_t> ord(len);
    for (long j = 0; j < len; ++j) ord[j] = (int32_t)j;
    std::partial_sort(ord.begin(), ord.begin() + nk, ord.end(),
                      [&](int32_t a, int32_t b) { return hs[a] > hs[b] || (hs[a] == hs[b] && a < b); });
    std::sort(ord.begin(), ord.begin() + nk);
    for (int i = 0; i < nk; ++i) sel[i] = ord[i] + 128;
    return sel;
}

int main(int argc, char **argv) {
    const int cases = argc > 1 ? atoi(argv[1]) : 400;
    sycl::queue q{sycl::gpu_selector_v, sycl::property::queue::in_order{}};
    const long MAXN = 140000;
    float *sc = sycl::malloc_device<float>(MAXN, q);
    uint8_t *cd = sycl::malloc_device<uint8_t>(MAXN, q);
    int32_t *out = sycl::malloc_device<int32_t>(512, q);
    using KR = TopKSelP<false>;
    using KB = TopKSelP<true>;
    constexpr size_t SLM = (size_t)KR::NSG * 256 + 8;
    auto run = [&](auto k, const float *a, const uint8_t *ci, int32_t *o, uint8_t *co) {
        return q.submit([&](sycl::handler &h) {
            sycl::local_accessor<float, 1> lt(SLM, h);
            h.parallel_for(sycl::nd_range<1>(1024, 1024),
                           [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, a, ci, o, co, &lt[0]); });
        });
    };
    std::mt19937_64 rng(12345);
    long bad = 0, ncand_diff = 0, masked_cases = 0, tie_cases = 0;
    const long lens_fixed[] = {513, 514, 600, 1024, 1025, 2047, 2048, 2049, 4096, 16383, 16384, 16385, 16392,
                               16393, 20000, 40000, 65536, 131072};
    for (int cs = 0; cs < cases; ++cs) {
        long len = cs < (int)(sizeof(lens_fixed) / sizeof(long)) ? lens_fixed[cs]
                                                                    : 513 + (long)(rng() % (cs % 5 == 0 ? 130000 : 20000));
        const int mode = (int)(rng() % 6);
        std::vector<float> hs(len);
        for (long j = 0; j < len; ++j) {
            const uint64_t r = rng();
            float v;
            switch (mode) {
            case 0: v = std::ldexp((float)(r % 1000000) / 1e6f, (int)(r >> 40) % 20 - 5); break; // spread
            case 1: v = (float)(r % 7); break;                                                      // heavy ties
            case 2: v = (r % 3 == 0) ? -0.0f : ((r % 3 == 1) ? 0.0f : (float)(r % 5)); break;  // signed zeros
            case 3: v = (r % 4 == 0) ? -INFINITY : (float)((int)(r % 2001) - 1000) * 0.25f; break; // -inf + negatives
            case 4: v = 1.0f + (float)(r % 3) * 1e-7f; break;                                       // near-equal
            default: v = (float)(r % 100000) * 0.5f - 20000.0f; break;
            }
            hs[j] = v;
        }
        if (mode == 1 || mode == 2 || mode == 4) ++tie_cases;
        q.memcpy(sc, hs.data(), len * 4).wait();
        // layer-20 form: candidate blocks, then the unmasked top-512 (as index() at L == 20)
        std::vector<uint8_t> hc;
        host_cand(hs, len, hc);
        const int nb = (int)((len + 7) / 8);
        run(KB{nb, 2048, 0, 0, 0, 8, (int)len}, sc, nullptr, nullptr, cd);
        std::vector<uint8_t> dc(len);
        q.memcpy(dc.data(), cd, len).wait();
        if (dc != hc) {
            ++ncand_diff;
            long first = 0;
            while (dc[first] == hc[first]) ++first;
            printf("case %d len %ld mode %d: candidate mask differs at row %ld\n", cs, len, mode, first);
        }
        if (nb > 2048) ++masked_cases;
        for (int masked = 0; masked < 2; ++masked) {
            // a later layer: different scores under the layer-20 mask
            if (masked)
                for (long j = 0; j < len; ++j)
                    if (rng() % 3 == 0) hs[j] = (float)(rng() % 9) - 4.0f;
            if (masked) q.memcpy(sc, hs.data(), len * 4).wait();
            const auto ref = host_sel(hs, len, masked ? &hc : nullptr);
            run(KR{(int)len, 512, 128, 512, masked ? (int)len : 0, 0, 0}, sc, masked ? cd : nullptr, out, nullptr);
            std::vector<int32_t> got(512);
            q.memcpy(got.data(), out, 512 * 4).wait();
            if (got != ref) {
                ++bad;
                int first = 0;
                while (got[first] == ref[first]) ++first;
                printf("case %d len %ld mode %d masked %d: list differs at %d (got %d want %d)\n", cs, len, mode,
                       masked, first, got[first], ref[first]);
            }
        }
    }
    printf("%d cases (%ld tie-heavy, %ld with more than 2048 blocks): %ld list mismatches, %ld mask mismatches\n",
           cases, tie_cases, masked_cases, bad, ncand_diff);
    // timing: one rows call (and one blocks call) per length, GPU time
    for (long len : {600L, 1700L, 3400L, 10000L, 40000L, 131072L}) {
        std::vector<float> hs(len);
        for (auto &v : hs) v = (float)(rng() % 1000000) * 1e-3f;
        q.memcpy(sc, hs.data(), len * 4).wait();
        double tr = 1e30, tb = 1e30;
        for (int r = 0; r < 20; ++r) {
            auto t0 = std::chrono::steady_clock::now();
            run(KR{(int)len, 512, 128, 512, 0, 0, 0}, sc, nullptr, out, nullptr).wait();
            auto t1 = std::chrono::steady_clock::now();
            run(KB{(int)((len + 7) / 8), 2048, 0, 0, 0, 8, (int)len}, sc, nullptr, nullptr, cd).wait();
            auto t2 = std::chrono::steady_clock::now();
            tr = std::min(tr, std::chrono::duration<double, std::micro>(t1 - t0).count());
            tb = std::min(tb, std::chrono::duration<double, std::micro>(t2 - t1).count());
        }
        printf("len %6ld: rows top-512 %7.1f us, blocks top-2048 %7.1f us (wall per call, incl. submit)\n", len, tr, tb);
    }
    return bad || ncand_diff ? 1 : 0;
}
