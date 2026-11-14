// rux6 (2026-11-13): prompt routed-expert kernel forms (sycl_v41_routed_rux6.hpp) and diagnostics (rux6_diag.hpp)
// against today's production (rux4's picks, RoutedIQ*SUP<NB, 6> = OWN_RUX4=1, default on since tp109), from bench_rux4.
// Timing reference = the pick ("pick"); bitwise reference = ship6 (RoutedIQ*SUX; the pick and prod6 are checked
// against it as well, so every candidate is checked against production's bits).
// Shapes as the six-card engine on card 2: gate + up pair (w2 / out2), 384 rows per expert, 20 blocks; down: per-slot
// x, 864 rows, 9 blocks; 384 experts. Weights: card 2's real rows of ALL 384 experts of one GGUF layer per format
// (REALW=0: random packed rows). Groups: ExpertGroupM's rule on the host (an expert's slots ascending in chunks of at
// most 6), groups in ascending first-slot order (the engine's order since tp106, OWN_MT_EU_HEAVY=0).
// Patterns:
//   tpe T : every one of the 384 experts picked by exactly T tokens (64 T tokens)
//   real M: blocks of M consecutive tokens of the 3K prompt's real picks (u84 dump; sets from different layers)
// Every candidate is compared float for float (memcmp) with ship6 (and ship6 with prod6 = RoutedIQ*SU<NB, 6>) on
// real weights, real picks at 16, 64, 256 and 512 tokens (2 sets each) and tpe 4 / 8. Diagnostic forms (VarD) skip it.
// Build: rux4/build.sh. Run: ONEAPI_DEVICE_SELECTOR=level_zero:2 bench_rux4 [ONLY=s20,..] [TPE=..] [RM=256,512]
//        [NOCHECK=1] [NOTIME=1] [ROUNDS=n] [WARM=n]
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
#include "stage2/packet3/kernels/sycl_v41_routed_rux4.hpp"
#include "stage2/packet3/kernels/sycl_v41_routed_rux6.hpp"
using namespace ops41sycl;
using Ty = iq3::Type;

struct VarShip { // the backend's RoutedIQ*SUX<NB, 6>
};
struct VarPick { // the backend's OWN_RUX4=1 kernel: RoutedIQ*SUP<NB, 6> (Rux4Pick; R = 0 picks: the same as VarShip)
};
template <unsigned R_, unsigned E_, unsigned XA_, unsigned PF_, unsigned LV_, unsigned G_> struct VarP {
    static constexpr unsigned R = R_, E = E_, XA = XA_, PF = PF_, LV = LV_, G = G_;
};
#include "rux6_diag.hpp"
template <unsigned R_, unsigned E_, unsigned XA_, unsigned LV_, unsigned G_, unsigned W_, unsigned D_> struct VarQ { // diag
    static constexpr unsigned R = R_, E = E_, XA = XA_, LV = LV_, G = G_, W = W_, D = D_;
};
struct VarPD0 {}; // diag on the pick's own parameters: D below
template <unsigned D_> struct VarPD {
    static constexpr unsigned D = D_;
};
#ifdef RUX4_DIAG
#include "rux4_diag.hpp"
#endif
template <unsigned R_, unsigned E_, unsigned G_, unsigned D_> struct VarD { // diagnostic (rux4_diag.hpp)
    static constexpr unsigned R = R_, E = E_, G = G_, D = D_;
};
template <typename V> struct IsD : std::false_type {};
template <unsigned R_, unsigned E_, unsigned G_, unsigned D_> struct IsD<VarD<R_, E_, G_, D_>> : std::true_type {};
template <unsigned R_, unsigned E_, unsigned XA_, unsigned LV_, unsigned G_, unsigned W_, unsigned D_>
struct IsD<VarQ<R_, E_, XA_, LV_, G_, W_, D_>> : std::bool_constant<D_ != 0> {};
template <unsigned D_> struct IsD<VarPD<D_>> : std::bool_constant<D_ != 0> {};
template <unsigned D_, unsigned XP_> struct VarPDX { // diag on the pick + rux6's x prefetch (XP blocks ahead, XW 0)
    static constexpr unsigned PDX = 1, D = D_, XP = XP_;
};
template <unsigned D_, unsigned XP_> struct IsD<VarPDX<D_, XP_>> : std::bool_constant<D_ != 0> {};
template <typename... C> struct CList {};
#include "rux6_tags.inc"
#ifndef RUX4_CANDS
#define RUX4_CANDS VarShip
#endif
using Cands = CList<RUX4_CANDS>;
#ifndef RUX4_FMT
#define RUX4_FMT 0x7f
#endif
#define FMT_S20_V 1
#define FMT_XXS20_V 2
#define FMT_1S20_V 4
#define FMT_3XXS9_V 8
#define FMT_S9_V 16
#define FMT_XS9_V 32
#define FMT_XXS9_V 64

