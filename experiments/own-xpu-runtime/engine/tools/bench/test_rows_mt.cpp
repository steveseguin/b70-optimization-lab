// Multi-token rows (rowm<MT>, sycl_v41.hpp "multi-token rows") against the one-token kernels, BITWISE per
// token, on one card: every dense row kernel of the multi-token step at its production shapes
// (GemvQ8P, GemvQ6KP, GemvQ5KP, GemvH16P, GemvF32P, GemvT<BF16>, HcMixDotsP), MT in {1, 4, 6, 8, 16},
// mt in {MT, MT - 1}. Reference: the existing one-token launch, once per token. Rows of tokens >= mt and
// the padding between tokens must stay untouched. Also the adapters in one fused launch
// (RowsP<RowsPair<HcDotsRowsM, DenseRowsM<GemvQ8P<160>>>>, as launch_dense_ex composes them).
// Timing (GPU event time): MT one-token launches against one MT-token launch at MT = 8 and 16, warm
// (back to back: the matrix stays in the card's cache) and cold (a 128 MiB write before every launch,
// as in a decode step where the matrix was evicted). Exit status 1 on any mismatch.
// Random packed rows as planning/dsv41-fixtures/test_packed_v41_device.cpp (half scales 1e-3..2e-3),
// per-token strides padded (xs = x floats + 32, ys = rows + 8) so a stride slip shows.
//
//   source /opt/intel/oneapi/setvars.sh; cd engine
//   icpx -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off -Wno-deprecated-declarations -I src \
//     tools/bench/test_rows_mt.cpp -o /tmp/test_rows_mt
//   (add -fsycl-targets=intel_gpu_bmg_g31 to compile the ~65 kernels ahead of time instead of at first launch)
//   LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib /tmp/test_rows_mt [CARD]
//   ONLY=q8,q6,q5,h16,f32,bf16,hc,fused selects tests; NOTIME=1 skips the timing.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
using namespace ops41sycl;

static constexpr unsigned MTMAX = 16;          // buffers hold 16 tokens
static constexpr size_t FLUSH_WORDS = (size_t)32 << 20; // 128 MiB written before every cold launch
static uint32_t *g_flush = nullptr;
static int g_fail = 0;
static bool g_time = true;

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
static void flush(sycl::queue &q, uint32_t v) {
    uint32_t *p = g_flush;
    q.parallel_for(sycl::range<1>(FLUSH_WORDS), [=](sycl::id<1> i) { p[i] = v; });
}
template <typename T> T *dev_copy(sycl::queue &q, const std::vector<T> &h) {
    T *d = sycl::malloc_device<T>(h.size(), q);
    for (size_t o = 0; o < h.size(); o += (16 << 20))
        q.memcpy(d + o, h.data() + o, std::min<size_t>(16 << 20, h.size() - o) * sizeof(T));
    q.wait();
    return d;
}
static std::vector<float> rand_f(size_t n, unsigned seed, float lo, float hi) {
    std::mt19937 rng(seed);
    std::uniform_real_distribution<float> u(lo, hi);
    std::vector<float> v(n);
    for (auto &f : v) f = u(rng);
    return v;
}
// packed rows of a GGUF block format: random bytes, sane half scales (any other byte is a valid code)
template <iq3::Type T> std::vector<uint8_t> packed_rows(unsigned cols, unsigned rows, unsigned seed) {
    constexpr auto L = iq3::layout(T);
    const size_t rb = (size_t)cols / L.elements * L.bytes, prb = pk41::packed_row_bytes(T, cols);
    std::mt19937 rng(seed);
    std::vector<uint8_t> hw((size_t)rows * rb);
    for (auto &b : hw) b = uint8_t(rng());
    for (size_t blk = 0; blk < hw.size() / L.bytes; ++blk) {
        uint8_t *bp = hw.data() + blk * L.bytes;
        auto put = [&](size_t off) { uint16_t h = 0x1400 + (rng() & 0x3ff); bp[off] = h & 255; bp[off + 1] = h >> 8; };
        if (T == iq3::Type::Q8_0) put(0);
        if (T == iq3::Type::Q6_K) put(208);
        if (T == iq3::Type::Q5_K) { put(0); put(2); }
    }
    std::vector<uint8_t> hp((size_t)rows * prb);
    for (size_t r = 0; r < rows; ++r) pk41::pack_row(T, hw.data() + r * rb, hp.data() + r * prb, cols);
    return hp;
}
// F32 rows (GemvF32P), or F32 rows with zero low halves stored as their upper halves (GemvH16P,
// pk41::pack_row F32), or BF16 rows (GemvT<BF16>): finite values in +-0.05
static std::vector<uint8_t> float_rows(unsigned cols, unsigned rows, unsigned seed, int kind /*0 f32, 1 h16, 2 bf16*/) {
    const std::vector<float> f = rand_f((size_t)cols * rows, seed, -0.05f, 0.05f);
    std::vector<uint8_t> out;
    if (kind == 0) {
        out.resize(f.size() * 4);
        std::memcpy(out.data(), f.data(), out.size());
    } else if (kind == 1) {
        std::vector<uint8_t> src(f.size() * 4);
        for (size_t i = 0; i < f.size(); ++i) {
            uint32_t u;
            std::memcpy(&u, &f[i], 4);
            u &= 0xFFFF0000u;
            std::memcpy(&src[i * 4], &u, 4);
        }
        const size_t prb = pk41::packed_row_bytes(iq3::Type::F32, cols);
        out.resize((size_t)rows * prb);
        for (size_t r = 0; r < rows; ++r) pk41::pack_row(iq3::Type::F32, src.data() + r * cols * 4, out.data() + r * prb, cols);
    } else {
        out.resize(f.size() * 2);
        for (size_t i = 0; i < f.size(); ++i) {
            uint32_t u;
            std::memcpy(&u, &f[i], 4);
            const uint16_t h = (uint16_t)(u >> 16);
            std::memcpy(&out[i * 2], &h, 2);
        }
    }
    return out;
}

