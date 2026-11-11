// The one-token routed expert kernels at the six-card shapes (card 2's slices): production RoutedIQ*P against the
// r2 forms (kernels/sycl_v41_routed_r2.hpp, the selectors RoutedIQ*Px the backend uses), BITWISE on random packed
// rows (6 slots at 128 and 96 work-groups, 12 slots with a second token's x) and on real GGUF expert rows, then
// timed (event time of back-to-back launches after a warm-up, mean over 10 passes x 16 id sets of 6 random experts
// of 384; production and candidate alternate, 3 rounds). Exit status 1 on any mismatch.
//   pair: gate + up in one launch (w2 / out2), 384 rows per expert, 20 blocks (5120 columns)
//   down: per-slot x, 864 rows per expert, 9 blocks (2304 columns)
// Build (engine dir):
//   icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -Xsycl-target-backend=intel_gpu_bmg_g31 \
//     "-options -ze-intel-enable-auto-large-GRF-mode" -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
//     -Wno-deprecated-declarations -I src tools/bench/bench_routed_r2.cpp -o bench_routed_r2 -lze_loader
// Random checks also run 16- and 256-token blocks' slots (96 / 1,536 slots, OWN_MT_EU=0's slot-major rows; BIG0=1
// skips them); the *_ex cases add the HcFinishRows extra row of the gates (OWN_HC_FIN=1: form 1; HCF=0 form 0).
// Run: ONEAPI_DEVICE_SELECTOR=level_zero:N bench_routed_r2   (ONLY=iq2s_pair,iq1_pair,... selects cases;
//   WGS=96,128,... the candidate's work-group counts, PWG=96 production's; REAL0=1 skips the GGUF rows;
//   DBG=1 prints the first mismatches)
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

