// bench_xs: the one-token NVFP4 expert products (8 experts, real weights of layers 0-3, each timed launch the next
// layer so the weights come from memory) in three arithmetics / decodes, timed and checked against double:
//   V0  today's (xmx_moe.hpp XFull): the B tile holds the exact weights code x scale (bf16), per segment of 16 steps
//       c1 (input part 1) and c23 (parts 2, 3) from zero, total = total + (c1 + c23)
//   V1  the scale outside the products: the B tile holds the codes' magnitudes (x 2^-15, through halves, no multiply),
//       per step c = x3.B + x2.B + x1.B from zero, total = fma(scale x 2^15, c, total)
//   V2  V1's arithmetic with the magnitudes from a 256-entry local table (codes re-laid so byte j holds inputs 2j, 2j+1)
// V1 and V2 differ only by the exact power of two 2^15 in B and in the scale, so they must give the same bits.
// The engine's own one-token kernel (xm::full_prod, with its activation epilogue) is timed for reference.
// BENCH_XL=1: instead of V0-V2, physical layouts of the same NVFP4 bytes (TLay below: blocks interleaved by pass, panels
// of one segment over all blocks, the layout before round 4 without the scales after each pass's codes) relaid in place
// over the used experts of all BENCH_NL layers; XFull (one token) and XSmall3 (BENCH_T = 2-8 tokens) read through each,
// checked bit for bit against today's layout and the production kernels on every layer (exit 1 on a differing bit),
// then timed in BENCH_ROUNDS rounds of A B B A (A today's, B the layout).
//   bench_xs <model.gguf> <card>
#include "../../src/xmx_moe.hpp"
#include <algorithm>
#include <random>

using namespace ink;
namespace jm = sycl::ext::oneapi::experimental::matrix;
using bf = sycl::ext::oneapi::bfloat16;

static float host_ue4m3(uint8_t x) {
    const int e = (x >> 3) & 0xF, m = x & 0x7;
    if (x == 0x7F) return 0.0f;
    return e ? std::ldexp((float)(8 + m), e - 11) : (float)m * 0x1p-10f;
}
static double host_nvfp4(const uint8_t *row, int cols, int i) { // value i of a planar NVFP4 row
    const int blk = i / 16, w = i % 16;
    const uint8_t byte = row[blk * 8 + (w % 8)];
    const int nib = w < 8 ? (byte & 0xF) : (byte >> 4);
    static const int mag[8] = {0, 1, 2, 3, 4, 6, 8, 12};
    const double v = mag[nib & 7] * (double)host_ue4m3(row[cols / 2 + blk]);
    return (nib & 8) ? -v : v;
}

// one sub-group per (expert, 16-row block) over all inputs; work-group = 2 sub-groups (MODE 0: the gate and up blocks
// gi and nff/16 + gi, as XFull; MODE 1: blocks 2 gi, 2 gi + 1). Raw sums to Y[expert slot][row].
template <int V, int MODE, int PF = 4, int PD = 8> struct XS {
    const uint8_t *W; size_t estride; int cols, nff;
    const int32_t *ex; const uint16_t *P; size_t pp; float *Y; int ldy;
    const uint32_t *gtab;
    sycl::local_accessor<bf, 1> zb;
    sycl::local_accessor<uint32_t, 1> tab;
    sycl::local_accessor<float, 1> st;
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const {
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 1, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, 1, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        const auto sg = it.get_sub_group();
        const int t = (int)it.get_group(0), gi = (int)it.get_group(1);
        const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id(), lid = (int)it.get_local_linear_id();
        const int steps = cols / 16;
        const int blk = MODE == 0 ? sgi * (nff / 16) + gi : gi * 2 + sgi;
        const uint8_t *w = W + (size_t)ex[t] * estride + (size_t)blk * steps * xm::TB;
        if (lid < 128) reinterpret_cast<uint32_t *>(&zb[0])[lid] = 0u;
        if constexpr (V == 2)
            for (int i = lid; i < 256; i += 32) tab[i] = gtab[i];
        sycl::group_barrier(it.get_group());
        xm::Raw r[PF];
        xm::fetchn<PF>(w, 0, ln, r);
        C tot, c1, c23, zc;
        jm::joint_matrix_fill(sg, tot, 0.0f);
        jm::joint_matrix_fill(sg, zc, 0.0f);
        B rb;
        jm::joint_matrix_load(sg, rb, zb.template get_multi_ptr<sycl::access::decorated::no>(), 32);
        const bf *pa = reinterpret_cast<const bf *>(P);
        for (int k0 = 0; k0 < steps; k0 += xm::SEG) {
            const int ns = sycl::min(xm::SEG, steps - k0);
            if constexpr (V == 0) {
                jm::joint_matrix_fill(sg, c1, 0.0f);
                jm::joint_matrix_fill(sg, c23, 0.0f);
            }
            for (int b = 0; b < ns; b += PF) {
                const int kb = k0 + b, kn = sycl::min(kb + PF, steps - PF);
                xm::Raw n[PF];
                xm::fetchn<PF>(w, kn, ln, n);
                if constexpr (PD > 0) {
                    namespace sx = sycl::ext::oneapi::experimental;
                    const int kp = sycl::min(kb + PD, steps - PF);
                    const uint8_t *pp8 = w + (size_t)kp * xm::TB + (size_t)sycl::min(ln, PF * xm::TB / 64 - 1) * 64;
                    sx::prefetch((void *)pp8, 64, sx::properties{sx::prefetch_hint_L1});
                }
#pragma unroll
                for (int i = 0; i < PF; ++i) {
                    float s = 0.0f;
                    if constexpr (V == 0) {
                        float v[16];
                        xm::decode_vals(r[i], v);
                        int e = 0;
                        jm::joint_matrix_apply(sg, rb, [&](bf &x) { x = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v[e]) >> 16)); ++e; });
                    } else if constexpr (V == 1) {
                        float v[16];
                        const uint32_t cw[2] = {(uint32_t)r[i].cw, (uint32_t)(r[i].cw >> 32)};
#pragma unroll
                        for (int hh = 0; hh < 2; ++hh) {
                            const uint32_t x = cw[hh];
                            const int j0 = 4 * hh;
                            pl::NVFP4P::pair(x, 9, 1.0f, v[j0 + 0], v[j0 + 2]);
                            pl::NVFP4P::pair(x, 5, 1.0f, v[8 + j0 + 0], v[8 + j0 + 2]);
                            pl::NVFP4P::pair(x, 1, 1.0f, v[j0 + 1], v[j0 + 3]);
                            pl::NVFP4P::pair(x, -3, 1.0f, v[8 + j0 + 1], v[8 + j0 + 3]);
                        }
                        int e = 0;
                        jm::joint_matrix_apply(sg, rb, [&](bf &x) { x = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v[e]) >> 16)); ++e; });
                        s = pl::ue4m3_bits((uint8_t)r[i].sc) * 32768.0f;
                    } else {
                        uint32_t wd[8];
#pragma unroll
                        for (int j = 0; j < 8; ++j) wd[j] = tab[(uint32_t)(r[i].cw >> (8 * j)) & 0xFFu];
                        int e = 0;
                        jm::joint_matrix_apply(sg, rb, [&](bf &x) { x = sycl::bit_cast<bf>((uint16_t)(wd[e >> 1] >> ((e & 1) * 16))); ++e; });
                        s = pl::ue4m3_bits((uint8_t)r[i].sc);
                    }
                    A x0, x1, x2;
                    const bf *pk = pa + (size_t)(kb + i) * 16;
                    jm::joint_matrix_load(sg, x0, gp(pk), cols);
                    jm::joint_matrix_load(sg, x1, gp(pk + pp), cols);
                    jm::joint_matrix_load(sg, x2, gp(pk + 2 * pp), cols);
                    if constexpr (V == 0) {
                        jm::joint_matrix_mad(sg, c1, x0, rb, c1);
                        jm::joint_matrix_mad(sg, c23, x1, rb, c23);
                        jm::joint_matrix_mad(sg, c23, x2, rb, c23);
                    } else {
                        C c;
                        jm::joint_matrix_mad(sg, c, x2, rb, zc);
                        jm::joint_matrix_mad(sg, c, x1, rb, c);
                        jm::joint_matrix_mad(sg, c, x0, rb, c);
                        jm::joint_matrix_apply(sg, tot, c, [&](float &u, float &cv) { u = sycl::fma(s, cv, u); });
                    }
                }