static constexpr unsigned NEXP = 384, PAIR_ROWS = 384, DOWN_ROWS = 864;
static constexpr unsigned PAIR_R0 = 768, DOWN_R0 = 1696; // card 2's first row of each expert (gate/up, down)
static constexpr unsigned MMAX = 512;                    // tokens (real 512; tpe up to 8)
static_assert(RUGrp::MAXU >= 6 * 256, "RUGrp");
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

// ---- real GGUF expert rows: all 384 experts x card 2's rows [r0, r0 + rows), packed --------------------------
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
template <Ty TY> static uint8_t *real_bank_all(sycl::queue &q, const std::string &name, unsigned cols, unsigned r0, unsigned rows) {
    GgufT g;
    if (!gguf_find(name, g)) { std::printf("  real: %s not found\n", name.c_str()); return nullptr; }
    if (g.ne[0] != cols || g.type != (uint32_t)TY || g.ne[1] < r0 + rows || g.ne[2] < NEXP) {
        std::printf("  real: %s type %u shape %llu x %llu x %llu does not fit\n", name.c_str(), g.type,
                    (unsigned long long)g.ne[0], (unsigned long long)g.ne[1], (unsigned long long)g.ne[2]);
        return nullptr;
    }
    constexpr auto L = iq3::layout(TY);
    const size_t rb = (size_t)cols / L.elements * L.bytes, prb = pk41::packed_row_bytes(TY, cols);
    constexpr unsigned CH = 32; // experts per host chunk
    std::vector<uint8_t> hw((size_t)rows * rb), hp((size_t)CH * rows * prb);
    uint8_t *d = sycl::malloc_device<uint8_t>((size_t)NEXP * rows * prb, q);
    if (!d) return nullptr;
    const int fd = open(g.file.c_str(), O_RDONLY);
    if (fd < 0) { sycl::free(d, q); return nullptr; }
    for (unsigned e0 = 0; e0 < NEXP; e0 += CH) {
        for (unsigned e = e0; e < e0 + CH; ++e) {
            const uint64_t off = g.off + ((uint64_t)e * g.ne[1] + r0) * rb;
            if (pread(fd, hw.data(), hw.size(), (off_t)off) != (ssize_t)hw.size()) { close(fd); sycl::free(d, q); return nullptr; }
            for (unsigned r = 0; r < rows; ++r)
                pk41::pack_row(TY, hw.data() + (size_t)r * rb, hp.data() + ((size_t)(e - e0) * rows + r) * prb, cols);
        }
        q.memcpy(d + (size_t)e0 * rows * prb, hp.data(), hp.size()).wait();
    }
    close(fd);
    return d;
}

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}


