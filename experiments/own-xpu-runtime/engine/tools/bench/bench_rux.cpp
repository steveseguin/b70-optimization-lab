// Row-tiled expert-major routed kernels for prompt blocks (RoutedUT, kernels/sycl_v41_routed_rux.hpp) against what
// the backend's routed_m runs today (the RoutedIQ*SU selectors, sycl_v41_routed_r2.hpp), BITWISE on every output
// float, and timed. Shapes as the six-card engine on card 2: gate + up pair (w2 / out2), 384 rows per expert,
// 20 blocks; down: per-slot x, 864 rows, 9 blocks; 384 experts; groups written by production's ExpertGroupM.
// Id patterns:
//   real3k: blocks of M consecutive tokens of the 3K prompt's real picks (u84 dump, every token's 6 ids per layer;
//           RUX_IDS=<file>), sets from different layers / positions; caps as the backend: 6 below 128 tokens, 16 from
//           128 (8 for IQ2_S gate + up at 20 blocks); OWN_MT_EU_BIG_M=64-like cap 16 at 64 as an extra line
//   uniform c: 64 tokens, every expert exactly c slots (c = 1, 2, 4, 6, 8, 16; cap c)
//   checks also: bench_routed_u2's random "real" pool, "repeat" (6 of 10 experts), "distinct", M = 1..6, 15-17, 32,
//   64, 128, 256; real GGUF expert rows (24 experts of card 2's rows).
// Variants (compile time, RUX_VARS; default "VarShip, VarRE<2, 8, 0, 128>"): VarShip = the backend's OWN_MT_RUX
// selectors as shipped (RoutedIQ*SUX: RuxPick's form per shape, production's where R = 0); VarRE<R, E, XA, G> =
// RoutedUT<F, MT, NoRows, 6, R, E, XA, G> (R rows per tile, E elements per lane per x load, XA = 2: next slot's x
// first, G = pinned registers 128 / 256). RUX_FMT: bit mask of format / shape pairs to build (see FMT_* below).
// Also checked: production on cap-16 groups against production and every variant on cap-8 groups (no output
// depends on the grouping: OWN_MT_RUX_CAP).
// Build (engine dir): icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_rux.cpp -o bench_rux -lze_loader
// Run: ONEAPI_DEVICE_SELECTOR=level_zero:N bench_rux  (NOTIME=1, NOCHECK=1, REAL0=1 skips GGUF rows, TM=16,64,..
//   timed M of the real3k pattern, UNI=0 skips the uniform table, NOCAP2=1 skips the extra-cap lines, CAP6=1 adds
//   cap-6 lines from 128 tokens, CHK=1 times guess checks of 2-6 tokens, TILE_NSL=n lets RoutedUT tile from n slots
//   (the backend: 6 * OWN_MT_RUX_MIN), ONLY=s20,xxs20,.. formats, DBG=1 first mismatches). Exit 1 on any mismatch.
// rux-1 numbers: /home/steve/dsv41-work/rux/README.md (card 5, 2026-11-11).
#include <sycl/sycl.hpp>
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>
#include <fcntl.h>
#include <unistd.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <numeric>
#include <random>
#include <sstream>
#include <string>
#include <type_traits>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
#include "stage2/packet3/kernels/sycl_v41_routed_rux.hpp"
using namespace ops41sycl;
using Ty = iq3::Type;

template <unsigned R_, unsigned E_, unsigned XA_ = 0, unsigned G_ = 0> struct VarRE {
    static constexpr unsigned R = R_, E = E_, XA = XA_, G = G_;
};
// VarShip: the backend's OWN_MT_RUX selectors as patched (RoutedIQ*SUX: RuxPick's form, or production's where R = 0)
struct VarShip {
    static constexpr unsigned R = 1, E = 8, XA = 0, G = 0;
    static constexpr bool SHIP = true;
};
template <typename V> inline constexpr bool is_ship = requires { V::SHIP; };
template <typename... V> struct VList {};
#ifndef RUX_VARS
#define RUX_VARS VarShip, VarRE<2, 8, 0, 128>
#endif
using Vars = VList<RUX_VARS>;
#ifndef RUX_FMT
#define RUX_FMT 0x3ff
#endif
// RUX_FMT bits (preprocessor: unselected formats are not compiled)
#define FMT_S20_V 1
#define FMT_1S20_V 2
#define FMT_XXS20_V 4
#define FMT_3XXS20_V 8
#define FMT_XS20_V 16
#define FMT_S9_V 32
#define FMT_3XXS9_V 64
#define FMT_XS9_V 128
#define FMT_XXS9_V 256
#define FMT_1S9_V 512

