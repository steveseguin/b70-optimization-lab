// The expert-major routed kernels of multi-token steps (checks of 1-6 tokens, prompt blocks): production RoutedU
// (sycl_v41.hpp, RUFmt*: RoutedIQ2XXSU0 ...) against RoutedIQ2XXSU ... (sycl_v41_routed_r2.hpp: RoutedU3, RU3*, what
// the backend's routed_m runs), BITWISE on every output float, on the groups production's ExpertGroupM writes:
//   pair: gate + up in one launch (w2 / out2), 384 rows per expert, 20 blocks; down: per-slot x, 864 rows, 9 blocks
//   M tokens (6M slots) 1-6, 16, 64 with cap 6 (MT 6 kernels, as OWN_MT_EU=6), M 16 / 256 with cap 16 (MT 16;
//   IQ2_S pair: cap 8, MT 8, as the backend), forced cap 8 on MT 8 and MT 16 kernels; id patterns "real" (each
//   token's 6 from a pool sized for the measured distinct fraction, 66.8 % at M <= 6, 49.6 % above), "repeat"
//   (6 of 10 consecutive experts: up to M slots per expert) and "distinct"; real GGUF expert rows (24 experts, so
//   heavy grouping); the HcFinishRows extra row (gate + up and down shapes). Timed (event time of back-to-back launches after a warm-up, mean
//   over passes x 16 "real" id sets, production and candidate alternated, 3 rounds) at the check shapes and
//   M 16 / 64 / 256. Exit status 1 on any mismatch.
// Build (engine dir): icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_routed_u2.cpp -o bench_routed_u2 -lze_loader
// Run: ONEAPI_DEVICE_SELECTOR=level_zero:N bench_routed_u2  (ONLY=xxs,iq2s,iq3,iq2xs,iq1 formats; KIND=pair|down;
//   NOTIME=1; NOCHECK=1; REAL0=1 skips GGUF rows; TM=1,2,3,4,5,6,16,64,256 timed M; DBG=1 first mismatches)
#include <sycl/sycl.hpp>
#include <fcntl.h>
#include <unistd.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <numeric>
#include <random>
#include <string>
#include <type_traits>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
#include "stage2/packet3/kernels/sycl_v41_routed_r2.hpp"
using namespace ops41sycl;
using Ty = iq3::Type;

static constexpr unsigned NEXP = 384, NSET = 16, PAIR_ROWS = 384, DOWN_ROWS = 864, NREAL = 24, MMAX = 256;
static constexpr unsigned PAIR_R0 = 768, DOWN_R0 = 1696; // card 2's first row of each expert (gate/up, down)
static int g_fail = 0;
static HcFinishRows g_ex{};
static float *g_exo = nullptr;
static uint64_t sm64(uint64_t &s) {
    uint64_t z = (s += 0x9E3779B97F4A7C15ull);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}
template <Ty TY> uint8_t *packed_bank(sycl::queue &q, unsigned cols, size_t nrow, uint64_t seed) {
    constexpr auto L = iq3::layout(TY);
    const size_t nb = cols / L.elements, rb = nb * L.bytes, prb = pk41::packed_row_bytes(TY, cols);
    uint8_t *d = sycl::malloc_device<uint8_t>(nrow * prb, q);
    if (!d) {
        std::printf("FAIL cannot allocate %.0f MB of card memory\n", nrow * prb / 1e6);
        std::exit(1);
    }
    constexpr size_t CH = 4096;
    std::vector<uint8_t> src(rb), dst(CH * prb);
    for (size_t r0 = 0; r0 < nrow; r0 += CH) {
        const size_t n = std::min(CH, nrow - r0);
        for (size_t r = 0; r < n; ++r) {
            for (size_t i = 0; i < rb; i += 8) {
                const uint64_t v = sm64(seed);
                std::memcpy(&src[i], &v, std::min<size_t>(8, rb - i));
            }
            for (size_t b = 0; b < nb; ++b) {
                const uint16_t h = 0x1400 + (sm64(seed) & 0x3ff);
                src[b * L.bytes] = h & 255;
                src[b * L.bytes + 1] = h >> 8;
            }
            pk41::pack_row(TY, src.data(), dst.data() + r * prb, cols);
        }
        q.memcpy(d + r0 * prb, dst.data(), n * prb).wait();
    }
    return d;
}