// ---- formats ----------------------------------------------------------------------------------------------------
template <Ty TY, unsigned NB> struct FT;
template <unsigned NB> struct FT<Ty::IQ2_XXS, NB> {
    using F = RU3IQ2XXS<NB>;
    using P6 = RoutedIQ2XXSU<NB, 6>;
    using S6 = RoutedIQ2XXSUX<NB, 6>;
    using U6 = RoutedIQ2XXSUP<NB, 6>;
};
template <unsigned NB> struct FT<Ty::IQ2_S, NB> {
    using F = RU3IQ2S<NB>;
    using P6 = RoutedIQ2SU<NB, 6>;
    using S6 = RoutedIQ2SUX<NB, 6>;
    using U6 = RoutedIQ2SUP<NB, 6>;
};
template <unsigned NB> struct FT<Ty::IQ3_XXS, NB> {
    using F = RU3IQ3XXS<NB>;
    using P6 = RoutedIQ3XXSU<NB, 6>;
    using S6 = RoutedIQ3XXSUX<NB, 6>;
    using U6 = RoutedIQ3XXSUP<NB, 6>;
};
template <unsigned NB> struct FT<Ty::IQ2_XS, NB> {
    using F = RU3IQ2XS<NB>;
    using P6 = RoutedIQ2XSU<NB, 6>;
    using S6 = RoutedIQ2XSUX<NB, 6>;
    using U6 = RoutedIQ2XSUP<NB, 6>;
};
template <unsigned NB> struct FT<Ty::IQ1_S, NB> {
    using F = RU3IQ1S<NB>;
    using P6 = RoutedIQ1SU<NB, 6, true>;
    using S6 = RoutedIQ1SUX<NB, 6>;
    using U6 = RoutedIQ1SUP<NB, 6>;
};
template <Ty TY, unsigned NB, typename V> struct KOf;
template <Ty TY, unsigned NB> struct KOf<TY, NB, VarShip> {
    using T = typename FT<TY, NB>::S6;
};
template <Ty TY, unsigned NB> struct KOf<TY, NB, VarPick> {
    using T = typename FT<TY, NB>::U6;
};
template <Ty TY, unsigned NB, unsigned R, unsigned E, unsigned XA, unsigned PF, unsigned LV, unsigned G>
struct KOf<TY, NB, VarP<R, E, XA, PF, LV, G>> {
    using T = RoutedUP<typename FT<TY, NB>::F, 6, R, E, XA, PF, LV, G>;
};
template <Ty TY, unsigned NB, unsigned R, unsigned E, unsigned XA, unsigned LV, unsigned G, unsigned W, unsigned D>
struct KOf<TY, NB, VarQ<R, E, XA, LV, G, W, D>> {
    using T = RoutedUPD<typename FT<TY, NB>::F, 6, R, E, XA, LV, G, W, D>;
};
template <Ty TY, unsigned NB, unsigned D, unsigned XP> struct KOf<TY, NB, VarPDX<D, XP>> {
    using PK = Rux4Pick<TY, NB>;
    using T = RoutedUPD<typename FT<TY, NB>::F, 6, PK::R, PK::E, PK::XA, PK::LV, PK::G, PK::W, D, XP>;
};
template <Ty TY, unsigned NB, unsigned D> struct KOf<TY, NB, VarPD<D>> { // the pick's parameters (Rux4Pick)
    using PK = Rux4Pick<TY, NB>;
    using T = RoutedUPD<typename FT<TY, NB>::F, 6, PK::R, PK::E, PK::XA, PK::LV, PK::G, PK::W, D>;
};
#include "rux6_cands.inc"
#ifdef RUX4_DIAG
template <Ty TY, unsigned NB, unsigned R, unsigned E, unsigned G, unsigned D> struct KOf<TY, NB, VarD<R, E, G, D>> {
    using T = RoutedUTD<typename FT<TY, NB>::F, 6, R, E, G, D>;
};
#endif
template <Ty TY, unsigned NB, typename V> using CandK = typename KOf<TY, NB, V>::T;
static const char *dname(unsigned d) {
    static const char *n[] = {"ctl", "noX", "noDec", "fpOnly", "xOnly", "decOnly", "cfG", "xSame", "noGat", "noFP", "xHit"};
    return d < 11 ? n[d] : "?";
}
template <typename V> static std::string cname() {
    char b[64];
    if constexpr (std::is_same_v<V, VarShip>) std::snprintf(b, sizeof b, "ship6");
    else if constexpr (std::is_same_v<V, VarPick>) std::snprintf(b, sizeof b, "pick (OWN_RUX4=1)");
    else if constexpr (requires { V::PDX; })
        std::snprintf(b, sizeof b, "pickD+xp%u %s", V::XP, dname(V::D));
    else if constexpr (requires { V::D; } && !requires { V::E; })
        std::snprintf(b, sizeof b, "pickD %s", dname(V::D));
    else if constexpr (requires { V::D; V::W; })
        std::snprintf(b, sizeof b, "Q R%uE%u x%u lv%u %s w%u %s", V::R, V::E, V::XA, V::LV, V::G == 128 ? "g" : "G", V::W, dname(V::D));
    else if constexpr (requires { cname6<V>(b, sizeof b); })
        cname6<V>(b, sizeof b);
    else if constexpr (IsD<V>::value)
        std::snprintf(b, sizeof b, "D R%uE%u%s-%s", V::R, V::E, V::G == 128 ? "g" : "G",
                      V::D == 0 ? "ctl" : V::D == 1 ? "noX" : V::D == 2 ? "noDec" : V::D == 3 ? "fpOnly" : V::D == 4 ? "xOnly"
                                                                                                    : V::D == 5 ? "decOnly" : "?");
    else
        std::snprintf(b, sizeof b, "P R%uE%u x%u pf%u lv%u %s", V::R, V::E, V::XA, V::PF, V::LV, V::G == 128 ? "g" : V::G == 256 ? "G" : "a");
    return b;
}

