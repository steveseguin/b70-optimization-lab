// test_cert_layout: host-only checks of src/cert_layout.hpp (the per-tensor lossless-layout certificate, F32_HI16).
//   g++ -std=c++20 -O2 -Wall -Wextra -ffp-contract=off -fsanitize=undefined,alignment tools/test_cert_layout.cpp -o test_cert_layout
//   UBSAN_OPTIONS=halt_on_error=1 ./test_cert_layout [model.gguf]   (TMPDIR: where the small synthetic GGUFs go, deleted after)
// With a GGUF (the CPU only; reads the selected tensors' bytes): the engine's selection (cert::inkling2::half_target,
// half_group) over the checkpoint, every group certified and packed as certify_half does, every element decoded back
// and compared with the file's 32 bits, and every row's dot product (gemv1_rows order) compared bit for bit.
// (also with -DINK_NO_FMA: products rounded before the addition, as the engine's baselines v1 / v2)
// Checks: certification pass / fail (a single low bit at the first, a middle and the last element; counts and first
// index), group all-or-nothing, the exact 32-bit round trip of every halfword and of the special values (+-0, normals,
// subnormals, +-Inf, NaN payloads in the upper half), the packed-word decode pl::F32H and CtlRows<true> use (element 2k
// in the low half of word k), and bit equality of dot products in the kernels' fixed orders (gemv1_rows: 16 lanes,
// chunks l, l + 16, ..., each chunk's 32 products in index order, lane sums in chunk order, the xor butterfly; CtlRows:
// 16 virtual lanes in registers) between the FP32 weights and their decoded halfwords. Also the checked inputs:
// unaligned source / destination buffers (memcpy access), zero / overflowing / unrepresentable dimensions (no division
// before the check), byte size != 4 x elements, destination capacity and parallel-vector lengths, gain / forget pairs
// (formed before eligibility; mismatched shapes refuse the model; one ineligible member keeps both FP32), strict
// INK_CERT_HALF parsing, FNV-1a 64 against the published vectors, and the GGUF reader's duplicate-name and dimension
// checks on small synthetic files. Prints PASS / FAIL lines.
#include "../src/cert_layout.hpp"
#include "../src/gguf.hpp"
#include <map>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <functional>
#include <random>
#include <unistd.h>
#include <vector>

using namespace ink::cert;

static int fails = 0, checks = 0;
static void expect(bool ok, const char *what) {
    ++checks;
    if (!ok) { ++fails; std::printf("FAIL %s\n", what); }
}
static uint32_t bits(float f) { return std::bit_cast<uint32_t>(f); }
static bool throws(const std::function<void()> &f, const char *needle = nullptr) {
    try { f(); } catch (const std::exception &e) { return !needle || std::strstr(e.what(), needle); }
    return false;
}
// the engine's descriptor (gemv2.hpp half_desc)
static inkling2::TDesc desc_of(const ink::Tensor &t) {
    inkling2::TDesc e;
    e.name = t.name; e.is_f32 = t.type == ink::G_F32; e.bytes = t.bytes;
    e.nne = std::min<size_t>(t.ne.size(), 4);
    for (size_t i = 0; i < e.nne; ++i) e.ne[i] = t.ne[i];
    return e;
}
static inkling2::TDesc desc(const std::string &name, bool f32, int64_t ne0, int64_t ne1, uint64_t bytes = 0) {
    inkling2::TDesc e;
    e.name = name; e.is_f32 = f32; e.ne[0] = ne0; e.ne[1] = ne1; e.nne = 2;
    e.bytes = bytes ? bytes : (ne0 > 0 && ne1 > 0 ? 4 * (uint64_t)ne0 * (uint64_t)ne1 : 0);
    return e;
}

// the engine's mac (formats.hpp): one rounding per term, or a rounded product then the addition (INK_NO_FMA)
static float mac(float acc, float a, float b) {
#ifdef INK_NO_FMA
    const float p = a * b;
    return acc + p;
#else
    return std::fma(a, b, acc);
#endif
}
constexpr int SG = 16;