static constexpr unsigned NEXP = 384, NSET = 16, PAIR_ROWS = 384, DOWN_ROWS = 864, NREAL = 24, MMAX = 256;
static constexpr unsigned PAIR_R0 = 768, DOWN_R0 = 1696; // card 2's first row of each expert (gate/up, down)
static int g_fail = 0;
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

// ---- real GGUF expert rows: NREAL experts (0, 16, 32, ...) x card 2's rows [r0, r0 + rows), packed (bench_routed_u2)
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
    if (fd < 0) return nullptr;
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

// ---- formats: F = the RU3 decoder; P<MT> = what routed_m launches today (backend selectors) --------------------
template <Ty TY, unsigned NB> struct FT;
template <unsigned NB> struct FT<Ty::IQ2_XXS, NB> {
    using F = RU3IQ2XXS<NB>;
    template <unsigned MT> using P = RoutedIQ2XXSU<NB, MT>;
};
template <unsigned NB> struct FT<Ty::IQ2_S, NB> {
    using F = RU3IQ2S<NB>;
    template <unsigned MT> using P = RoutedIQ2SU<NB, MT>;
};
template <unsigned NB> struct FT<Ty::IQ3_XXS, NB> {
    using F = RU3IQ3XXS<NB>;
    template <unsigned MT> using P = RoutedIQ3XXSU<NB, MT>;
};
template <unsigned NB> struct FT<Ty::IQ2_XS, NB> {
    using F = RU3IQ2XS<NB>;
    template <unsigned MT> using P = RoutedIQ2XSU<NB, MT>;
};
template <unsigned NB> struct FT<Ty::IQ1_S, NB> {
    using F = RU3IQ1S<NB>;
    template <unsigned MT> using P = RoutedIQ1SU<NB, MT, true>;
};
template <Ty TY, unsigned NB, unsigned MT> struct ShipSel;
template <unsigned NB, unsigned MT> struct ShipSel<Ty::IQ2_XXS, NB, MT> { using T = RoutedIQ2XXSUX<NB, MT>; };
template <unsigned NB, unsigned MT> struct ShipSel<Ty::IQ2_S, NB, MT> { using T = RoutedIQ2SUX<NB, MT>; };
template <unsigned NB, unsigned MT> struct ShipSel<Ty::IQ3_XXS, NB, MT> { using T = RoutedIQ3XXSUX<NB, MT>; };
template <unsigned NB, unsigned MT> struct ShipSel<Ty::IQ2_XS, NB, MT> { using T = RoutedIQ2XSUX<NB, MT>; };
template <unsigned NB, unsigned MT> struct ShipSel<Ty::IQ1_S, NB, MT> { using T = RoutedIQ1SUX<NB, MT>; };
template <Ty TY, unsigned NB, unsigned MT, typename V>
using CandT = std::conditional_t<is_ship<V>, typename ShipSel<TY, NB, MT>::T,
                                 RoutedUT<typename FT<TY, NB>::F, MT, NoRows, 6, V::R, V::E, V::XA, V::G>>;