static constexpr unsigned NEXP = 384, NSET = 16, PASSES = 10, PAIR_ROWS = 384, DOWN_ROWS = 864, NREAL = 24;
static constexpr unsigned PAIR_R0 = 768, DOWN_R0 = 1696; // card 2's first row of each expert (gate/up, down)
static int g_fail = 0;
// the extra row the gates run in the gate + up launch (OWN_HC_FIN=1: HcFinishRows, form 1), on random inputs;
// its 24 outputs (pre 4, post 4, comb 16) are compared too
static HcFinishRows g_ex{};
static float *g_exo = nullptr;
// multi-token blocks with slot-major rows (OWN_MT_EU=0): 16 and 256 tokens' slots, one id set each
static const float *g_bx = nullptr;
static const uint32_t *g_bids = nullptr;
// many extra rows (as the shared expert's dense rows in routed_gemv_ex): row r writes a value of r (lane 0)
struct TestRows {
    float *o;
    unsigned m;
    unsigned n() const { return m; }
    void row(sycl::sub_group, unsigned lane, unsigned r) const {
        if (lane == 0) o[r] = float(r) * 0.5f + 1.0f;
    }
};
static TestRows g_tex{};
template <typename K> using ex_t = std::remove_cv_t<decltype(K::ex)>;
template <typename K> static constexpr bool has_ex = !std::is_same_v<ex_t<K>, NoRows>;
template <typename K> static size_t exn() {
    if constexpr (std::is_same_v<ex_t<K>, TestRows>) return g_tex.m;
    else if constexpr (has_ex<K>) return 24;
    else return 0;
}

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
template <typename K>
static sycl::event launch(sycl::queue &q, size_t npos, size_t maxwg, const K &k, const uint8_t *w, const float *x,
                          const uint32_t *ids, float *y) {
    size_t nwg = (npos + 15) / 16;
    if (maxwg && nwg > maxwg) nwg = maxwg;
    const K kk = k;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> lt(K::TAB, h);
        h.parallel_for(sycl::nd_range<1>(nwg * 512, 512),
                       [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kk(it, w, x, ids, y, &lt[0]); });
    });
}
struct Bank {
    const uint8_t *w1, *w2;
    const float *x;
    const uint32_t *ids; // sets of 12 slot ids
    float *o1, *o2;
    unsigned rows;
    bool down;
    unsigned nsl = 6, xtok = 0;
};
template <typename K> static K make(const Bank &b) {
    K k{b.rows, b.down};
    if constexpr (std::is_same_v<ex_t<K>, TestRows>) k.ex = g_tex;
    else if constexpr (has_ex<K>) k.ex = g_ex;
    if (!b.down) {
        k.w2 = b.w2;
        k.out2 = b.o2;
    }
    k.nsl = b.nsl;
    k.xtok = b.xtok;
    return k;
}
template <typename K> static size_t npos_of(const Bank &b) {
    return (size_t)(b.down ? 1 : 2) * b.nsl * b.rows + exn<K>() / (std::is_same_v<ex_t<K>, TestRows> ? 1 : 24);
}
template <typename K> static double time_k(sycl::queue &q, const Bank &b, size_t maxwg) {
    const K k = make<K>(b);
    const size_t npos = npos_of<K>(b);
    // warm-up (keeps the card's clock up), then back-to-back launches as in the engine, one event each
    for (unsigned r = 0; r < 20; ++r)
        for (unsigned s = 0; s < NSET; ++s) launch(q, npos, maxwg, k, b.w1, b.x, b.ids + 12 * s, b.o1);
    std::vector<sycl::event> ev;
    ev.reserve(PASSES * NSET);
    for (unsigned p = 0; p < PASSES; ++p)
        for (unsigned s = 0; s < NSET; ++s) ev.push_back(launch(q, npos, maxwg, k, b.w1, b.x, b.ids + 12 * s, b.o1));
    q.wait();
    double sum = 0;
    for (auto &e : ev) sum += ev_us(e);
    return sum / (PASSES * NSET);
}
template <typename K> static std::vector<float> run_out(sycl::queue &q, const Bank &b, size_t maxwg, unsigned set) {
    const size_t n = (size_t)b.nsl * b.rows;
    q.memset(b.o1, 0xff, n * 4);
    q.memset(b.o2, 0xff, n * 4);
    q.memset(g_exo, 0xff, 4096 * 4).wait();
    launch(q, npos_of<K>(b), maxwg, make<K>(b), b.w1, b.x, b.ids + 12 * set, b.o1).wait();
    std::vector<float> h(2 * n + exn<K>());
    q.memcpy(h.data(), b.o1, n * 4);
    if (has_ex<K>) q.memcpy(h.data() + 2 * n, g_exo, exn<K>() * 4);
    q.memcpy(h.data() + n, b.o2, n * 4).wait();
    return h;
}
template <typename KP, typename KK> static size_t diff(sycl::queue &q, const Bank &b, size_t wgc, unsigned sets, size_t &tot) {
    size_t bad = 0;
    for (unsigned s = 0; s < sets; ++s) {
        static_assert(has_ex<KP> == has_ex<KK>);
        const auto a = run_out<KP>(q, b, 128, s), c = run_out<KK>(q, b, wgc, s);
        if (has_ex<KP> && s == 0) {
            size_t xn = 0;
            for (size_t i = a.size() - exn<KP>(); i < a.size(); ++i) xn += a[i] != a[i];
            if (xn) std::printf(" [%zu NaN in production's extra-row outputs]", xn);
        }
        for (size_t i = 0; i < a.size(); ++i) {
            const bool d = std::memcmp(&a[i], &c[i], 4) != 0;
            if (d && getenv("DBG") && bad < 6) std::printf("\n  [%zu] prod %.9g cand %.9g", i, a[i], c[i]);
            bad += d;
        }
        size_t nan = 0;
        for (size_t i = 0; i < a.size(); ++i) nan += a[i] != a[i];
        tot += a.size() - (b.down ? a.size() / 2 : 0);
        if (s == 0 && nan > (b.down ? a.size() / 2 : 0)) std::printf(" [%zu NaN in production]", nan);
    }
    return bad;
}

