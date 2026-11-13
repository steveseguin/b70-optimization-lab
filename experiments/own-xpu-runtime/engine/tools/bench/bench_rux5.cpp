// rux5 (2026-11-13): one-token (M = 1) and check (M = 2-6) routed-expert kernels: today's against RoutedUQ
// (sycl_v41_routed_rux5.hpp, rux4's gathers-first form; one-token through the slot ids).
// Shapes as the six-card engine on card 2: gate + up pair (w2 / out2), 384 rows per expert, 20 blocks; down: per-slot
// x, 864 rows, 9 blocks; 384 experts; card 2's real GGUF rows of ALL 384 experts of one layer per format.
// Today's kernels (what the backend launches, tp107 defaults):
//   M = 1: routed_pair / routed_gemv: IQ2_S gate+up RoutedIQ2SPe128<20> (OWN_PAIR_G128 default), else RoutedIQ*Px<NB>
//          (IQ2_XXS gate+up Pe, IQ1_S gate+up Pb, IQ3_XXS down Pb, IQ2_S down Pd, IQ2_XS down Pb, IQ2_XXS down Pd),
//          ids of one token (6 slots), 128 work-groups of 512.
//   M = 2-6: routed_m's expert-major RoutedU3<RU3*, 6> (OWN_MT_EU=6, OWN_U3_NOPAIR default: no pair code), groups by
//          ExpertGroupM's rule (an expert's slots ascending, groups by ascending first slot), 128 work-groups.
// Picks: real 3K-prompt ids (u84 dump): one token / M consecutive tokens of a layer, sets spread over layers.
// Every candidate's outputs (every float) are compared with today's kernel's on every set (and today's check kernel
// at M = 1 against today's one-token kernel). Timing: rounds alternating today's kernel and the candidates, us per
// launch; COLD=1 (default): each launch after a 48 MB stream + a small kernel touching x and the ids / groups (the
// engine's state at a routed launch: xperm ledger sections 9-10), COLD=0: back to back.
// Run: ONEAPI_DEVICE_SELECTOR=level_zero:2 bench_rux5 [ONLY=s20,..] [MS=1,2,3,4,5,6] [NSET=n] [ROUNDS=n] [COLD=0|1]
//      [NOCHECK=1] [NOTIME=1]
#include "bench_rux5_head.inc"

struct VarT { // today's kernel
};
// RoutedUQ<F, MT, R, E, XA, LV, G, W>: MT_ = 0: MT = the check's M (6 at M = 1 is not used: one-token = MT 1, IDS)
template <unsigned MT_, unsigned R_, unsigned E_, unsigned XA_, unsigned LV_, unsigned G_, unsigned W_> struct VarQ {
    static constexpr unsigned MT = MT_, R = R_, E = E_, XA = XA_, LV = LV_, G = G_, W = W_;
};
struct VarP { // the picks as the backend runs them (Rux5Q1 / Rux5QK; R = 0: today's kernel)
};
template <typename... C> struct CList {};
#ifndef RUX5_C1
#define RUX5_C1 VarQ<1, 2, 8, 0, 0, 128, 0>
#endif
#ifndef RUX5_CK
#define RUX5_CK VarQ<6, 1, 8, 0, 0, 128, 0>
#endif
using C1 = CList<RUX5_C1>;
using CK = CList<RUX5_CK>;
#ifndef RUX5_FMT
#define RUX5_FMT 0x7f
#endif
#define FMT_S20_V 1
#define FMT_XXS20_V 2
#define FMT_1S20_V 4
#define FMT_3XXS9_V 8
#define FMT_S9_V 16
#define FMT_XS9_V 32
#define FMT_XXS9_V 64