// ---- real GGUF expert rows: NREAL experts (0, 16, 32, ...) x card 2's rows [r0, r0 + rows), packed ----------------
static const char *GGUF_DIR = "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS";
struct GgufT {
    std::string file;
    uint64_t off = 0;
    uint32_t type = 0;
    uint64_t ne[3] = {1, 1, 1};
};
static bool gguf_find(const std::string &name, GgufT &out) {
    for (int part = 1; part <= 6; ++part) {
        char fn[512];
        std::snprintf(fn, sizeof fn, "%s/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-%05d-of-00006.gguf", GGUF_DIR, part);
        const int fd = open(fn, O_RDONLY);
        if (fd < 0) continue;
        std::vector<uint8_t> h((size_t)32 << 20);
        const ssize_t n = pread(fd, h.data(), h.size(), 0);
        close(fd);
        if (n < 64 || std::memcmp(h.data(), "GGUF", 4)) continue;
        const uint8_t *p = h.data() + 4, *end = h.data() + n;
        auto rd = [&](auto &v) { std::memcpy(&v, p, sizeof v); p += sizeof v; };
        uint32_t ver;
        uint64_t nt, nkv;
        rd(ver), rd(nt), rd(nkv);
        static const int tsz[13] = {1, 1, 2, 2, 4, 4, 4, 1, -1, -1, 8, 8, 8};
        uint64_t align = 32;
        bool bad = false;
        for (uint64_t i = 0; i < nkv && !bad; ++i) {
            uint64_t kl;
            rd(kl);
            const std::string key((const char *)p, kl);
            p += kl;
            uint32_t t;
            rd(t);
            if (t == 8) { uint64_t m; rd(m); p += m; }
            else if (t == 9) {
                uint32_t et;
                uint64_t m;
                rd(et), rd(m);
                if (et == 8) for (uint64_t j = 0; j < m; ++j) { uint64_t sl; rd(sl); p += sl; }
                else p += m * tsz[et];
            } else {
                if (key == "general.alignment" && t == 4) { uint32_t a; std::memcpy(&a, p, 4); align = a; }
                p += tsz[t];
            }
            if (p > end) bad = true;
        }
        if (bad) continue;
        bool found = false;
        GgufT g;
        for (uint64_t i = 0; i < nt && p < end; ++i) {
            uint64_t nl;
            rd(nl);
            const std::string tn((const char *)p, nl);
            p += nl;
            uint32_t nd;
            rd(nd);
            uint64_t dims[4] = {1, 1, 1, 1};
            for (uint32_t d = 0; d < nd; ++d) rd(dims[d]);
            uint32_t ty;
            uint64_t off;
            rd(ty), rd(off);
            if (tn == name) {
                found = true;
                g.file = fn, g.type = ty, g.off = off;
                for (int d = 0; d < 3; ++d) g.ne[d] = dims[d];
            }
        }
        if (!found) continue;
        g.off += ((size_t)(p - h.data()) + align - 1) / align * align;
        out = g;
        return true;
    }
    return false;
}
template <Ty TY> static uint8_t *real_bank(sycl::queue &q, const std::string &name, unsigned cols, unsigned r0, unsigned rows) {
    GgufT g;
    if (!gguf_find(name, g)) { std::printf("  real: %s not found\n", name.c_str()); return nullptr; }
    if (g.ne[0] != cols || g.type != (uint32_t)TY || g.ne[1] < r0 + rows || g.ne[2] < 16 * (NREAL - 1) + 1) {
        std::printf("  real: %s type %u shape %llu x %llu x %llu does not fit\n", name.c_str(), g.type,
                    (unsigned long long)g.ne[0], (unsigned long long)g.ne[1], (unsigned long long)g.ne[2]);
        return nullptr;
    }
    constexpr auto L = iq3::layout(TY);
    const size_t rb = (size_t)cols / L.elements * L.bytes, prb = pk41::packed_row_bytes(TY, cols);
    std::vector<uint8_t> hw((size_t)rows * rb), hp((size_t)NREAL * rows * prb);
    const int fd = open(g.file.c_str(), O_RDONLY);
    for (unsigned e = 0; e < NREAL; ++e) {
        const uint64_t off = g.off + ((uint64_t)(16 * e) * g.ne[1] + r0) * rb;
        if (pread(fd, hw.data(), hw.size(), (off_t)off) != (ssize_t)hw.size()) { close(fd); return nullptr; }
        for (unsigned r = 0; r < rows; ++r) pk41::pack_row(TY, hw.data() + (size_t)r * rb, hp.data() + ((size_t)e * rows + r) * prb, cols);
    }
    close(fd);
    uint8_t *d = sycl::malloc_device<uint8_t>(hp.size(), q);
    q.memcpy(d, hp.data(), hp.size()).wait();
    return d;
}

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
// as Backend41::launch_rows: 512 items (16 sub-groups) per work-group, positions / 16 work-groups capped at maxwg

