// Host-only bit-exact model of INK_WO_MR_PE and INK_WO_MR_TAIL (engine wo_mr: the attention output of a step of 2-8
// tokens of one sequence).
// Build: g++ -std=c++20 -O1 -g -Wall -Wextra -Werror -ffp-contract=off -fsanitize=address,undefined tools/test_wo_mr.cpp -o /tmp/test_wo_mr && /tmp/test_wo_mr
// and once more with -DINK_NO_FMA (the mac() of baselines v1/v2). Checks:
//  1. live_plan.hpp pe_mp / pe_index against xd::splite's own index expression and Engine::with_mp's widths: each
//     part's cols x mp places taken exactly once.
//  2. bfsplit.hpp pe_store (its three lines mirrored below over split3's integer ties-to-even expressions) against
//     splite, whole buffers as halfwords: random and crafted words (signed zeros, subnormals, bf16 ties of both
//     parities, infinities, NaN), steps of 1-8 rows written by launches of 1-8 rows at any first row t0 (attn_flash_sum
//     chunks), every halfword written exactly once, the padded rows zero, guards untouched; pe_shape_ok's cases.
//  3. XDGroupEJ::tail (mirrored with its own gather / scatter address expressions) against fz::attn_tail (mirrored) for
//     2-8 tokens, with and without the residual and the per-token states: attn_out, ffn_inp, the state buffer and the
//     per-token state rows as words, guards included; every accepted prefix a (Engine::accept: per-token row a - 1, or
//     st_out at a = ntok) equals the state a tail of a tokens alone leaves; the four R10c witness channels' IEEE words.
//  4. INK_WO_MR_PE / INK_WO_MR_TAIL parsing (live_env_flag: unset 1, else exactly "0" or "1").
// The device code itself (IGC, VC's contraction, the bit barrier) is checked by tools/benches/bench_wo_mr.cpp.
#include "../src/live_plan.hpp"
#include <algorithm>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <vector>