// pl::F32H::decode32 on the host: chunk c of a packed row, read as 32-bit words (little endian), two values per word
static void decode32_hi16(const uint16_t *row, int c, float *o) {
    uint32_t w[16];
    std::memcpy(w, row + 32 * c, sizeof w);
    for (int k = 0; k < 16; ++k) { o[2 * k] = f32_even_from_pair(w[k]); o[2 * k + 1] = f32_odd_from_pair(w[k]); }
}
static void decode32_f32(const float *row, int c, float *o) { for (int i = 0; i < 32; ++i) o[i] = row[32 * c + i]; }
// gemv1_rows' order for one row (lanes l = 0..15 take chunks l, l + 16, ...; then sg_sum's xor butterfly)
template <class Dec> static float gemv_row(Dec dec, int cols, const float *x) {
    float lane[SG];
    const int nc = cols / 32;
    for (int l = 0; l < SG; ++l) {
        float acc = 0.0f;
        for (int c = l; c < nc; c += SG) {
            float o[32];
            dec(c, o);
            float s = 0.0f;
            for (int i = 0; i < 32; ++i) s = mac(s, o[i], x[32 * c + i]);
            acc += s;
        }
        lane[l] = acc;
    }
    for (int off = SG / 2; off > 0; off >>= 1) {
        float t[SG];
        for (int l = 0; l < SG; ++l) t[l] = lane[l] + lane[l ^ off];
        std::memcpy(lane, t, sizeof t);
    }
    return lane[0];
}
// CtlRows<true>'s streamed form: each word's two values multiplied as they are decoded, chunk sums into va[c % 16]
static float ctlrows_row_streamed(const uint16_t *row, int cols, const float *x) {
    float va[SG] = {};
    for (int c = 0; c < cols / 32; ++c) {
        uint32_t w[16];
        std::memcpy(w, row + 32 * c, sizeof w);
        float sm = 0.0f;
        for (int q = 0; q < 4; ++q)
            for (int k = 0; k < 4; ++k) {
                sm = mac(sm, f32_even_from_pair(w[4 * q + k]), x[32 * c + 8 * q + 2 * k]);
                sm = mac(sm, f32_odd_from_pair(w[4 * q + k]), x[32 * c + 8 * q + 2 * k + 1]);
            }
        va[c % SG] += sm;
    }
    for (int off = SG / 2; off > 0; off >>= 1) {
        float t[SG];
        for (int l = 0; l < SG; ++l) t[l] = va[l] + va[l ^ off];
        std::memcpy(va, t, sizeof t);
    }
    return va[0];
}
static float ctlrows_row_f32(const float *row, int cols, const float *x) {
    float va[SG] = {};
    for (int c = 0; c < cols / 32; ++c) {
        float sm = 0.0f;
        for (int i = 0; i < 32; ++i) sm = mac(sm, row[32 * c + i], x[32 * c + i]);
        va[c % SG] += sm;
    }
    for (int off = SG / 2; off > 0; off >>= 1) {
        float t[SG];
        for (int l = 0; l < SG; ++l) t[l] = va[l] + va[l ^ off];
        std::memcpy(va, t, sizeof t);
    }
    return va[0];
}

// a weight matrix as the checkpoint's: random finite FP32 values with zero low halfwords (bf16-representable),
// magnitudes like the router / control weights
static std::vector<uint32_t> make_weights(size_t n, std::mt19937 &rng) {
    std::normal_distribution<float> nd(0.0f, 0.02f);
    std::vector<uint32_t> w(n);
    for (auto &u : w) u = bits(nd(rng)) & 0xFFFF0000u;
    return w;
}

// the checkpoint: the engine's selection and groups, certified and packed; decoded bits and row products compared
static void check_model(const char *path, std::mt19937 &rng) {
    ink::GGUF g(path);
    const bool arch = g.has("general.architecture") && g.s("general.architecture") == "inkling2";
    expect(arch, "model: architecture inkling2 (the engine certifies only this architecture)");
    // the engine's plan (certify_half): pairs formed by name first, shapes checked against the GGUF's gate_rank x n_embd
    std::vector<inkling2::TDesc> descs;
    for (auto &t : g.tensors) descs.push_back(desc_of(t));
    const auto plan = inkling2::plan_groups(descs, g.i("inkling2.loop.gate_rank"), g.i("inkling2.embedding_length"));
    std::vector<std::vector<const ink::Tensor *>> groups;
    size_t n_pairs = 0;
    for (const auto &ix : plan) {
        groups.emplace_back();
        for (size_t i : ix) groups.back().push_back(&g.tensors[i]);
        n_pairs += ix.size() == 2;
    }
    expect(n_pairs == 48, "model: 48 gain / forget pairs planned as pairs");
    Census cs;
    size_t n_router = 0, n_down = 0, n_gf = 0, bad_bits = 0, bad_rows = 0, rows_checked = 0;
    std::normal_distribution<float> xd(0.0f, 1.0f);
    for (const auto &ts : groups) {
        std::vector<std::vector<uint32_t>> src(ts.size());
        std::vector<std::vector<uint16_t>> dst(ts.size());
        std::vector<std::string> names;
        std::vector<const void *> sp;
        std::vector<size_t> ns, dns;
        std::vector<void *> dp;
        std::vector<Extent> ex;
        for (size_t k = 0; k < ts.size(); ++k) {
            ex.push_back(f32_extent(ts[k]->ne.data(), ts[k]->ne.size(), ts[k]->bytes));
            const size_t n = ex.back().elems;
            src[k].resize(n); dst[k].resize(n);
            g.read_at(src[k].data(), 4 * n, g.data_off + ts[k]->off);
            names.push_back(ts[k]->name); sp.push_back(src[k].data()); ns.push_back(n);
            dp.push_back(dst[k].data()); dns.push_back(dst[k].size());
        }
        auto cr = certify_group_f32_hi16(names, sp, ns, dp, dns);
        for (size_t k = 0; k < ts.size(); ++k) {
            cs.add(cr[k]);
            const std::string &nm = ts[k]->name;
            if (inkling2::ends_with(nm, ".ffn_gate_inp.weight")) ++n_router;
            else if (inkling2::ends_with(nm, "_down.weight")) ++n_down;
            else ++n_gf;
            if (cr[k].layout != Layout::F32_HI16) continue;
            for (size_t i = 0; i < ns[k]; ++i) bad_bits += bits(f32_from_hi16(dst[k][i])) != src[k][i];
            const int cols = ex[k].cols, rows = ex[k].rows; // (from the checked extent, not t.rows())
            std::vector<float> wf(ns[k]); // the file's FP32 values, each word bit_cast (no float* over uint32_t storage)
            for (size_t i = 0; i < ns[k]; ++i) wf[i] = std::bit_cast<float>(src[k][i]);
            std::vector<float> x(cols);
            for (auto &v : x) v = xd(rng);
            for (int r = 0; r < rows; ++r) {
                const float *rf = wf.data() + (size_t)r * cols;
                const uint16_t *rh = dst[k].data() + (size_t)r * cols;
                const float a = gemv_row([&](int cc, float *o) { decode32_f32(rf, cc, o); }, cols, x.data());
                const float b = gemv_row([&](int cc, float *o) { decode32_hi16(rh, cc, o); }, cols, x.data());
                bad_rows += bits(a) != bits(b);
                if (cols <= 32 * SG) bad_rows += bits(ctlrows_row_f32(rf, cols, x.data())) != bits(ctlrows_row_streamed(rh, cols, x.data()));
                ++rows_checked;
            }
        }
    }
    std::printf("model census: %s\n", cs.summary().c_str());
    std::printf("model tensors: %zu routers, %zu loop down, %zu gain/forget; %zu rows' products compared\n", n_router, n_down, n_gf, rows_checked);
    expect(n_router == 24 && n_down == 48 && n_gf == 96, "model: the selection is the 168 tensors (24 / 48 / 96)");
    expect(cs.n_packed == 168 && cs.n_kept == 0 && cs.src_packed == 141557760 && cs.dst_packed == 70778880,
           "model: all 168 certified, 141.6 MB -> 70.8 MB");
    expect(bad_bits == 0, "model: every decoded element equals the file's 32 bits");
    expect(bad_rows == 0, "model: every row's product (gemv1_rows and CtlRows orders) bit-identical");
}