// ---- kernels per format: production RoutedU and the r4 selectors ---------------------------------------------
// P = RoutedU (RUFmt*); C = what the backend runs (the RoutedIQ*SU selectors) with no extra rows, else RoutedU3
template <typename EX, typename SEL, typename U3> using cand_t = std::conditional_t<std::is_same_v<EX, NoRows>, SEL, U3>;
template <Ty TY, unsigned NB, unsigned MT, typename EX> struct KT;
template <unsigned NB, unsigned MT, typename EX> struct KT<Ty::IQ2_XXS, NB, MT, EX> {
    using P = RoutedU<RUFmtIQ2XXS<NB>, MT, EX>;
    using C = cand_t<EX, RoutedIQ2XXSU<NB, MT>, RoutedU3<RU3IQ2XXS<NB>, MT, EX, 6, (MT <= 6)>>;
};
template <unsigned NB, unsigned MT, typename EX> struct KT<Ty::IQ2_S, NB, MT, EX> {
    using P = RoutedU<RUFmtIQ2S<NB>, MT, EX>;
    using C = cand_t<EX, RoutedIQ2SU<NB, MT>, RoutedU3<RU3IQ2S<NB>, MT, EX>>;
};
template <unsigned NB, unsigned MT, typename EX> struct KT<Ty::IQ3_XXS, NB, MT, EX> {
    using P = RoutedU<RUFmtIQ3XXS<NB>, MT, EX>;
    using C = cand_t<EX, RoutedIQ3XXSU<NB, MT>, RoutedU3<RU3IQ3XXS<NB>, MT, EX>>;
};
template <unsigned NB, unsigned MT, typename EX> struct KT<Ty::IQ2_XS, NB, MT, EX> {
    using P = RoutedU<RUFmtIQ2XS<NB>, MT, EX>;
    using C = cand_t<EX, RoutedIQ2XSU<NB, MT>, RoutedU3<RU3IQ2XS<NB>, MT, EX, 6, (MT <= 6)>>;
};
template <unsigned NB, unsigned MT, typename EX> struct KT<Ty::IQ1_S, NB, MT, EX> {
    using P = RoutedU<RUFmtIQ1S<NB, true>, MT, EX>;
    using C = cand_t<EX, RoutedIQ1SU<NB, MT, true>, RoutedU3<RU3IQ1S<NB>, MT, EX>>;
};

// ---- ids and groups ---------------------------------------------------------------------------------------
enum { REPEAT = 0, DISTINCT = 1, REAL = 2 };
static const char *const pat_name[3] = {"repeat", "distinct", "real"};
static unsigned real_pool(unsigned M, unsigned E) {
    const double target = M >= 16 ? 0.496 : 0.668;
    unsigned best = 6;
    double bd = 1e9;
    for (unsigned P = 6; P <= E; ++P) {
        const double d = P * (1.0 - std::pow(1.0 - 6.0 / P, (double)M)) / (6.0 * M);
        if (std::fabs(d - target) < bd) bd = std::fabs(d - target), best = P;
    }
    return best;
}
static std::vector<uint32_t> gen_ids(unsigned M, int pat, unsigned E, std::mt19937 &rng) {
    std::vector<uint32_t> all(E);
    std::iota(all.begin(), all.end(), 0u);
    std::shuffle(all.begin(), all.end(), rng);
    std::vector<uint32_t> ids(6 * M);
    if (pat == DISTINCT && 6 * M <= E) {
        std::copy(all.begin(), all.begin() + 6 * M, ids.begin());
        return ids;
    }
    std::vector<uint32_t> pool;
    if (pat == REPEAT) {
        const unsigned b = rng() % (E - 9);
        for (unsigned k = 0; k < 10; ++k) pool.push_back(b + k);
    } else if (pat == DISTINCT) {
        pool = all;
    } else {
        pool.assign(all.begin(), all.begin() + real_pool(M, E));
    }
    const unsigned P = (unsigned)pool.size();
    for (unsigned t = 0; t < M; ++t)
        for (unsigned k = 0; k < 6; ++k) {
            const unsigned j = k + rng() % (P - k);
            std::swap(pool[k], pool[j]);
            ids[6 * t + k] = pool[k];
        }
    return ids;
}
static void group(sycl::queue &q, const uint32_t *ids, unsigned nsl, unsigned cap, uint32_t *grp) {
    ExpertGroupM k{nsl, cap};
    k.heavy = cap > 6; // the backend: heavy for the big groups of long blocks
    const size_t n = ExpertGroupM::items(nsl);
    q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> lt(ExpertGroupM::LM, h);
        h.parallel_for(sycl::nd_range<1>(n, n), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            k(it, ids, grp, &lt[0]);
        });
    });
}