static std::vector<size_t> g_wgs = {128};
static size_t g_pwg = 128; // production's work-groups in the timing (PWG=)

// one case: production KP and candidate KK on the random bank (6 and 12 slots), the real bank, then timed
template <Ty TY, typename KP, typename KK>
static void run_case(sycl::queue &q, const char *name, bool down, const char *real_name, const float *x,
                     const uint32_t *ids, const uint32_t *rids, float *o1, float *o2) {
    const unsigned cols = down ? 2304 : 5120, rows = down ? DOWN_ROWS : PAIR_ROWS;
    uint8_t *g = packed_bank<TY>(q, cols, (size_t)NEXP * rows, down ? 13 : 11);
    uint8_t *u = down ? nullptr : packed_bank<TY>(q, cols, (size_t)NEXP * rows, 12);
    Bank b{g, u, x, ids, o1, o2, rows, down};
    std::printf("%-14s", name);
    size_t tot = 0, bad = 0;
    for (size_t wg : {(size_t)128, (size_t)96}) bad += diff<KP, KK>(q, b, wg, 4, tot);
    Bank b2 = b;
    b2.nsl = 12;
    b2.xtok = down ? 6 * 2304 : 5120;
    bad += diff<KP, KK>(q, b2, 128, 2, tot);
    if (!getenv("BIG0"))
        for (unsigned nt : {16u, 256u}) {
            Bank b3 = b;
            b3.nsl = 6 * nt;
            b3.xtok = down ? 6 * 2304 : 5120;
            b3.x = g_bx;
            b3.ids = g_bids;
            bad += diff<KP, KK>(q, b3, 128, 1, tot);
        }
    std::printf(" random %s %zu of %zu differ |", bad ? "FAIL" : "PASS", bad, tot);
    g_fail += bad != 0;
    if (real_name && !getenv("REAL0")) {
        const std::string gn = std::string("blk.") + real_name + (down ? ".ffn_down_exps.weight" : ".ffn_gate_exps.weight");
        const std::string un = std::string("blk.") + real_name + ".ffn_up_exps.weight";
        uint8_t *rg = real_bank<TY>(q, gn, cols, down ? DOWN_R0 : PAIR_R0, rows);
        uint8_t *ru = down ? nullptr : real_bank<TY>(q, un, cols, PAIR_R0, rows);
        if (rg && (down || ru)) {
            Bank br{rg, ru, x, rids, o1, o2, rows, down};
            size_t rt = 0;
            const size_t rbad = diff<KP, KK>(q, br, 128, 4, rt);
            std::printf(" real blk.%s %s %zu of %zu differ |", real_name, rbad ? "FAIL" : "PASS", rbad, rt);
            g_fail += rbad != 0;
        } else {
            std::printf(" real: none |");
        }
        if (rg) sycl::free(rg, q);
        if (ru) sycl::free(ru, q);
    }
    // timing: production at 128 work-groups, candidate at each of g_wgs, alternated twice
    double tp = 0, tc[16] = {};
    for (int rep = 0; rep < 3; ++rep) {
        tp += time_k<KP>(q, b, g_pwg) / 3;
        for (size_t i = 0; i < g_wgs.size(); ++i) tc[i] += time_k<KK>(q, b, g_wgs[i]) / 3;
    }
    std::printf(" prod wg%zu %.2f us | cand", g_pwg, tp);
    for (size_t i = 0; i < g_wgs.size(); ++i) std::printf(" wg%zu %.2f", g_wgs[i], tc[i]);
    std::printf(" us\n");
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
    std::printf("card %d %s, local memory %zu KiB\n", card, dev.get_info<sycl::info::device::name>().c_str(),
                (size_t)dev.get_info<sycl::info::device::local_mem_size>() / 1024);
    const std::string only = getenv("ONLY") ? getenv("ONLY") : "";
    auto want = [&](const char *f) { return only.empty() || ("," + only + ",").find(std::string(",") + f + ",") != std::string::npos; };
    if (const char *s = getenv("PWG")) g_pwg = std::strtoul(s, nullptr, 10);
    if (const char *s = getenv("WGS")) {
        g_wgs.clear();
        for (const char *p = s; *p;) {
            g_wgs.push_back(std::strtoul(p, (char **)&p, 10));
            if (*p == ',') ++p;
        }
    }

    { // warm the card up (~0.4 s of busy kernels) so that the first case does not time a clocked-down card
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
    std::vector<float> hx(2 * 6 * 2304 + 64);
    for (auto &v : hx) v = ux(rng);
    std::vector<uint32_t> hid(NSET * 12), hrid(NSET * 12);
    for (unsigned s = 0; s < NSET; ++s) {
        std::vector<uint32_t> all(NEXP);
        std::iota(all.begin(), all.end(), 0u);
        std::shuffle(all.begin(), all.end(), rng);
        std::copy(all.begin(), all.begin() + 12, hid.begin() + 12 * s);
        std::vector<uint32_t> ra(NREAL);
        std::iota(ra.begin(), ra.end(), 0u);
        std::shuffle(ra.begin(), ra.end(), rng);
        std::copy(ra.begin(), ra.begin() + 12, hrid.begin() + 12 * s);
    }
    float *x = sycl::malloc_device<float>(hx.size(), q);
    uint32_t *ids = sycl::malloc_device<uint32_t>(hid.size(), q), *rids = sycl::malloc_device<uint32_t>(hrid.size(), q);
    const size_t on = (size_t)6 * 256 * DOWN_ROWS + 256;
    float *o1 = sycl::malloc_device<float>(on, q), *o2 = sycl::malloc_device<float>(on, q);
    q.memcpy(x, hx.data(), hx.size() * 4);
    q.memcpy(ids, hid.data(), hid.size() * 4);
    q.memcpy(rids, hrid.data(), hrid.size() * 4).wait();
    { // HcFinishRows inputs: 25 x 8 positive double partials (24 dots' squares-like sums, last = sum of squares)
        std::vector<double> hd(25 * 8);
        std::uniform_real_distribution<double> ud(0.01, 4.0);
        for (auto &v : hd) v = ud(rng);
        std::vector<float> hs(3 + 24);
        for (auto &v : hs) v = ux(rng);
        double *d = sycl::malloc_device<double>(hd.size(), q);
        float *sb = sycl::malloc_device<float>(hs.size(), q);
        g_exo = sycl::malloc_device<float>(4096, q);
        q.memcpy(d, hd.data(), hd.size() * 8);
        q.memcpy(sb, hs.data(), hs.size() * 4).wait();
        HcMixFinishSG k{5120, 8};
        k.form = getenv("HCF") ? std::atoi(getenv("HCF")) : 1;
        g_ex = HcFinishRows{k, d, sb, sb + 3, g_exo, g_exo + 4, g_exo + 8};
    }
    { // 256 tokens' x (down: 6 slots' x per token) and 1,536 slot ids (repeats allowed, as across tokens)
        std::vector<float> bx((size_t)256 * 6 * 2304 + 64);
        for (auto &v : bx) v = ux(rng);
        std::vector<uint32_t> bi(6 * 256);
        std::uniform_int_distribution<uint32_t> ue(0, NEXP - 1);
        for (auto &v : bi) v = ue(rng);
        float *dx = sycl::malloc_device<float>(bx.size(), q);
        uint32_t *di = sycl::malloc_device<uint32_t>(bi.size(), q);
        q.memcpy(dx, bx.data(), bx.size() * 4);
        q.memcpy(di, bi.data(), bi.size() * 4).wait();
        g_bx = dx, g_bids = di;
    }

    if (want("iq2s_pair")) run_case<Ty::IQ2_S, RoutedIQ2SP<20, ActF32>, RoutedIQ2SPx<20, ActF32>>(q, "IQ2_S pair", false, "30", x, ids, rids, o1, o2);
    if (want("iq1_pair")) run_case<Ty::IQ1_S, RoutedIQ1SP<20, ActF32, true>, RoutedIQ1SPx<20, ActF32>>(q, "IQ1_S pair", false, "5", x, ids, rids, o1, o2);
    if (want("xxs_pair")) run_case<Ty::IQ2_XXS, RoutedIQ2XXSP<20, ActF32>, RoutedIQ2XXSPx<20, ActF32>>(q, "IQ2_XXS pair", false, "12", x, ids, rids, o1, o2);
    if (want("iq2s_down")) run_case<Ty::IQ2_S, RoutedIQ2SP<9, ActF32>, RoutedIQ2SPx<9, ActF32>>(q, "IQ2_S down", true, "12", x, ids, rids, o1, o2);
    if (want("iq3_down")) run_case<Ty::IQ3_XXS, RoutedIQ3XXSP<9, ActF32>, RoutedIQ3XXSPx<9, ActF32>>(q, "IQ3_XXS down", true, "25", x, ids, rids, o1, o2);
    if (want("iq2xs_down")) run_case<Ty::IQ2_XS, RoutedIQ2XSP<9, ActF32>, RoutedIQ2XSPx<9, ActF32>>(q, "IQ2_XS down", true, "5", x, ids, rids, o1, o2);
    if (want("xxs_down")) run_case<Ty::IQ2_XXS, RoutedIQ2XXSP<9, ActF32>, RoutedIQ2XXSPx<9, ActF32>>(q, "IQ2_XXS down", true, "3", x, ids, rids, o1, o2);
    // shapes the dispatch also covers (not in the six-card model's profile): random rows only
    if (want("iq3_pair")) run_case<Ty::IQ3_XXS, RoutedIQ3XXSP<20, ActF32>, RoutedIQ3XXSPx<20, ActF32>>(q, "IQ3_XXS pair", false, nullptr, x, ids, rids, o1, o2);
    if (want("iq2xs_pair")) run_case<Ty::IQ2_XS, RoutedIQ2XSP<20, ActF32>, RoutedIQ2XSPx<20, ActF32>>(q, "IQ2_XS pair", false, nullptr, x, ids, rids, o1, o2);
    if (want("iq1_down")) run_case<Ty::IQ1_S, RoutedIQ1SP<9, ActF32, true>, RoutedIQ1SPx<9, ActF32>>(q, "IQ1_S down", true, nullptr, x, ids, rids, o1, o2);
    // the b forms of IQ2_S / IQ2_XXS (what the selectors pick with extra rows)
    if (want("iq2s_pairb")) run_case<Ty::IQ2_S, RoutedIQ2SP<20, ActF32>, RoutedIQ2SPb<20, ActF32>>(q, "IQ2_S pair b", false, "30", x, ids, rids, o1, o2);
    if (want("xxs_pairb")) run_case<Ty::IQ2_XXS, RoutedIQ2XXSP<20, ActF32>, RoutedIQ2XXSPb<20, ActF32>>(q, "IQ2_XXS pair b", false, "12", x, ids, rids, o1, o2);
    if (want("iq2s_downb")) run_case<Ty::IQ2_S, RoutedIQ2SP<9, ActF32>, RoutedIQ2SPb<9, ActF32>>(q, "IQ2_S down b", true, "12", x, ids, rids, o1, o2);
    if (want("xxs_downb")) run_case<Ty::IQ2_XXS, RoutedIQ2XXSP<9, ActF32>, RoutedIQ2XXSPb<9, ActF32>>(q, "IQ2_XXS down b", true, "3", x, ids, rids, o1, o2);
    // with the extra row (as the gates run it: OWN_HC_FIN=1, finish in the gate + up launch); what the selectors
    // pick then is the b form
    if (want("iq2s_pair_ex")) run_case<Ty::IQ2_S, RoutedIQ2SP<20, ActF32, HcFinishRows>, RoutedIQ2SPx<20, ActF32, HcFinishRows>>(q, "IQ2_S pair ex", false, "30", x, ids, rids, o1, o2);
    if (want("iq1_pair_ex")) run_case<Ty::IQ1_S, RoutedIQ1SP<20, ActF32, true, HcFinishRows>, RoutedIQ1SPx<20, ActF32, HcFinishRows>>(q, "IQ1_S pair ex", false, "5", x, ids, rids, o1, o2);
    if (want("xxs_pair_ex")) run_case<Ty::IQ2_XXS, RoutedIQ2XXSP<20, ActF32, HcFinishRows>, RoutedIQ2XXSPx<20, ActF32, HcFinishRows>>(q, "IQ2_XXS pair ex", false, "12", x, ids, rids, o1, o2);
    if (want("iq3_pair_ex")) run_case<Ty::IQ3_XXS, RoutedIQ3XXSP<20, ActF32, HcFinishRows>, RoutedIQ3XXSPx<20, ActF32, HcFinishRows>>(q, "IQ3_XXS pair ex", false, nullptr, x, ids, rids, o1, o2);
    if (want("iq2s_pairb_ex")) run_case<Ty::IQ2_S, RoutedIQ2SP<20, ActF32, HcFinishRows>, RoutedIQ2SPb<20, ActF32, HcFinishRows>>(q, "IQ2_S pair b ex", false, "30", x, ids, rids, o1, o2);
    if (want("xxs_pairb_ex")) run_case<Ty::IQ2_XXS, RoutedIQ2XXSP<20, ActF32, HcFinishRows>, RoutedIQ2XXSPb<20, ActF32, HcFinishRows>>(q, "IQ2_XXS pair b ex", false, "12", x, ids, rids, o1, o2);
    // many extra rows (TER=n, default 3000: more than the 2,048 sub-groups) through the b forms and the pair forms
    g_tex = TestRows{g_exo, getenv("TER") ? (unsigned)std::atoi(getenv("TER")) : 3000u};
    if (want("iq2s_down_tex")) run_case<Ty::IQ2_S, RoutedIQ2SP<9, ActF32, TestRows>, RoutedIQ2SPx<9, ActF32, TestRows>>(q, "IQ2_S down tex", true, nullptr, x, ids, rids, o1, o2);
    if (want("iq1_down_tex")) run_case<Ty::IQ1_S, RoutedIQ1SP<9, ActF32, true, TestRows>, RoutedIQ1SPx<9, ActF32, TestRows>>(q, "IQ1_S down tex", true, nullptr, x, ids, rids, o1, o2);
    if (want("xxs_down_texd")) run_case<Ty::IQ2_XXS, RoutedIQ2XXSP<9, ActF32, TestRows>, RoutedIQ2XXSPd<9, ActF32, TestRows>>(q, "IQ2_XXS down d tex", true, nullptr, x, ids, rids, o1, o2);
    if (want("iq2s_pair_texe")) run_case<Ty::IQ2_S, RoutedIQ2SP<20, ActF32, TestRows>, RoutedIQ2SPe<20, ActF32, TestRows>>(q, "IQ2_S pair e tex", false, nullptr, x, ids, rids, o1, o2);
    if (want("iq2xs_pair_ex")) run_case<Ty::IQ2_XS, RoutedIQ2XSP<20, ActF32, HcFinishRows>, RoutedIQ2XSPx<20, ActF32, HcFinishRows>>(q, "IQ2_XS pair ex", false, nullptr, x, ids, rids, o1, o2);
    sycl::free(x, q);
    sycl::free(ids, q);
    sycl::free(rids, q);
    sycl::free(o1, q);
    sycl::free(o2, q);
    std::printf("%s\n", g_fail ? "FAIL" : "PASS");
    return g_fail ? 1 : 0;
}