// a small GGUF v3 file (architecture inkling2, the given tensor table, data_bytes of zeros) under $TMPDIR; returns its path
struct GT { std::string name; std::vector<uint64_t> dims; uint32_t type; uint64_t off; };
static std::string write_gguf(const std::vector<GT> &ts, size_t data_bytes) {
    std::vector<uint8_t> b;
    auto put = [&](const void *p, size_t n) { const uint8_t *c = (const uint8_t *)p; b.insert(b.end(), c, c + n); };
    auto u32 = [&](uint32_t v) { put(&v, 4); };
    auto u64 = [&](uint64_t v) { put(&v, 8); };
    auto str = [&](const std::string &x) { u64(x.size()); put(x.data(), x.size()); };
    put("GGUF", 4); u32(3); u64(ts.size()); u64(1);
    str("general.architecture"); u32(8); str("inkling2");
    for (const GT &t : ts) {
        str(t.name); u32((uint32_t)t.dims.size());
        for (uint64_t d : t.dims) u64(d);
        u32(t.type); u64(t.off);
    }
    while (b.size() % 32) b.push_back(0);
    b.resize(b.size() + data_bytes, 0);
    const char *td = std::getenv("TMPDIR");
    std::string path = std::string(td && *td ? td : "/tmp") + "/test_cert_layout_XXXXXX";
    std::vector<char> pb(path.begin(), path.end());
    pb.push_back(0);
    const int fd = mkstemp(pb.data());
    if (fd < 0) throw std::runtime_error("test: mkstemp failed");
    const bool ok = ::write(fd, b.data(), b.size()) == (ssize_t)b.size();
    ::close(fd);
    if (!ok) throw std::runtime_error("test: write failed");
    return pb.data();
}
// parse a synthetic file; "" when it loads, else the reader's message (the file is removed either way)
static std::string gguf_error(const std::vector<GT> &ts, size_t data_bytes, const std::function<void(const ink::GGUF &)> &more = {}) {
    const std::string path = write_gguf(ts, data_bytes);
    std::string err;
    try {
        ink::GGUF g(path);
        if (more) more(g);
    } catch (const std::exception &e) { err = e.what(); if (err.empty()) err = "?"; }
    ::unlink(path.c_str());
    return err;
}