// ---- launches (as launch_rows: 512 items, positions / 16 work-groups capped at 128) ---------------------------
template <typename K>
static sycl::event launch(sycl::queue &q, size_t npos, const K &k, const uint8_t *w, const float *x,
                          const uint32_t *grp, float *y) {
    size_t nwg = (npos + 15) / 16;
    if (nwg > 128) nwg = 128;
    const K kk = k;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> lt(K::TAB, h);
        h.parallel_for(sycl::nd_range<1>(nwg * 512, 512),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kk(it, w, x, grp, y, &lt[0]); });
    });
}
struct Bank {
    const uint8_t *w1, *w2;
    unsigned rows;
    bool down;
};
struct Env {
    const float *x; // MMAX tokens' x (down: 6 slots' x per token)
    uint32_t *ids, *grp; // NSET sets: ids at 6 * MMAX each, grp at RUGrp::WORDS each
    float *o1, *o2;
};
static Env g_env;
static size_t xtok_of(bool down) { return down ? 6 * 2304 : 5120; }
template <typename K> static K make(const Bank &b, unsigned M) {
    K k{b.rows, b.down};
    if (!b.down) {
        k.w2 = b.w2;
        k.out2 = g_env.o2;
    }
    k.nsl = 6 * M;
    k.xtok = (unsigned)xtok_of(b.down);
    if constexpr (std::is_same_v<std::remove_cv_t<decltype(K::ex)>, HcFinishRows>) k.ex = g_ex;
    return k;
}
template <typename K> static size_t npos(const Bank &b, unsigned M) {
    return (size_t)(b.down ? 1 : 2) * 6 * M * b.rows + (std::is_same_v<std::remove_cv_t<decltype(K::ex)>, NoRows> ? 0 : 1);
}
static uint32_t *grp_of(unsigned s) { return g_env.grp + (size_t)s * RUGrp::WORDS; }
static uint32_t *ids_of(unsigned s) { return g_env.ids + (size_t)s * 6 * MMAX; }
// ids for sets 0 .. n - 1 (uploaded) and their groups at cap
static void set_ids(sycl::queue &q, unsigned M, int pat, unsigned E, unsigned n, unsigned cap, std::mt19937 &rng) {
    for (unsigned s = 0; s < n; ++s) {
        const auto h = gen_ids(M, pat, E, rng);
        q.memcpy(ids_of(s), h.data(), h.size() * 4);
    }
    for (unsigned s = 0; s < n; ++s) group(q, ids_of(s), 6 * M, cap, grp_of(s));
    q.wait();
}
template <typename K> static std::vector<float> run_out(sycl::queue &q, const Bank &b, unsigned M, unsigned s) {
    const size_t n = (size_t)6 * M * b.rows;
    q.memset(g_env.o1, 0xff, n * 4);
    q.memset(g_env.o2, 0xff, n * 4);
    q.memset(g_exo, 0xff, 24 * 4).wait();
    launch(q, npos<K>(b, M), make<K>(b, M), b.w1, g_env.x, grp_of(s), g_env.o1).wait();
    std::vector<float> h(2 * n + 24);
    q.memcpy(h.data(), g_env.o1, n * 4);
    q.memcpy(h.data() + n, g_env.o2, n * 4);
    q.memcpy(h.data() + 2 * n, g_exo, 24 * 4).wait();
    return h;
}
// bitwise over sets 0 .. n - 1; returns mismatching floats, adds compared floats to tot
template <typename KP, typename KK> static size_t diff(sycl::queue &q, const Bank &b, unsigned M, unsigned n, size_t &tot) {
    size_t bad = 0;
    for (unsigned s = 0; s < n; ++s) {
        const auto a = run_out<KP>(q, b, M, s), c = run_out<KK>(q, b, M, s);
        size_t nan = 0;
        for (size_t i = 0; i < a.size(); ++i) {
            const bool d = std::memcmp(&a[i], &c[i], 4) != 0;
            if (d && getenv("DBG") && bad < 6) std::printf("\n  [%zu] prod %.9g cand %.9g", i, a[i], c[i]);
            bad += d;
            nan += a[i] != a[i];
        }
        const size_t n1 = (size_t)6 * M * b.rows, expect_nan = (b.down ? n1 : 0) + (std::is_same_v<std::remove_cv_t<decltype(KP::ex)>, NoRows> ? 24 : 0);
        if (nan != expect_nan) std::printf(" [%zu NaN in production, %zu expected]", nan, expect_nan);
        tot += a.size() - expect_nan;
    }
    return bad;
}
template <typename K> static double time_k(sycl::queue &q, const Bank &b, unsigned M) {
    const K k = make<K>(b, M);
    const size_t np = npos<K>(b, M);
    const unsigned warm = M >= 64 ? 3 : 20, passes = M >= 64 ? 2 : 10;
    for (unsigned r = 0; r < warm; ++r)
        for (unsigned s = 0; s < NSET; ++s) launch(q, np, k, b.w1, g_env.x, grp_of(s), g_env.o1);
    std::vector<sycl::event> ev;
    for (unsigned p = 0; p < passes; ++p)
        for (unsigned s = 0; s < NSET; ++s) ev.push_back(launch(q, np, k, b.w1, g_env.x, grp_of(s), g_env.o1));
    q.wait();
    double sum = 0;
    for (auto &e : ev) sum += ev_us(e);
    return sum / ev.size();
}

