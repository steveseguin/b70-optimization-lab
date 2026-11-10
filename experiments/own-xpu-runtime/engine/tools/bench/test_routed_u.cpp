// Expert-major routed kernels (sycl_v41.hpp "expert-major routed rows": ExpertGroupM + RoutedU, aliases
// RoutedIQ2XXSU ... RoutedIQ1SU) against the slot-major packed routed kernels (RoutedIQ2XXSP ... RoutedIQ1SP),
// BITWISE on every output float of every slot, on one card. Reference: the slot-major kernel run on the same
// packed bank, x and ids, launched as routed_m does (backend_sycl_v41_mt.inc).
//   formats IQ2_XXS, IQ2_S, IQ3_XXS, IQ2_XS, IQ1_S (bytes table) at NB 20 and 9 (cols 5120, 2304);
//   rows 384 (per-card slice) and 383; gate + up pair (x shared by a token's 6 slots, w2 / out2 set) and down
//   (per_slot_x, one matrix); cases (M tokens, nsl = 6M, kernel MT = ExpertGroupM cap):
//   M1/MT2, M2/MT2, M6/MT6, M6/MT16, M16/MT16, M16/MT8 (an expert with more than 8 slots splits into
//   groups), M16/MT6; each with three id patterns: "repeat" (6 distinct experts per token from 10 consecutive
//   ids: up to M slots per expert), "distinct" (all 6M slots distinct) and "real" (each token's 6 from a pool
//   sized for the measured distinct fraction: 66.8 % at M <= 6, 49.6 % at M = 16).
// Also checked: the grouping itself (every slot in exactly one group, ascending, 1..cap slots, nu), no store
// past slot nsl - 1, finite non-vacuous references. Timing (GPU event time, mean over 16 "real" id sets of
// the best of 5, sets interleaved): slot-major vs ExpertGroupM vs expert-major at M = 6 and 16, gate + up at
// NB 20 and down at NB 9 (the production shapes). Exit status 1 on any mismatch.
// Random packed rows as tools/bench/test_rows_mt.cpp (random bytes, half scales 1e-3..2e-3, pk41::pack_row).
//
//   source /opt/intel/oneapi/setvars.sh; cd engine
//   icpx -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src \
//     tools/bench/test_routed_u.cpp -o /tmp/test_routed_u -lze_loader
//   (add -fsycl-targets=intel_gpu_bmg_g31 to compile the 51 kernels ahead of time instead of at first launch)
//   LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib /tmp/test_routed_u [CARD]
//   ONLY=xxs,iq2s,iq3,iq2xs,iq1 selects formats; NOTIME=1 skips the timing; NEXP = experts in the bank
//   (default 256, at least 96); ROUTED_WG caps the work-groups of both routed kernels (default 128 = the
//   engine's o.pair_wg / o.down_wg). Card memory: two banks, at most 2 x 194 MB (IQ3_XXS, NB 20, 256 experts).
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <numeric>
#include <random>
#include <string>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
using namespace ops41sycl;
using Ty = iq3::Type;

static constexpr unsigned MMAX = 16, SMAX = 6 * MMAX, ROWS = 384, NSET = 16, REPS = 5;
static constexpr size_t OUTN = (size_t)SMAX * ROWS + 256; // per output buffer: 96 slots x 384 rows + a guard tail
static int g_fail = 0;
static bool g_time = true;
static unsigned g_wg = 128;
static unsigned g_nexp = 256;

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
template <typename T> T *dev_copy(sycl::queue &q, const std::vector<T> &h) {
    T *d = sycl::malloc_device<T>(h.size(), q);
    for (size_t o = 0; o < h.size(); o += (16 << 20))
        q.memcpy(d + o, h.data() + o, std::min<size_t>(16 << 20, h.size() - o) * sizeof(T));
    q.wait();
    return d;
}
static uint64_t sm64(uint64_t &s) {
    uint64_t z = (s += 0x9E3779B97F4A7C15ull);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}