using namespace ink;
namespace {
int fails = 0;
long long words = 0, configs = 0;
#define CHECK(c, ...) do { if (!(c)) { ++fails; std::printf("FAIL %s:%d: ", __FILE__, __LINE__); std::printf(__VA_ARGS__); std::printf("\n"); } } while (0)
template <class F> bool throws(F f) {
    try { f(); } catch (const std::exception &) { return true; }
    return false;
}
uint32_t fb(float f) { return std::bit_cast<uint32_t>(f); }
float bf(uint32_t u) { return std::bit_cast<float>(u); }

// ---- bfsplit.hpp, its expressions (sycl::bit_cast -> std::bit_cast) ----
uint16_t bf_rn(float f) {
    const uint32_t u = std::bit_cast<uint32_t>(f);
    return (uint16_t)((u + 0x7fffu + ((u >> 16) & 1u)) >> 16);
}
float bf_f(uint16_t b) { return std::bit_cast<float>((uint32_t)b << 16); }
void split3(float x, uint16_t &a, uint16_t &b, uint16_t &c) {
    a = bf_rn(x);
    const float r1 = x - bf_f(a);
    b = bf_rn(r1);
    c = bf_rn(r1 - bf_f(b));
}
void split3_store(float v, uint16_t *p, size_t ps) {
    uint16_t a, b, c;
    split3(v, a, b, c);
    p[0] = a; p[ps] = b; p[2 * ps] = c;
}
// pe_store; cnt (test only): +1 per halfword written
void pe_store(const PeOut &o, int t, int k, float v, uint8_t *cnt) {
    const size_t ps = (size_t)o.cols * o.mp;
    const int tg = o.t0 + t;
    split3_store(v, o.pe + pe_index(o.mp, tg, k), ps);
    for (int p = 0; p < 3; ++p) ++cnt[pe_index(o.mp, tg, k) + p * ps];
    if (tg == 0)
        for (int u = o.m; u < o.mp; ++u) {
            uint16_t *q = o.pe + pe_index(o.mp, u, k);
            q[0] = 0; q[ps] = 0; q[2 * ps] = 0;
            for (int p = 0; p < 3; ++p) ++cnt[pe_index(o.mp, u, k) + p * ps];
        }
}
// ---- xmx_esimd.hpp splite<MP>, its body per work item (t, k) ----
void splite(const float *x, int ldx, int M, int cols, int MP, uint16_t *Pe) {
    const size_t ps = (size_t)cols * MP;
    for (int t = 0; t < MP; ++t)
        for (int k = 0; k < cols; ++k) {
            const int g = k / 256, j = (k % 256) / 32, s = (k % 32) / 16, e = k % 16;
            const float v = t < M ? x[(size_t)t * ldx + k] : 0.0f;
            uint16_t a, b, c;
            split3(v, a, b, c);
            const size_t o = ((((size_t)g * 8 + j) * 2 + s) * MP + t) * 16 + e;
            Pe[o] = a; Pe[ps + o] = b; Pe[2 * ps + o] = c;
        }
}
// Engine::with_mp's widths
int with_mp_width(int n) { return n == 1 ? 1 : n == 2 ? 2 : n <= 4 ? 4 : 8; }

// ---- formats.hpp mac, fused.hpp conv_out / conv_win / conv_save / attn_tail ----
float mac(float acc, float a, float b) {
#ifdef INK_NO_FMA
    const float p = a * b;
    return acc + p;
#else
    return std::fma(a, b, acc);
#endif
}
float conv_out(const float *win, const float *w, int c, float scale) {
    float s = 0.0f;
    for (int i = 0; i < 4; ++i) s = mac(s, win[i], w[c * 4 + i]);
    return (win[3] + s) * scale;
}
void attn_tail(const float *ob, const float *st_in, float *st_out, int off, const float *w, float scale, float *attn_out,
               const float *inpSA, float *ffn_inp, int E, int ntok, float *st_tok, size_t sst) {
    for (int t = 0; t < ntok; ++t)
        for (int c = 0; c < E; ++c) {
            float win[4];
            for (int i = 0; i < 4; ++i) {
                const int tt = t - 3 + i;
                win[i] = tt >= 0 ? ob[(size_t)tt * E + c] : st_in[(size_t)(off + c) * 3 + (3 + tt)];
            }
            const float o = conv_out(win, w, c, scale);
            const size_t i = (size_t)t * E + c;
            attn_out[i] = o;
            if (inpSA) ffn_inp[i] = inpSA[i] + o;
            float *sv = t == ntok - 1 ? st_out : st_tok ? st_tok + (size_t)t * sst : nullptr;
            if (sv)
                for (int k = 0; k < 3; ++k) sv[(size_t)(off + c) * 3 + k] = win[1 + k];
        }
}
// ---- xmx_esimd.hpp EjTail + XDGroupEJ::tail, per work-group r16 and lane n (byte offsets as the kernel's) ----
struct EjTail {
    const float *cv = nullptr, *si = nullptr; float *so = nullptr, *stok = nullptr;
    const float *res = nullptr; float *fo = nullptr;
    size_t sst = 0; float sc = 0.0f;
};
// tot: the fold's totals, row t at tot + t * ldy (what the stores' path writes to y); y: attn_out
void ej_tail(const EjTail &tl, const float *tot, int rows, int mst, int ldy, float *y) {
    const auto at = [](const float *p, uint32_t byte) { return p[byte / 4]; };
    const auto put = [](float *p, uint32_t byte, float v) { p[byte / 4] = v; };
    const uint32_t zmask = (uint32_t)(tl.sc < -1e30f);
    for (int r16 = 0; r16 < rows / 16; ++r16)
        for (int n = 0; n < 16; ++n) {
            const uint32_t o3 = 12u * n, o4 = 16u * n;
            const float *sp = tl.si + (size_t)r16 * 48, *tp = tl.cv + (size_t)r16 * 64;
            const float s0 = at(sp, o3), s1 = at(sp, o3 + 4u), s2 = at(sp, o3 + 8u);
            const float w0 = at(tp, o4), w1 = at(tp, o4 + 4u), w2 = at(tp, o4 + 8u), w3 = at(tp, o4 + 12u);
            float a0 = s0, a1 = s1, a2 = s2;
            for (int t = 0; t < 8; ++t)
                if (t < mst) {
                    const float x3 = tot[(size_t)t * ldy + r16 * 16 + n];
                    float s = mac(0.0f, a0, w0);
                    s = mac(s, a1, w1);
                    s = mac(s, a2, w2);
                    s = mac(s, x3, w3);
                    const float o = (x3 + s) * tl.sc;
                    y[(size_t)t * ldy + r16 * 16 + n] = o;
                    if (tl.res) {
                        const float o_rnd = bf(fb(o) ^ zmask);
                        tl.fo[(size_t)t * ldy + r16 * 16 + n] = tl.res[(size_t)t * ldy + r16 * 16 + n] + o_rnd;
                    }
                    float *sv = t == mst - 1 ? tl.so : tl.stok ? tl.stok + (size_t)t * tl.sst : nullptr;
                    if (sv) {
                        sv += (size_t)r16 * 48;
                        put(sv, o3, a1);
                        put(sv, o3 + 4u, a2);
                        put(sv, o3 + 8u, x3);
                    }
                    a0 = a1; a1 = a2; a2 = x3;
                }
        }
}

constexpr uint32_t POISON = 0x7fc5a17eu;
constexpr uint16_t POISON16 = 0xa5a5u;

std::vector<float> crafted_words(std::mt19937 &rng) {
    std::vector<float> v;
    for (uint32_t u : {0x00000000u, 0x80000000u, 0x00000001u, 0x80000001u, 0x000000e5u, 0x007fffffu, 0x807fffffu, 0x00800000u,
                       0x7f7fffffu, 0xff7fffffu, 0x7f800000u, 0xff800000u, 0x7fc00000u, 0xffc00001u, 0x3f800000u, 0xbf800000u,
                       0x3f808000u, 0x3f818000u, 0x3f807fffu, 0x3f808001u, 0x3f80ffffu, 0x7f7f8000u, 0x7f7f7fffu, 0x00008000u,
                       0x00018000u, 0x34e4f92eu, 0xa7e4f92eu})
        v.push_back(bf(u));
    std::uniform_int_distribution<uint32_t> any;
    for (int i = 0; i < 64; ++i) v.push_back(bf((any(rng) & 0xffff0000u) | 0x8000u)); // exact bf16 ties
    for (int i = 0; i < 64; ++i) v.push_back(bf(any(rng)));
    return v;
}

void check_layout() {
    for (int n = 1; n <= 8; ++n) CHECK(pe_mp(n) == with_mp_width(n), "pe_mp(%d) = %d, with_mp %d", n, pe_mp(n), with_mp_width(n));
    for (int cols : {256, 512, 2304, 3072})
        for (int mp : {1, 2, 4, 8}) {
            std::vector<uint8_t> seen((size_t)cols * mp, 0);
            for (int t = 0; t < mp; ++t)
                for (int k = 0; k < cols; ++k) {
                    const int g = k / 256, j = (k % 256) / 32, s = (k % 32) / 16, e = k % 16;
                    const size_t o = ((((size_t)g * 8 + j) * 2 + s) * mp + t) * 16 + e;
                    CHECK(pe_index(mp, t, k) == o, "pe_index(%d, %d, %d)", mp, t, k);
                    if (o < seen.size()) ++seen[o];
                }
            int bad = 0;
            for (uint8_t c : seen) bad += c != 1;
            CHECK(bad == 0, "cols %d mp %d: %d places not taken exactly once", cols, mp, bad);
        }
    uint16_t dummy[1];
    const auto ok = [&](int mp, int m, int t0, int cols, int n, int ccols) { return pe_shape_ok(PeOut{dummy, mp, m, t0, cols}, n, ccols); };
    CHECK(pe_shape_ok(PeOut{}, 0, 0), "a null PeOut is always accepted");
    for (int m = 1; m <= 8; ++m) {
        CHECK(ok(pe_mp(m), m, 0, 3072, m, 3072), "m %d whole", m);
        for (int t0 = 0; t0 < m; ++t0)
            for (int n = 1; t0 + n <= m; ++n) CHECK(ok(pe_mp(m), m, t0, 3072, n, 3072), "m %d t0 %d n %d", m, t0, n);
        CHECK(!ok(pe_mp(m), m, 0, 3072, m + 1, 3072), "m %d: one row too many", m);
        CHECK(!ok(pe_mp(m), m, m, 3072, 1, 3072), "m %d: launch past the rows", m);
        CHECK(!ok(pe_mp(m), m, -1, 3072, 1, 3072), "m %d: negative t0", m);
        CHECK(!ok(pe_mp(m), m, 0, 3072, 0, 3072), "m %d: no rows", m);
        CHECK(!ok(pe_mp(m), m, 0, 3072, m, 2304), "m %d: other cols", m);
        if (pe_mp(m) != 8) CHECK(!ok(8, m, 0, 3072, m, 3072), "m %d: wrong width", m);
    }
    CHECK(!ok(8, 9, 0, 3072, 9, 3072), "9 rows");
    CHECK(!ok(1, 0, 0, 3072, 1, 3072), "0 rows");
    CHECK(!ok(2, 2, 0, 3000, 2, 3000), "cols not a multiple of 256");
}

// a step of m rows written by launches of ch rows (the last may be shorter), work items in a scrambled order
void check_pe(int cols, int m, int ch, const std::vector<float> &x, std::mt19937 &rng) {
    const int mp = pe_mp(m);
    const size_t ps = (size_t)cols * mp, G = 37;
    std::vector<uint16_t> ref(3 * ps + 2 * G, POISON16), got(3 * ps + 2 * G, POISON16);
    std::vector<uint8_t> cnt(3 * ps, 0);
    splite(x.data(), cols, m, cols, mp, ref.data() + G);
    const PeOut base{got.data() + G, mp, m, 0, cols};
    for (int t0 = 0; t0 < m; t0 += ch) {
        const int n = std::min(ch, m - t0);
        PeOut o = base;
        o.t0 = t0;
        CHECK(pe_shape_ok(o, n, cols), "shape m %d t0 %d n %d", m, t0, n);
        std::vector<int> items((size_t)n * cols);
        for (size_t i = 0; i < items.size(); ++i) items[i] = (int)i;
        std::shuffle(items.begin(), items.end(), rng);
        for (int it : items) {
            const int t = it / cols, k = it % cols;
            pe_store(o, t, k, x[(size_t)(t0 + t) * cols + k], cnt.data());
        }
    }
    int diff = 0, once = 0;
    for (size_t i = 0; i < ref.size(); ++i) diff += ref[i] != got[i];
    for (uint8_t c : cnt) once += c != 1;
    for (size_t i = 0; i < G; ++i) diff += (got[i] != POISON16) + (got[G + 3 * ps + i] != POISON16);
    for (int p = 0; p < 3; ++p)
        for (int t = m; t < mp; ++t)
            for (int k = 0; k < cols; ++k) diff += got[G + p * ps + pe_index(mp, t, k)] != 0;
    CHECK(diff == 0 && once == 0, "PE cols %d m %d chunks %d: %d halfwords differ, %d not written exactly once", cols, m, ch, diff, once);
    words += (long long)ref.size();
    ++configs;
}

struct TailCase {
    int E = 0, off = 0, ntok = 0;
    size_t sst = 0;
    std::vector<float> ob, cv, st, res;
};
// the state buffer: [off + E + 5] x 3 words (states of channel c at 3 (off + c)); per-token rows: (ntok - 1) x sst
TailCase make_case(std::mt19937 &rng, int E, int ntok, bool witness) {
    TailCase k;
    k.E = E; k.off = 2 * 16 + 5; k.ntok = ntok; k.sst = (size_t)(k.off + E + 9) * 3 + 11;
    std::normal_distribution<float> nd(0.0f, 1.0f);
    k.ob.resize((size_t)ntok * E); k.cv.resize((size_t)E * 4); k.st.resize((size_t)(k.off + E + 5) * 3); k.res.resize((size_t)ntok * E);
    for (auto &v : k.ob) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
    for (auto &v : k.cv) v = nd(rng) * 0.5f;
    for (auto &v : k.st) v = nd(rng);
    for (auto &v : k.res) v = nd(rng);
    const float sub = std::ldexp(1.0f, -140), nz = -0.0f;
    if (witness) { // channels 0..3: a zero product (tot = +0 in every row), the states and taps of bench_wo's witness rows
        for (int c = 0; c < 4; ++c) {
            for (int t = 0; t < ntok; ++t) { k.ob[(size_t)t * E + c] = 0.0f; k.res[(size_t)t * E + c] = 0.0f; }
            for (int i = 0; i < 4; ++i) k.cv[(size_t)c * 4 + i] = 0.0f;
            for (int i = 0; i < 3; ++i) k.st[(size_t)(k.off + c) * 3 + i] = 0.0f;
        }
        k.st[(size_t)(k.off + 0) * 3 + 0] = std::ldexp(1.0f, -140); k.cv[0 * 4 + 0] = std::ldexp(1.0f, 120);
        k.st[(size_t)(k.off + 1) * 3 + 0] = std::ldexp(1.0f, -140); k.cv[1 * 4 + 0] = 1.0f;
        k.st[(size_t)(k.off + 2) * 3 + 0] = -std::ldexp(1.0f, -149); k.cv[2 * 4 + 0] = 1.0f;
        k.st[(size_t)(k.off + 3) * 3 + 0] = -1.0f; k.cv[3 * 4 + 0] = 1.0f;
        k.st[(size_t)(k.off + 3) * 3 + 1] = 1.0f + std::ldexp(1.0f, -23); k.cv[3 * 4 + 1] = 1.0f - std::ldexp(1.0f, -23);
    }
    int nc = 0;
    for (int c = 5; c < E; c += 7, ++nc) { // signed zeros, subnormal taps / states / inputs / residuals, huge cancelling states
        float *t = &k.cv[(size_t)c * 4], *s = &k.st[(size_t)(k.off + c) * 3];
        const int r = (int)(rng() % ntok);
        switch (nc % 6) {
        case 0: t[0] = nz; t[1] = 0.0f; t[2] = nz; s[0] = 0.0f; s[1] = nz; s[2] = 1.0f; break;
        case 1: t[0] = sub; t[1] = -sub; t[2] = 0.25f * sub; s[0] = 1.0f; s[1] = 0.5f; s[2] = 3.0f; k.res[(size_t)r * E + c] = nz; break;
        case 2: s[0] = sub; s[1] = -sub; s[2] = 4.0f * sub; t[3] = 0.0f; k.res[(size_t)r * E + c] = sub; break;
        case 3:
            t[0] = t[1] = t[2] = t[3] = 0.0f; s[0] = s[1] = s[2] = nz; k.res[(size_t)r * E + c] = nz;
            for (int u = 0; u < ntok; ++u) k.ob[(size_t)u * E + c] = nz;
            break;
        case 4: t[3] = nz; s[0] = std::ldexp(1.0f, 100); s[1] = -std::ldexp(1.0f, 100); k.res[(size_t)r * E + c] = std::ldexp(1.0f, -126); break;
        default: k.ob[(size_t)r * E + c] = sub; t[3] = std::ldexp(1.0f, 20); k.res[(size_t)r * E + c] = -std::ldexp(1.0f, -130); break;
        }
    }
    return k;
}

int cmp_words(const std::vector<float> &a, const std::vector<float> &b) {
    int n = 0;
    for (size_t i = 0; i < a.size(); ++i) n += fb(a[i]) != fb(b[i]);
    words += (long long)a.size();
    return n;
}

void check_tail(std::mt19937 &rng, int E, int ntok, bool residual, bool per_token, bool witness) {
    const TailCase k = make_case(rng, E, ntok, witness);
    const float scale = 1.0f / std::sqrt(5.0f);
    const size_t RZ = 13, SN = k.st.size(), TN = (size_t)7 * k.sst;
    // reference: fz::attn_tail from ob
    std::vector<float> ao0((size_t)ntok * E + 2 * RZ, bf(POISON)), fi0(ao0), so0(SN, bf(POISON)), tk0(TN, bf(POISON));
    attn_tail(k.ob.data(), k.st.data(), so0.data(), k.off, k.cv.data(), scale, ao0.data() + RZ, residual ? k.res.data() : nullptr,
              fi0.data() + RZ, E, ntok, per_token ? tk0.data() : nullptr, k.sst);
    // candidate: the tail inside the product, from the same totals
    std::vector<float> ao1(ao0.size(), bf(POISON)), fi1(ao0.size(), bf(POISON)), so1(SN, bf(POISON)), tk1(TN, bf(POISON));
    EjTail tl{k.cv.data(), k.st.data() + (size_t)3 * k.off, so1.data() + (size_t)3 * k.off,
              per_token ? tk1.data() + (size_t)3 * k.off : nullptr, residual ? k.res.data() : nullptr, fi1.data() + RZ, k.sst, scale};
    ej_tail(tl, k.ob.data(), E, ntok, E, ao1.data() + RZ);
    const int da = cmp_words(ao0, ao1), df = cmp_words(fi0, fi1), ds = cmp_words(so0, so1), dt = cmp_words(tk0, tk1);
    CHECK(da + df + ds + dt == 0, "tail E %d ntok %d res %d per-token %d witness %d: attn_out %d, ffn_inp %d, st_out %d, per-token %d words differ",
          E, ntok, residual, per_token, witness, da, df, ds, dt);
    // the reference's own contract: guards untouched; a block start leaves ffn_inp; no per-token rows: none written
    int g = 0;
    for (size_t i = 0; i < RZ; ++i) g += (fb(ao0[i]) != POISON) + (fb(ao0[RZ + (size_t)ntok * E + i]) != POISON);
    if (!residual) for (float v : fi0) g += fb(v) != POISON;
    for (size_t i = 0; i < SN; ++i) {
        const long c = (long)(i / 3) - k.off;
        if (c < 0 || c >= E) g += fb(so0[i]) != POISON;
    }
    for (size_t i = 0; i < TN; ++i) {
        const size_t row = i / k.sst, w = i % k.sst;
        const long c = (long)(w / 3) - k.off;
        const bool live = per_token && (int)row < ntok - 1 && c >= 0 && c < E;
        if (!live) g += fb(tk0[i]) != POISON;
    }
    CHECK(g == 0, "tail E %d ntok %d: the reference wrote %d words outside its places", E, ntok, g);
    // every accepted prefix a: Engine::accept copies per-token row a - 1 (a < ntok), else st_out stays
    if (per_token)
        for (int a = 1; a <= ntok; ++a) {
            std::vector<float> aoa((size_t)a * E), soa(SN, bf(POISON));
            attn_tail(k.ob.data(), k.st.data(), soa.data(), k.off, k.cv.data(), scale, aoa.data(), nullptr, nullptr, E, a, nullptr, 0);
            int d = 0;
            for (int c = 0; c < E; ++c)
                for (int j = 0; j < 3; ++j) {
                    const size_t si = (size_t)(k.off + c) * 3 + j;
                    const float kept = a == ntok ? so1[si] : tk1[(size_t)(a - 1) * k.sst + si];
                    d += fb(kept) != fb(soa[si]);
                }
            for (size_t i = 0; i < aoa.size(); ++i) d += fb(aoa[i]) != fb(ao1[RZ + i]);
            CHECK(d == 0, "tail E %d ntok %d: prefix %d's state or rows differ in %d words", E, ntok, a, d);
            words += (long long)E * 3 + (long long)aoa.size();
        }
    if (witness) {
        const uint32_t want[4] = {0x34e4f92eu, 0x000000e5u, 0x80000000u,
#ifdef INK_NO_FMA
                                  0x00000000u
#else
                                  0xa7e4f92eu
#endif
        };
        for (int c = 0; c < 4; ++c)
            CHECK(fb(ao1[RZ + c]) == want[c] && fb(ao0[RZ + c]) == want[c], "witness channel %d: tail 0x%08x, attn_tail 0x%08x, IEEE 0x%08x", c,
                  fb(ao1[RZ + c]), fb(ao0[RZ + c]), want[c]);
    }
    ++configs;
}

void check_flags() {
    for (const char *nm : {"INK_WO_MR_PE", "INK_WO_MR_TAIL"}) {
        CHECK(live_parse_flag(nm, nullptr, true), "%s unset", nm);
        CHECK(!live_parse_flag(nm, "0", true) && live_parse_flag(nm, "1", false), "%s 0 / 1", nm);
        for (const char *s : {"", "00", "01", "2", "-1", "true", "on", " 1", "1 ", "0x1"})
            CHECK(throws([&] { live_parse_flag(nm, s, true); }), "%s='%s' accepted", nm, s);
        unsetenv(nm);
        CHECK(live_env_flag(nm, true), "%s unset in the environment", nm);
        setenv(nm, "0", 1);
        CHECK(!live_env_flag(nm, true), "%s=0", nm);
        setenv(nm, "1", 1);
        CHECK(live_env_flag(nm, true), "%s=1", nm);
        setenv(nm, "yes", 1);
        CHECK(throws([&] { live_env_flag(nm, true); }), "%s=yes accepted", nm);
        unsetenv(nm);
    }
}
} // namespace