// ---- kernel families: one(q, t, y) = the one-token launch for token t; many<MT>(q, mt, y) = one launch ----
// packed dense kernel K (GemvQ8P / GemvQ6KP / GemvQ5KP / GemvH16P / GemvF32P), launched as launch_rows does
template <typename K> struct DenseFam {
    using E = float;
    char name[64];
    K k;
    unsigned nout;
    size_t xs, ys, wbytes;
    const uint8_t *w;
    const float *x;
    size_t nwg() const { return ((size_t)k.rows + 15) / 16; }
    sycl::event one(sycl::queue &q, unsigned t, E *y) const {
        const K kk = k;
        const uint8_t *ww = w;
        const float *xx = x + t * xs;
        E *yy = y + t * ys;
        return q.parallel_for(sycl::nd_range<1>(nwg() * 512, 512),
                              [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kk(it, ww, xx, yy); });
    }
    template <unsigned MT> sycl::event many(sycl::queue &q, unsigned mt, E *y) const {
        const DenseM<K, MT> km{k, xs, ys, mt};
        const uint8_t *ww = w;
        const float *xx = x;
        return q.parallel_for(sycl::nd_range<1>(nwg() * 512, 512),
                              [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { km(it, ww, xx, y); });
    }
};
// T: the GGUF format of the packed rows (Q8_0 / Q6_K / Q5_K), or F32 (FK 0: plain F32 rows, GemvF32P;
// FK 1: F32 rows with zero low halves stored as upper halves, GemvH16P)
template <typename K, iq3::Type T, int FK = 0>
DenseFam<K> dense_fam(sycl::queue &q, const char *name, unsigned cols, unsigned rows, unsigned xn, unsigned seed) {
    DenseFam<K> f{};
    std::snprintf(f.name, sizeof f.name, "%s %ux%u%s", name, cols, rows, xn ? " grouped" : "");
    f.k = K{};
    f.k.rows = rows;
    if constexpr (requires(K &kk) { kk.xn; }) f.k.xn = xn;
    f.nout = rows;
    const size_t nx = xn ? (size_t)rows / xn * cols : cols;
    f.xs = nx + 32;
    f.ys = rows + 8;
    std::vector<uint8_t> hw;
    if constexpr (T == iq3::Type::F32) hw = float_rows(cols, rows, seed, FK);
    else hw = packed_rows<T>(cols, rows, seed);
    f.wbytes = hw.size();
    f.w = dev_copy(q, hw);
    f.x = dev_copy(q, rand_f(MTMAX * f.xs, seed + 1, -2.0f, 2.0f));
    return f;
}

// GemvT<BF16, ActF32> (compressor / indexer matrices), launched as launch_sg does
struct BF16Fam {
    using E = float;
    using K = GemvT<iq3::Type::BF16, ActF32>;
    char name[64];
    K k;
    unsigned nout;
    size_t xs, ys, wbytes;
    const uint8_t *w;
    const float *x;
    sycl::event one(sycl::queue &q, unsigned t, E *y) const {
        const K kk = k;
        const uint8_t *ww = w;
        const float *xx = x + t * xs;
        void *yy = y + t * ys;
        return q.parallel_for(sycl::nd_range<1>((size_t)k.rows * 32, 32),
                              [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { kk(it, ww, xx, yy); });
    }
    template <unsigned MT> sycl::event many(sycl::queue &q, unsigned mt, E *y) const {
        const GemvTM<iq3::Type::BF16, ActF32, MT> km{k, xs, ys, mt};
        const uint8_t *ww = w;
        const float *xx = x;
        void *yy = y;
        return q.parallel_for(sycl::nd_range<1>((size_t)k.rows * 32, 32),
                              [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { km(it, ww, xx, yy); });
    }
};
static BF16Fam bf16_fam(sycl::queue &q, unsigned cols, unsigned rows, unsigned seed) {
    BF16Fam f{};
    std::snprintf(f.name, sizeof f.name, "GemvT<BF16> %ux%u", cols, rows);
    f.k = BF16Fam::K{rows, cols, false};
    f.nout = rows;
    f.xs = cols + 32;
    f.ys = rows + 8;
    const std::vector<uint8_t> hw = float_rows(cols, rows, seed, 2);
    f.wbytes = hw.size();
    f.w = dev_copy(q, hw);
    f.x = dev_copy(q, rand_f(MTMAX * f.xs, seed + 1, -2.0f, 2.0f));
    return f;
}

// HcMixDotsP<5120, 8>: 25 x 8 double partials per token (24 fn rows + the sum of squares)
struct HcFam {
    using E = double;
    static constexpr unsigned H = 5120, SEG = 8;
    char name[64];
    unsigned nout;
    size_t xs, ys, wbytes;
    const float *st, *fn;
    sycl::event one(sycl::queue &q, unsigned t, E *y) const {
        const HcMixDotsP<H, SEG> k{};
        const float *ss = st + t * xs, *ff = fn;
        E *yy = y + t * ys;
        return q.parallel_for(sycl::nd_range<1>((size_t)25 * SEG * 32, 32),
                              [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { k(it, ss, ff, yy); });
    }
    template <unsigned MT> sycl::event many(sycl::queue &q, unsigned mt, E *y) const {
        const HcMixDotsPM<H, SEG, MT> km{xs, ys, mt};
        const float *ss = st, *ff = fn;
        return q.parallel_for(sycl::nd_range<1>((size_t)25 * SEG * 32, 32),
                              [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] { km(it, ss, ff, y); });
    }
};
static HcFam hc_fam(sycl::queue &q, unsigned seed) {
    HcFam f{};
    std::snprintf(f.name, sizeof f.name, "HcMixDotsP<5120,8>");
    f.nout = 25 * HcFam::SEG;
    f.xs = 4 * HcFam::H + 64;
    f.ys = f.nout + 8;
    const std::vector<float> fn = rand_f((size_t)24 * 4 * HcFam::H, seed, -0.02f, 0.02f);
    f.wbytes = fn.size() * 4;
    f.fn = dev_copy(q, fn);
    f.st = dev_copy(q, rand_f(MTMAX * f.xs, seed + 1, -2.0f, 2.0f));
    return f;
}

// ---- checks ----------------------------------------------------------------------------------------------
// got vs ref for tokens t < mt (rows i < nout); every other element (tokens >= mt, padding) must still
// hold the 0xff fill
template <typename E>
static void compare(const std::vector<E> &got, const std::vector<E> &ref, unsigned mt, unsigned nout, size_t ys,
                    size_t &differ, size_t &stray) {
    differ = stray = 0;
    for (unsigned t = 0; t < MTMAX; ++t)
        for (size_t i = 0; i < ys; ++i) {
            const E *g = &got[t * ys + i];
            if (t < mt && i < nout) {
                differ += std::memcmp(g, &ref[t * ys + i], sizeof(E)) != 0;
            } else {
                const uint8_t *b = reinterpret_cast<const uint8_t *>(g);
                bool ff = true;
                for (size_t j = 0; j < sizeof(E); ++j) ff = ff && b[j] == 0xff;
                stray += !ff;
            }
        }
}
static void report(const char *name, unsigned MT, unsigned mt, size_t differ, size_t of, size_t stray) {
    const bool ok = !differ && !stray;
    g_fail += !ok;
    std::printf("%s %-36s MT %2u mt %2u | differ %zu of %zu | stray writes %zu\n", ok ? "PASS" : "FAIL", name, MT, mt,
                differ, of, stray);
    std::fflush(stdout);
}
template <unsigned MT, typename F>
static void check(sycl::queue &q, const F &f, typename F::E *ym, const std::vector<typename F::E> &ref) {
    using E = typename F::E;
    const size_t n = (size_t)MTMAX * f.ys;
    std::vector<E> got(n);
    const unsigned mts[2] = {MT, MT - 1};
    for (unsigned j = 0; j < (MT > 1 ? 2u : 1u); ++j) {
        const unsigned mt = mts[j];
        q.memset(ym, 0xff, n * sizeof(E)).wait();
        f.template many<MT>(q, mt, ym).wait();
        q.memcpy(got.data(), ym, n * sizeof(E)).wait();
        size_t differ, stray;
        compare(got, ref, mt, f.nout, f.ys, differ, stray);
        report(f.name, MT, mt, differ, (size_t)mt * f.nout, stray);
    }
}
template <unsigned MT, typename F>
static void timing(sycl::queue &q, const F &f, typename F::E *yr, typename F::E *ym) {
    for (int i = 0; i < 300; ++i) f.one(q, i % MT, yr); // warm the card's clock (idle cards run slower)
    for (int i = 0; i < 40; ++i) f.template many<MT>(q, MT, ym);
    q.wait();
    double w1 = 1e30, wm = 1e30, c1 = 1e30, cm = 1e30;
    std::vector<sycl::event> ev(MT);
    for (unsigned rep = 0; rep < 10; ++rep) {
        for (unsigned t = 0; t < MT; ++t) ev[t] = f.one(q, t, yr);
        sycl::event em = f.template many<MT>(q, MT, ym);
        q.wait();
        double s = 0;
        for (auto &e : ev) s += ev_us(e);
        w1 = std::min(w1, s);
        wm = std::min(wm, ev_us(em));
        for (unsigned t = 0; t < MT; ++t) {
            flush(q, rep * 64 + t);
            ev[t] = f.one(q, t, yr);
        }
        flush(q, rep * 64 + 63);
        em = f.template many<MT>(q, MT, ym);
        q.wait();
        s = 0;
        for (auto &e : ev) s += ev_us(e);
        c1 = std::min(c1, s);
        cm = std::min(cm, ev_us(em));
    }
    std::printf("time %-36s MT %2u | warm: %2u one-token %8.1f us, one launch %8.1f us (x%5.2f) | cold: %8.1f us vs "
                "%8.1f us (x%5.2f) = %6.1f us/token | weights %.2f MB\n",
                f.name, MT, MT, w1, wm, w1 / wm, c1, cm, c1 / cm, cm / MT, f.wbytes / 1e6);
    std::fflush(stdout);
}
// references (one-token launch per token, all MTMAX tokens), then every (MT, mt), then the timing
template <typename F> static std::vector<typename F::E> run_family(sycl::queue &q, const F &f) {
    using E = typename F::E;
    const size_t n = (size_t)MTMAX * f.ys;
    E *yr = sycl::malloc_device<E>(n, q), *ym = sycl::malloc_device<E>(n, q);
    q.memset(yr, 0xff, n * sizeof(E)).wait();
    for (unsigned t = 0; t < MTMAX; ++t) f.one(q, t, yr);
    q.wait();
    std::vector<E> ref(n);
    q.memcpy(ref.data(), yr, n * sizeof(E)).wait();
    size_t bad = 0, same01 = 0;
    for (unsigned t = 0; t < MTMAX; ++t)
        for (unsigned i = 0; i < f.nout; ++i) bad += !std::isfinite((double)ref[t * f.ys + i]);
    for (unsigned i = 0; i < f.nout; ++i) same01 += std::memcmp(&ref[i], &ref[f.ys + i], sizeof(E)) == 0;
    if (bad || same01 == f.nout) { // a vacuous reference would pass anything
        std::printf("FAIL %-36s reference: %zu non-finite, token 0 == token 1 on %zu of %u rows\n", f.name, bad, same01, f.nout);
        ++g_fail;
    }
    check<1>(q, f, ym, ref);
    check<4>(q, f, ym, ref);
    check<6>(q, f, ym, ref);
    check<8>(q, f, ym, ref);
    check<16>(q, f, ym, ref);
    if (g_time) {
        timing<8>(q, f, yr, ym);
        timing<16>(q, f, yr, ym);
    }
    sycl::free(yr, q);
    sycl::free(ym, q);
    return ref;
}

// The adapters in one launch, composed as launch_dense_ex does (extra rows first):
// RowsP<RowsPair<HcDotsRowsM, DenseRowsM<GemvQ8P<160>>>> against both families' one-token references.
using Q8K160 = GemvQ8P<160, ActF32>;
template <unsigned MT>
static void fused(sycl::queue &q, const HcFam &hc, const std::vector<double> &href, const DenseFam<Q8K160> &d8,
                  const std::vector<float> &dref) {
    using R1 = HcDotsRowsM<5120, 8, MT>;
    using R2 = DenseRowsM<Q8K160, MT>;
    using R = RowsPair<R1, R2>;
    const size_t nh = (size_t)MTMAX * hc.ys, nd = (size_t)MTMAX * d8.ys;
    double *ho = sycl::malloc_device<double>(nh, q);
    float *dout = sycl::malloc_device<float>(nd, q);
    std::vector<double> gh(nh);
    std::vector<float> gd(nd);
    const unsigned mts[2] = {MT, MT - 1};
    for (unsigned j = 0; j < (MT > 1 ? 2u : 1u); ++j) {
        const unsigned mt = mts[j];
        q.memset(ho, 0xff, nh * 8);
        q.memset(dout, 0xff, nd * 4).wait();
        const RowsP<R> kr{R{R1{hc.st, hc.xs, hc.fn, ho, hc.ys, mt}, R2{d8.k, d8.w, d8.x, d8.xs, dout, d8.ys, mt}}};
        const size_t nwg = ((size_t)kr.rows.n() + 15) / 16;
        q.parallel_for(sycl::nd_range<1>(nwg * 512, 512), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
             kr(it);
         }).wait();
        q.memcpy(gh.data(), ho, nh * 8);
        q.memcpy(gd.data(), dout, nd * 4).wait();
        size_t d1, s1, d2, s2;
        compare(gh, href, mt, hc.nout, hc.ys, d1, s1);
        compare(gd, dref, mt, d8.nout, d8.ys, d2, s2);
        report("fused HcDotsRowsM + DenseRowsM<Q8 160>", MT, mt, d1 + d2, (size_t)mt * (hc.nout + d8.nout), s1 + s2);
    }
    sycl::free(ho, q);
    sycl::free(dout, q);
}

int main(int argc, char **argv) {
    const int card = argc > 1 ? std::atoi(argv[1]) : 0;
    if (const char *e = std::getenv("NOTIME")) g_time = !(e[0] && e[0] != '0');
    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    const sycl::device dev = l0.at(card);
    const sycl::context ctx(dev); // one context per card
    sycl::queue q(ctx, dev, {sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
    std::printf("card %d %s\n", card, dev.get_info<sycl::info::device::name>().c_str());
    if (g_time) g_flush = sycl::malloc_device<uint32_t>(FLUSH_WORDS, q);
    const char *only = std::getenv("ONLY");
    auto want = [&](const char *n) { return !only || std::strstr(only, n); };
    using T = iq3::Type;
    std::vector<void *> keep;
    auto drop = [&](const auto &f) { keep.push_back((void *)f.w); keep.push_back((void *)f.x); };

    DenseFam<Q8K160> q8a{};
    std::vector<float> q8a_ref;
    if (want("q8") || want("fused")) {
        q8a = dense_fam<Q8K160, T::Q8_0>(q, "GemvQ8P<160>", 5120, 1280, 0, 101);
        drop(q8a);
        q8a_ref = run_family(q, q8a);
    }
    if (want("q8")) {
        auto f1 = dense_fam<GemvQ8P<40, ActF32>, T::Q8_0>(q, "GemvQ8P<40>", 1280, 4096, 0, 102);
        drop(f1);
        run_family(q, f1);
        auto f2 = dense_fam<GemvQ8P<128, ActF32>, T::Q8_0>(q, "GemvQ8P<128>", 4096, 2048, 1024, 103);
        drop(f2);
        run_family(q, f2);
    }
    if (want("q6")) {
        auto f1 = dense_fam<GemvQ6KP<20, ActF32>, T::Q6_K>(q, "GemvQ6KP<20>", 5120, 1280, 0, 201);
        drop(f1);
        run_family(q, f1);
        auto f2 = dense_fam<GemvQ6KP<16, ActF32>, T::Q6_K>(q, "GemvQ6KP<16>", 4096, 2048, 1024, 202);
        drop(f2);
        run_family(q, f2);
    }
    if (want("q5")) {
        auto f1 = dense_fam<GemvQ5KP<9, ActF32>, T::Q5_K>(q, "GemvQ5KP<9>", 2304, 848, 0, 301);
        drop(f1);
        run_family(q, f1);
    }
    if (want("h16")) {
        auto f1 = dense_fam<GemvH16P<160, ActF32>, T::F32, 1>(q, "GemvH16P<160>", 5120, 384, 0, 401);
        drop(f1);
        run_family(q, f1);
    }
    if (want("f32")) {
        auto f1 = dense_fam<GemvF32P<160, ActF32>, T::F32>(q, "GemvF32P<160>", 5120, 384, 0, 501);
        drop(f1);
        run_family(q, f1);
    }
    if (want("bf16")) {
        auto f1 = bf16_fam(q, 1280, 4096, 601);
        drop(f1);
        run_family(q, f1);
        auto f2 = bf16_fam(q, 5120, 512, 602);
        drop(f2);
        run_family(q, f2);
    }
    HcFam hc{};
    std::vector<double> hc_ref;
    if (want("hc") || want("fused")) {
        hc = hc_fam(q, 701);
        keep.push_back((void *)hc.st);
        keep.push_back((void *)hc.fn);
        hc_ref = run_family(q, hc);
    }
    if (want("fused")) {
        fused<4>(q, hc, hc_ref, q8a, q8a_ref);
        fused<16>(q, hc, hc_ref, q8a, q8a_ref);
    }
    for (void *p : keep) sycl::free(p, q);
    if (g_flush) sycl::free(g_flush, q);
    std::printf("%s: %d failed check(s)\n", g_fail ? "FAIL" : "PASS", g_fail);
    return g_fail ? 1 : 0;
}