// nrow packed rows of a GGUF IQ format: random bytes, sane half scales (any other byte is a valid code),
// generated and uploaded in chunks (small host memory)
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
                const uint16_t h = 0x1400 + (sm64(seed) & 0x3ff); // half 1e-3 .. 2e-3
                src[b * L.bytes] = h & 255;
                src[b * L.bytes + 1] = h >> 8;
            }
            pk41::pack_row(TY, src.data(), dst.data() + r * prb, cols);
        }
        q.memcpy(d + r0 * prb, dst.data(), n * prb).wait();
    }
    return d;
}

// ---- formats: slot-major kernel and expert-major decode ---------------------------------------------------
template <Ty TY, unsigned NB> struct Fmt;
template <unsigned NB> struct Fmt<Ty::IQ2_XXS, NB> {
    using Old = RoutedIQ2XXSP<NB, ActF32>;
    using U = RUFmtIQ2XXS<NB>;
    static constexpr const char *name = "IQ2_XXS";
};
template <unsigned NB> struct Fmt<Ty::IQ2_S, NB> {
    using Old = RoutedIQ2SP<NB, ActF32>;
    using U = RUFmtIQ2S<NB>;
    static constexpr const char *name = "IQ2_S";
};
template <unsigned NB> struct Fmt<Ty::IQ3_XXS, NB> {
    using Old = RoutedIQ3XXSP<NB, ActF32>;
    using U = RUFmtIQ3XXS<NB>;
    static constexpr const char *name = "IQ3_XXS";
};
template <unsigned NB> struct Fmt<Ty::IQ2_XS, NB> {
    using Old = RoutedIQ2XSP<NB, ActF32>;
    using U = RUFmtIQ2XS<NB>;
    static constexpr const char *name = "IQ2_XS";
};
template <unsigned NB> struct Fmt<Ty::IQ1_S, NB> {
    using Old = RoutedIQ1SP<NB, ActF32, true>;
    using U = RUFmtIQ1S<NB, true>;
    static constexpr const char *name = "IQ1_S";
};

// ---- launches (as launch_rows: 512 items, 16 sub-groups per work-group, capped work-groups, TAB local floats)
// ig = ids (slot-major kernel) or grp (expert-major kernel)
template <typename K>
static sycl::event launch_routed(sycl::queue &q, size_t npos, const K &k, const uint8_t *w, const float *x,
                                 const uint32_t *ig, float *y) {
    size_t nwg = (npos + 15) / 16;
    if (g_wg && nwg > g_wg) nwg = g_wg;
    const K kk = k;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> lt(K::TAB, h);
        h.parallel_for(sycl::nd_range<1>(nwg * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
            kk(it, w, x, ig, y, &lt[0]);
        });
    });
}
static sycl::event launch_group(sycl::queue &q, unsigned nsl, unsigned cap, const uint32_t *ids, uint32_t *grp) {
    const ExpertGroupM k{nsl, cap};
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> lt(ExpertGroupM::LM, h);
        h.parallel_for(sycl::nd_range<1>(ExpertGroupM::WG, ExpertGroupM::WG),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, ids, grp, &lt[0]); });
    });
}