int main() {
    std::mt19937 rng(20261128);
    check_layout();
    check_flags();
    const std::vector<float> cw = crafted_words(rng);
    for (int cols : {256, 3072})
        for (int m = 1; m <= 8; ++m)
            for (int ch = 1; ch <= 8; ++ch) {
                if (ch > m && ch != 8) continue;
                std::vector<float> x((size_t)m * cols);
                std::normal_distribution<float> nd(0.0f, 1.0f);
                for (auto &v : x) v = nd(rng) * (rng() % 32 == 0 ? 1e30f : 1.0f);
                for (size_t i = 0; i < x.size(); i += 3) x[i] = cw[(i / 3) % cw.size()];
                check_pe(cols, m, ch, x, rng);
            }
    for (int ntok = 2; ntok <= 8; ++ntok)
        for (int E : {16, 64, 2304})
            for (int f = 0; f < 4; ++f) check_tail(rng, E, ntok, f & 1, f & 2, true);
    for (int rep = 0; rep < 3; ++rep)
        for (int ntok = 2; ntok <= 8; ++ntok) check_tail(rng, 2304, ntok, true, true, false);
#ifdef INK_NO_FMA
    const char *ar = "INK_NO_FMA (rounded product, then the addition)";
#else
    const char *ar = "fma";
#endif
    if (fails) { std::printf("test_wo_mr [%s]: %d FAIL (%lld configurations, %lld words compared)\n", ar, fails, configs, words); return 1; }
    std::printf("test_wo_mr [%s]: PASS (%lld configurations, %lld words compared)\n", ar, configs, words);
    return 0;
}