#pragma unroll
                for (int i = 0; i < PF; ++i) r[i] = n[i];
            }
            if constexpr (V == 0) {
                jm::joint_matrix_apply(sg, c1, c23, [](float &u, float &v) { u = u + v; });
                jm::joint_matrix_apply(sg, tot, c1, [](float &u, float &v) { u = u + v; });
            }
        }
        jm::joint_matrix_store(sg, tot, st.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)sgi * 16, 16, jm::layout::row_major);
        sycl::group_barrier(sg);
        Y[(size_t)t * ldy + blk * 16 + ln] = st[(size_t)sgi * 16 + ln];
    }
};
template <int V, int MODE>
static sycl::event xs(sycl::queue &q, const uint8_t *W, size_t estride, int cols, int nff, int rows, const int32_t *ex, int nex,
                      const uint16_t *P, size_t pp, float *Y, int ldy, const uint32_t *gtab) {
    const int ngr = MODE == 0 ? nff / 16 : rows / 32;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<bf, 1> zb(256, h);
        sycl::local_accessor<uint32_t, 1> tab(V == 2 ? 256 : 1, h);
        sycl::local_accessor<float, 1> st(32, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nex, (size_t)ngr * 32), sycl::range<2>(1, 32)),
                       XS<V, MODE>{W, estride, cols, nff, ex, P, pp, Y, ldy, gtab, zb, tab, st});
    });
}

// ---- BENCH_XL: physical layouts of the NVFP4 tile tensor (xm::repack_tiles' bytes, moved inside each expert) ----
// A layout places step k (16 inputs) of 16-row block blk: its 16 rows' 8 code bytes and scale bytes. Logical block lb:
// gate|up's gate and up blocks of the same 16 rows adjacent (blk = j nh + gi -> lb = 2 gi + j), down lb = blk (a
// work-group's two blocks are adjacent either way). [group of G logical blocks (0: all)][panel of KP steps (0: all;
// only the last may be shorter)][block in group][step in panel][144 bytes as today]. SOA: inside each pass of 4 steps
// (576 bytes, 9 whole 64-byte lines) the 4 steps' codes (step i at 128 i, row n's 8 bytes at 8 n), then their scales
// (row n's 4 bytes at 512 + 4 n, step i at byte i). TLay<1, 0, true> is today's layout (xm::repack_tiles since round 4;
// lb not used), TLay<1, 0, false> the layout before it ([step][144 bytes]: codes at 8 n, scales at 128 + n). Every layout is a
// bijection of the expert's bytes, so a kernel that reads step k of block blk through it loads the same code word and
// scale byte as today's, in the same registers, and computes the same bits.
struct LGeo { int steps, nblk, mode, nh; }; // nh: blocks per matrix of gate|up (nff / 16)
// one step of the [step][144 bytes] form (row ln's code word at 8 ln, its scale byte at 128 + ln)
static inline xm::Raw aos_fetch(const uint8_t *tp, int ln) { return xm::Raw{*reinterpret_cast<const uint64_t *>(tp + 8 * ln), tp[128 + ln]}; }
template <int G_, int KP_, bool SOA_> struct TLay {
    static_assert(KP_ % 4 == 0, "panels of whole passes of 4 steps");
    static constexpr int G = G_, KP = KP_;
    static constexpr bool SOA = SOA_, BASE = G_ == 1 && KP_ == 0 && SOA_; // BASE: xm's own reads (today's layout)
    static int lbof(const LGeo &q, int blk) { return q.mode == 0 ? 2 * (blk % q.nh) + blk / q.nh : blk; }
    // byte offset in the expert of step k's 144 bytes (AoS); with k % 4 == 0 the first byte of its pass (both forms)
    static size_t off(const LGeo &q, int blk, int k) {
        if constexpr (G_ == 1 && KP_ == 0) return ((size_t)blk * q.steps + k) * xm::TB;
        else {
            const int lb = lbof(q, blk), g = G_ == 0 ? q.nblk : G_, kp = KP_ == 0 ? q.steps : KP_;
            const int gr = lb / g, j = lb % g, p = k / kp, kk = k % kp, rest = q.steps - p * kp, len = rest < kp ? rest : kp;
            return ((size_t)gr * g * q.steps + (size_t)p * g * kp + (size_t)j * len + kk) * xm::TB;
        }
    }
    static xm::Raw fetch(const uint8_t *we, const LGeo &q, int blk, int k, int ln) { // one step (lane ln = row ln)
        if constexpr (!SOA_) return aos_fetch(we + off(q, blk, k), ln);
        else {
            const int i = k & 3;
            const uint8_t *pb = we + off(q, blk, k - i);
            return xm::Raw{*reinterpret_cast<const uint64_t *>(pb + i * 128 + 8 * ln), (uint32_t)pb[512 + 4 * ln + i]};
        }
    }
    static void fetch4(const uint8_t *we, const LGeo &q, int blk, int k, int ln, xm::Raw *r) { // steps k..k+3, k % 4 == 0
        const uint8_t *pb = we + off(q, blk, k);
        if constexpr (!SOA_) {
#pragma unroll
            for (int i = 0; i < 4; ++i) r[i] = aos_fetch(pb + (size_t)i * xm::TB, ln);
        } else {
            const uint32_t sc = *reinterpret_cast<const uint32_t *>(pb + 512 + 4 * ln);
#pragma unroll
            for (int i = 0; i < 4; ++i) r[i] = xm::Raw{*reinterpret_cast<const uint64_t *>(pb + i * 128 + 8 * ln), (sc >> (8 * i)) & 0xFFu};
        }
    }
    static void put(uint8_t *we, const LGeo &q, int blk, int k, int n, const xm::Raw &v) { // row n of step k (its code word, scale)
        uint8_t *o, *s;
        if constexpr (!SOA_) {
            uint8_t *tp = we + off(q, blk, k);
            o = tp + 8 * n;
            s = tp + 128 + n;
        } else {
            const int i = k & 3;
            uint8_t *pb = we + off(q, blk, k - i);
            o = pb + i * 128 + 8 * n;
            s = pb + 512 + 4 * n + i;
        }
        for (int b = 0; b < 8; ++b) o[b] = (uint8_t)(v.cw >> (8 * b)); // the loaded word's bytes (little-endian)
        *s = (uint8_t)v.sc;
    }
};
using L_TODAY = TLay<1, 0, true>;   // today's: one contiguous stream per block, each pass's scales after its codes (5 loads)
using L_PAIR4 = TLay<2, 4, false>;  // a work-group's two blocks interleaved by pass: one stream per work-group (576)
using L_SWEEP = TLay<0, 16, false>; // panels of one segment over all 144 blocks: the launch sweeps 8 x 332 KB at a time
using L_SWEEPS = TLay<0, 16, true>; // L_SWEEP with each pass's scales after its codes
using L_AOS = TLay<1, 0, false>;    // the layout before round 4: today's order, [step][144 bytes] (8 loads per pass)