// ---- ids and groups ---------------------------------------------------------------------------------------
enum { REPEAT = 0, DISTINCT = 1, POOL = 2 };
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
// the 3K prompt's real picks: per layer, every token's 6 ids (u84 dump lines "L M id0 .. id(6M-1)")
static std::map<int, std::vector<uint32_t>> g_real;
static bool load_real(const char *fn) {
    std::ifstream f(fn);
    if (!f) return false;
    std::string line;
    while (std::getline(f, line)) {
        std::istringstream s(line);
        int L, M;
        if (!(s >> L >> M)) continue;
        auto &v = g_real[L];
        for (int i = 0; i < 6 * M; ++i) {
            unsigned id;
            s >> id;
            v.push_back(id);
        }
    }
    return !g_real.empty();
}
// set s of blocks of M tokens: layer and block position spread over the prompt
static std::vector<uint32_t> real_ids(unsigned M, unsigned s, unsigned E) {
    std::vector<int> layers;
    for (auto &kv : g_real) layers.push_back(kv.first);
    const auto &v = g_real[layers[(3 + 7 * s) % layers.size()]];
    const unsigned ntok = (unsigned)(v.size() / 6), nblk = ntok / M;
    const unsigned b = nblk ? (5 * s + 1) % nblk : 0;
    std::vector<uint32_t> ids(v.begin() + (size_t)6 * b * M, v.begin() + (size_t)6 * (b * M + M));
    if (E < NEXP)
        for (auto &e : ids) e %= E; // GGUF banks: 24 experts (picks of a token may then repeat; groups stay valid)
    return ids;
}
// uniform: 6M slots, every expert exactly c slots (G = 6M / c experts, a token's 6 picks distinct)
static std::vector<uint32_t> uni_ids(unsigned M, unsigned c, std::mt19937 &rng) {
    std::vector<uint32_t> perm(NEXP);
    std::iota(perm.begin(), perm.end(), 0u);
    std::shuffle(perm.begin(), perm.end(), rng);
    const unsigned G = 6 * M / c;
    std::vector<uint32_t> ids(6 * M);
    for (unsigned s = 0; s < 6 * M; ++s) ids[s] = perm[s % G];
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
template <typename K> static constexpr unsigned grf_of() {
    if constexpr (requires { K::GRF; }) return K::GRF;
    else return 0;
}
// a kernel whose register mode is pinned (K::GRF = 128 or 256) instead of the build's automatic choice
template <typename K, unsigned G> struct GrfLaunch {
    K k;
    const uint8_t *w;
    const float *x;
    const uint32_t *grp;
    float *y;
    sycl::local_accessor<float, 1> lt;
    void operator()(sycl::nd_item<1> it) const { k(it, w, x, grp, y, &lt[0]); }
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<G>,
                                                           sycl::ext::oneapi::experimental::sub_group_size<32>};
    }
};
template <typename K>
static sycl::event launch(sycl::queue &q, size_t npos, const K &k, const uint8_t *w, const float *x,
                          const uint32_t *grp, float *y) {
    size_t nwg = (npos + 15) / 16;
    if (nwg > 128) nwg = 128;
    const K kk = k;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> lt(K::TAB, h);
        if constexpr (grf_of<K>() != 0)
            h.parallel_for(sycl::nd_range<1>(nwg * 512, 512), GrfLaunch<K, grf_of<K>()>{kk, w, x, grp, y, lt});
        else
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
    const float *x;
    uint32_t *ids, *grp;
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
    if constexpr (requires { k.tile_nsl; }) // TILE_NSL=n: RoutedUT tiles from n slots (the backend: 6 * OWN_MT_RUX_MIN)
        if (const char *e = getenv("TILE_NSL")) k.tile_nsl = (unsigned)std::atoi(e);
    return k;
}
static size_t npos(const Bank &b, unsigned M) { return (size_t)(b.down ? 1 : 2) * 6 * M * b.rows; }
static uint32_t *grp_of(unsigned s) { return g_env.grp + (size_t)s * RUGrp::WORDS; }
static uint32_t *ids_of(unsigned s) { return g_env.ids + (size_t)s * 6 * MMAX; }
static void put_ids(sycl::queue &q, unsigned s, const std::vector<uint32_t> &h) { q.memcpy(ids_of(s), h.data(), h.size() * 4); }
static void make_groups(sycl::queue &q, unsigned M, unsigned n, unsigned cap) {
    for (unsigned s = 0; s < n; ++s) group(q, ids_of(s), 6 * M, cap, grp_of(s));
    q.wait();
}
template <typename K> static std::vector<float> run_out(sycl::queue &q, const Bank &b, unsigned M, unsigned s) {
    const size_t n = (size_t)6 * M * b.rows;
    q.memset(g_env.o1, 0xff, n * 4);
    q.memset(g_env.o2, 0xff, n * 4).wait();
    launch(q, npos(b, M), make<K>(b, M), b.w1, g_env.x, grp_of(s), g_env.o1).wait();
    std::vector<float> h(2 * n);
    q.memcpy(h.data(), g_env.o1, n * 4);
    q.memcpy(h.data() + n, g_env.o2, n * 4).wait();
    return h;
}
// bitwise over sets 0 .. n - 1 (production's outputs computed once per set, every candidate against them)
template <typename KP, typename... KC> static size_t diff(sycl::queue &q, const Bank &b, unsigned M, unsigned n, size_t &tot) {
    size_t bad = 0;
    for (unsigned s = 0; s < n; ++s) {
        const auto a = run_out<KP>(q, b, M, s);
        const size_t n1 = (size_t)6 * M * b.rows, expect_nan = b.down ? n1 : 0;
        size_t nan = 0;
        for (size_t i = 0; i < a.size(); ++i) nan += a[i] != a[i];
        if (nan != expect_nan) std::printf(" [%zu NaN in production, %zu expected]", nan, expect_nan);
        auto one = [&](auto kt) {
            using K = typename decltype(kt)::type;
            const auto c = run_out<K>(q, b, M, s);
            size_t bd = 0;
            for (size_t i = 0; i < a.size(); ++i) {
                const bool d = std::memcmp(&a[i], &c[i], 4) != 0;
                if (d && getenv("DBG") && bd < 6) std::printf("\n  [%zu] prod %.9g cand %.9g", i, a[i], c[i]);
                bd += d;
            }
            bad += bd;
            tot += a.size() - expect_nan;
        };
        (one(std::type_identity<KC>{}), ...);
    }
    return bad;
}
// grouping changes no output: KP on group set sa against every KC on group set sb (the same ids, another cap)
template <typename KP, typename... KC>
static size_t diff_sets(sycl::queue &q, const Bank &b, unsigned M, unsigned sa, unsigned sb, size_t &tot) {
    const auto a = run_out<KP>(q, b, M, sa);
    const size_t n1 = (size_t)6 * M * b.rows, expect_nan = b.down ? n1 : 0;
    size_t bad = 0;
    auto one = [&](auto kt) {
        const auto c = run_out<typename decltype(kt)::type>(q, b, M, sb);
        for (size_t i = 0; i < a.size(); ++i) bad += std::memcmp(&a[i], &c[i], 4) != 0;
        tot += a.size() - expect_nan;
    };
    (one(std::type_identity<KC>{}), ...);
    return bad;
}
template <Ty TY, unsigned NB, typename... V>
static size_t diff_caps(sycl::queue &q, const Bank &b, unsigned M, size_t &tot, VList<V...>) {
    // production MT 16 on cap-16 groups (set 0) against production MT 8 and every candidate MT 8 on cap-8 groups (set 1)
    return diff_sets<typename FT<TY, NB>::template P<16>, typename FT<TY, NB>::template P<8>, CandT<TY, NB, 8, V>...>(
        q, b, M, 0, 1, tot);
}
template <typename K> static double time_k(sycl::queue &q, const Bank &b, unsigned M, unsigned nset) {
    const K k = make<K>(b, M);
    const size_t np = npos(b, M);
    const unsigned warm = M >= 64 ? 2 : 10, passes = M >= 64 ? 2 : 6;
    for (unsigned r = 0; r < warm; ++r)
        for (unsigned s = 0; s < nset; ++s) launch(q, np, k, b.w1, g_env.x, grp_of(s), g_env.o1);
    std::vector<sycl::event> ev;
    for (unsigned p = 0; p < passes; ++p)
        for (unsigned s = 0; s < nset; ++s) ev.push_back(launch(q, np, k, b.w1, g_env.x, grp_of(s), g_env.o1));
    q.wait();
    double sum = 0;
    for (auto &e : ev) sum += ev_us(e);
    return sum / ev.size();
}
// production and every variant at MT, 3 rounds alternated; prints one line
template <Ty TY, unsigned NB, unsigned MT, typename... V>
static void time_line(sycl::queue &q, const Bank &b, unsigned M, unsigned nset, const char *what, VList<V...>) {
    constexpr unsigned NV = sizeof...(V);
    double tp = 0, tc[NV] = {};
    for (int rep = 0; rep < 3; ++rep) {
        tp += time_k<typename FT<TY, NB>::template P<MT>>(q, b, M, nset) / 3;
        unsigned j = 0;
        ((tc[j++] += time_k<CandT<TY, NB, MT, V>>(q, b, M, nset) / 3), ...);
    }
    std::printf("  %-22s MT %2u | prod %8.2f us |", what, MT, tp);
    unsigned j = 0;
    auto pr = [&](auto vt) {
        using V1 = typename decltype(vt)::type;
        if constexpr (is_ship<V1>) std::printf(" ship %8.2f (%+5.1f%%)", tc[j], 100.0 * (tc[j] / tp - 1.0));
        else
            std::printf(" R%uE%u%s%s %8.2f (%+5.1f%%)", V1::R, V1::E, V1::XA == 1 ? "A" : V1::XA == 2 ? "P" : "",
                        V1::G == 128 ? "g" : V1::G == 256 ? "G" : "", tc[j], 100.0 * (tc[j] / tp - 1.0));
        ++j;
    };
    (pr(std::type_identity<V>{}), ...);
    std::printf("\n");
    std::fflush(stdout);
}