// ---- formats ----------------------------------------------------------------------------------------------------
template <Ty TY, unsigned NB> struct FT;
template <unsigned NB> struct FT<Ty::IQ2_XXS, NB> {
    using F = RU3IQ2XXS<NB>;
    using T1 = RoutedIQ2XXSPx<NB, ActF32>;
};
template <unsigned NB> struct FT<Ty::IQ2_S, NB> {
    using F = RU3IQ2S<NB>;
    using T1 = std::conditional_t<NB == 20, RoutedIQ2SPe128<NB, ActF32>, RoutedIQ2SPx<NB, ActF32>>;
};
template <unsigned NB> struct FT<Ty::IQ3_XXS, NB> {
    using F = RU3IQ3XXS<NB>;
    using T1 = RoutedIQ3XXSPx<NB, ActF32>;
};
template <unsigned NB> struct FT<Ty::IQ2_XS, NB> {
    using F = RU3IQ2XS<NB>;
    using T1 = RoutedIQ2XSPx<NB, ActF32>;
};
template <unsigned NB> struct FT<Ty::IQ1_S, NB> {
    using F = RU3IQ1S<NB>;
    using T1 = RoutedIQ1SPx<NB, ActF32>;
};
template <Ty TY, unsigned NB> using TKof = RoutedU3<typename FT<TY, NB>::F, 6>; // today's check kernel (no pair code)
// kernel of variant V at check size M (M = 1: the one-token form)
template <Ty TY, unsigned NB, typename V, unsigned M> struct KOf;
template <Ty TY, unsigned NB, unsigned M> struct KOf<TY, NB, VarT, M> {
    using T = std::conditional_t<M == 1, typename FT<TY, NB>::T1, TKof<TY, NB>>;
};
template <Ty TY, unsigned NB, unsigned MT, unsigned R, unsigned E, unsigned XA, unsigned LV, unsigned G, unsigned W, unsigned M>
struct KOf<TY, NB, VarQ<MT, R, E, XA, LV, G, W>, M> {
    static constexpr unsigned MTK = M == 1 ? 1 : MT ? MT : M;
    using T = RoutedUQ<typename FT<TY, NB>::F, MTK, R, E, XA, LV, G, W, M == 1>;
};
template <Ty TY, unsigned NB, unsigned M> struct KOf<TY, NB, VarP, M> {
    using T = std::conditional_t<M == 1,
                                 std::conditional_t<Rux5Pick1<TY, NB>::R != 0, Rux5Q1<TY, NB>, typename FT<TY, NB>::T1>,
                                 std::conditional_t<Rux5PickK<TY, NB, (M < 2 ? 2 : M)>::R != 0,
                                                    Rux5QK<TY, NB, (M < 2 ? 2 : M)>, TKof<TY, NB>>>;
};
template <Ty TY, unsigned NB, typename V, unsigned M> using CandK = typename KOf<TY, NB, V, M>::T;
template <typename V> static std::string cname() {
    char b[80];
    if constexpr (std::is_same_v<V, VarT>) std::snprintf(b, sizeof b, "today");
    else if constexpr (std::is_same_v<V, VarP>) std::snprintf(b, sizeof b, "pick");
    else
        std::snprintf(b, sizeof b, "Q mt%u R%uE%u x%u lv%u %s%s", V::MT, V::R, V::E, V::XA, V::LV,
                      V::G == 128 ? "g" : V::G == 256 ? "G" : "a", V::W ? (" w" + std::to_string(V::W)).c_str() : "");
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
// set s of M consecutive tokens: layer and position spread over the prompt (bench_rux4's real_ids)
static std::vector<uint32_t> real_ids(unsigned M, unsigned s) {
    std::vector<int> layers;
    for (auto &kv : g_real) layers.push_back(kv.first);
    const auto &v = g_real[layers[(3 + 7 * s) % layers.size()]];
    const unsigned ntok = (unsigned)(v.size() / 6), nblk = ntok / M;
    const unsigned b = nblk ? (5 * s + 1 + 3 * (s / layers.size())) % nblk : 0;
    return std::vector<uint32_t>(v.begin() + (size_t)6 * b * M, v.begin() + (size_t)6 * (b * M + M));
}
// ExpertGroupM's groups on the host: per expert its slots ascending in chunks of at most cap, ascending first slot
struct HGrp {
    std::vector<uint32_t> w;
    unsigned nu = 0;
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
    h.w[0] = h.nu;
    for (unsigned u = 0; u < h.nu; ++u) {
        h.w[RUGrp::EXP + u] = gs[u].e;
        h.w[RUGrp::CNT + u] = (uint32_t)gs[u].sl.size();
        for (size_t i = 0; i < gs[u].sl.size(); ++i) h.w[RUGrp::SLOT + u * RUGrp::CAP + i] = gs[u].sl[i];
    }
    return h;
}

// ---- launches (as the backend's launch_rows: 512 items, positions / 16 work-groups capped at 128 or K::WGCAP) ----
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
template <typename K>
static sycl::event launch(sycl::queue &q, size_t npos, const K &k, const uint8_t *w, const float *x, const uint32_t *grp, float *y) {
    size_t nwg = (npos + 15) / 16, cap = 128; // o.pair_wg = o.down_wg = 128
    if constexpr (requires { K::WGCAP; })
        if (K::WGCAP && K::WGCAP < cap) cap = K::WGCAP;
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
// a set: one token's ids (M = 1) or M tokens' groups (ids kept for the M = 1 cross-check)
struct DevS {
    uint32_t *ids = nullptr, *grp = nullptr;
    unsigned M = 1, nu = 0;
};
template <typename K> static K make(const Bank &b, unsigned M) {
    K k{b.rows, b.down};
    if (!b.down) {
        k.w2 = b.w2;
        k.out2 = g_o2;
    }
    if (M > 1) {
        k.nsl = 6 * M;
        k.xtok = (unsigned)xtok_of(b.down);
    }
    return k;
}
static size_t npos(const Bank &b, unsigned M) { return (size_t)(b.down ? 6 : 12) * M * b.rows; }
template <Ty TY, unsigned NB, typename V, unsigned M> static sycl::event go(sycl::queue &q, const Bank &b, const DevS &s) {
    using K = CandK<TY, NB, V, M>;
    return launch(q, npos(b, M), make<K>(b, M), b.w1, g_x, M == 1 ? s.ids : s.grp, g_o1);
}
static DevS put(sycl::queue &q, const std::vector<uint32_t> &ids, unsigned M) {
    DevS d;
    d.M = M;
    d.ids = sycl::malloc_device<uint32_t>(ids.size(), q);
    q.memcpy(d.ids, ids.data(), ids.size() * 4).wait(); // (ids is the caller's: waited before it can go)
    const HGrp h = host_groups(ids, 6);
    d.grp = sycl::malloc_device<uint32_t>(h.w.size(), q);
    q.memcpy(d.grp, h.w.data(), h.w.size() * 4).wait(); // (h is a temporary: waited)
    d.nu = h.nu;
    return d;
}
static void drop(sycl::queue &q, DevS &d) {
    sycl::free(d.ids, q);
    sycl::free(d.grp, q);
}
static void clear_out(sycl::queue &q, const Bank &b, unsigned M) {
    const size_t n = (size_t)6 * M * b.rows;
    q.memset(g_o1, 0xff, n * 4);
    q.memset(g_o2, 0xff, n * 4).wait();
}
static std::vector<float> fetch(sycl::queue &q, const Bank &b, unsigned M) {
    const size_t n = (size_t)6 * M * b.rows;
    std::vector<float> h(2 * n);
    q.memcpy(h.data(), g_o1, n * 4);
    q.memcpy(h.data() + n, g_o2, n * 4).wait();
    return h;
}
static size_t cmp(const std::vector<float> &a, const std::vector<float> &c) {
    size_t bd = 0;
    for (size_t i = 0; i < a.size(); ++i) {
        const bool d = std::memcmp(&a[i], &c[i], 4) != 0;
        if (d && getenv("DBG") && bd < 4) std::printf("\n  [%zu] today %.9g cand %.9g", i, a[i], c[i]);
        bd += d;
    }
    return bd;
}

// ---- the engine's cache state at a routed launch (xperm ledger sections 9-10): a 48 MB stream, then a small kernel
// touching the launch's x and ids / groups (the router / exchange writes them right before in the engine)
static uint32_t *g_s48 = nullptr, *g_s48o = nullptr;
static constexpr size_t S48W = (size_t)12 << 20; // 48 MB of words
static void pre_cold(sycl::queue &q, const float *x, size_t xbytes, const uint32_t *ids, size_t nids) {
    const uint32_t *p = g_s48;
    uint32_t *o = g_s48o;
    q.parallel_for(sycl::nd_range<1>(128 * 512, 512), [=](sycl::nd_item<1> it) {
        const size_t g = it.get_global_id(0);
        uint32_t acc = 0;
        for (size_t i = 4 * g; i < S48W; i += (size_t)4 * 128 * 512) {
            const sycl::vec<uint32_t, 4> v = *reinterpret_cast<const sycl::vec<uint32_t, 4> *>(p + i);
            acc ^= v[0] ^ v[1] ^ v[2] ^ v[3];
        }
        if (acc == 0x12345678u) o[g & 1023] = acc;
    });
    q.parallel_for(sycl::nd_range<1>(4 * 512, 512), [=](sycl::nd_item<1> it) {
        const size_t g = it.get_global_id(0);
        uint32_t acc = 0;
        for (size_t i = g; 64 * i < xbytes; i += 2048) acc ^= sycl::bit_cast<uint32_t>(x[16 * i]);
        if (16 * g < nids) acc ^= ids[16 * g]; // the ids / the groups (one word per line)
        if (acc == 0x12345678u) o[g & 1023] = acc;
    });
}
static bool g_cold = true;
// mean us per launch of variant V over the sets
template <Ty TY, unsigned NB, typename V, unsigned M> static double time_v(sycl::queue &q, const Bank &b, std::vector<DevS> &ss) {
    const unsigned passes = 4;
    const size_t xbytes = (size_t)M * xtok_of(b.down) * 4;
    const size_t nids = M == 1 ? 6 : RUGrp::WORDS;
    for (auto &s : ss) {
        if (g_cold) pre_cold(q, g_x, xbytes, M == 1 ? s.ids : s.grp, nids);
        go<TY, NB, V, M>(q, b, s);
    }
    std::vector<sycl::event> ev;
    for (unsigned r = 0; r < passes; ++r)
        for (auto &s : ss) {
            if (g_cold) pre_cold(q, g_x, xbytes, M == 1 ? s.ids : s.grp, nids);
            ev.push_back(go<TY, NB, V, M>(q, b, s));
        }
    q.wait();
    double t = 0;
    for (auto &e : ev) t += ev_us(e);
    return t / (double)ev.size();
}

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
static const char *g_fname = "";

// one check size M: bitwise on every set, then the timing rounds
template <Ty TY, unsigned NB, unsigned M, typename... C> static void run_m(sycl::queue &q, const Bank &b, CList<C...>) {
    const unsigned nset = getenv("NSET") ? std::max(1, std::atoi(getenv("NSET"))) : (M == 1 ? 16 : 8);
    std::vector<DevS> ss;
    unsigned nu = 0;
    for (unsigned s = 0; s < nset; ++s) {
        ss.push_back(put(q, real_ids(M, s), M));
        nu += ss.back().nu;
    }
    constexpr unsigned NC = sizeof...(C);
    std::printf("%-8s %-4s M=%u: %u sets, %.2f slots per group", g_fname, b.down ? "down" : "pair", M, nset, 6.0 * M * nset / nu);
    if (!getenv("NOCHECK")) {
        std::vector<size_t> bad(NC + 1, 0);
        size_t tot = 0;
        const size_t nout = (size_t)6 * M * b.rows * (b.down ? 1 : 2);
        for (auto &s : ss) {
            clear_out(q, b, M);
            go<TY, NB, VarT, M>(q, b, s).wait();
            const auto ref = fetch(q, b, M);
            size_t nan = 0;
            for (float v : ref) nan += v != v;
            if (nan != ref.size() - nout) std::printf(" [%zu NaN in today's, %zu expected]", nan, ref.size() - nout), ++bad[0];
            tot += nout;
            if constexpr (M == 1) { // today's check kernel at one token (groups of one slot) against the one-token kernel
                clear_out(q, b, M);
                launch(q, npos(b, M), make<TKof<TY, NB>>(b, M), b.w1, g_x, s.grp, g_o1).wait();
                bad[0] += cmp(ref, fetch(q, b, M));
            }
            unsigned j = 1;
            auto one = [&](auto ct) {
                using V = typename decltype(ct)::type;
                clear_out(q, b, M);
                go<TY, NB, V, M>(q, b, s).wait();
                bad[j++] += cmp(ref, fetch(q, b, M));
            };
            (one(std::type_identity<C>{}), ...);
        }
        size_t nb = 0;
        for (auto v : bad) nb += v;
        std::printf(" | bitwise vs today (%u forms%s, %zu floats each): %s", NC, M == 1 ? " + RoutedU3 at M 1" : "", tot,
                    nb ? "FAIL" : "PASS");
        if (nb) {
            std::printf(" [%s %zu", M == 1 ? "u3m1" : "today", bad[0]);
            for (size_t i = 1; i < bad.size(); ++i) std::printf(", c%zu %zu", i, bad[i]);
            std::printf("]");
        }
        g_fail += nb != 0;
    }
    std::printf("\n");
    if (!getenv("NOTIME")) {
        const int ROUNDS = getenv("ROUNDS") ? std::max(1, std::atoi(getenv("ROUNDS"))) : 3;
        double t0 = 0, tc[NC + 1] = {};
        (void)time_v<TY, NB, VarT, M>(q, b, ss); // warm-up
        for (int rep = 0; rep < ROUNDS; ++rep) {
            t0 += time_v<TY, NB, VarT, M>(q, b, ss) / ROUNDS;
            unsigned j = 0;
            auto one = [&](auto ct) {
                using V = typename decltype(ct)::type;
                tc[j++] += time_v<TY, NB, V, M>(q, b, ss) / ROUNDS;
            };
            (one(std::type_identity<C>{}), ...);
        }
        std::printf("    today %8.2f us%s\n", t0, g_cold ? " (cold)" : " (warm)");
        unsigned j = 0;
        auto pr = [&](auto ct) {
            using V = typename decltype(ct)::type;
            std::printf("    %-26s %8.2f us (%+6.1f%%)\n", cname<V>().c_str(), tc[j], 100.0 * (tc[j] / t0 - 1.0));
            ++j;
        };
        (pr(std::type_identity<C>{}), ...);
    }
    std::fflush(stdout);
    for (auto &s : ss) drop(q, s);
}

template <Ty TY, unsigned NB> static void run_fmt(sycl::queue &q, const char *name, bool down, const char *layer) {
    const unsigned cols = NB * 256, rows = down ? DOWN_ROWS : PAIR_ROWS;
    const auto t0 = std::chrono::steady_clock::now();
    g_fname = name;
    uint8_t *g = nullptr, *u = nullptr;
    const std::string gn = std::string("blk.") + layer + (down ? ".ffn_down_exps.weight" : ".ffn_gate_exps.weight");
    const std::string un = std::string("blk.") + layer + ".ffn_up_exps.weight";
    g = real_bank_all<TY>(q, gn, cols, down ? DOWN_R0 : PAIR_R0, rows);
    u = down ? nullptr : real_bank_all<TY>(q, un, cols, PAIR_R0, rows);
    if (!g || (!down && !u)) {
        std::printf("FAIL %s: real weights of blk.%s not loaded\n", name, layer);
        ++g_fail;
        if (g) sycl::free(g, q);
        if (u) sycl::free(u, q);
        return;
    }
    const Bank b{g, u, rows, down};
    std::printf("%-8s %-4s weights: real blk.%s, 384 experts (%.1f s)\n", name, down ? "down" : "pair", layer,
                std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count());
    for (unsigned M : parse_list(getenv("MS"), {1, 2, 3, 4, 5, 6})) {
        switch (M) {
        case 1: run_m<TY, NB, 1>(q, b, C1{}); break;
        case 2: run_m<TY, NB, 2>(q, b, CK{}); break;
        case 3: run_m<TY, NB, 3>(q, b, CK{}); break;
        case 4: run_m<TY, NB, 4>(q, b, CK{}); break;
        case 5: run_m<TY, NB, 5>(q, b, CK{}); break;
        case 6: run_m<TY, NB, 6>(q, b, CK{}); break;
        default: break;
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
    if (!load_real(idf)) { std::printf("FAIL no real ids (%s)\n", idf); return 1; }
    std::printf("real ids: %s\n", idf);
    if (getenv("COLD")) g_cold = std::atoi(getenv("COLD")) != 0;
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
    const size_t xn = (size_t)6 * 6 * 2304 + 64; // down: per-slot x of 6 tokens (the gate + up x is smaller)
    std::vector<float> hx(xn);
    for (auto &v : hx) v = ux(rng);
    float *x = sycl::malloc_device<float>(xn, q);
    q.memcpy(x, hx.data(), xn * 4).wait();
    g_x = x;
    const size_t on = (size_t)6 * 6 * DOWN_ROWS + 256;
    g_o1 = sycl::malloc_device<float>(on, q);
    g_o2 = sycl::malloc_device<float>(on, q);
    g_s48 = sycl::malloc_device<uint32_t>(S48W, q);
    g_s48o = sycl::malloc_device<uint32_t>(1024, q);
    if (!x || !g_o1 || !g_o2 || !g_s48 || !g_s48o) { std::printf("FAIL card memory\n"); return 1; }
    q.memset(g_s48, 0x5a, S48W * 4).wait();
    const std::string only = getenv("ONLY") ? getenv("ONLY") : "";
    auto want = [&](const char *f) { return only.empty() || ("," + only + ",").find(std::string(",") + f + ",") != std::string::npos; };
#if (RUX5_FMT) & FMT_S20_V
    if (want("s20")) run_fmt<Ty::IQ2_S, 20>(q, "IQ2_S", false, "30");
#endif
#if (RUX5_FMT) & FMT_XXS20_V
    if (want("xxs20")) run_fmt<Ty::IQ2_XXS, 20>(q, "IQ2_XXS", false, "12");
#endif
#if (RUX5_FMT) & FMT_1S20_V
    if (want("1s20")) run_fmt<Ty::IQ1_S, 20>(q, "IQ1_S", false, "5");
#endif
#if (RUX5_FMT) & FMT_3XXS9_V
    if (want("3xxs9")) run_fmt<Ty::IQ3_XXS, 9>(q, "IQ3_XXS", true, "25");
#endif
#if (RUX5_FMT) & FMT_S9_V
    if (want("s9")) run_fmt<Ty::IQ2_S, 9>(q, "IQ2_S", true, "12");
#endif
#if (RUX5_FMT) & FMT_XS9_V
    if (want("xs9")) run_fmt<Ty::IQ2_XS, 9>(q, "IQ2_XS", true, "5");
#endif
#if (RUX5_FMT) & FMT_XXS9_V
    if (want("xxs9")) run_fmt<Ty::IQ2_XXS, 9>(q, "IQ2_XXS", true, "3");
#endif
    std::printf("%s\n", g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