// ---- ids --------------------------------------------------------------------------------------------------
enum { REPEAT = 0, DISTINCT = 1, REAL = 2 };
static const char *const pat_name[3] = {"repeat", "distinct", "real"};
// pool size whose expected distinct fraction (6 distinct of P per token, M tokens) is closest to the measured one
static unsigned real_pool(unsigned M) {
    const double target = M >= 16 ? 0.496 : 0.668;
    unsigned best = 6;
    double bd = 1e9;
    for (unsigned P = 6; P <= g_nexp; ++P) {
        const double d = P * (1.0 - std::pow(1.0 - 6.0 / P, (double)M)) / (6.0 * M);
        if (std::fabs(d - target) < bd) bd = std::fabs(d - target), best = P;
    }
    return best;
}
// 6M slots: slot s = token s / 6's pick s % 6; a token's 6 picks are distinct experts
static std::vector<uint32_t> gen_ids(unsigned M, int pat, std::mt19937 &rng) {
    const unsigned E = g_nexp;
    std::vector<uint32_t> all(E);
    std::iota(all.begin(), all.end(), 0u);
    std::shuffle(all.begin(), all.end(), rng);
    std::vector<uint32_t> ids(6 * M);
    if (pat == DISTINCT) {
        std::copy(all.begin(), all.begin() + 6 * M, ids.begin());
        return ids;
    }
    std::vector<uint32_t> pool;
    if (pat == REPEAT) {
        const unsigned b = rng() % (E - 9);
        for (unsigned k = 0; k < 10; ++k) pool.push_back(b + k);
    } else {
        pool.assign(all.begin(), all.begin() + real_pool(M));
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
static double distinct_frac(const uint32_t *ids, unsigned nsl) {
    std::vector<uint32_t> v(ids, ids + nsl);
    std::sort(v.begin(), v.end());
    return (double)(std::unique(v.begin(), v.end()) - v.begin()) / nsl;
}
// grp as ExpertGroupM must write it: every slot in exactly one group, a group's slots ascending and all
// picked its expert, 1..cap slots per group, nu = sum over experts of ceil(count / cap)
static bool grp_ok(const std::vector<uint32_t> &g, const std::vector<uint32_t> &ids, unsigned cap, char *why, size_t wn) {
    const unsigned nsl = (unsigned)ids.size(), nu = g[0];
    std::vector<unsigned> cnt(g_nexp, 0);
    for (auto e : ids) cnt[e]++;
    unsigned want = 0;
    for (auto c : cnt) want += (c + cap - 1) / cap;
    if (nu != want) return std::snprintf(why, wn, "nu %u, want %u", nu, want), false;
    std::vector<char> seen(nsl, 0);
    for (unsigned u = 0; u < nu; ++u) {
        const unsigned e = g[RUGrp::EXP + u], c = g[RUGrp::CNT + u];
        if (c < 1 || c > cap) return std::snprintf(why, wn, "group %u count %u", u, c), false;
        int prev = -1;
        for (unsigned i = 0; i < c; ++i) {
            const unsigned s = g[RUGrp::SLOT + u * RUGrp::CAP + i];
            if (s >= nsl || ids[s] != e || (int)s <= prev || seen[s])
                return std::snprintf(why, wn, "group %u (expert %u) entry %u = slot %u", u, e, i, s), false;
            seen[s] = 1;
            prev = (int)s;
        }
    }
    for (unsigned s = 0; s < nsl; ++s)
        if (!seen[s]) return std::snprintf(why, wn, "slot %u in no group", s), false;
    return true;
}

// ---- one comparison ---------------------------------------------------------------------------------------
struct Env {
    sycl::queue *q;
    const uint8_t *w1, *w2;
    const float *x;
    uint32_t *ids, *grp; // NSET id sets / grp buffers
    float *o[4];         // slot-major out, out2; expert-major out, out2 (OUTN floats each)
    unsigned cols;
};
static unsigned xtok_of(const Env &v, bool down) { return down ? 6 * v.cols + 64 : v.cols + 64; }
// number of problems: differing floats, stores past slot nsl - 1, non-finite reference floats, a bad grouping,
// a vacuous reference (slot 0 == slot 1 on every row)
template <typename FM, unsigned MT>
static size_t check_case(Env &v, unsigned M, int pat, unsigned rows, bool down, std::mt19937 &rng) {
    sycl::queue &q = *v.q;
    const unsigned nsl = 6 * M;
    const std::vector<uint32_t> ids = gen_ids(M, pat, rng);
    q.memcpy(v.ids, ids.data(), ids.size() * 4);
    for (int k = 0; k < 4; ++k) q.memset(v.o[k], 0xff, OUTN * 4);
    q.memset(v.grp, 0xff, RUGrp::WORDS * 4).wait();
    typename FM::Old ko{rows, down};
    RoutedU<typename FM::U, MT> kn{rows, down};
    ko.nsl = kn.nsl = nsl;
    ko.xtok = kn.xtok = xtok_of(v, down);
    if (!down) {
        ko.w2 = kn.w2 = v.w2;
        ko.out2 = v.o[1];
        kn.out2 = v.o[3];
    }
    const size_t npos = (size_t)(down ? 1 : 2) * nsl * rows;
    launch_routed(q, npos, ko, v.w1, v.x, v.ids, v.o[0]);
    launch_group(q, nsl, MT, v.ids, v.grp);
    launch_routed(q, npos, kn, v.w1, v.x, v.grp, v.o[2]);
    q.wait();
    std::vector<float> h[4];
    for (int k = 0; k < 4; ++k) {
        h[k].resize(OUTN);
        q.memcpy(h[k].data(), v.o[k], OUTN * 4);
    }
    std::vector<uint32_t> g(RUGrp::WORDS);
    q.memcpy(g.data(), v.grp, g.size() * 4).wait();
    char why[160] = "";
    const bool gok = grp_ok(g, ids, MT, why, sizeof why);
    size_t differ = 0, stray = 0, nonfin = 0, same01 = 0;
    const size_t n = (size_t)nsl * rows;
    for (int m = 0; m < 2; ++m) {
        const std::vector<float> &a = h[m], &b = h[2 + m];
        const bool used = m == 0 || !down;
        for (size_t i = 0; i < OUTN; ++i) {
            differ += std::memcmp(&a[i], &b[i], 4) != 0;
            uint32_t ub;
            std::memcpy(&ub, &b[i], 4);
            if (!used || i >= n) stray += ub != 0xffffffffu;
            else nonfin += !std::isfinite(a[i]);
        }
        if (used)
            for (unsigned r = 0; r < rows; ++r) same01 += std::memcmp(&a[r], &a[rows + r], 4) == 0;
    }
    const bool vacuous = same01 >= (size_t)(down ? 1 : 2) * rows;
    const size_t bad = differ + stray + nonfin + !gok + vacuous;
    if (bad) {
        std::printf("FAIL %-7s NB %2u rows %3u %-4s M %2u MT %2u %-8s | differ %zu of %zu | stray %zu | "
                    "non-finite ref %zu | slot0==slot1 rows %zu | grouping %s %s\n",
                    FM::name, FM::U::NB, rows, down ? "down" : "pair", M, MT, pat_name[pat], differ,
                    (size_t)(down ? 1 : 2) * n, stray, nonfin, same01, gok ? "ok" : "BAD:", gok ? "" : why);
        std::fflush(stdout);
    }
    return bad;
}
template <typename FM, unsigned MT>
static size_t check3(Env &v, unsigned M, unsigned rows, bool down, std::mt19937 &rng) {
    size_t bad = 0;
    for (int p = 0; p < 3; ++p) bad += check_case<FM, MT>(v, M, p, rows, down, rng);
    return bad;
}
template <typename FM> static void check_line(Env &v, unsigned rows, bool down) {
    std::mt19937 rng(1000 * rows + 10 * FM::U::NB + down);
    struct C {
        const char *name;
        size_t bad;
    } c[] = {
        {"M1/MT2", check3<FM, 2>(v, 1, rows, down, rng)},
        {"M2/MT2", check3<FM, 2>(v, 2, rows, down, rng)},
        {"M6/MT6", check3<FM, 6>(v, 6, rows, down, rng)},
        {"M6/MT16", check3<FM, 16>(v, 6, rows, down, rng)},
        {"M16/MT16", check3<FM, 16>(v, 16, rows, down, rng)},
        {"M16/MT8", check3<FM, 8>(v, 16, rows, down, rng)},
        {"M16/MT6", check3<FM, 6>(v, 16, rows, down, rng)},
    };
    size_t tot = 0;
    for (auto &e : c) tot += e.bad;
    g_fail += tot != 0;
    std::printf("%s %-7s NB %2u rows %3u %-4s |", tot ? "FAIL" : "PASS", FM::name, FM::U::NB, rows, down ? "down" : "pair");
    for (auto &e : c) std::printf(" %s %zu", e.name, e.bad);
    std::printf("  (problems per case, 3 id patterns)\n");
    std::fflush(stdout);
}

// ---- timing -----------------------------------------------------------------------------------------------
// mean over the NSET id sets of the best of REPS launches; within a rep the sets run back to back
template <typename L> static double time_sets(sycl::queue &q, L launch) {
    std::vector<double> best(NSET, 1e30);
    std::vector<sycl::event> ev(NSET);
    for (unsigned rep = 0; rep < REPS; ++rep) {
        for (unsigned s = 0; s < NSET; ++s) ev[s] = launch(s);
        q.wait();
        for (unsigned s = 0; s < NSET; ++s) best[s] = std::min(best[s], ev_us(ev[s]));
    }
    double m = 0;
    for (double b : best) m += b;
    return m / NSET;
}
struct TimeRes {
    double grp, kern;
};
template <typename FM, unsigned MT> static TimeRes time_new(Env &v, unsigned M, bool down) {
    sycl::queue &q = *v.q;
    const unsigned nsl = 6 * M;
    RoutedU<typename FM::U, MT> kn{ROWS, down};
    kn.nsl = nsl;
    kn.xtok = xtok_of(v, down);
    if (!down) {
        kn.w2 = v.w2;
        kn.out2 = v.o[3];
    }
    const size_t npos = (size_t)(down ? 1 : 2) * nsl * ROWS;
    TimeRes t;
    t.grp = time_sets(q, [&](unsigned s) {
        return launch_group(q, nsl, MT, v.ids + (size_t)s * SMAX, v.grp + (size_t)s * RUGrp::WORDS);
    });
    t.kern = time_sets(q, [&](unsigned s) {
        return launch_routed(q, npos, kn, v.w1, v.x, v.grp + (size_t)s * RUGrp::WORDS, v.o[2]);
    });
    return t;
}
template <typename FM> static void time_line(Env &v, unsigned M, bool down) {
    sycl::queue &q = *v.q;
    const unsigned nsl = 6 * M;
    std::mt19937 rng(77 + M + 100 * down);
    std::vector<uint32_t> all((size_t)NSET * SMAX, 0);
    double df = 0;
    for (unsigned s = 0; s < NSET; ++s) {
        const auto ids = gen_ids(M, REAL, rng);
        std::copy(ids.begin(), ids.end(), all.begin() + (size_t)s * SMAX);
        df += distinct_frac(ids.data(), nsl) / NSET;
    }
    q.memcpy(v.ids, all.data(), all.size() * 4).wait();
    typename FM::Old ko{ROWS, down};
    ko.nsl = nsl;
    ko.xtok = xtok_of(v, down);
    if (!down) {
        ko.w2 = v.w2;
        ko.out2 = v.o[1];
    }
    const size_t npos = (size_t)(down ? 1 : 2) * nsl * ROWS;
    auto old = [&](unsigned s) { return launch_routed(q, npos, ko, v.w1, v.x, v.ids + (size_t)s * SMAX, v.o[0]); };
    for (unsigned i = 0; i < 300; ++i) old(i % NSET); // warm the card's clock (idle cards run slower)
    q.wait();
    const double to = time_sets(q, old);
    std::printf("time %-7s %-4s NB %2u rows %u M %2u distinct %.3f | slot-major %7.1f us |", FM::name,
                down ? "down" : "pair", FM::U::NB, ROWS, M, df, to);
    auto show = [&](const char *name, TimeRes t) {
        std::printf(" %s %7.1f us x%.2f (+group %.1f us)", name, t.kern, to / t.kern, t.grp);
    };
    if (M <= 6) {
        show("MT6", time_new<FM, 6>(v, M, down));
        show(" MT16", time_new<FM, 16>(v, M, down));
    } else {
        show("MT16", time_new<FM, 16>(v, M, down));
        show(" MT8", time_new<FM, 8>(v, M, down));
        show(" MT6", time_new<FM, 6>(v, M, down));
    }
    std::printf("\n");
    std::fflush(stdout);
}

// ---- one format at one NB ---------------------------------------------------------------------------------
template <Ty TY, unsigned NB> static void run_fmt(sycl::queue &q) {
    using FM = Fmt<TY, NB>;
    const unsigned cols = NB * 256;
    const size_t nrow = (size_t)g_nexp * ROWS;
    uint8_t *w1 = packed_bank<TY>(q, cols, nrow, 1000003ull * (unsigned)TY + NB);
    uint8_t *w2 = packed_bank<TY>(q, cols, nrow, 2000003ull * (unsigned)TY + NB);
    std::vector<float> hx((size_t)MMAX * (6 * cols + 64));
    {
        std::mt19937 rng(31 * (unsigned)TY + NB);
        std::uniform_real_distribution<float> ud(-2.0f, 2.0f);
        for (auto &f : hx) f = ud(rng);
    }
    float *x = dev_copy(q, hx);
    uint32_t *ids = sycl::malloc_device<uint32_t>((size_t)NSET * SMAX, q);
    uint32_t *grp = sycl::malloc_device<uint32_t>((size_t)NSET * RUGrp::WORDS, q);
    Env v{&q, w1, w2, x, ids, grp, {}, cols};
    for (auto &o : v.o) o = sycl::malloc_device<float>(OUTN, q);
    for (unsigned rows : {ROWS, ROWS - 1})
        for (bool down : {false, true}) check_line<FM>(v, rows, down);
    if (g_time && (NB == 20 || NB == 9)) {
        const bool down = NB == 9; // production shapes: gate + up over 5120 columns, down over 2304
        time_line<FM>(v, 6, down);
        time_line<FM>(v, 16, down);
    }
    for (auto &o : v.o) sycl::free(o, q);
    sycl::free(grp, q);
    sycl::free(ids, q);
    sycl::free(x, q);
    sycl::free(w2, q);
    sycl::free(w1, q);
}

int main(int argc, char **argv) {
    const int card = argc > 1 ? std::atoi(argv[1]) : 0;
    if (const char *e = std::getenv("NOTIME")) g_time = !(e[0] && e[0] != '0');
    if (const char *e = std::getenv("NEXP")) g_nexp = std::max(96, std::atoi(e));
    if (const char *e = std::getenv("ROUTED_WG")) g_wg = (unsigned)std::atoi(e);
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const sycl::device dev = l0.at(card);
    const sycl::context ctx(dev); // one context per card
    sycl::queue q(ctx, dev, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
    std::printf("card %d %s | %u experts x %u rows per bank, routed work-groups <= %u\n", card,
                dev.get_info<sycl::info::device::name>().c_str(), g_nexp, ROWS, g_wg);
    std::printf("real-pattern pool: %u experts at M <= 6, %u at M = 16\n", real_pool(6), real_pool(16));
    const char *only = std::getenv("ONLY");
    auto want = [&](const char *n) { return !only || std::strstr(only, n); };
    if (want("xxs")) run_fmt<Ty::IQ2_XXS, 20>(q), run_fmt<Ty::IQ2_XXS, 9>(q);
    if (want("iq2s")) run_fmt<Ty::IQ2_S, 20>(q), run_fmt<Ty::IQ2_S, 9>(q);
    if (want("iq3")) run_fmt<Ty::IQ3_XXS, 20>(q), run_fmt<Ty::IQ3_XXS, 9>(q);
    if (want("iq2xs")) run_fmt<Ty::IQ2_XS, 20>(q), run_fmt<Ty::IQ2_XS, 9>(q);
    if (want("iq1")) run_fmt<Ty::IQ1_S, 20>(q), run_fmt<Ty::IQ1_S, 9>(q);
    std::printf("%s: %d failed line(s)\n", g_fail ? "FAIL" : "PASS", g_fail);
    return g_fail ? 1 : 0;
}