// xm::XFull as the engine runs it for one token (MMAX 1, PF 4, PD 8, L1 prefetch hint, 128 registers; work-group =
// gate|up's gate and up blocks gi / down's blocks 2 gi, 2 gi + 1), the weights read through LA (LA::BASE: XFull's
// own address expressions). Raw sums to Y[expert slot][row] as XS.
template <class LA, int MODE, int PF = 4, int PD = 8> struct XFL {
    static_assert(PF == 4, "passes of 4 steps");
    const uint8_t *W; size_t estride; int cols, nff, nblk;
    const int32_t *ex; const uint16_t *P; size_t pp; float *Y; int ldy;
    sycl::local_accessor<float, 1> st;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<128>};
    }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const {
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 1, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, 1, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        const auto sg = it.get_sub_group();
        const int t = (int)it.get_group(0), gi = (int)it.get_group(1);
        const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
        const int steps = cols / 16;
        const int blk = MODE == 0 ? sgi * (nff / 16) + gi : gi * 2 + sgi;
        const LGeo geo{steps, nblk, MODE, nff / 16};
        const uint8_t *We = W + (size_t)ex[t] * estride;
        const uint8_t *w = We + (size_t)blk * steps * xm::TB;
        auto pass = [&](int k, xm::Raw *r) {
            if constexpr (LA::BASE) xm::fetchn<PF>(w, k, ln, r);
            else LA::fetch4(We, geo, blk, k, ln, r);
        };
        xm::Raw r[PF];
        pass(0, r);
        C c1, c23, tot;
        jm::joint_matrix_fill(sg, tot, 0.0f);
        B rb;
        jm::joint_matrix_fill(sg, rb, bf(0.0f));
        const bf *pa = reinterpret_cast<const bf *>(P);
        for (int k0 = 0; k0 < steps; k0 += xm::SEG) {
            const int ns = sycl::min(xm::SEG, steps - k0);
            jm::joint_matrix_fill(sg, c1, 0.0f);
            jm::joint_matrix_fill(sg, c23, 0.0f);
            for (int b = 0; b < ns; b += PF) {
                const int kb = k0 + b, kn = sycl::min(kb + PF, steps - PF);
                xm::Raw n[PF];
                pass(kn, n);
                if constexpr (PD > 0) {
                    namespace sx = sycl::ext::oneapi::experimental;
                    const int kp = sycl::min(kb + PD, steps - PF);
                    const uint8_t *pb;
                    if constexpr (LA::BASE) pb = w + (size_t)kp * xm::TB;
                    else pb = We + LA::off(geo, blk, kp); // a pass is 576 contiguous bytes in every layout
                    const uint8_t *pp8 = pb + (size_t)sycl::min(ln, PF * xm::TB / 64 - 1) * 64;
                    sx::prefetch((void *)pp8, 64, sx::properties{sx::prefetch_hint_L1});
                }
#pragma unroll
                for (int i = 0; i < PF; ++i) {
                    float v[16];
                    xm::decode_vals(r[i], v);
                    int e = 0;
                    jm::joint_matrix_apply(sg, rb, [&](bf &x) { x = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v[e]) >> 16)); ++e; });
                    A x0, x1, x2;
                    const bf *pk = pa + (size_t)(kb + i) * 16;
                    jm::joint_matrix_load(sg, x0, gp(pk), cols);
                    jm::joint_matrix_load(sg, x1, gp(pk + pp), cols);
                    jm::joint_matrix_load(sg, x2, gp(pk + 2 * pp), cols);
                    jm::joint_matrix_mad(sg, c1, x0, rb, c1);
                    jm::joint_matrix_mad(sg, c23, x1, rb, c23);
                    jm::joint_matrix_mad(sg, c23, x2, rb, c23);
                }
#pragma unroll
                for (int i = 0; i < PF; ++i) r[i] = n[i];
            }
            jm::joint_matrix_apply(sg, c1, c23, [](float &u, float &v) { u = u + v; });
            jm::joint_matrix_apply(sg, tot, c1, [](float &u, float &v) { u = u + v; });
        }
        jm::joint_matrix_store(sg, tot, st.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)sgi * 16, 16, jm::layout::row_major);
        sycl::group_barrier(sg);
        Y[(size_t)t * ldy + blk * 16 + ln] = st[(size_t)sgi * 16 + ln];
    }
};
template <class LA, int MODE>
static sycl::event xfl(sycl::queue &q, const uint8_t *W, size_t estride, int cols, int nff, int rows, const int32_t *ex, int nex,
                      const uint16_t *P, size_t pp, float *Y, int ldy) {
    const int ngr = MODE == 0 ? nff / 16 : rows / 32;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> st(32, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)nex, (size_t)ngr * 32), sycl::range<2>(1, 32)),
                       XFL<LA, MODE>{W, estride, cols, nff, rows / 16, ex, P, pp, Y, ldy, st});
    });
}