static std::map<int, std::vector<uint32_t>> g_real; // per layer: every token's 6 ids (u84 dump)
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
// set s of blocks of M tokens: layer and block position spread over the prompt (bench_rux's real_ids)
static std::vector<uint32_t> real_ids(unsigned M, unsigned s) {
    std::vector<int> layers;
    for (auto &kv : g_real) layers.push_back(kv.first);
    const auto &v = g_real[layers[(3 + 7 * s) % layers.size()]];
    const unsigned ntok = (unsigned)(v.size() / 6), nblk = ntok / M;
    const unsigned b = nblk ? (5 * s + 1) % nblk : 0;
    return std::vector<uint32_t>(v.begin() + (size_t)6 * b * M, v.begin() + (size_t)6 * (b * M + M));
}
// tpe T: 64 T tokens, every expert exactly T slots, a token's 6 picks distinct
static std::vector<uint32_t> tpe_ids(unsigned T, std::mt19937 &rng) {
    std::vector<uint32_t> perm(NEXP);
    std::iota(perm.begin(), perm.end(), 0u);
    std::shuffle(perm.begin(), perm.end(), rng);
    const unsigned M = 64 * T;
    std::vector<uint32_t> ids(6 * M);
    for (unsigned s = 0; s < 6 * M; ++s) ids[s] = perm[s % NEXP];
    return ids;
}
// ExpertGroupM's groups on the host: per expert its slots ascending in chunks of at most cap, ascending first slot
struct HGrp {
    std::vector<uint32_t> w;
    unsigned nu = 0, slots = 0;
};
static HGrp host_groups(const std::vector<uint32_t> &ids, unsigned cap) {
    std::map<uint32_t, std::vector<uint32_t>> by;
    for (uint32_t s = 0; s < ids.size(); ++s) by[ids[s]].push_back(s);
    struct G {
        uint32_t e, first;
        std::vector<uint32_t> sl;
    };
    std::vector<G> gs;
    for (auto &kv : by) {
        const auto &v = kv.second;
        for (size_t i = 0; i < v.size(); i += cap)
            gs.push_back({kv.first, v[i], std::vector<uint32_t>(v.begin() + i, v.begin() + std::min(v.size(), i + cap))});
    }
    std::sort(gs.begin(), gs.end(), [&](const G &a, const G &b) { return a.first < b.first; });
    HGrp h;
    h.w.assign(RUGrp::WORDS, 0u);
    h.nu = (unsigned)gs.size();
    if (h.nu > RUGrp::MAXU) { std::printf("FAIL %u groups > MAXU\n", h.nu); std::exit(1); }
    h.w[0] = h.nu;
    for (unsigned u = 0; u < h.nu; ++u) {
        h.w[RUGrp::EXP + u] = gs[u].e;
        h.w[RUGrp::CNT + u] = (uint32_t)gs[u].sl.size();
        for (size_t i = 0; i < gs[u].sl.size(); ++i) h.w[RUGrp::SLOT + u * RUGrp::CAP + i] = gs[u].sl[i];
        h.slots += (unsigned)gs[u].sl.size();
    }
    return h;
}