static std::vector<unsigned> g_tm = {1, 2, 3, 4, 5, 6, 16, 64, 256};
static std::mt19937 g_rng(7);

// one format and matrix kind: the checks, then the timing
template <Ty TY, unsigned NB> static void run_fmt(sycl::queue &q, const char *name, bool down, const char *real_layer) {
    const unsigned cols = NB * 256, rows = down ? DOWN_ROWS : PAIR_ROWS;
    constexpr bool S20 = TY == Ty::IQ2_S && NB == 20; // the backend caps these groups at 8 (MT 16 spills)
    constexpr unsigned MB = S20 ? 8 : 16;
    uint8_t *g = packed_bank<TY>(q, cols, (size_t)NEXP * rows, down ? 13 : 11);
    uint8_t *u = down ? nullptr : packed_bank<TY>(q, cols, (size_t)NEXP * rows, 12);
    const Bank b{g, u, rows, down};
    std::printf("%-8s %-4s", name, down ? "down" : "pair");
    if (!getenv("NOCHECK")) {
        size_t tot = 0, bad = 0;
        auto chk6 = [&](unsigned M, int pat, unsigned E) {
            set_ids(q, M, pat, E, 2, 6, g_rng);
            bad += diff<typename KT<TY, NB, 6, NoRows>::P, typename KT<TY, NB, 6, NoRows>::C>(q, b, M, 2, tot);
        };
        for (unsigned M : {1u, 2u, 3u, 4u, 5u, 6u, 15u, 16u, 32u, 64u})
            for (int pat : {REAL, REPEAT, DISTINCT}) chk6(M, pat, NEXP);
        for (unsigned M : {16u, 256u}) // the long blocks' groups (cap MB, MT MB)
            for (int pat : {REAL, REPEAT}) {
                set_ids(q, M, pat, NEXP, 1, MB, g_rng);
                bad += diff<typename KT<TY, NB, MB, NoRows>::P, typename KT<TY, NB, MB, NoRows>::C>(q, b, M, 1, tot);
            }
        set_ids(q, 16, REPEAT, NEXP, 2, 8, g_rng); // forced cap 8 on MT 8 and MT 16 kernels
        bad += diff<typename KT<TY, NB, 8, NoRows>::P, typename KT<TY, NB, 8, NoRows>::C>(q, b, 16, 2, tot);
        if constexpr (!S20) bad += diff<typename KT<TY, NB, 16, NoRows>::P, typename KT<TY, NB, 16, NoRows>::C>(q, b, 16, 2, tot);
        for (unsigned M : {2u, 16u}) { // the stream mix's finish as an extra row (M 16: with row pairs)
            set_ids(q, M, REAL, NEXP, 2, 6, g_rng);
            bad += diff<typename KT<TY, NB, 6, HcFinishRows>::P, typename KT<TY, NB, 6, HcFinishRows>::C>(q, b, M, 2, tot);
        }
        std::printf(" random %s %zu of %zu differ |", bad ? "FAIL" : "PASS", bad, tot);
        g_fail += bad != 0;
        if (real_layer && !getenv("REAL0")) {
            const std::string gn = std::string("blk.") + real_layer + (down ? ".ffn_down_exps.weight" : ".ffn_gate_exps.weight");
            const std::string un = std::string("blk.") + real_layer + ".ffn_up_exps.weight";
            uint8_t *rg = real_bank<TY>(q, gn, cols, down ? DOWN_R0 : PAIR_R0, rows);
            uint8_t *ru = down ? nullptr : real_bank<TY>(q, un, cols, PAIR_R0, rows);
            if (rg && (down || ru)) {
                const Bank br{rg, ru, rows, down};
                size_t rt = 0, rbad = 0;
                for (unsigned M : {1u, 2u, 6u, 16u}) {
                    set_ids(q, M, REAL, NREAL, 2, 6, g_rng);
                    rbad += diff<typename KT<TY, NB, 6, NoRows>::P, typename KT<TY, NB, 6, NoRows>::C>(q, br, M, 2, rt);
                }
                set_ids(q, 64, REAL, NREAL, 1, MB, g_rng);
                rbad += diff<typename KT<TY, NB, MB, NoRows>::P, typename KT<TY, NB, MB, NoRows>::C>(q, br, 64, 1, rt);
                std::printf(" real blk.%s %s %zu of %zu differ |", real_layer, rbad ? "FAIL" : "PASS", rbad, rt);
                g_fail += rbad != 0;
            } else {
                std::printf(" real: none |");
            }
            if (rg) sycl::free(rg, q);
            if (ru) sycl::free(ru, q);
        }
        std::printf("\n");
    } else {
        std::printf("\n");
    }
    if (!getenv("NOTIME"))
        for (unsigned M : g_tm) {
            const bool big = M >= 128;
            set_ids(q, M, REAL, NEXP, NSET, big ? MB : 6, g_rng);
            double tp = 0, tc = 0;
            for (int rep = 0; rep < 3; ++rep) {
                if (big) {
                    tp += time_k<typename KT<TY, NB, MB, NoRows>::P>(q, b, M) / 3;
                    tc += time_k<typename KT<TY, NB, MB, NoRows>::C>(q, b, M) / 3;
                } else {
                    tp += time_k<typename KT<TY, NB, 6, NoRows>::P>(q, b, M) / 3;
                    tc += time_k<typename KT<TY, NB, 6, NoRows>::C>(q, b, M) / 3;
                }
            }
            std::printf("  time %-8s %-4s M %3u cap %2u | prod %8.2f us | r4 %8.2f us | %+.1f %%\n", name,
                        down ? "down" : "pair", M, big ? MB : 6, tp, tc, 100.0 * (tc / tp - 1.0));
            std::fflush(stdout);
        }
    std::fflush(stdout);
    sycl::free(g, q);
    if (u) sycl::free(u, q);
}