static std::mt19937 g_rng(7);
static std::vector<unsigned> g_tm = {16, 32, 64, 128, 256};

template <Ty TY, unsigned NB, unsigned MT, typename... V>
static size_t diff_v(sycl::queue &q, const Bank &b, unsigned M, unsigned n, size_t &tot, VList<V...>) {
    return diff<typename FT<TY, NB>::template P<MT>, CandT<TY, NB, MT, V>...>(q, b, M, n, tot);
}

template <Ty TY, unsigned NB> static void run_fmt(sycl::queue &q, const char *name, bool down, const char *real_layer) {
    const unsigned cols = NB * 256, rows = down ? DOWN_ROWS : PAIR_ROWS;
    constexpr bool S20 = TY == Ty::IQ2_S && NB == 20; // the backend caps these groups at 8 (MT 16 spills)
    constexpr unsigned MB = S20 ? 8 : 16;
    // the kernels' MT for groups of at most cap slots: 6, 8, else MB
    auto by_cap = [&](unsigned cap, auto fn) {
        if (cap <= 6) fn(std::integral_constant<unsigned, 6>{});
        else if (cap <= 8) fn(std::integral_constant<unsigned, 8>{});
        else if constexpr (!S20) fn(std::integral_constant<unsigned, 16>{});
    };
    uint8_t *g = packed_bank<TY>(q, cols, (size_t)NEXP * rows, down ? 13 : 11);
    uint8_t *u = down ? nullptr : packed_bank<TY>(q, cols, (size_t)NEXP * rows, 12);
    const Bank b{g, u, rows, down};
    std::printf("%-8s %-4s", name, down ? "down" : "pair");
    if (!getenv("NOCHECK")) {
        size_t tot = 0, bad = 0;
        auto chk = [&](unsigned M, unsigned cap, unsigned nset, auto gen) {
            for (unsigned s = 0; s < nset; ++s) put_ids(q, s, gen(s));
            make_groups(q, M, nset, cap);
            by_cap(cap, [&](auto mt) { bad += diff_v<TY, NB, decltype(mt)::value>(q, b, M, nset, tot, Vars{}); });
        };
        for (unsigned M : {1u, 2u, 3u, 5u, 6u, 15u, 16u, 17u, 32u, 64u})
            for (int pat : {POOL, REPEAT, DISTINCT}) chk(M, 6, 1, [&](unsigned) { return gen_ids(M, pat, NEXP, g_rng); });
        if (!g_real.empty()) {
            for (unsigned M : {16u, 33u, 64u}) chk(M, 6, 2, [&](unsigned s) { return real_ids(M, s, NEXP); });
            for (unsigned M : {64u, 128u, 256u}) chk(M, MB, 2, [&](unsigned s) { return real_ids(M, s, NEXP); });
        }
        for (unsigned M : {128u, 256u}) chk(M, MB, 1, [&](unsigned) { return gen_ids(M, REPEAT, NEXP, g_rng); });
        for (unsigned c : {1u, 2u, 4u, 6u}) chk(64, 6, 1, [&](unsigned) { return uni_ids(64, c, g_rng); });
        chk(64, 8, 1, [&](unsigned) { return uni_ids(64, 8, g_rng); });
        chk(16, 8, 1, [&](unsigned) { return gen_ids(16, REPEAT, NEXP, g_rng); }); // forced cap 8
        if constexpr (!S20) chk(64, 16, 1, [&](unsigned) { return uni_ids(64, 16, g_rng); });
        std::printf(" random %s %zu of %zu differ |", bad ? "FAIL" : "PASS", bad, tot);
        g_fail += bad != 0;
        if constexpr (!S20) { // OWN_MT_RUX_CAP=8: the same outputs from cap-8 groups as from production's cap 16
            size_t ct = 0, cbad = 0;
            for (unsigned M : {64u, 128u, 256u}) {
                const auto ids = g_real.empty() ? gen_ids(M, POOL, NEXP, g_rng) : real_ids(M, 0, NEXP);
                put_ids(q, 0, ids);
                put_ids(q, 1, ids);
                q.wait();
                group(q, ids_of(0), 6 * M, 16, grp_of(0));
                group(q, ids_of(1), 6 * M, 8, grp_of(1));
                q.wait();
                cbad += diff_caps<TY, NB>(q, b, M, ct, Vars{});
            }
            std::printf(" cap16 vs cap8 %s %zu of %zu differ |", cbad ? "FAIL" : "PASS", cbad, ct);
            g_fail += cbad != 0;
        }
        if (real_layer && !getenv("REAL0")) {
            const std::string gn = std::string("blk.") + real_layer + (down ? ".ffn_down_exps.weight" : ".ffn_gate_exps.weight");
            const std::string un = std::string("blk.") + real_layer + ".ffn_up_exps.weight";
            uint8_t *rg = real_bank<TY>(q, gn, cols, down ? DOWN_R0 : PAIR_R0, rows);
            uint8_t *ru = down ? nullptr : real_bank<TY>(q, un, cols, PAIR_R0, rows);
            if (rg && (down || ru)) {
                const Bank br{rg, ru, rows, down};
                size_t rt = 0, rbad = 0;
                auto chkr = [&](unsigned M, unsigned cap, auto gen) {
                    put_ids(q, 0, gen());
                    make_groups(q, M, 1, cap);
                    by_cap(cap, [&](auto mt) { rbad += diff_v<TY, NB, decltype(mt)::value>(q, br, M, 1, rt, Vars{}); });
                };
                for (unsigned M : {2u, 16u, 64u}) chkr(M, 6, [&] { return gen_ids(M, POOL, NREAL, g_rng); });
                if (!g_real.empty())
                    for (unsigned M : {64u, 256u}) chkr(M, M >= 128 ? MB : 6, [&] { return real_ids(M, 1, NREAL); });
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
    if (!getenv("NOTIME")) {
        char what[64];
        if (!getenv("UNI") || std::atoi(getenv("UNI"))) { // uniform group sizes at 64 tokens (384 slots)
            for (unsigned c : {1u, 2u, 4u, 6u, 8u, 16u}) {
                const unsigned cap = c <= 6 ? 6 : c > MB ? MB : c;
                for (unsigned s = 0; s < 4; ++s) put_ids(q, s, uni_ids(64, c, g_rng));
                make_groups(q, 64, 4, cap);
                std::snprintf(what, sizeof what, "uniform %2u slots cap %2u", c, cap);
                by_cap(cap, [&](auto mt) { time_line<TY, NB, decltype(mt)::value>(q, b, 64, 4, what, Vars{}); });
            }
        }
        if (!g_real.empty() && getenv("CHK")) // guess checks: 2-6 tokens (real picks of the 3K prompt), cap 6
            for (unsigned M : {2u, 3u, 4u, 5u, 6u}) {
                for (unsigned s = 0; s < NSET; ++s) put_ids(q, s, real_ids(M, s, NEXP));
                make_groups(q, M, NSET, 6);
                std::snprintf(what, sizeof what, "check M %u cap 6", M);
                time_line<TY, NB, 6>(q, b, M, NSET, what, Vars{});
            }
        if (!g_real.empty())
            for (unsigned M : g_tm) {
                const unsigned nset = M >= 128 ? 8 : NSET;
                for (unsigned s = 0; s < nset; ++s) put_ids(q, s, real_ids(M, s, NEXP));
                const unsigned cap = M >= 128 ? MB : 6;
                make_groups(q, M, nset, cap);
                std::snprintf(what, sizeof what, "real3k M %3u cap %2u", M, cap);
                by_cap(cap, [&](auto mt) { time_line<TY, NB, decltype(mt)::value>(q, b, M, nset, what, Vars{}); });
                // other caps: 16 (or 8) at 64 tokens (OWN_MT_EU_BIG_M=64), 8 from 128 where production uses 16
                const unsigned cap2 = M == 64 ? MB : M >= 128 && MB == 16 ? 8 : 0;
                if (cap2 && !getenv("NOCAP2")) {
                    make_groups(q, M, nset, cap2);
                    std::snprintf(what, sizeof what, "real3k M %3u cap %2u", M, cap2);
                    by_cap(cap2, [&](auto mt) { time_line<TY, NB, decltype(mt)::value>(q, b, M, nset, what, Vars{}); });
                }
                if (M >= 128 && getenv("CAP6")) { // OWN_MT_RUX_CAP=6 from 128 tokens too
                    make_groups(q, M, nset, 6);
                    std::snprintf(what, sizeof what, "real3k M %3u cap %2u", M, 6u);
                    time_line<TY, NB, 6>(q, b, M, nset, what, Vars{});
                }
            }
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
    const char *idf = getenv("RUX_IDS") ? getenv("RUX_IDS") : "/home/steve/dsv41-work/runs/u84/p3k-ids-per-layer.txt";
    std::printf("real ids: %s\n", load_real(idf) ? idf : "none (real3k lines skipped)");
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
    const std::string only = getenv("ONLY") ? getenv("ONLY") : "";
    auto want = [&](const char *f) { return only.empty() || ("," + only + ",").find(std::string(",") + f + ",") != std::string::npos; };
#if (RUX_FMT) & FMT_S20_V
    if (want("s20")) run_fmt<Ty::IQ2_S, 20>(q, "IQ2_S", false, "30");
#endif
#if (RUX_FMT) & FMT_XXS20_V
    if (want("xxs20")) run_fmt<Ty::IQ2_XXS, 20>(q, "IQ2_XXS", false, "12");
#endif
#if (RUX_FMT) & FMT_1S20_V
    if (want("1s20")) run_fmt<Ty::IQ1_S, 20>(q, "IQ1_S", false, "5");
#endif
#if (RUX_FMT) & FMT_3XXS20_V
    if (want("3xxs20")) run_fmt<Ty::IQ3_XXS, 20>(q, "IQ3_XXS", false, nullptr);
#endif
#if (RUX_FMT) & FMT_XS20_V
    if (want("xs20")) run_fmt<Ty::IQ2_XS, 20>(q, "IQ2_XS", false, nullptr);
#endif
#if (RUX_FMT) & FMT_3XXS9_V
    if (want("3xxs9")) run_fmt<Ty::IQ3_XXS, 9>(q, "IQ3_XXS", true, "25");
#endif
#if (RUX_FMT) & FMT_S9_V
    if (want("s9")) run_fmt<Ty::IQ2_S, 9>(q, "IQ2_S", true, "12");
#endif
#if (RUX_FMT) & FMT_XS9_V
    if (want("xs9")) run_fmt<Ty::IQ2_XS, 9>(q, "IQ2_XS", true, "5");
#endif
#if (RUX_FMT) & FMT_XXS9_V
    if (want("xxs9")) run_fmt<Ty::IQ2_XXS, 9>(q, "IQ2_XXS", true, "3");
#endif
#if (RUX_FMT) & FMT_1S9_V
    if (want("1s9")) run_fmt<Ty::IQ1_S, 9>(q, "IQ1_S", true, nullptr);
#endif
    std::printf("%s\n", g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