// xm::XSmall3 as the engine runs it for 2-8 tokens (small3<8, MODE, 4, 1, 0, 2>: SR 4, PF 1, B tiles in registers, no
// fused fold, inputs by sorted position), the weights read through LA (LA::BASE: XSmall3's own address expressions).
// Segment sums to S[(t nseg + seg) 8 + r][ncol], as small3.
template <class LA, int MMAX, int MODE, int SR = 4, int PF = 1> struct XS3L {
    const uint8_t *W; size_t estride; int cols, nff, ncol, nblk;
    MoeGroups g; const uint16_t *P; size_t pp; float *S;
    sycl::local_accessor<bf, 1> bs;
    int blkof(int rbk, int j) const { return MODE == 1 ? rbk * 2 + j : j * (nff / 16) + rbk; }
    int colof(int rbk, int j) const { return MODE == 1 ? rbk * 32 + j * 16 : j * nff + rbk * 16; }
    template <int M>
    void body(sycl::sub_group sg, int sgi, int ln, const uint8_t *We, const LGeo &geo, int bk0, int bk1, int k0, int ns, size_t row0, float *so,
              float *so1) const {
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, M, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, M, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        const int steps = cols / 16;
        const uint8_t *w0 = We + (size_t)bk0 * steps * xm::TB, *w1 = We + (size_t)bk1 * steps * xm::TB;
        auto fe = [&](int k, xm::Raw &a, xm::Raw &b) {
            if constexpr (LA::BASE) { a = xm::fetch16t(w0, k, ln); b = xm::fetch16t(w1, k, ln); }
            else { a = LA::fetch(We, geo, bk0, k, ln); b = LA::fetch(We, geo, bk1, k, ln); }
        };
        xm::Raw r0[PF], r1[PF];
#pragma unroll
        for (int i = 0; i < PF; ++i) fe(k0 + i, r0[i], r1[i]);
        C c1[2], c23[2];
#pragma unroll
        for (int j = 0; j < 2; ++j) { jm::joint_matrix_fill(sg, c1[j], 0.0f); jm::joint_matrix_fill(sg, c23[j], 0.0f); }
        uint32_t *bw = reinterpret_cast<uint32_t *>(&bs[0]) + sgi * 512;
        auto lb = [&](size_t off) { return bs.template get_multi_ptr<sycl::access::decorated::no>() + off; };
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        const bf *pa = reinterpret_cast<const bf *>(P) + row0 * cols + (size_t)k0 * 16;
        B rb0, rb1; // defined once (zeros), then every element written each step
#pragma unroll
        for (int j = 0; j < 8; ++j) bw[j * 16 + ln] = 0u;
        sycl::group_barrier(sg);
        jm::joint_matrix_load(sg, rb0, lb((size_t)sgi * 1024), 32);
        jm::joint_matrix_load(sg, rb1, lb((size_t)sgi * 1024), 32);
        for (int b = 0; b < ns; b += PF) {
            xm::Raw n0[PF], n1[PF];
            const int kn = k0 + sycl::min(b + PF, ns - PF);
#pragma unroll
            for (int i = 0; i < PF; ++i) fe(kn + i, n0[i], n1[i]);
#pragma unroll
            for (int i = 0; i < PF; ++i) {
                const int kk = b + i;
                float v0[16], v1[16];
                xm::decode_vals(r0[i], v0);
                xm::decode_vals(r1[i], v1);
                int e0 = 0, e1 = 0;
                jm::joint_matrix_apply(sg, rb0, [&](bf &x) { x = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v0[e0]) >> 16)); ++e0; });
                jm::joint_matrix_apply(sg, rb1, [&](bf &x) { x = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v1[e1]) >> 16)); ++e1; });
                A x0, x1, x2;
                jm::joint_matrix_load(sg, x0, gp(pa + kk * 16), cols);
                jm::joint_matrix_load(sg, x1, gp(pa + pp + kk * 16), cols);
                jm::joint_matrix_load(sg, x2, gp(pa + 2 * pp + kk * 16), cols);
                jm::joint_matrix_mad(sg, c1[0], x0, rb0, c1[0]);
                jm::joint_matrix_mad(sg, c23[0], x1, rb0, c23[0]);
                jm::joint_matrix_mad(sg, c23[0], x2, rb0, c23[0]);
                jm::joint_matrix_mad(sg, c1[1], x0, rb1, c1[1]);
                jm::joint_matrix_mad(sg, c23[1], x1, rb1, c23[1]);
                jm::joint_matrix_mad(sg, c23[1], x2, rb1, c23[1]);
            }
#pragma unroll
            for (int i = 0; i < PF; ++i) { r0[i] = n0[i]; r1[i] = n1[i]; }
        }
#pragma unroll
        for (int j = 0; j < 2; ++j) {
            jm::joint_matrix_apply(sg, c1[j], c23[j], [](float &u, float &v) { u = u + v; });
            jm::joint_matrix_store(sg, c1[j], sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(j ? so1 : so),
                                   ncol, jm::layout::row_major);
        }
    }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const {
        const int t = (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        const auto sg = it.get_sub_group();
        const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
        const int steps = cols / 16, nseg = (steps + xm::SEG - 1) / xm::SEG;
        const int gi = (int)it.get_group(1), seg = gi % nseg, rbk = (gi / nseg) * SR + sgi;
        const int k0 = seg * xm::SEG, ns = sycl::min(xm::SEG, steps - k0), cnt = g.tile_n[t];
        const uint8_t *We = W + (size_t)g.tile_exp[t] * estride;
        const LGeo geo{steps, nblk, MODE, nff / 16};
        const int bk0 = blkof(rbk, 0), bk1 = blkof(rbk, 1);
        const size_t row0 = (size_t)g.tile_s0[t];
        float *sb = S + (size_t)(t * nseg + seg) * MMAX * ncol, *so = sb + colof(rbk, 0), *so1 = sb + colof(rbk, 1);
        if (cnt <= 1) body<1>(sg, sgi, ln, We, geo, bk0, bk1, k0, ns, row0, so, so1);
        else if (cnt <= 2) body<2>(sg, sgi, ln, We, geo, bk0, bk1, k0, ns, row0, so, so1);
        else if (cnt <= 4) body<4>(sg, sgi, ln, We, geo, bk0, bk1, k0, ns, row0, so, so1);
        else body<8>(sg, sgi, ln, We, geo, bk0, bk1, k0, ns, row0, so, so1);
    }
};
template <class LA, int MODE>
static sycl::event xs3l(sycl::queue &q, const uint8_t *W, size_t estride, int cols, int nff, int ncol, int nrb, int nblk, MoeGroups g, int tiles,
                        const uint16_t *P, size_t pp, float *S) {
    constexpr int SR = 4;
    const int steps = cols / 16, nseg = (steps + xm::SEG - 1) / xm::SEG;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<bf, 1> bs(SR * 1024, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)tiles, (size_t)(nrb / SR) * nseg * SR * 16), sycl::range<2>(1, SR * 16)),
                       XS3L<LA, 8, MODE>{W, estride, cols, nff, ncol, nblk, g, P, pp, S, bs});
    });
}

// the used experts' bytes in layout LA, from a compact copy of today's (bk: [used expert][estride])
template <class LA>
static sycl::event relay_to(sycl::queue &q, uint8_t *W, size_t estride, const int32_t *uex, int nu, const uint8_t *bk, LGeo geo) {
    return q.parallel_for(sycl::range<3>((size_t)nu, (size_t)geo.nblk * geo.steps, 16), [=](sycl::id<3> id) {
        const int u = (int)id[0], blk = (int)(id[1] / geo.steps), k = (int)(id[1] % geo.steps), n = (int)id[2];
        LA::put(W + (size_t)uex[u] * estride, geo, blk, k, n, L_TODAY::fetch(bk + (size_t)u * estride, geo, blk, k, n));
    });
}
// cnt += the (expert, block, step, row) whose code word or scale read through LA differs from today's copy
template <class LA>
static sycl::event perm_count(sycl::queue &q, const uint8_t *W, size_t estride, const int32_t *uex, int nu, const uint8_t *bk, LGeo geo, int32_t *cnt) {
    return q.parallel_for(sycl::range<3>((size_t)nu, (size_t)geo.nblk * geo.steps, 16), [=](sycl::id<3> id) {
        const int u = (int)id[0], blk = (int)(id[1] / geo.steps), k = (int)(id[1] % geo.steps), n = (int)id[2];
        const xm::Raw a = L_TODAY::fetch(bk + (size_t)u * estride, geo, blk, k, n);
        const xm::Raw b = LA::fetch(W + (size_t)uex[u] * estride, geo, blk, k, n);
        if (a.cw != b.cw || a.sc != b.sc)
            sycl::atomic_ref<int32_t, sycl::memory_order::relaxed, sycl::memory_scope::device, sycl::access::address_space::global_space>(*cnt).fetch_add(1);
    });
}
// cnt += the floats of a and b whose bits differ (signed zeros and NaN payloads included)
static sycl::event diff_count(sycl::queue &q, const float *a, const float *b, size_t n, int32_t *cnt) {
    return q.parallel_for(sycl::range<1>(n), [=](sycl::id<1> i) {
        if (sycl::bit_cast<uint32_t>(a[i]) != sycl::bit_cast<uint32_t>(b[i]))
            sycl::atomic_ref<int32_t, sycl::memory_order::relaxed, sycl::memory_scope::device, sycl::access::address_space::global_space>(*cnt).fetch_add(1);
    });
}