// ---- launches (as the backend's launch_rows: 512 items, positions / 16 work-groups capped at 128) -----------------
template <typename K> static constexpr unsigned grf_of() {
    if constexpr (requires { K::GRF; }) return K::GRF;
    else return 0;
}
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
static size_t g_wg256 = 128; // WG256=n: work-group cap of the 256-register RoutedUP forms (the backend: o.pair_wg / o.down_wg = 128)
template <typename K> struct IsUP : std::false_type {};
template <typename F, unsigned MT, unsigned R, unsigned E, unsigned XA, unsigned PF, unsigned LV, unsigned G, unsigned W>
struct IsUP<RoutedUP<F, MT, R, E, XA, PF, LV, G, W>> : std::true_type {};
template <typename K>
static sycl::event launch(sycl::queue &q, size_t npos, const K &k, const uint8_t *w, const float *x, const uint32_t *grp, float *y) {
    size_t nwg = (npos + 15) / 16;
    size_t cap = IsUP<K>::value && grf_of<K>() == 256 ? g_wg256 : 128;
    if constexpr (requires { K::WGCAP; })
        if (K::WGCAP && K::WGCAP < cap) cap = K::WGCAP; // (the backend: max_wg lowered to the form's WGCAP)
    if (nwg > cap) nwg = cap;
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
static const float *g_x = nullptr;
static float *g_o1 = nullptr, *g_o2 = nullptr;
static size_t xtok_of(bool down) { return down ? 6 * 2304 : 5120; }
template <typename K> static K make(const Bank &b, unsigned nsl) {
    K k{b.rows, b.down};
    if (!b.down) {
        k.w2 = b.w2;
        k.out2 = g_o2;
    }
    k.nsl = nsl;
    k.xtok = (unsigned)xtok_of(b.down);
    if constexpr (requires { k.tile_nsl; }) k.tile_nsl = 96; // the backend: 6 * OWN_MT_RUX_MIN
    return k;
}
static size_t npos(const Bank &b, unsigned nsl) { return (size_t)(b.down ? 1 : 2) * nsl * b.rows; }
struct DevG {
    uint32_t *d = nullptr;
    unsigned nu = 0, slots = 0, nsl = 0;
};
static DevG put(sycl::queue &q, const std::vector<uint32_t> &ids) {
    const HGrp h = host_groups(ids, 6);
    DevG g;
    g.d = sycl::malloc_device<uint32_t>(h.w.size(), q);
    q.memcpy(g.d, h.w.data(), h.w.size() * 4).wait();
    g.nu = h.nu, g.slots = h.slots, g.nsl = (unsigned)ids.size();
    return g;
}
template <typename K> static void run_into(sycl::queue &q, const Bank &b, const DevG &g) {
    launch(q, npos(b, g.nsl), make<K>(b, g.nsl), b.w1, g_x, g.d, g_o1).wait();
}
static void clear_out(sycl::queue &q, const Bank &b, unsigned nsl) {
    const size_t n = (size_t)nsl * b.rows;
    q.memset(g_o1, 0xff, n * 4);
    q.memset(g_o2, 0xff, n * 4).wait();
}
static std::vector<float> fetch(sycl::queue &q, const Bank &b, unsigned nsl) {
    const size_t n = (size_t)nsl * b.rows;
    std::vector<float> h(2 * n);
    q.memcpy(h.data(), g_o1, n * 4);
    q.memcpy(h.data() + n, g_o2, n * 4).wait();
    return h;
}
static size_t cmp(const std::vector<float> &a, const std::vector<float> &c) {
    size_t bd = 0;
    for (size_t i = 0; i < a.size(); ++i) {
        const bool d = std::memcmp(&a[i], &c[i], 4) != 0;
        if (d && getenv("DBG") && bd < 4) std::printf("\n  [%zu] ship %.9g cand %.9g", i, a[i], c[i]);
        bd += d;
    }
    return bd;
}
// every candidate (and ship6) against ship6 / prod6 on one pattern; counts differing floats per candidate
template <Ty TY, unsigned NB, typename... C>
static void check_set(sycl::queue &q, const Bank &b, const DevG &g, size_t &tot, std::vector<size_t> &bad, CList<C...>) {
    using P6 = typename FT<TY, NB>::P6;
    using S6 = typename FT<TY, NB>::S6;
    clear_out(q, b, g.nsl);
    run_into<S6>(q, b, g);
    const auto ref = fetch(q, b, g.nsl);
    const size_t n1 = (size_t)g.nsl * b.rows, nan_ok = b.down ? n1 : 0; // down: out2 untouched (NaN)
    size_t nan = 0;
    for (size_t i = 0; i < ref.size(); ++i) nan += ref[i] != ref[i];
    if (nan != nan_ok) std::printf(" [%zu NaN in ship6, %zu expected]", nan, nan_ok), ++bad[0];
    clear_out(q, b, g.nsl);
    run_into<P6>(q, b, g);
    bad[0] += cmp(ref, fetch(q, b, g.nsl));
    tot += ref.size() - nan_ok;
    unsigned j = 1;
    auto one = [&](auto ct) {
        using V = typename decltype(ct)::type;
        if constexpr (!IsD<V>::value && !std::is_same_v<V, VarShip>) {
            clear_out(q, b, g.nsl);
            run_into<CandK<TY, NB, V>>(q, b, g);
            bad[j] += cmp(ref, fetch(q, b, g.nsl));
        }
        ++j;
    };
    (one(std::type_identity<C>{}), ...);
}
// mean us per launch of K over the pattern's sets
template <typename K> static double time_k(sycl::queue &q, const Bank &b, std::vector<DevG> &gs) {
    const unsigned slots = gs[0].nsl;
    const unsigned warm = 1, passes = slots >= 3000 ? 3 : 5;
    for (unsigned r = 0; r < warm; ++r)
        for (auto &g : gs) launch(q, npos(b, g.nsl), make<K>(b, g.nsl), b.w1, g_x, g.d, g_o1);
    std::vector<sycl::event> ev;
    for (unsigned r = 0; r < passes; ++r)
        for (auto &g : gs) ev.push_back(launch(q, npos(b, g.nsl), make<K>(b, g.nsl), b.w1, g_x, g.d, g_o1));
    q.wait();
    double s = 0;
    for (auto &e : ev) s += ev_us(e);
    return s / (double)gs.size() / passes;
}
template <Ty TY, unsigned NB, typename... C>
static void time_pattern(sycl::queue &q, const Bank &b, std::vector<DevG> &gs, const char *what, CList<C...>) {
    using S6 = typename FT<TY, NB>::U6; // rux6: the timing reference is today's production (the rux4 pick)
    constexpr unsigned NC = sizeof...(C);
    double t6 = 0, tc[NC] = {};
    const int ROUNDS = getenv("ROUNDS") ? std::max(1, std::atoi(getenv("ROUNDS"))) : 3;
    for (int w = 0, nw = getenv("WARM") ? std::atoi(getenv("WARM")) : 3; w < nw; ++w) (void)time_k<S6>(q, b, gs);
    for (int rep = 0; rep < ROUNDS; ++rep) {
        t6 += time_k<S6>(q, b, gs) / ROUNDS;
        unsigned j = 0;
        auto one = [&](auto ct) {
            using V = typename decltype(ct)::type;
            tc[j++] += time_k<CandK<TY, NB, V>>(q, b, gs) / ROUNDS;
        };
        (one(std::type_identity<C>{}), ...);
    }
    const double ns = gs[0].nsl;
    unsigned nu = 0;
    for (auto &g : gs) nu += g.nu;
    std::printf("  %-22s %5u slots (%.2f per group) | pick %9.1f us %6.3f us/slot\n", what, gs[0].nsl, ns * gs.size() / nu, t6,
                t6 / ns);
    unsigned j = 0;
    auto pr = [&](auto ct) {
        using V = typename decltype(ct)::type;
        std::printf("    %-24s %9.1f us %6.3f us/slot (%+6.1f%%)\n", cname<V>().c_str(), tc[j], tc[j] / ns, 100.0 * (tc[j] / t6 - 1.0));
        ++j;
    };
    (pr(std::type_identity<C>{}), ...);
    std::fflush(stdout);
}

static std::mt19937 g_rng(7);
static std::vector<unsigned> parse_list(const char *s, std::vector<unsigned> def) {
    if (!s) return def;
    std::vector<unsigned> v;
    for (const char *p = s; *p;) {
        v.push_back((unsigned)std::strtoul(p, (char **)&p, 10));
        if (*p == ',') ++p;
        else if (*p) break;
    }
    return v;
}

template <Ty TY, unsigned NB> static void run_fmt(sycl::queue &q, const char *name, bool down, const char *layer) {
    const unsigned cols = NB * 256, rows = down ? DOWN_ROWS : PAIR_ROWS;
    const auto t0 = std::chrono::steady_clock::now();
    uint8_t *g = nullptr, *u = nullptr;
    bool real = false;
    if (!getenv("REALW") || std::atoi(getenv("REALW"))) {
        const std::string gn = std::string("blk.") + layer + (down ? ".ffn_down_exps.weight" : ".ffn_gate_exps.weight");
        const std::string un = std::string("blk.") + layer + ".ffn_up_exps.weight";
        g = real_bank_all<TY>(q, gn, cols, down ? DOWN_R0 : PAIR_R0, rows);
        u = down ? nullptr : real_bank_all<TY>(q, un, cols, PAIR_R0, rows);
        real = g && (down || u);
        if (!real) {
            if (g) sycl::free(g, q);
            if (u) sycl::free(u, q);
            g = u = nullptr;
        }
    }
    if (!real) {
        g = packed_bank<TY>(q, cols, (size_t)NEXP * rows, down ? 13 : 11);
        u = down ? nullptr : packed_bank<TY>(q, cols, (size_t)NEXP * rows, 12);
    }
    const Bank b{g, u, rows, down};
    std::printf("%-8s %-4s weights: %s (%.1f s)", name, down ? "down" : "pair",
                real ? (std::string("real blk.") + layer + ", 384 experts").c_str() : "random",
                std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count());
    if (!getenv("NOCHECK")) {
        constexpr unsigned NC = []<typename... C>(CList<C...>) { return (unsigned)sizeof...(C); }(Cands{});
        std::vector<size_t> bad(NC + 1, 0);
        size_t tot = 0;
        auto chk = [&](const std::vector<uint32_t> &ids) {
            DevG dg = put(q, ids);
            check_set<TY, NB>(q, b, dg, tot, bad, Cands{});
            sycl::free(dg.d, q);
        };
        // CHECKM: the real block sizes checked (default 16, 64, 256, 512; two id sets each, CHECK1=1: one); NOTPE=1: no
        // random tokens-per-expert sets (rux6 first runs: CHECKM=16 CHECK1=1 NOTPE=1 NOTIME=1 = one small shape, once)
        if (!g_real.empty())
            for (unsigned M : parse_list(getenv("CHECKM"), {16u, 64u, 256u, 512u}))
                for (unsigned s = 0; s < (getenv("CHECK1") ? 1u : 2u); ++s) chk(real_ids(M, s));
        if (!getenv("NOTPE"))
            for (unsigned T : {4u, 8u}) chk(tpe_ids(T, g_rng));
        size_t nb = 0;
        for (size_t i = 0; i < bad.size(); ++i) nb += bad[i];
        std::printf(" | bitwise vs ship6 (prod6 + %u forms, %zu floats each): %s", NC, tot, nb ? "FAIL" : "PASS");
        if (nb) {
            std::printf(" [prod6 %zu", bad[0]);
            for (size_t i = 1; i < bad.size(); ++i) std::printf(", c%zu %zu", i, bad[i]);
            std::printf("]");
        }
        std::printf("\n");
        g_fail += nb != 0;
    } else {
        std::printf("\n");
    }
    if (!getenv("NOTIME")) {
        char what[64];
        for (unsigned T : parse_list(getenv("TPE"), {})) {
            if (64 * T > MMAX) continue;
            std::vector<DevG> gs;
            for (unsigned s = 0; s < 2; ++s) gs.push_back(put(q, tpe_ids(T, g_rng)));
            std::snprintf(what, sizeof what, "tpe %2u (%u tokens)", T, 64 * T);
            time_pattern<TY, NB>(q, b, gs, what, Cands{});
            for (auto &d : gs) sycl::free(d.d, q);
        }
        if (!g_real.empty())
            for (unsigned M : parse_list(getenv("RM"), {256, 512})) {
                const unsigned nset = getenv("NSET") ? std::atoi(getenv("NSET")) : 4;
                std::vector<DevG> gs;
                for (unsigned s = 0; s < nset; ++s) gs.push_back(put(q, real_ids(M, s)));
                std::snprintf(what, sizeof what, "real %4u tokens", M);
                time_pattern<TY, NB>(q, b, gs, what, Cands{});
                for (auto &d : gs) sycl::free(d.d, q);
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
    std::printf("card %d %s, free %.1f GiB\n", card, dev.get_info<sycl::info::device::name>().c_str(),
                dev.has(sycl::aspect::ext_intel_free_memory)
                    ? dev.get_info<sycl::ext::intel::info::device::free_memory>() / 1073741824.0
                    : -1.0);
    const char *idf = getenv("RUX_IDS") ? getenv("RUX_IDS") : "/home/steve/dsv41-work/runs/u84/p3k-ids-per-layer.txt";
    std::printf("real ids: %s\n", load_real(idf) ? idf : "none (real lines skipped)");
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
    const size_t xn = (size_t)MMAX * 6 * 2304 + 64; // down: per-slot x of every token (the gate + up x is smaller)
    std::vector<float> hx(xn);
    for (auto &v : hx) v = ux(rng);
    float *x = sycl::malloc_device<float>(xn, q);
    q.memcpy(x, hx.data(), xn * 4).wait();
    hx.clear();
    hx.shrink_to_fit();
    g_x = x;
    const size_t on = (size_t)6 * MMAX * DOWN_ROWS + 256;
    g_o1 = sycl::malloc_device<float>(on, q);
    g_o2 = sycl::malloc_device<float>(on, q);
    if (!x || !g_o1 || !g_o2) { std::printf("FAIL card memory\n"); return 1; }
    if (getenv("WG256")) g_wg256 = (size_t)std::max(1, std::atoi(getenv("WG256")));
    if (g_wg256 != 128) std::printf("256-register RoutedUP forms: at most %zu work-groups\n", g_wg256);
    const std::string only = getenv("ONLY") ? getenv("ONLY") : "";
    auto want = [&](const char *f) { return only.empty() || ("," + only + ",").find(std::string(",") + f + ",") != std::string::npos; };
#if (RUX4_FMT) & FMT_S20_V
    if (want("s20")) run_fmt<Ty::IQ2_S, 20>(q, "IQ2_S", false, "30");
#endif
#if (RUX4_FMT) & FMT_XXS20_V
    if (want("xxs20")) run_fmt<Ty::IQ2_XXS, 20>(q, "IQ2_XXS", false, "12");
#endif
#if (RUX4_FMT) & FMT_1S20_V
    if (want("1s20")) run_fmt<Ty::IQ1_S, 20>(q, "IQ1_S", false, "5");
#endif
#if (RUX4_FMT) & FMT_3XXS9_V
    if (want("3xxs9")) run_fmt<Ty::IQ3_XXS, 9>(q, "IQ3_XXS", true, "25");
#endif
#if (RUX4_FMT) & FMT_S9_V
    if (want("s9")) run_fmt<Ty::IQ2_S, 9>(q, "IQ2_S", true, "12");
#endif
#if (RUX4_FMT) & FMT_XS9_V
    if (want("xs9")) run_fmt<Ty::IQ2_XS, 9>(q, "IQ2_XS", true, "5");
#endif
#if (RUX4_FMT) & FMT_XXS9_V
    if (want("xxs9")) run_fmt<Ty::IQ2_XXS, 9>(q, "IQ2_XXS", true, "3");
#endif
    std::printf("%s\n", g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
