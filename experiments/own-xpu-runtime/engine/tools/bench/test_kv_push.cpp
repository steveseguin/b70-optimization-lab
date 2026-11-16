// Build + run (from experiments/own-xpu-runtime/engine): icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src tools/bench/test_kv_push.cpp -o test_kv_push && ONEAPI_DEVICE_SELECTOR=level_zero:1 ./test_kv_push
//
// kvshard push (2026-11-16; /home/steve/dsv41-work/kvshard/README-push.md): the push form's layout kernels
// (ops41sycl::KvPushCount / KvPushScan / KvPushSlots / KvPushCopy) for six owners, all on ONE card. Each simulated
// card d runs the four launches over the same lists into its own staging rows (its own chunk, the shared tail ring);
// the "pushes" are plain copies of card d's run [so + base[d], so + base[d] + n[d]) into the other five cards' staging
// rows at the same rows (what the backend's kvs_push does on the copy engines). Checks, every case and card:
//   - the bases / counts (hb) are the same on all six cards, form a layout (base 0 = 0, each class ends where the next
//     starts, inside the half's rows) and match the host's class counts;
//   - the slot lists are the same on all six cards; a skipped entry's slot is the entry; a row's slot names a staging
//     row inside [so, so + rows), each used exactly once;
//   - every staged row equals the full row (host memcmp) AND the row KvGather (the pull form, over the same chunks and
//     tail) stages for the same entry;
//   - KvStageCmpP (OWN_KV_SHARD=2's check of the push form) counts 0 differing words, and its rows / tail / own chunk /
//     peers / distinct counts match the host's.
// Cases: R 8 / 64 / 2048 rows per chunk; tail 1024 / 4096 rows; tokens M 1, 7 (half B: so = 7 x 512), 64 (half B),
// 256 (the engine's half), 260 (KvPushScan's second round); lists: kind 0 random rows ascending with -1 padding
// (lengths 0 .. 512), 1 tokens drawing from a shared pool of 700 rows (heavy overlap), 2 recent rows only (all from
// the tail), 3 old rows only (none from the tail). Rows: 120,000 random BF16 rows; chunk rows the tail serves and the
// tail's other slots hold NaN patterns, so a row taken from the wrong place shows. Time (R 2048, tail 4096, M 256,
// kind 0, card 0): the four launches together and KvGather alone (one card: no PCIe here; no cache flush).
// Env: ONLY=substring of the case tag. Ends PASS or FAIL (n of m cases). ~1.3 GB of card memory, ~0.5 GB of host.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
using namespace ops41sycl;

constexpr unsigned NO = 6;        // owners (cards)
constexpr unsigned HD = 512;      // BF16 words per row
constexpr long ROWS = 120000;     // rows of the source
constexpr unsigned MMAX = 260;    // tokens at most
constexpr size_t SROWS = (size_t)MMAX * 512; // staging rows per simulated card (every case's so + M x 512 fits)