// BENCH_XL: every layout in place over the used experts of all NL layers (relaid from a copy of today's bytes, so every
// arm reads the same allocations and pages), checked bit for bit against today's and against the production kernels,
// then timed against today's in rounds A B B A. Returns 1 on any differing bit.
static int xl_study(Device &d, const std::vector<WView> &gu, const std::vector<WView> &dn, int NL, int NSETS, const std::vector<int32_t> &hex,
                    const int32_t *ex, const uint16_t *Px, const uint16_t *Ph, int iters, std::mt19937 &rng) {
    constexpr int NE = 128, KU = 8, E = 2304, NFF = 1152, NA = 4;
    static const char *const names[NA + 1] = {"today", "pair4 (G 2, KP 4)", "sweep16 (G all, KP 16)", "sweep16s (G all, KP 16, SOA)",
                                              "aos (the layout before round 4)"};
    const int T = std::getenv("BENCH_T") ? std::atoi(std::getenv("BENCH_T")) : 4;
    const int ROUNDS = std::getenv("BENCH_ROUNDS") ? std::atoi(std::getenv("BENCH_ROUNDS")) : 3;
    if (T < 2 || T > 8 || ROUNDS < 1) throw std::runtime_error("BENCH_T 2-8, BENCH_ROUNDS >= 1");
    const size_t gub = gu[0].rb * (size_t)gu[0].t->ne[1], dnb = dn[0].rb * (size_t)dn[0].t->ne[1];
    const LGeo ggu{E / 16, 2 * NFF / 16, 0, NFF / 16}, gdn{NFF / 16, E / 16, 1, NFF / 16};
    if (ggu.steps % 4 || gdn.steps % 4 || ggu.nblk % 2 || gdn.nblk % 2 || gub % 64 || dnb % 64) throw std::runtime_error("BENCH_XL: shapes");
    // T tokens of 8 distinct experts each (the 2-8 token checks), grouped as the engine does
    const int K = T * KU;
    std::vector<int32_t> ids(K);
    for (int s = 0; s < T; ++s) {
        std::vector<int> pool(NE);
        for (int e = 0; e < NE; ++e) pool[e] = e;
        std::shuffle(pool.begin(), pool.end(), rng);
        for (int k = 0; k < KU; ++k) ids[(size_t)s * KU + k] = pool[k];
    }
    int32_t *dids = d.alloc<int32_t>(K);
    d.put(dids, ids.data(), (size_t)K);
    MoeGroups g3, g1;
    g3.alloc(d, NE, K);
    moe_group(d.q, dids, K, NE, g3).wait();
    g1.alloc(d, NE, KU); // expert set 0, for the engine's full_prod
    moe_group(d.q, ex, KU, NE, g1).wait();
    const int tiles1 = MoeGroups::max_tiles(NE, KU);
    int nt3 = 0;
    d.get(&nt3, g3.ntiles, 1);
    std::normal_distribution<float> nd(0.0f, 1.0f);
    std::vector<float> xt((size_t)T * E), ht((size_t)T * NFF);
    for (auto &v : xt) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
    for (auto &v : ht) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
    float *dxt = d.alloc<float>(xt.size()), *dht = d.alloc<float>(ht.size());
    d.put(dxt, xt.data(), xt.size());
    d.put(dht, ht.data(), ht.size());
    const size_t ppg = (size_t)(K + 16) * E, ppd = (size_t)(K + 16) * NFF; // rows past K (read by a tile's last M rows) zero
    uint16_t *P3g = d.alloc_zero<uint16_t>(3 * ppg), *P3d = d.alloc_zero<uint16_t>(3 * ppd);
    xm::split_gather_c(d.q, g3, K, dxt, E, KU, E, P3g, ppg).wait();
    xm::split_gather_c(d.q, g3, K, dht, NFF, KU, NFF, P3d, ppd).wait();
    const int nsg = (ggu.steps + xm::SEG - 1) / xm::SEG, nsd = (gdn.steps + xm::SEG - 1) / xm::SEG;
    const size_t nSg = (size_t)nt3 * nsg * 8 * 2 * NFF, nSd = (size_t)nt3 * nsd * 8 * E;
    float *S = d.alloc<float>(std::max(nSg, nSd)), *Y = d.alloc<float>((size_t)KU * 2 * NFF);
    int32_t *cnt = d.alloc<int32_t>(1);
    // the used experts (every one-token set, the T tokens'), today's bytes copied once per layer and tensor
    std::vector<int32_t> uex(hex.begin(), hex.end());
    uex.insert(uex.end(), ids.begin(), ids.end());
    std::sort(uex.begin(), uex.end());
    uex.erase(std::unique(uex.begin(), uex.end()), uex.end());
    const int nu = (int)uex.size();
    int32_t *duex = d.alloc<int32_t>(nu);
    d.put(duex, uex.data(), (size_t)nu);
    std::vector<uint8_t *> bgu(NL), bdn(NL);
    for (int l = 0; l < NL; ++l) {
        bgu[l] = d.alloc<uint8_t>((size_t)nu * gub);
        bdn[l] = d.alloc<uint8_t>((size_t)nu * dnb);
        for (int u = 0; u < nu; ++u) {
            d.q.memcpy(bgu[l] + (size_t)u * gub, gu[l].p + (size_t)uex[u] * gub, gub);
            d.q.memcpy(bdn[l] + (size_t)u * dnb, dn[l].p + (size_t)uex[u] * dnb, dnb);
        }
    }
    d.q.wait();
    std::printf("BENCH_XL: layouts in place over layers 0-%d, %d used experts (%d one-token sets, %d tokens -> %d tiles), copies %.2f GB, "
                "%d rounds A B B A of %d launches; tensor bases mod 64: %d / %d\n", NL - 1, nu, NSETS, T, nt3, (double)NL * nu * (gub + dnb) / 1e9,
                ROUNDS, iters, (int)((uintptr_t)gu[0].p & 63), (int)((uintptr_t)dn[0].p & 63));
    auto with = [&](int a, auto &&f) {
        switch (a) {
        case 0: f(L_TODAY{}); break;
        case 1: f(L_PAIR4{}); break;
        case 2: f(L_SWEEP{}); break;
        case 3: f(L_SWEEPS{}); break;
        default: f(L_AOS{}); break;
        }
    };
    // kernel kk on layer l, one-token set s: 0 XFull gate|up, 1 XFull down, 2 XSmall3 gate|up, 3 XSmall3 down
    static const char *const kname[4] = {"XFull gate|up", "XFull down", "XSmall3 gate|up", "XSmall3 down"};
    auto launch = [&](auto lay, int kk, int l, int s) {
        using LA = decltype(lay);
        const int32_t *es = ex + (size_t)s * KU;
        if (kk == 0) xfl<LA, 0>(d.q, gu[l].p, gub, E, NFF, 2 * NFF, es, KU, Px, (size_t)E, Y, 2 * NFF);
        else if (kk == 1) xfl<LA, 1>(d.q, dn[l].p, dnb, NFF, NFF, E, es, KU, Ph, (size_t)NFF, Y, E);
        else if (kk == 2) xs3l<LA, 0>(d.q, gu[l].p, gub, E, NFF, 2 * NFF, NFF / 16, ggu.nblk, g3, nt3, P3g, ppg, S);
        else xs3l<LA, 1>(d.q, dn[l].p, dnb, NFF, NFF, E, E / 32, gdn.nblk, g3, nt3, P3d, ppd, S);
    };
    auto outp = [&](int kk) -> std::pair<float *, size_t> {
        if (kk < 2) return {Y, (size_t)KU * (kk == 0 ? 2 * NFF : E)};
        return {S, kk == 2 ? nSg : nSd};
    };
    auto run_out = [&](auto lay, int kk, int l) { // set 0; the outputs zeroed first (rows past a tile's M are not written)
        const auto o = outp(kk);
        d.q.memset(o.first, 0, o.second * sizeof(float)).wait();
        launch(lay, kk, l, 0);
        d.q.wait();
        return o;
    };
    auto ndiff = [&](const float *a, const float *b, size_t n) {
        d.q.memset(cnt, 0, sizeof(int32_t)).wait();
        diff_count(d.q, a, b, n, cnt).wait();
        int32_t h = 0;
        d.get(&h, cnt, 1);
        return (long)h;
    };
    // today's outputs of every layer (references), and today's against the production kernels
    std::vector<float *> ref[4];
    long chain[4] = {0, 0, 0, 0};
    const xm::ActOp op{nullptr, 8.0f, 4.0f};
    for (int kk = 0; kk < 4; ++kk) ref[kk].resize(NL);
    for (int l = 0; l < NL; ++l) {
        for (int kk = 0; kk < 4; ++kk) {
            const auto o = run_out(L_TODAY{}, kk, l);
            ref[kk][l] = d.alloc<float>(o.second);
            d.q.memcpy(ref[kk][l], o.first, o.second * sizeof(float)).wait();
        }
        // gate|up: production full_prod<MODE=1> over gate|up tensor exposes every block's exact production sum in slot order
        d.q.memset(Y, 0, (size_t)KU * 2 * NFF * sizeof(float)).wait();
        xm::full_prod<1, 1, 4, 2, 128, 8, 1>(d.q, gu[l].p, gub, E, NFF, 2 * NFF, g1, tiles1, Px, (size_t)E, true, op, nullptr, 0, Y, 2 * NFF).wait();
        chain[0] += ndiff(Y, ref[0][l], (size_t)KU * 2 * NFF);
        // down: the engine's xm::full_prod (y[slot][row]; slot k = expert hex[k], as XFL's row k)
        d.q.memset(Y, 0, (size_t)KU * E * sizeof(float)).wait();
        xm::full_prod<1, 1, 4, 2, 128, 8, 1>(d.q, dn[l].p, dnb, NFF, NFF, E, g1, tiles1, Ph, (size_t)NFF, true, op, nullptr, 0, Y, E).wait();
        chain[1] += ndiff(Y, ref[1][l], (size_t)KU * E);
        // 2-8 tokens: the engine's xm::small3
        d.q.memset(S, 0, nSg * sizeof(float)).wait();
        xm::small3<8, 0, 4, 1, 0, 2>(d.q, gu[l].p, gub, E, NFF, 2 * NFF, NFF / 16, g3, nt3, P3g, ppg, false, S).wait();
        chain[2] += ndiff(S, ref[2][l], nSg);
        d.q.memset(S, 0, nSd * sizeof(float)).wait();
        xm::small3<8, 1, 4, 1, 0, 2>(d.q, dn[l].p, dnb, NFF, NFF, E, E / 32, g3, nt3, P3d, ppd, false, S).wait();
        chain[3] += ndiff(S, ref[3][l], nSd);
    }
    std::printf("  today's copies against the originals, %d layers: XFull gate|up vs bench V0 %ld, XFull down vs engine full_prod %ld, "
                "XSmall3 gate|up / down vs engine small3 %ld / %ld floats differ\n", NL, chain[0], chain[1], chain[2], chain[3]);
    if (chain[0] || chain[1] || chain[2] || chain[3]) {
        std::printf("  DIFF: the bench's copy of a production kernel does not give the production bits; no layout verdict\n");
        return 1;
    }
    if (chain[0]) std::printf("  note: bench V0 and the XFull copy differ on gate|up (V0 is not the engine kernel); the layouts are checked against the copy\n");
    int cur = 0;
    auto set_layout = [&](int a) {
        if (a == cur) return;
        with(a, [&](auto lay) {
            using LA = decltype(lay);
            for (int l = 0; l < NL; ++l) {
                relay_to<LA>(d.q, const_cast<uint8_t *>(gu[l].p), gub, duex, nu, bgu[l], ggu);
                relay_to<LA>(d.q, const_cast<uint8_t *>(dn[l].p), dnb, duex, nu, bdn[l], gdn);
            }
            d.q.wait();
        });
        cur = a;
    };
    // every layout: the bytes it reads and the sums of every layer, bit for bit against today's
    bool bad = false;
    for (int a = 1; a <= NA; ++a) {
        set_layout(a);
        long perm = 0, od[4] = {0, 0, 0, 0};
        with(a, [&](auto lay) {
            using LA = decltype(lay);
            for (int l = 0; l < NL; ++l) {
                d.q.memset(cnt, 0, sizeof(int32_t)).wait();
                perm_count<LA>(d.q, gu[l].p, gub, duex, nu, bgu[l], ggu, cnt).wait();
                perm_count<LA>(d.q, dn[l].p, dnb, duex, nu, bdn[l], gdn, cnt).wait();
                int32_t h = 0;
                d.get(&h, cnt, 1);
                perm += h;
                for (int kk = 0; kk < 4; ++kk) {
                    const auto o = run_out(lay, kk, l);
                    od[kk] += ndiff(o.first, ref[kk][l], o.second);
                }
            }
        });
        const bool ok = perm == 0 && od[0] == 0 && od[1] == 0 && od[2] == 0 && od[3] == 0;
        std::printf("  %-30s %s: %ld of %zu code words / scales, floats %ld / %ld / %ld / %ld (XFull g|u, down, XSmall3 g|u, down) differ\n",
                    names[a], ok ? "same bits" : "DIFF", perm, (size_t)NL * nu * 16 * ((size_t)ggu.nblk * ggu.steps + (size_t)gdn.nblk * gdn.steps),
                    od[0], od[1], od[2], od[3]);
        bad = bad || !ok;
    }
    if (bad) {
        set_layout(0);
        std::printf("  DIFF: a layout changes the bits; no timing\n");
        return 1;
    }
    auto timeit = [&](auto &&launch1) {
        for (int i = 0; i < 8; ++i) launch1(i);
        d.q.wait();
        const double t0 = now_s();
        for (int i = 0; i < iters; ++i) launch1(i);
        d.q.wait();
        return (now_s() - t0) / iters * 1e6;
    };
    if (iters <= 0) throw std::runtime_error("BENCH_ITERS must be >= 1");
    set_layout(0);
    for (int kk = 0; kk < 4; ++kk) timeit([&](int i) { launch(L_TODAY{}, kk, i % NL, (i / NL) % NSETS); });
    // A B B A per round: today's (A) and the arm (B), each slot every kernel over all layers in turn
    std::vector<double> us[NA + 1][2][4];
    for (int a = 1; a <= NA; ++a)
        for (int rnd = 0; rnd < ROUNDS; ++rnd)
            for (int slot = 0; slot < 4; ++slot) {
                const int isb = slot == 1 || slot == 2 ? 1 : 0;
                set_layout(isb ? a : 0);
                with(isb ? a : 0, [&](auto lay) {
                    for (int kk = 0; kk < 4; ++kk) us[a][isb][kk].push_back(timeit([&](int i) { launch(lay, kk, i % NL, (i / NL) % NSETS); }));
                });
            }
    set_layout(0);
    auto stat = [](const std::vector<double> &v, double &mn, double &mx) {
        double s = 0;
        mn = 1e30; mx = 0;
        for (double x : v) { s += x; mn = std::min(mn, x); mx = std::max(mx, x); }
        return s / v.size();
    };
    const double bytes[4] = {(double)KU * gub, (double)KU * dnb, (double)nt3 * gub, (double)nt3 * dnb};
    for (int a = 1; a <= NA; ++a) {
        std::printf("  %s against today's (%d x A B B A, mean [min-max] us):\n", names[a], ROUNDS);
        for (int kk = 0; kk < 4; ++kk) {
            double amn, amx, bmn, bmx;
            const double ma = stat(us[a][0][kk], amn, amx), mb = stat(us[a][1][kk], bmn, bmx);
            std::printf("    %-16s today %7.2f [%7.2f-%7.2f] %6.1f GB/s   arm %7.2f [%7.2f-%7.2f] %6.1f GB/s   %+6.2f us (%+5.1f %%)%s\n", kname[kk], ma,
                        amn, amx, bytes[kk] / ma / 1e3, mb, bmn, bmx, bytes[kk] / mb / 1e3, mb - ma, (mb - ma) / ma * 100.0,
                        bmx < amn ? "  faster in every slot" : (bmn > amx ? "  slower in every slot" : ""));
        }
    }
    std::printf("  (today's = the round 4 layout; the aos arm is the rollback check: it should be slower on XFull)\n");
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 3) { std::fprintf(stderr, "usage: bench_xs <model.gguf> <card>\n"); return 2; }
    try {
        GGUF gf(argv[1]);
        Device d(std::atoi(argv[2]));
        Weights w;
        w.upload(d, gf, false);
        auto views = planarize(d, gf, w, false);
        const int iters = std::getenv("BENCH_ITERS") ? std::atoi(std::getenv("BENCH_ITERS")) : 200;
        // BENCH_NL layers in turn (1-20; 20 spreads the reads over ~11 GB of weights), BENCH_SETS expert sets in turn
        const int NL = std::getenv("BENCH_NL") ? std::atoi(std::getenv("BENCH_NL")) : 4;
        const int NSETS = std::getenv("BENCH_SETS") ? std::atoi(std::getenv("BENCH_SETS")) : 1;
        const bool only_engine = std::getenv("BENCH_ENGINE_ONLY") != nullptr;
        const bool xl_mode = std::getenv("BENCH_XL") != nullptr; // the layout study (no V1 / V2 copies)
        constexpr int NE = 128, KU = 8, E = 2304, NFF = 1152;
        if (NL < 1 || NL > 20 || NSETS < 1) throw std::runtime_error("BENCH_NL 1-20, BENCH_SETS >= 1");
        std::vector<WView> gu(NL), dn(NL);
        for (int l = 0; l < NL; ++l) {
            gu[l] = views.at("blk." + std::to_string(l) + ".ffn_gate_up_exps.weight");
            dn[l] = views.at("blk." + std::to_string(l) + ".ffn_down_exps.weight");
            if (gu[l].kind != K_NVFP4P || dn[l].kind != K_NVFP4P) throw std::runtime_error("layer " + std::to_string(l) + " is not NVFP4");
        }
        const size_t gub = gu[0].rb * (size_t)gu[0].t->ne[1], dnb = dn[0].rb * (size_t)dn[0].t->ne[1];
        std::mt19937 rng(11);
        std::vector<int32_t> hex((size_t)KU * NSETS);
        for (int st = 0; st < NSETS; ++st) {
            std::vector<int> pool(NE);
            for (int e = 0; e < NE; ++e) pool[e] = e;
            if (st == 0) for (int k = 0; k < KU; ++k) hex[k] = (int)((k * 37 + 5) % NE);
            else {
                std::shuffle(pool.begin(), pool.end(), rng);
                for (int k = 0; k < KU; ++k) hex[(size_t)st * KU + k] = pool[k];
            }
        }
        std::normal_distribution<float> nd(0.0f, 1.0f);
        std::vector<float> hx(E), hh(NFF);
        for (auto &v : hx) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
        for (auto &v : hh) v = nd(rng) * (rng() % 64 == 0 ? 20.0f : 1.0f);
        auto parts = [](const std::vector<float> &x) {
            std::vector<uint16_t> p(3 * x.size());
            for (size_t i = 0; i < x.size(); ++i) {
                uint16_t a, b, c;
                split3(x[i], a, b, c);
                p[i] = a; p[x.size() + i] = b; p[2 * x.size() + i] = c;
            }
            return p;
        };
        const std::vector<uint16_t> px = parts(hx), ph = parts(hh);
        uint16_t *Px = d.alloc<uint16_t>(px.size()), *Ph = d.alloc<uint16_t>(ph.size());
        d.put(Px, px.data(), px.size());
        d.put(Ph, ph.data(), ph.size());
        int32_t *ex = d.alloc<int32_t>(hex.size());
        d.put(ex, hex.data(), hex.size());
        // host rows of layer 0's chosen experts (planar, before the tile layout) for the check against double
        std::vector<uint8_t> rg((size_t)KU * 2 * NFF * gu[0].rb), rd((size_t)KU * E * dn[0].rb);
        for (int k = 0; k < KU; ++k) {
            d.get(rg.data() + (size_t)k * 2 * NFF * gu[0].rb, gu[0].p + (size_t)hex[k] * gub, 2 * NFF * gu[0].rb);
            d.get(rd.data() + (size_t)k * E * dn[0].rb, dn[0].p + (size_t)hex[k] * dnb, E * dn[0].rb);
        }
        // the tile layout (today's), in place; and V2's copies with the codes re-laid (byte j: inputs 2j, 2j+1), scales kept
        std::vector<uint8_t *> gu2(NL), dn2(NL);
        {
            uint8_t *tmp = d.alloc<uint8_t>(std::max(gub, dnb));
            for (int l = 0; l < NL; ++l) {
                xm::repack_tiles(d.q, const_cast<uint8_t *>(gu[l].p), gu[l].rb, 2 * NFF, E, NE, tmp);
                xm::repack_tiles(d.q, const_cast<uint8_t *>(dn[l].p), dn[l].rb, E, NFF, NE, tmp);
            }
            d.release(tmp);
            auto relay = [&](const uint8_t *src, size_t bytes) {
                uint8_t *o = d.alloc<uint8_t>(bytes);
                const size_t nt = bytes / xm::TB; // steps; every pass of 4 (576 bytes) whole (xm::repack_tiles' layout)
                d.q.parallel_for(sycl::range<2>(nt, 16), [=](sycl::id<2> id) {
                    const int s = (int)(id[0] % xm::TP), n = (int)id[1];
                    const size_t pb = (id[0] - s) * xm::TB; // the step's pass
                    const uint8_t *tp = src + pb + 128 * s;
                    uint8_t *op = o + pb + 128 * s;
                    auto nib = [&](int k) { return k < 8 ? (tp[8 * n + k] & 0xF) : (tp[8 * n + k - 8] >> 4); };
                    for (int j = 0; j < 8; ++j) op[8 * n + j] = (uint8_t)(nib(2 * j) | (nib(2 * j + 1) << 4));
                    o[pb + 512 + 4 * n + s] = src[pb + 512 + 4 * n + s];
                }).wait();
                return o;
            };
            for (int l = 0; l < (only_engine || xl_mode ? 0 : NL); ++l) { gu2[l] = relay(gu[l].p, NE * gub); dn2[l] = relay(dn[l].p, NE * dnb); } // (every expert)
        }
        std::vector<uint32_t> htab(256);
        for (int v = 0; v < 256; ++v) {
            auto bfmag = [](int c) -> uint32_t {
                static const float mag[8] = {0, 1, 2, 3, 4, 6, 8, 12};
                float f = mag[c & 7];
                uint32_t u;
                std::memcpy(&u, &f, 4);
                return (u >> 16) | ((c & 8) ? 0x8000u : 0u);
            };
            htab[v] = bfmag(v & 0xF) | (bfmag(v >> 4) << 16);
        }
        uint32_t *gtab = d.alloc<uint32_t>(256);
        d.put(gtab, htab.data(), 256);
        float *Y = d.alloc<float>((size_t)KU * E);
        const double macs_gu = (double)KU * 2 * NFF * E, macs_dn = (double)KU * E * NFF;
        auto timeit = [&](auto &&launch) {
            for (int i = 0; i < 8; ++i) launch(i);
            d.q.wait();
            const double e0 = d.energy_j(), t0 = now_s();
            for (int i = 0; i < iters; ++i) launch(i);
            d.q.wait();
            const double us = (now_s() - t0) / iters * 1e6, ej = (d.energy_j() - e0) / iters;
            return std::pair<double, double>(us, ej);
        };
        // the sums of layer 0 against double: mean and max error in units of 2^-24 x sum |w x|
        auto check = [&](int mode, std::vector<float> &out) {
            const int rows = mode == 0 ? 2 * NFF : E, cols = mode == 0 ? E : NFF;
            const std::vector<float> &x = mode == 0 ? hx : hh;
            const std::vector<uint8_t> &R = mode == 0 ? rg : rd;
            const size_t rb = mode == 0 ? gu[0].rb : dn[0].rb;
            out.resize((size_t)KU * rows);
            d.get(out.data(), Y, out.size());
            double sm = 0, mx = 0;
            int n = 0;
            for (int k = 0; k < KU; ++k)
                for (int r = 0; r < rows; r += 7) {
                    const uint8_t *row = R.data() + ((size_t)k * rows + r) * rb;
                    double s = 0, a = 0;
                    for (int i = 0; i < cols; ++i) { const double p = host_nvfp4(row, cols, i) * (double)x[i]; s += p; a += std::fabs(p); }
                    const double err = std::fabs((double)out[(size_t)k * rows + r] - s) / (a * 0x1p-24 + 1e-300);
                    sm += err; mx = std::max(mx, err); ++n;
                }
            return std::pair<double, double>(sm / n, mx);
        };
        std::printf("one token, 8 experts, layers 0-%d in turn, %d launches each\n", NL - 1, iters);
        std::vector<float> o0, o1, o2;
        for (int mode = 0; mode < (only_engine || xl_mode ? 0 : 2); ++mode) {
            const char *nm = mode == 0 ? "gate|up" : "down";
            const int cols = mode == 0 ? E : NFF, rows = mode == 0 ? 2 * NFF : E;
            const uint16_t *P = mode == 0 ? Px : Ph;
            const size_t pp = cols, eb = mode == 0 ? gub : dnb;
            const double macs = mode == 0 ? macs_gu : macs_dn;
            auto L = [&](int l) { return mode == 0 ? gu[l].p : dn[l].p; };
            auto L2 = [&](int l) { return mode == 0 ? gu2[l] : dn2[l]; };
            auto run = [&](int v, int i) {
                const int l = i % NL;
                if (mode == 0) {
                    if (v == 0) xs<0, 0>(d.q, L(l), eb, cols, NFF, rows, ex, KU, P, pp, Y, rows, gtab);
                    else if (v == 1) xs<1, 0>(d.q, L(l), eb, cols, NFF, rows, ex, KU, P, pp, Y, rows, gtab);
                    else xs<2, 0>(d.q, L2(l), eb, cols, NFF, rows, ex, KU, P, pp, Y, rows, gtab);
                } else {
                    if (v == 0) xs<0, 1>(d.q, L(l), eb, cols, NFF, rows, ex, KU, P, pp, Y, rows, gtab);
                    else if (v == 1) xs<1, 1>(d.q, L(l), eb, cols, NFF, rows, ex, KU, P, pp, Y, rows, gtab);
                    else xs<2, 1>(d.q, L2(l), eb, cols, NFF, rows, ex, KU, P, pp, Y, rows, gtab);
                }
            };
            for (int rep = 0; rep < 2; ++rep)
                for (int v = 0; v < 3; ++v) {
                    const auto [us, ej] = timeit([&](int i) { run(v, i); });
                    run(v, 0);
                    d.q.wait();
                    std::vector<float> &o = v == 0 ? o0 : (v == 1 ? o1 : o2);
                    const auto [em, ex2] = check(mode, o);
                    std::printf("  %-8s V%d  %7.2f us  %6.1f GB/s  %6.1f pJ/MAC  error mean %.4f max %.4f\n", nm, v, us,
                                (double)KU * eb / us / 1e3, ej / macs * 1e12, em, ex2);
                }
            std::printf("  %-8s V1 vs V2: %s; V0 vs V1: %s\n", nm, std::memcmp(o1.data(), o2.data(), o1.size() * 4) ? "DIFFER" : "same bits",
                        std::memcmp(o0.data(), o1.data(), o0.size() * 4) ? "differ (another arithmetic)" : "same bits");
        }
        { // the engine's kernel, for reference (its epilogue too)
            std::vector<MoeGroups> grps(NSETS);
            for (int st = 0; st < NSETS; ++st) {
                grps[st].alloc(d, NE, KU);
                moe_group(d.q, ex + (size_t)st * KU, KU, NE, grps[st]).wait();
            }
            const int tiles = MoeGroups::max_tiles(NE, KU);
            uint16_t *Hp = d.alloc<uint16_t>((size_t)3 * NFF * 16);
            float *Y2 = d.alloc<float>((size_t)KU * E);
            const xm::ActOp op{nullptr, 8.0f, 4.0f};
            double us, ej;
            std::tie(us, ej) = timeit([&](int i) {
                xm::full_prod<1, 0, 4, 2, 128, 8, 1>(d.q, gu[i % NL].p, gub, E, NFF, 2 * NFF, grps[(i / NL) % NSETS], tiles, Px, (size_t)E, true, op, Hp, (size_t)16 * NFF, nullptr, 0);
            });
            std::printf("  (%d layers, %d expert sets in turn)\n", NL, NSETS);
            std::printf("  engine full_prod gate|up %7.2f us  %6.1f pJ/MAC\n", us, ej / macs_gu * 1e12);
            std::tie(us, ej) = timeit([&](int i) {
                xm::full_prod<1, 1, 4, 2, 128, 8, 1>(d.q, dn[i % NL].p, dnb, NFF, NFF, E, grps[(i / NL) % NSETS], tiles, Ph, (size_t)NFF, true, op, nullptr, 0, Y2, E);
            });
            std::printf("  engine full_prod down    %7.2f us  %6.1f pJ/MAC\n", us, ej / macs_dn * 1e12);
        }
        if (xl_mode && xl_study(d, gu, dn, NL, NSETS, hex, ex, Px, Ph, iters, rng)) return 1;
    } catch (std::exception &ex) {
        std::fprintf(stderr, "error: %s\n", ex.what());
        return 1;
    }
    return 0;
}