int main(int argc, char **argv) {
    const int card = argc > 1 ? std::atoi(argv[1]) : 0;
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const sycl::device dev = l0.at(card);
    const sycl::context ctx(dev);
    sycl::queue q(ctx, dev, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
    std::printf("card %d %s\n", card, dev.get_info<sycl::info::device::name>().c_str());
    const std::string only = getenv("ONLY") ? getenv("ONLY") : "", kind = getenv("KIND") ? getenv("KIND") : "";
    auto want = [&](const char *f) { return only.empty() || ("," + only + ",").find(std::string(",") + f + ",") != std::string::npos; };
    if (const char *s = getenv("TM")) {
        g_tm.clear();
        for (const char *p = s; *p;) {
            g_tm.push_back((unsigned)std::strtoul(p, (char **)&p, 10));
            if (*p == ',') ++p;
        }
    }
    { // warm the card up (~0.4 s of busy kernels)
        float *wo = sycl::malloc_device<float>(1, q);
        const auto t0 = std::chrono::steady_clock::now();
        while (std::chrono::steady_clock::now() - t0 < std::chrono::milliseconds(400)) {
            for (int i = 0; i < 20; ++i)
                q.parallel_for(sycl::nd_range<1>(65536, 512), [=](sycl::nd_item<1> it) {
                    float a = float(it.get_global_id(0));
                    for (int k = 0; k < 2048; ++k) a = a * 1.0001f + 0.5f;
                    if (a == 12345.f) wo[0] = a;
                });
            q.wait();
        }
        sycl::free(wo, q);
    }
    std::mt19937 rng(5);
    std::uniform_real_distribution<float> ux(-1.f, 1.f);
    std::vector<float> hx((size_t)MMAX * 6 * 2304 + 64);
    for (auto &v : hx) v = ux(rng);
    float *x = sycl::malloc_device<float>(hx.size(), q);
    q.memcpy(x, hx.data(), hx.size() * 4).wait();
    g_env.x = x;
    g_env.ids = sycl::malloc_device<uint32_t>((size_t)NSET * 6 * MMAX, q);
    g_env.grp = sycl::malloc_device<uint32_t>((size_t)NSET * RUGrp::WORDS, q);
    const size_t on = (size_t)6 * MMAX * DOWN_ROWS + 256;
    g_env.o1 = sycl::malloc_device<float>(on, q);
    g_env.o2 = sycl::malloc_device<float>(on, q);
    { // HcFinishRows inputs (as bench_routed_r2)
        std::vector<double> hd(25 * 8);
        std::uniform_real_distribution<double> ud(0.01, 4.0);
        for (auto &v : hd) v = ud(rng);
        std::vector<float> hs(3 + 24);
        for (auto &v : hs) v = ux(rng);
        double *d = sycl::malloc_device<double>(hd.size(), q);
        float *sb = sycl::malloc_device<float>(hs.size(), q);
        g_exo = sycl::malloc_device<float>(24, q);
        q.memcpy(d, hd.data(), hd.size() * 8);
        q.memcpy(sb, hs.data(), hs.size() * 4).wait();
        HcMixFinishSG k{5120, 8};
        k.form = 1;
        g_ex = HcFinishRows{k, d, sb, sb + 3, g_exo, g_exo + 4, g_exo + 8};
    }
    const bool pair = kind.empty() || kind == "pair", down = kind.empty() || kind == "down";
    if (want("iq2s") && pair) run_fmt<Ty::IQ2_S, 20>(q, "IQ2_S", false, "30");
    if (want("iq1") && pair) run_fmt<Ty::IQ1_S, 20>(q, "IQ1_S", false, "5");
    if (want("xxs") && pair) run_fmt<Ty::IQ2_XXS, 20>(q, "IQ2_XXS", false, "12");
    if (want("iq3") && pair) run_fmt<Ty::IQ3_XXS, 20>(q, "IQ3_XXS", false, nullptr);
    if (want("iq2xs") && pair) run_fmt<Ty::IQ2_XS, 20>(q, "IQ2_XS", false, nullptr);
    if (want("iq2s") && down) run_fmt<Ty::IQ2_S, 9>(q, "IQ2_S", true, "12");
    if (want("iq3") && down) run_fmt<Ty::IQ3_XXS, 9>(q, "IQ3_XXS", true, "25");
    if (want("iq2xs") && down) run_fmt<Ty::IQ2_XS, 9>(q, "IQ2_XS", true, "5");
    if (want("xxs") && down) run_fmt<Ty::IQ2_XXS, 9>(q, "IQ2_XXS", true, "3");
    if (want("iq1") && down) run_fmt<Ty::IQ1_S, 9>(q, "IQ1_S", true, nullptr);
    std::printf("%s\n", g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