// the row that owner d's chunk row l holds (the inverse of kvs_owner / kvs_local)
static long kvs_global_(size_t l, unsigned d, unsigned R, unsigned N) {
    return (long)(l / R) * (long)N * (long)R + (long)d * (long)R + (long)(l % R);
}
static double evus(const sycl::event &a, const sycl::event &b) {
    return (double)(b.get_profiling_info<sycl::info::event_profiling::command_end>() -
                    a.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}

int main() {
    sycl::queue q{sycl::gpu_selector_v, sycl::property_list{sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}}};
    std::printf("%s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    const char *only = std::getenv("ONLY");
    std::mt19937 rng(20261116u);
    std::vector<uint16_t> full((size_t)ROWS * HD);
    for (auto &x : full) x = (uint16_t)(rng() & 0xffffu);
    uint16_t *dfull = sycl::malloc_device<uint16_t>(full.size(), q);
    int32_t *cidx = sycl::malloc_device<int32_t>((size_t)MMAX * 512, q);
    uint16_t *gstg = sycl::malloc_device<uint16_t>(SROWS * HD, q);
    int32_t *gsl = sycl::malloc_device<int32_t>(SROWS, q);
    uint32_t *mark = sycl::malloc_device<uint32_t>((size_t)ROWS, q), *cw = sycl::malloc_device<uint32_t>(16, q);
    uint64_t *ct = sycl::malloc_device<uint64_t>(16, q);
    uint16_t *stg[NO] = {};
    int32_t *sl[NO] = {};
    uint32_t *tb[NO] = {}, *hb[NO] = {};
    bool alloc_ok = dfull && cidx && gstg && gsl && mark && cw && ct;
    for (unsigned d = 0; d < NO; ++d) {
        stg[d] = sycl::malloc_device<uint16_t>(SROWS * HD, q);
        sl[d] = sycl::malloc_device<int32_t>(SROWS, q);
        tb[d] = sycl::malloc_device<uint32_t>((size_t)MMAX * KVP_K, q);
        hb[d] = sycl::malloc_device<uint32_t>(2 * KVP_K, q);
        alloc_ok &= stg[d] && sl[d] && tb[d] && hb[d];
    }
    if (!alloc_ok) {
        std::printf("card allocation failed\n");
        return 2;
    }
    q.memcpy(dfull, full.data(), full.size() * 2).wait();
    q.fill(mark, 0u, (size_t)ROWS).wait();
    q.fill(cw, 0u, 16).wait();
    uint32_t stamp = 0;
    int fails = 0, cases = 0;
    // n distinct rows of [lo, hi) in ascending order (hi - lo >= n)
    auto pick = [&](long lo, long hi, int n) {
        std::vector<long> v;
        while ((int)v.size() < n) {
            v.push_back(lo + (long)(rng() % (uint32_t)(hi - lo)));
            if ((int)v.size() == n) {
                std::sort(v.begin(), v.end());
                v.erase(std::unique(v.begin(), v.end()), v.end());
            }
        }
        return v;
    };
    struct Case {
        unsigned M;
        size_t so;
        int kind;
    };
    const Case cs[] = {{1, 0, 0},   {7, 7 * 512, 0}, {64, 64 * 512, 0}, {64, 0, 1},  {256, 0, 0},
                       {256, 0, 1}, {256, 0, 2},     {256, 0, 3},       {260, 0, 0}};
    std::vector<uint16_t> hst, hg;
    std::vector<int32_t> hs, hs0, hgs;
    for (unsigned R : {8u, 64u, 2048u})
        for (unsigned TT : {1024u, 4096u}) {
            const long tail0 = std::max(0L, ROWS - (long)TT + 512);
            const size_t nloc = (size_t)((ROWS + (long)NO * R - 1) / ((long)NO * R)) * R;
            uint16_t *ch[NO] = {};
            for (unsigned d = 0; d < NO; ++d) { // owner d's chunk (rows past the end, rows the tail serves: NaN patterns)
                std::vector<uint16_t> c(nloc * HD, (uint16_t)0x7fc1);
                for (size_t l = 0; l < nloc; ++l) {
                    const long r = kvs_global_(l, d, R, NO);
                    if (r < tail0) std::memcpy(&c[l * HD], &full[(size_t)r * HD], HD * 2);
                    else if (r < ROWS) std::fill(c.begin() + (long)(l * HD), c.begin() + (long)((l + 1) * HD), (uint16_t)0x7fc2);
                }
                ch[d] = sycl::malloc_device<uint16_t>(nloc * HD, q);
                if (!ch[d]) {
                    std::printf("card allocation failed\n");
                    return 2;
                }
                q.memcpy(ch[d], c.data(), c.size() * 2).wait();
            }
            uint16_t *tail = sycl::malloc_device<uint16_t>((size_t)TT * HD, q);
            {
                std::vector<uint16_t> t((size_t)TT * HD, (uint16_t)0x7fc3);
                for (long r = tail0; r < ROWS; ++r) std::memcpy(&t[(size_t)(r % TT) * HD], &full[(size_t)r * HD], HD * 2);
                q.memcpy(tail, t.data(), t.size() * 2).wait();
            }
            for (const Case &k : cs) {
                const unsigned M = k.M;
                const size_t so = k.so, ne = (size_t)M * 512;
                char tag[96];
                std::snprintf(tag, sizeof tag, "R%u TT%u M%u so%zu kind%d", R, TT, M, so, k.kind);
                if (only && !std::strstr(tag, only)) continue;
                ++cases;
                // the lists (each token's rows ascending, then -1: as the selects leave them)
                std::vector<int32_t> hc(ne, -1);
                std::vector<long> pool;
                if (k.kind == 1) {
                    pool = pick(0, tail0, 600);
                    const std::vector<long> p2 = pick(tail0, ROWS, 100);
                    pool.insert(pool.end(), p2.begin(), p2.end());
                }
                for (unsigned t = 0; t < M; ++t) {
                    std::vector<long> v;
                    if (k.kind == 0) v = pick(0, ROWS, (int)(rng() % 513));
                    else if (k.kind == 1) {
                        std::vector<long> p = pool;
                        std::shuffle(p.begin(), p.end(), rng);
                        p.resize(400 + rng() % 113);
                        std::sort(p.begin(), p.end());
                        v = p;
                    } else if (k.kind == 2) v = pick(tail0, ROWS, 512);
                    else v = pick(0, tail0, 512);
                    for (size_t i = 0; i < v.size(); ++i) hc[(size_t)t * 512 + i] = (int32_t)(128 + v[i]);
                }
                q.memcpy(cidx, hc.data(), ne * 4).wait();
                // the host's classes: per class the entries, the distinct rows
                uint64_t ncl[KVP_K] = {}, nrow = 0;
                std::vector<long> rows;
                for (size_t e = 0; e < ne; ++e) {
                    const int kc = kvp_class(hc[e], tail0, R, NO);
                    if (kc < 0) continue;
                    ++ncl[kc], ++nrow;
                    rows.push_back((long)hc[e] - 128);
                }
                std::sort(rows.begin(), rows.end());
                const uint64_t nu = (uint64_t)(std::unique(rows.begin(), rows.end()) - rows.begin());
                // the four launches on each simulated card
                std::string why;
                uint32_t h[NO][2 * KVP_K] = {};
                double tpush = 0;
                for (unsigned d = 0; d < NO; ++d) {
                    q.fill(stg[d], (uint16_t)0x7fc4, SROWS * HD);
                    q.fill(sl[d], (int32_t)-7, SROWS);
                    q.fill(tb[d], 0xdeadu, (size_t)MMAX * KVP_K);
                    q.fill(hb[d], 0xdeadu, 2 * KVP_K).wait();
                    const int32_t *ci = cidx;
                    uint32_t *tbd = tb[d], *hbd = hb[d];
                    int32_t *sld = sl[d];
                    uint16_t *sd = stg[d];
                    const uint16_t *own = ch[d], *tl = tail;
                    const KvPushCount k1{M, R, NO, tail0};
                    const KvPushScan k2{M};
                    const KvPushSlots k3{M, R, NO, tail0, so};
                    const KvPushCopy k4{HD, M, R, NO, TT, d, tail0, so};
                    sycl::event a = q.parallel_for(sycl::nd_range<1>((size_t)M * KvPushCount::WG, KvPushCount::WG),
                                                   [=](sycl::nd_item<1> it) { k1(it, ci, tbd); });
                    q.parallel_for(sycl::nd_range<1>(KvPushScan::WG, KvPushScan::WG), [=](sycl::nd_item<1> it) { k2(it, tbd, hbd); });
                    q.parallel_for(sycl::nd_range<1>((size_t)M * KvPushSlots::WG, KvPushSlots::WG),
                                   [=](sycl::nd_item<1> it) { k3(it, ci, (const uint32_t *)tbd, sld); });
                    sycl::event z = q.parallel_for(sycl::nd_range<1>(ne * KvPushCopy::WG, KvPushCopy::WG),
                                                   [=](sycl::nd_item<1> it) { k4(it, ci, (const int32_t *)sld, tl, own, sd); });
                    q.memcpy(h[d], hbd, sizeof h[d]).wait();
                    if (d == 0) tpush = evus(a, z);
                }
                // the bases / counts: the same everywhere, a layout, the host's counts
                for (unsigned d = 1; d < NO; ++d)
                    if (std::memcmp(h[d], h[0], sizeof h[0])) why += " hb differs on card " + std::to_string(d) + ";";
                bool lay = h[0][0] == 0;
                for (unsigned c = 0; c < KVP_K; ++c) {
                    const uint64_t end = (uint64_t)h[0][c] + h[0][KVP_K + c];
                    lay &= end <= ne && (c + 1 < KVP_K ? end == h[0][c + 1] : true) && h[0][KVP_K + c] == ncl[c];
                }
                const uint64_t total = (uint64_t)h[0][KVP_K - 1] + h[0][2 * KVP_K - 1];
                if (!lay || total != nrow) why += " hb is not the host's layout;";
                if (why.empty()) {
                    // the pushes: card d's run into the five others at the same rows
                    for (unsigned d = 0; d < NO; ++d) {
                        const size_t b0 = so + h[0][d], n = h[0][KVP_K + d];
                        if (n)
                            for (unsigned p = 0; p < NO; ++p)
                                if (p != d) q.memcpy(stg[p] + b0 * HD, stg[d] + b0 * HD, n * HD * 2);
                    }
                    q.wait();
                    // the pull form over the same chunks and tail
                    q.fill(gstg, (uint16_t)0x7fc5, SROWS * HD);
                    q.fill(gsl, (int32_t)-7, SROWS).wait();
                    KvGather kg{};
                    for (unsigned d = 0; d < NO; ++d) kg.set_ch(d, ch[d]);
                    kg.hd = HD, kg.m = M, kg.R = R, kg.N = NO, kg.TT = TT, kg.tail0 = tail0, kg.so = so;
                    {
                        const int32_t *ci = cidx;
                        const uint16_t *tl = tail;
                        uint16_t *gs = gstg;
                        int32_t *gl = gsl;
                        sycl::event eg = q.parallel_for(sycl::nd_range<1>(ne * KvGather::WG, KvGather::WG),
                                                        [=](sycl::nd_item<1> it) { kg(it, ci, tl, gs, gl); });
                        eg.wait();
                        if (R == 2048 && TT == 4096 && M == 256 && k.kind == 0)
                            std::printf("time M256 R2048 TT4096 kind0: push layout + own rows (4 launches) %.1f us, "
                                        "KvGather %.1f us\n", tpush, evus(eg, eg));
                    }
                    hg.resize(ne * HD);
                    hgs.resize(ne);
                    q.memcpy(hg.data(), gstg + so * HD, ne * HD * 2);
                    q.memcpy(hgs.data(), gsl + so, ne * 4).wait();
                    std::vector<int> used(ne, 0);
                    long bad_sl = 0, bad_row = 0, bad_g = 0, bad_gs = 0, bad_cmp = 0;
                    for (unsigned d = 0; d < NO; ++d) {
                        hst.resize(ne * HD);
                        hs.resize(ne);
                        q.memcpy(hst.data(), stg[d] + so * HD, ne * HD * 2);
                        q.memcpy(hs.data(), sl[d] + so, ne * 4).wait();
                        if (d == 0) hs0 = hs;
                        else if (hs != hs0) why += " slot lists differ on card " + std::to_string(d) + ";";
                        for (size_t e = 0; e < ne; ++e) {
                            const int32_t v = hc[e], s = hs[e];
                            if (d == 0 && hgs[e] != (v < 128 ? v : (int32_t)(128 + so + e))) ++bad_gs;
                            if (v < 128) {
                                bad_sl += s != v;
                                continue;
                            }
                            const long srow = (long)s - 128, r = (long)v - 128;
                            if (srow < (long)so || srow >= (long)(so + total)) {
                                ++bad_sl;
                                continue;
                            }
                            if (d == 0) ++used[(size_t)(srow - (long)so)];
                            const uint16_t *x = &hst[(size_t)(srow - (long)so) * HD];
                            bad_row += std::memcmp(x, &full[(size_t)r * HD], HD * 2) != 0;
                            bad_g += std::memcmp(x, &hg[e * HD], HD * 2) != 0;
                        }
                        // OWN_KV_SHARD=2's check of the push form on the card
                        q.fill(ct, (uint64_t)0, 16).wait();
                        if (++stamp == 0u) stamp = 1u;
                        const KvStageCmpP kp{KvStageCmp{HD, M, R, NO, TT, d, stamp, tail0, so}};
                        const KvStageFold kf{};
                        const int32_t *ci = cidx, *sld = sl[d];
                        const uint16_t *sd = stg[d], *fu = dfull;
                        uint32_t *mk = mark, *w = cw;
                        uint64_t *cc = ct;
                        q.parallel_for(sycl::nd_range<1>(ne * KvStageCmpP::WG, KvStageCmpP::WG),
                                       [=](sycl::nd_item<1> it) { kp(it, ci, sld, sd, fu, mk, w); });
                        q.parallel_for(sycl::nd_range<1>(1, 1), [=](sycl::nd_item<1> it) { kf(it, w, cc); });
                        uint64_t hc8[16] = {};
                        q.memcpy(hc8, ct, sizeof hc8).wait();
                        const uint64_t own = d < NO ? ncl[d] : 0;
                        if (hc8[1] || hc8[0] != nrow || hc8[2] != ncl[NO] || hc8[3] != own || hc8[4] != nrow - ncl[NO] - own ||
                            hc8[5] != nu || hc8[7] != 1)
                            ++bad_cmp;
                    }
                    long unused = 0;
                    for (size_t i = 0; i < (size_t)total; ++i) unused += used[i] != 1;
                    if (bad_sl || bad_row || bad_g || bad_gs || bad_cmp || unused) {
                        char b[256];
                        std::snprintf(b, sizeof b, " slots %ld bad, rows %ld differ from the full rows, %ld from KvGather's, "
                                                   "KvGather slots %ld bad, KvStageCmpP %ld cards off, staging rows not used once %ld;",
                                      bad_sl, bad_row, bad_g, bad_gs, bad_cmp, unused);
                        why += b;
                    }
                }
                if (why.empty())
                    std::printf("%-34s ok: %llu rows (tail %llu), runs %u %u %u %u %u %u\n", tag, (unsigned long long)nrow,
                                (unsigned long long)ncl[NO], h[0][KVP_K + 0], h[0][KVP_K + 1], h[0][KVP_K + 2],
                                h[0][KVP_K + 3], h[0][KVP_K + 4], h[0][KVP_K + 5]);
                else {
                    ++fails;
                    std::printf("%-34s FAIL:%s\n", tag, why.c_str());
                }
            }
            for (unsigned d = 0; d < NO; ++d) sycl::free(ch[d], q);
            sycl::free(tail, q);
        }
    if (fails) std::printf("FAIL (%d of %d cases)\n", fails, cases);
    else std::printf("PASS (%d cases)\n", cases);
    return fails ? 1 : 0;
}