int main(int argc, char **argv) {
    std::mt19937 rng(20261128);
    if (argc > 1) check_model(argv[1], rng);

    // 1. certification: pass, then a single low bit at the first, a middle and the last element
    {
        const size_t n = 4608 * 64;
        std::vector<uint32_t> w = make_weights(n, rng);
        std::vector<uint16_t> dst(n, 0xABCD);
        Certificate c = certify_f32_hi16("pass", w.data(), n, dst.data(), dst.size());
        expect(c.check.ok && c.check.n_bad == 0 && c.layout == Layout::F32_HI16, "certify: clean tensor passes");
        bool packed = true;
        for (size_t i = 0; i < n; ++i) packed = packed && dst[i] == (uint16_t)(w[i] >> 16);
        expect(packed, "certify: packed halfwords are the upper 16 bits");
        for (size_t at : {(size_t)0, n / 2 + 7, n - 1})
            for (uint32_t bit : {1u, 0x8000u, 0x0100u}) {
                std::vector<uint32_t> b = w;
                b[at] |= bit;
                std::vector<uint16_t> d2(n, 0xABCD);
                Certificate f = certify_f32_hi16("fail", b.data(), n, d2.data(), d2.size());
                bool untouched = true;
                for (uint16_t h : d2) untouched = untouched && h == 0xABCD;
                char what[128];
                std::snprintf(what, sizeof what, "certify: low bit 0x%04x at element %zu fails, first_bad exact, dst untouched", bit, at);
                expect(!f.check.ok && f.check.n_bad == 1 && f.check.first_bad == at && f.layout == Layout::SOURCE && untouched, what);
            }
        std::vector<uint32_t> b = w;
        b[3] |= 2; b[n - 2] |= 0x4000;
        Check k = check_low16_zero(b.data(), n);
        expect(!k.ok && k.n_bad == 2 && k.first_bad == 3, "certify: every element counted (two failures)");
        Certificate off = certify_f32_hi16("off", w.data(), n, dst.data(), dst.size(), false);
        expect(off.check.ok && off.layout == Layout::SOURCE, "certify: allow = false keeps the source layout");
        expect(!check_low16_zero(w.data(), 0).ok, "certify: an empty tensor is not certified");
        expect(c.src_fnv == fnv1a64(w.data(), 4 * n) && c.src_fnv != fnv1a64(b.data(), 4 * n), "certificate: source identity hash");
    }
    // 2. group all-or-nothing (a gain / forget pair)
    {
        const size_t n = 64 * 2304;
        std::vector<uint32_t> g = make_weights(n, rng), f = make_weights(n, rng);
        std::vector<uint16_t> dg(n, 0x1111), df(n, 0x2222);
        auto ok = certify_group_f32_hi16({"gain", "forget"}, {g.data(), f.data()}, {n, n}, {dg.data(), df.data()}, {n, n});
        expect(ok.size() == 2 && ok[0].layout == Layout::F32_HI16 && ok[1].layout == Layout::F32_HI16, "group: both clean, both packed");
        f[n / 3] |= 1;
        std::vector<uint16_t> eg(n, 0x1111), ef(n, 0x2222);
        auto bad = certify_group_f32_hi16({"gain", "forget"}, {g.data(), f.data()}, {n, n}, {eg.data(), ef.data()}, {n, n});
        bool untouched = true;
        for (size_t i = 0; i < n; ++i) untouched = untouched && eg[i] == 0x1111 && ef[i] == 0x2222;
        expect(bad[0].layout == Layout::SOURCE && bad[1].layout == Layout::SOURCE && bad[0].check.ok && !bad[1].check.ok && untouched,
               "group: one member fails, none packed, nothing written");
        Census cs;
        for (auto &c : ok) cs.add(c);
        for (auto &c : bad) cs.add(c);
        expect(cs.n_packed == 2 && cs.n_kept == 2 && cs.dst_packed * 2 == cs.src_packed, "census: counts and bytes");
        std::printf("census line: %s\n", cs.summary().c_str());
    }
    // 3. exact round trip: every halfword, and the special values
    {
        bool all = true;
        for (uint32_t h = 0; h < 65536; ++h) all = all && bits(f32_from_hi16((uint16_t)h)) == (h << 16);
        expect(all, "round trip: all 65,536 halfwords give their exact 32-bit pattern");
        const uint32_t sp[] = {0x00000000u /* +0 */, 0x80000000u /* -0 */, 0x3F800000u /* 1 */, 0xC0200000u /* -2.5 */,
                               0x00800000u /* smallest normal */, 0x80800000u, 0x00010000u /* subnormal */,
                               0x007F0000u /* subnormal, top mantissa */, 0x80010000u /* negative subnormal */,
                               0x7F7F0000u /* largest finite */, 0x7F800000u /* +Inf */, 0xFF800000u /* -Inf */,
                               0x7FC00000u /* quiet NaN */, 0x7F810000u /* signalling NaN, payload in the upper half */,
                               0xFFC10000u /* negative NaN with payload */, 0x7FFF0000u, 0xFFFF0000u};
        const size_t ns = sizeof sp / sizeof sp[0];
        std::vector<uint16_t> pk(ns + 1, 0);
        Certificate c = certify_f32_hi16("special", sp, ns, pk.data(), pk.size());
        expect(c.layout == Layout::F32_HI16, "special values: certified");
        bool rt = true, pairs = true;
        for (size_t i = 0; i < ns; ++i) {
            const float f = f32_from_hi16(pk[i]);
            rt = rt && bits(f) == sp[i];
            if (std::isnan(f)) rt = rt && (bits(f) & 0x007F0000u) == (sp[i] & 0x007F0000u); // NaN payload kept
        }
        expect(rt, "special values: +-0, normals, subnormals, +-Inf, NaN payloads round-trip bit for bit");
        for (size_t i = 0; i + 1 < ns; i += 2) {
            uint32_t w;
            std::memcpy(&w, pk.data() + i, 4);
            pairs = pairs && bits(f32_even_from_pair(w)) == sp[i] && bits(f32_odd_from_pair(w)) == sp[i + 1];
        }
        expect(pairs, "packed words: element 2k in the low half, 2k + 1 in the high half (pl::F32H, CtlRows<true>)");
        expect(std::signbit(f32_from_hi16(0x8000)) && f32_from_hi16(0x8000) == 0.0f, "-0.0 keeps its sign");
        expect(std::fpclassify(f32_from_hi16(0x0001)) == FP_SUBNORMAL, "subnormal stays subnormal");
    }
    // 4. dot products in the kernels' orders: FP32 weights against their certified halfwords, bit for bit
    {
        struct Shape { const char *name; int rows, cols; };
        const Shape shapes[] = {{"router 128 x 2304", 128, 2304}, {"loop down 64 x 4608", 64, 4608}, {"gain 2304 x 64", 2304, 64}};
        std::normal_distribution<float> xd(0.0f, 1.0f);
        for (const Shape &s : shapes) {
            const size_t n = (size_t)s.rows * s.cols;
            std::vector<uint32_t> wu = make_weights(n, rng);
            std::vector<float> wf(n);
            for (size_t i = 0; i < n; ++i) wf[i] = std::bit_cast<float>(wu[i]);
            std::vector<uint16_t> wh(n);
            Certificate c = certify_f32_hi16(s.name, wu.data(), n, wh.data(), wh.size());
            std::vector<float> x(s.cols);
            for (auto &v : x) v = xd(rng);
            bool eq = c.layout == Layout::F32_HI16, eq_rows = true;
            int nd = 0;
            for (int r = 0; r < s.rows; ++r) {
                const float *rf = wf.data() + (size_t)r * s.cols;
                const uint16_t *rh = wh.data() + (size_t)r * s.cols;
                const float a = gemv_row([&](int cc, float *o) { decode32_f32(rf, cc, o); }, s.cols, x.data());
                const float b = gemv_row([&](int cc, float *o) { decode32_hi16(rh, cc, o); }, s.cols, x.data());
                if (bits(a) != bits(b)) { eq = false; ++nd; }
                if (s.cols <= 32 * SG) eq_rows = eq_rows && bits(ctlrows_row_f32(rf, s.cols, x.data())) == bits(ctlrows_row_streamed(rh, s.cols, x.data()));
            }
            char what[160];
            std::snprintf(what, sizeof what, "dot products (%s, gemv1_rows order): every row bit-identical (%d differ)", s.name, nd);
            expect(eq, what);
            if (s.cols <= 32 * SG) {
                std::snprintf(what, sizeof what, "dot products (%s, CtlRows streamed order): every row bit-identical", s.name);
                expect(eq_rows, what);
            }
        }
        // a value that would round differently if the weight lost or gained a low bit: the check sees it
        const float w = std::bit_cast<float>(0x3F810000u), x = 1.0f + 0x1p-12f;
        const float wb = std::bit_cast<float>(0x3F810001u);
        expect(bits(mac(0.0f, w, x)) == bits(mac(0.0f, f32_from_hi16(0x3F81), x)) && bits(mac(0.0f, wb, x)) != bits(mac(0.0f, w, x)),
               "sensitivity: one low bit changes the product, the decoded halfword does not");
    }
    // 5. unaligned buffers: source and destination at byte offsets 1, 2, 3 (memcpy access; -fsanitize=alignment clean)
    {
        const size_t n = 64 * 2304 + 3;
        std::vector<uint32_t> w = make_weights(n, rng);
        std::vector<uint16_t> ref(n);
        const Certificate rc = certify_f32_hi16("aligned", w.data(), n, ref.data(), ref.size());
        bool all = rc.layout == Layout::F32_HI16;
        for (size_t so : {1, 2, 3})
            for (size_t dof : {1, 3}) {
                std::vector<unsigned char> sb(4 * n + 8), db(2 * n + 8, 0xEE);
                std::memcpy(sb.data() + so, w.data(), 4 * n);
                const Certificate c = certify_f32_hi16("unaligned", sb.data() + so, n, db.data() + dof, n);
                all = all && c.layout == Layout::F32_HI16 && c.src_fnv == rc.src_fnv && c.check.n_bad == 0;
                all = all && std::memcmp(db.data() + dof, ref.data(), 2 * n) == 0 && db[dof - 1] == 0xEE && db[dof + 2 * n] == 0xEE;
                unsigned char one = 1;
                std::memcpy(sb.data() + so + 4 * (n - 1), &one, 1); // the last element's lowest byte
                const Check k = check_low16_zero(sb.data() + so, n);
                all = all && !k.ok && k.n_bad == 1 && k.first_bad == n - 1;
            }
        expect(all, "unaligned: source at +1/+2/+3, destination at +1/+3: same certificate, halfwords and failure index");
        std::vector<unsigned char> gb(2 * 4 * 64 + 16), gd(2 * 2 * 64 + 16, 0);
        std::vector<uint32_t> g2 = make_weights(128, rng);
        std::memcpy(gb.data() + 1, g2.data(), 4 * 64);
        std::memcpy(gb.data() + 1 + 4 * 64 + 2, g2.data() + 64, 4 * 64);
        const auto gc = certify_group_f32_hi16({"g", "f"}, {gb.data() + 1, gb.data() + 1 + 4 * 64 + 2}, {64, 64},
                                               {gd.data() + 1, gd.data() + 1 + 2 * 64 + 2}, {64, 64});
        bool gok = gc[0].layout == Layout::F32_HI16 && gc[1].layout == Layout::F32_HI16;
        for (size_t i = 0; i < 128; ++i) {
            uint16_t h;
            std::memcpy(&h, gd.data() + 1 + (i < 64 ? 2 * i : 2 * 64 + 2 + 2 * (i - 64)), 2);
            gok = gok && h == (uint16_t)(g2[i] >> 16);
        }
        expect(gok, "unaligned: group members at odd offsets packed exactly");
    }
    // 6. extents: zero width, zero / negative dimensions, overflow, byte size, int limits (no division before the check)
    {
        const int64_t z0[2] = {0, 128}, z1[2] = {2304, 0}, neg[2] = {-32, 4}, big[2] = {(int64_t)1 << 40, (int64_t)1 << 40};
        const int64_t wide[2] = {(int64_t)1 << 31, 1}, tall[2] = {32, (int64_t)1 << 31}, ok2[2] = {2304, 128};
        const int64_t ok4[4] = {64, 2304, 1, 1}, z3[4] = {64, 2304, 1, 0};
        expect(!f32_extent(z0, 2, 0).ok && !f32_extent(z1, 2, 0).ok && !f32_extent(z3, 4, 0).ok, "extent: a zero dimension (ne0 = 0, ne1 = 0, ne3 = 0) refused");
        expect(!f32_extent(neg, 2, 4 * 128).ok, "extent: a negative dimension refused");
        expect(!f32_extent(big, 2, 0).ok, "extent: an element count past SIZE_MAX / 4 refused");
        expect(!f32_extent(ok2, 2, 4 * 2304 * 128 + 4).ok && !f32_extent(ok2, 2, 2 * 2304 * 128).ok, "extent: bytes != 4 x elements refused");
        expect(!f32_extent(wide, 2, 4ull << 31).ok && !f32_extent(tall, 2, 4ull * 32 << 31).ok, "extent: a row length or row count past INT_MAX refused");
        expect(!f32_extent(ok2, 0, 0).ok && !f32_extent(nullptr, 2, 0).ok, "extent: no dimensions refused");
        const Extent e = f32_extent(ok2, 2, 4 * 2304 * 128), e4 = f32_extent(ok4, 4, 4 * 64 * 2304);
        expect(e.ok && e.cols == 2304 && e.rows == 128 && e.elems == 2304u * 128 && e4.ok && e4.cols == 64 && e4.rows == 2304,
               "extent: the router and gain shapes give cols, rows and elements");
        expect(!inkling2::half_target("blk.0.ffn_gate_inp.weight", true, z0, 2, 0) &&
               !inkling2::half_target("blk.0.ffn_gate_inp.weight", true, z1, 2, 0) &&
               !inkling2::half_target("blk.0.ffn_gate_inp.weight", true, big, 2, 0),
               "half_target: zero-width / zero-row / overflowing router refused without dividing");
        expect(inkling2::half_target("blk.0.ffn_gate_inp.weight", true, ok2, 2, 4 * 2304 * 128) &&
               !inkling2::half_target("blk.0.ffn_gate_inp.weight", false, ok2, 2, 4 * 2304 * 128) &&
               !inkling2::half_target("output.weight", true, ok2, 2, 4 * 2304 * 128),
               "half_target: the router passes; not F32 or not a selected name refused");
        std::vector<uint32_t> w(8, 0);
        std::vector<uint16_t> d(4);
        expect(throws([&] { certify_f32_hi16("small", w.data(), 8, d.data(), d.size()); }, "destination"),
               "capacity: a destination smaller than the source throws before writing");
        expect(throws([&] { check_low16_zero(w.data(), MAX_F32_ELEMS + 1); }, "overflows") &&
               throws([&] { certify_f32_hi16("huge", w.data(), MAX_F32_ELEMS + 1, nullptr, 0, false); }, "overflows"),
               "capacity: n > SIZE_MAX / 4 throws before any read");
        std::vector<uint16_t> d8(8);
        expect(throws([&] { certify_group_f32_hi16({"a", "b"}, {w.data(), w.data()}, {8}, {d8.data(), d8.data()}, {8, 8}); }, "lengths") &&
               throws([&] { certify_group_f32_hi16({"a"}, {w.data()}, {8}, {d8.data()}, {4}); }, "destination"),
               "group: parallel vectors of different lengths or a short destination throw");
    }
    // 7. gain / forget pairs: formed by name before eligibility; incompatible shapes refuse the model
    {
        const std::string G = "blk.5.loop_attn_gain.weight", F = "blk.5.loop_attn_forget.weight";
        constexpr int64_t R = 64, E = 2304;
        auto plan = [&](std::vector<inkling2::TDesc> ts, int64_t gr = 64, int64_t ne = 2304) { return inkling2::plan_groups(ts, gr, ne); };
        const auto good = plan({desc(G, true, R, E), desc(F, true, R, E), desc("blk.5.ffn_gate_inp.weight", true, E, 128)});
        bool pairs_ok = good.size() == 2;
        for (const auto &ix : good) pairs_ok = pairs_ok && (ix.size() == 1 ? ix[0] == 2 : (ix[0] == 0 && ix[1] == 1));
        expect(pairs_ok, "pairs: a compatible gain / forget is one group of both (gain first), the router its own");
        expect(throws([&] { plan({desc(G, true, R, E), desc(F, true, R, 2)}); }, "dimensions differ"),
               "pairs: 64 x 2304 gain beside a 64 x 2 forget refuses the model");
        expect(throws([&] { plan({desc(G, true, R, E), desc(F, true, 32, E)}); }, "incompatible"),
               "pairs: gain and forget row lengths differ: refused");
        expect(throws([&] { plan({desc(G, true, 32, E), desc(F, true, 32, E)}); }, "gate_rank"),
               "pairs: rows of 32 where loop.gate_rank is 64: refused");
        expect(throws([&] { plan({desc(G, true, R, 1024), desc(F, true, R, 1024)}); }, "embedding_length"),
               "pairs: 1024 rows where embedding_length is 2304: refused");
        expect(throws([&] { plan({desc(G, true, R, E)}); }, "missing a member") && throws([&] { plan({desc(F, true, R, E)}); }, "missing a member"),
               "pairs: a lone gain or a lone forget refuses the model (no single-member certification)");
        expect(throws([&] { plan({desc(G, true, R, E), desc(F, false, R, E, 2 * R * E)}); }, "not both F32"),
               "pairs: an F32 gain beside a non-F32 forget: refused");
        expect(throws([&] { plan({desc(G, true, 0, E), desc(F, true, 0, E)}); }, "not positive"),
               "pairs: zero-width members refused (checked before any division)");
        {
            inkling2::TDesc g3 = desc(G, true, R, E), f3 = desc(F, true, R, E);
            g3.ne[2] = f3.ne[2] = 2; g3.nne = f3.nne = 3; g3.bytes = f3.bytes = 4ull * R * E * 2;
            expect(throws([&] { plan({g3, f3}); }, "2-D"), "pairs: a 3-D pair refused");
        }
        expect(throws([&] { plan({desc(G, true, R, E), desc(G, true, R, E), desc(F, true, R, E)}); }, "duplicate") &&
               throws([&] { plan({desc("blk.1.ffn_gate_inp.weight", true, E, 128), desc("blk.1.ffn_gate_inp.weight", true, E, 128)}); }, "duplicate"),
               "plan: a duplicated name refused");
        // compatible but not eligible (48-value rows are not whole 32-value chunks): both stay FP32, no throw
        bool kept = false;
        try { kept = plan({desc(G, true, 48, E), desc(F, true, 48, E)}, 48).empty(); } catch (...) { kept = false; }
        expect(kept, "pairs: a compatible pair that is not eligible keeps both FP32 (no group, no error)");
        // a zero-width router is not a target (and does not throw); other names never planned
        bool none = false;
        try { none = plan({desc("blk.1.ffn_gate_inp.weight", true, 0, 128), desc("output.weight", true, E, 128)}).empty(); } catch (...) { none = false; }
        expect(none, "plan: zero-width router and unselected names: no group, no error");
        // one member failing the low-16 check keeps both FP32 (the planned pair through the group certifier)
        const size_t n = (size_t)R * E;
        std::vector<uint32_t> gw = make_weights(n, rng), fw = make_weights(n, rng);
        gw[n - 1] |= 0x10;
        std::vector<uint16_t> gd(n, 7), fd(n, 9);
        const auto cr = certify_group_f32_hi16({G, F}, {gw.data(), fw.data()}, {n, n}, {gd.data(), fd.data()}, {n, n});
        bool untouched = true;
        for (size_t i = 0; i < n; ++i) untouched = untouched && gd[i] == 7 && fd[i] == 9;
        expect(cr[0].layout == Layout::SOURCE && cr[1].layout == Layout::SOURCE && !cr[0].check.ok && cr[1].check.ok && untouched,
               "pairs: the gain fails low-16, the clean forget is kept FP32 too, nothing written");
    }
    // 8. INK_CERT_HALF: unset or "1" on, "0" off, anything else off with a warning
    {
        expect(half_from_env(nullptr, nullptr) && half_from_env("1", nullptr) && !half_from_env("0", nullptr), "INK_CERT_HALF: unset / 1 on, 0 off");
        bool strict = true;
        for (const char *v : {"", "2", "-1", "1junk", " 1", "1 ", "01", "true", "yes", "0x1"}) {
            char *buf = nullptr;
            size_t len = 0;
            FILE *m = open_memstream(&buf, &len);
            const bool on = half_from_env(v, m);
            std::fclose(m);
            strict = strict && !on && buf && std::strstr(buf, "warning") && std::strstr(buf, "kept FP32");
            std::free(buf);
        }
        expect(strict, "INK_CERT_HALF: \"\", 2, -1, 1junk, \" 1\", \"1 \", 01, true, yes, 0x1 keep FP32 and warn");
        char *buf = nullptr;
        size_t len = 0;
        FILE *m = open_memstream(&buf, &len);
        half_from_env("1", m); half_from_env("0", m); half_from_env(nullptr, m);
        std::fclose(m);
        expect(len == 0, "INK_CERT_HALF: the valid values print nothing");
        std::free(buf);
    }
    // 9. FNV-1a 64: the published vectors (Noll's test suite), independent of the helper's constants
    {
        auto h = [](const char *x) { return fnv1a64(x, std::strlen(x)); };
        expect(FNV1A64_OFFSET == 14695981039346656037ULL && h("") == 0xcbf29ce484222325ULL, "FNV-1a 64: offset basis 14695981039346656037");
        expect(h("a") == 0xaf63dc4c8601ec8cULL && h("foobar") == 0x85944171f73967e8ULL && h("chongo was here!\n") == 0x46810940eff5f915ULL,
               "FNV-1a 64: \"a\", \"foobar\", \"chongo was here!\\n\" give the published digests");
        unsigned char ub[8] = {0, 'f', 'o', 'o', 'b', 'a', 'r', 0};
        expect(fnv1a64(ub + 1, 6) == 0x85944171f73967e8ULL, "FNV-1a 64: an unaligned buffer hashes the same");
    }
    // 10. the GGUF reader: duplicate names, unrepresentable dimensions and byte sizes refused at parse time
    {
        const std::string ok = gguf_error({{"blk.0.ffn_gate_inp.weight", {32, 2}, ink::G_F32, 0}}, 256, [&](const ink::GGUF &g) {
            const ink::Tensor &t = g.at("blk.0.ffn_gate_inp.weight");
            if (t.rows() != 2 || t.bytes != 256 || !inkling2::half_target(t.name, true, t.ne.data(), t.ne.size(), t.bytes))
                throw std::runtime_error("unexpected descriptor");
        });
        expect(ok.empty(), "gguf: a well-formed file loads (rows 2, 256 bytes, a half target)");
        expect(gguf_error({{"blk.0.ffn_gate_inp.weight", {4}, ink::G_F32, 0}, {"blk.0.ffn_gate_inp.weight", {4}, ink::G_F32, 32}}, 64)
                   .find("duplicate tensor name") != std::string::npos,
               "gguf: two descriptors with one name refused");
        expect(gguf_error({{"t", {1ull << 32, 1ull << 32}, ink::G_F32, 0}}, 32).find("element count overflows") != std::string::npos,
               "gguf: 2^32 x 2^32 elements refused before nel() wraps");
        expect(gguf_error({{"t", {1ull << 63}, ink::G_F32, 0}}, 32).find("does not fit int64") != std::string::npos,
               "gguf: a dimension past INT64_MAX refused");
        expect(gguf_error({{"t", {1ull << 62}, ink::G_F32, 0}}, 32).find("byte size overflows") != std::string::npos,
               "gguf: 2^62 F32 elements (2^64 bytes) refused");
        expect(gguf_error({{"t", {4}, ink::G_F32, ~0ull - 4}}, 32).find("past end of file") != std::string::npos,
               "gguf: an offset that would wrap the end-of-file check refused");
        const std::string zw = gguf_error({{"blk.0.ffn_gate_inp.weight", {0, 128}, ink::G_F32, 0}}, 32, [&](const ink::GGUF &g) {
            const ink::Tensor &t = g.at("blk.0.ffn_gate_inp.weight");
            if (t.rows() != 0 || inkling2::half_target(t.name, true, t.ne.data(), t.ne.size(), t.bytes)) throw std::runtime_error("zero width taken");
        });
        expect(zw.empty(), "gguf: a zero-width tensor loads, rows() is 0 (no division), and it is not a half target");
    }
#ifdef INK_NO_FMA
    const char *mode = "rounded product + add (INK_NO_FMA)";
#else
    const char *mode = "fused multiply-add";
#endif
    std::printf("%s: %d checks, %d failed (%s)\n", fails ? "FAIL" : "PASS", checks, fails, mode);
    return fails ? 1 : 0;
}
