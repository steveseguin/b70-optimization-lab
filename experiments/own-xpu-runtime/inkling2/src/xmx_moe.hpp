// xmx_moe.hpp: the NVFP4 layers' experts on the matrix engines with exact products.
//
// Arithmetic (the same for every step size; README "Matrix engines with exact products"):
//   - every input x (fp32) is split into three bf16 parts, x1 = bf16(x), x2 = bf16(x - x1), x3 = bf16(x - x1 - x2)
//     (round to nearest even), and x = x1 + x2 + x3 exactly;
//   - a weight (an E2M1 value times its UE4M3 scale, at most 6 significant bits) is exactly a bf16;
//   - one output (slot, row) runs over segments of SEG = 16 steps of 16 inputs (the last one may be shorter): c1 = 0,
//     c23 = 0; at each step c1 = DPAS(c1, x1, w), c23 = DPAS(c23, x2, w), c23 = DPAS(c23, x3, w); at the segment's end
//     total = total + (c1 + c23), total starting at 0;
//   - DPAS tiles of 1, 2, 4 or 8 rows give each row the same bits (bench_xm1), so a slot's outputs do not depend on
//     the other slots of its tile.
// gate|up: H = act(gate total, up total) as SituOp::act; down: y[slot][row] = total.
//
// Layout: P = a tile's inputs in parts, [tile][3][16 slots][cols] bf16 (slots past the tile's count are zero); the
// gate|up kernel writes the down product's P (H in parts, [tile][3][16][nff]) itself.
#pragma once
#include "moe_group.hpp"
#include "planar.hpp"
#include "xlane.hpp"
#include <sycl/ext/oneapi/matrix/matrix.hpp>
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>

namespace ink::xm {
namespace jm = sycl::ext::oneapi::experimental::matrix;
using bf = sycl::ext::oneapi::bfloat16;
constexpr int SEG = 16; // steps of 16 inputs per segment

inline uint16_t bf_rn(float f) {
    const uint32_t u = sycl::bit_cast<uint32_t>(f);
    return (uint16_t)((u + 0x7fffu + ((u >> 16) & 1u)) >> 16);
}
inline float bf_f(uint16_t b) { return sycl::bit_cast<float>((uint32_t)b << 16); }
inline void split3(float x, uint16_t &a, uint16_t &b, uint16_t &c) {
    a = bf_rn(x);
    const float r1 = x - bf_f(a);
    b = bf_rn(r1);
    c = bf_rn(r1 - bf_f(b));
}

// super-tiles: up to SM consecutive tiles of one expert (moe_group's tiles are in ascending expert order)
struct Super {
    int32_t *t0 = nullptr, *n = nullptr, *count = nullptr;
    int sm = 0;
    void alloc(Device &d, int ne, int kmax, int sm_) {
        sm = sm_;
        const int b = bound(ne, kmax, sm);
        t0 = d.alloc<int32_t>(b); n = d.alloc<int32_t>(b); count = d.alloc<int32_t>(1);
    }
    static int bound(int ne, int kmax, int sm) { return ne + MoeGroups::max_tiles(ne, kmax) / sm; }
};
inline sycl::event super_tiles(sycl::queue &q, MoeGroups g, int ne, Super s) {
    constexpr int GW = 256;
    if (ne > GW) throw std::runtime_error("xm::super_tiles: too many experts");
    const int SMv = s.sm;
    return q.parallel_for(sycl::nd_range<1>(GW, GW), [=](sycl::nd_item<1> it) {
        const int e = (int)it.get_local_id(0);
        const int cnt = e < ne ? g.ecount[e] : 0, nt = (cnt + MOE_TS - 1) / MOE_TS, ns = (nt + SMv - 1) / SMv;
        const int t0 = sycl::exclusive_scan_over_group(it.get_group(), nt, sycl::plus<int>());
        const int s0 = sycl::exclusive_scan_over_group(it.get_group(), ns, sycl::plus<int>());
        const int tot = sycl::reduce_over_group(it.get_group(), ns, sycl::plus<int>());
        for (int j = 0; j < ns; ++j) { s.t0[s0 + j] = t0 + j * SMv; s.n[s0 + j] = sycl::min(SMv, nt - j * SMv); }
        if (e == 0) s.count[0] = tot;
    });
}

// P from x: row of slot s = s / xdiv (xdiv 0: s). Work-item = 8 columns of one row (two 16-byte loads, three 16-byte
// stores); cols % 8 == 0
inline sycl::event split_gather8(sycl::queue &q, MoeGroups g, int tiles, const float *x, int ldx, int xdiv, int cols, uint16_t *P) {
    constexpr int WG = 256;
    const int c8 = cols / 8;
    const size_t per = (size_t)16 * cols, n8 = (size_t)16 * c8;
    return q.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)tiles, (n8 + WG - 1) / WG * WG), sycl::range<2>(1, WG)),
                          [=](sycl::nd_item<2> it) {
        const int t = (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        const size_t i = it.get_global_id(1);
        if (i >= n8) return;
        const int r = (int)(i / c8), c = (int)(i % c8) * 8;
        sycl::float4 v0(0.0f), v1(0.0f);
        if (r < g.tile_n[t]) {
            const int s = g.slots[g.tile_s0[t] + r];
            const float *xr = x + (size_t)(xdiv ? s / xdiv : s) * ldx + c;
            v0 = *reinterpret_cast<const sycl::float4 *>(xr);
            v1 = *reinterpret_cast<const sycl::float4 *>(xr + 4);
        }
        const float v[8] = {v0.x(), v0.y(), v0.z(), v0.w(), v1.x(), v1.y(), v1.z(), v1.w()};
        sycl::vec<uint16_t, 8> a, b, d;
#pragma unroll
        for (int j = 0; j < 8; ++j) {
            uint16_t p0, p1, p2;
            split3(v[j], p0, p1, p2);
            a[j] = p0; b[j] = p1; d[j] = p2;
        }
        uint16_t *o = P + (size_t)t * 3 * per + (size_t)r * cols + c;
        *reinterpret_cast<sycl::vec<uint16_t, 8> *>(o) = a;
        *reinterpret_cast<sycl::vec<uint16_t, 8> *>(o + per) = b;
        *reinterpret_cast<sycl::vec<uint16_t, 8> *>(o + 2 * per) = d;
    });
}
inline sycl::event split_gather(sycl::queue &q, MoeGroups g, int tiles, const float *x, int ldx, int xdiv, int cols, uint16_t *P) {
    constexpr int WG = 256;
    const size_t per = (size_t)16 * cols;
    return q.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)tiles, (per + WG - 1) / WG * WG), sycl::range<2>(1, WG)),
                          [=](sycl::nd_item<2> it) {
        const int t = (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        const size_t i = it.get_global_id(1);
        if (i >= per) return;
        const int r = (int)(i / cols), c = (int)(i % cols);
        float v = 0.0f;
        if (r < g.tile_n[t]) {
            const int s = g.slots[g.tile_s0[t] + r];
            v = x[(size_t)(xdiv ? s / xdiv : s) * ldx + c];
        }
        uint16_t a, b, d;
        split3(v, a, b, d);
        uint16_t *o = P + (size_t)t * 3 * per + (size_t)r * cols + c;
        o[0] = a; o[per] = b; o[2 * per] = d;
    });
}

// one row's 16 values of step k (8 code bytes: value i < 8 = low nibble of byte i, 8 + i = its high nibble; one UE4M3
// scale byte) as 8 words of bf16 pairs (values 2j, 2j + 1) at o[j * os]: NVFP4P::pair's floats, exact, so their top
// 16 bits
inline void decode16(const uint8_t *row, int cols, int k, uint32_t *o, int os) {
    const sycl::vec<uint32_t, 2> cw = *reinterpret_cast<const sycl::vec<uint32_t, 2> *>(row + (size_t)8 * k);
    const float d = pl::ue4m3_bits(row[cols / 2 + k]) * 32768.0f;
    float v[16];
#pragma unroll
    for (int hh = 0; hh < 2; ++hh) { // bytes 4hh..4hh+3: low codes -> v[4hh + b], high -> v[8 + 4hh + b]
        const uint32_t x = cw[hh];
        const int j0 = 4 * hh;
        pl::NVFP4P::pair(x, 9, d, v[j0 + 0], v[j0 + 2]);
        pl::NVFP4P::pair(x, 5, d, v[8 + j0 + 0], v[8 + j0 + 2]);
        pl::NVFP4P::pair(x, 1, d, v[j0 + 1], v[j0 + 3]);
        pl::NVFP4P::pair(x, -3, d, v[8 + j0 + 1], v[8 + j0 + 3]);
    }
#pragma unroll
    for (int j = 0; j < 8; ++j)
        o[j * os] = (sycl::bit_cast<uint32_t>(v[2 * j]) >> 16) | (sycl::bit_cast<uint32_t>(v[2 * j + 1]) & 0xFFFF0000u);
}

// tile layout of an NVFP4 planar expert tensor (the same bytes): [expert][block of 16 rows][step k][144 bytes: row n's 8
// code bytes at 8n, its scale byte at 128 + n]. One sub-group reads a block's step with two contiguous loads.
constexpr int TB = 144;
inline void repack_tiles(sycl::queue &q, uint8_t *W, size_t rb, int rows, int cols, int ne, uint8_t *tmp) {
    const size_t es = rb * (size_t)rows;
    const int steps = cols / 16, nblk = rows / 16;
    if (rows % 16 || cols % 16 || rb != (size_t)cols / 2 + (size_t)cols / 16) throw std::runtime_error("xm::repack_tiles: shapes");
    for (int e = 0; e < ne; ++e) {
        uint8_t *we = W + (size_t)e * es;
        q.memcpy(tmp, we, es);
        q.parallel_for(sycl::range<2>((size_t)nblk * steps, 16), [=](sycl::id<2> i) {
            const int bk = (int)(i[0] / steps), k = (int)(i[0] % steps), n = (int)i[1];
            const uint8_t *row = tmp + (size_t)(bk * 16 + n) * rb;
            uint8_t *o = we + ((size_t)bk * steps + k) * TB;
            for (int b = 0; b < 8; ++b) o[8 * n + b] = row[8 * k + b];
            o[128 + n] = row[cols / 2 + k];
        });
    }
    q.wait();
}
struct Raw { uint64_t cw; uint32_t sc; };
inline Raw fetch16t(const uint8_t *tp, int ln) { return Raw{*reinterpret_cast<const uint64_t *>(tp + 8 * ln), tp[128 + ln]}; }
inline void decode_raw(const Raw &r, uint32_t *o, int os) {
    const uint32_t cw[2] = {(uint32_t)r.cw, (uint32_t)(r.cw >> 32)};
    const float d = pl::ue4m3_bits((uint8_t)r.sc) * 32768.0f;
    float v[16];
#pragma unroll
    for (int hh = 0; hh < 2; ++hh) {
        const uint32_t x = cw[hh];
        const int j0 = 4 * hh;
        pl::NVFP4P::pair(x, 9, d, v[j0 + 0], v[j0 + 2]);
        pl::NVFP4P::pair(x, 5, d, v[8 + j0 + 0], v[8 + j0 + 2]);
        pl::NVFP4P::pair(x, 1, d, v[j0 + 1], v[j0 + 3]);
        pl::NVFP4P::pair(x, -3, d, v[8 + j0 + 1], v[8 + j0 + 3]);
    }
#pragma unroll
    for (int j = 0; j < 8; ++j)
        o[j * os] = (sycl::bit_cast<uint32_t>(v[2 * j]) >> 16) | (sycl::bit_cast<uint32_t>(v[2 * j + 1]) & 0xFFFF0000u);
}
inline void decode16t(const uint8_t *tp, int ln, uint32_t *o, int os) { // decode16 from the tile layout
    const sycl::vec<uint32_t, 2> cw = *reinterpret_cast<const sycl::vec<uint32_t, 2> *>(tp + 8 * ln);
    const float d = pl::ue4m3_bits(tp[128 + ln]) * 32768.0f;
    float v[16];
#pragma unroll
    for (int hh = 0; hh < 2; ++hh) {
        const uint32_t x = cw[hh];
        const int j0 = 4 * hh;
        pl::NVFP4P::pair(x, 9, d, v[j0 + 0], v[j0 + 2]);
        pl::NVFP4P::pair(x, 5, d, v[8 + j0 + 0], v[8 + j0 + 2]);
        pl::NVFP4P::pair(x, 1, d, v[j0 + 1], v[j0 + 3]);
        pl::NVFP4P::pair(x, -3, d, v[8 + j0 + 1], v[8 + j0 + 3]);
    }
#pragma unroll
    for (int j = 0; j < 8; ++j)
        o[j * os] = (sycl::bit_cast<uint32_t>(v[2 * j]) >> 16) | (sycl::bit_cast<uint32_t>(v[2 * j + 1]) & 0xFFFF0000u);
}

struct ActOp { const float *escale; float beta, lb; };
inline float act(float g, float u, float s, bool sc, float beta, float lb) { // SituOp::act
    if (sc) { g = g * s; u = u * s; }
    const float a = (sycl::tanh(g * (1.0f / beta)) * beta) * (1.0f / (1.0f + sycl::exp(-g)));
    if (lb > 0.0f) u = sycl::tanh(u * (1.0f / lb)) * lb;
    return a * u;
}

// The product kernel. Work-group = SM x SR sub-groups: SM tiles of one super-tile x SR row blocks; a sub-group = one
// tile (16 slots, 2 DPAS row tiles) x one row block (2 B tiles of 16 rows: gate|up the same 16 rows of gate and up,
// down 32 consecutive rows). The work-group decodes its row blocks' weights for KC steps at a time into local memory
// (two buffers, one barrier per chunk), every sub-group reads them from there.
// MODE 0: gate|up, act, H in parts to Hp. MODE 1: down, y[slot][row]. MODE 2: gate|up sums to R[slot][2 nff] (tests).
// ABL (measurements only, wrong values): 1 no weight decode, 2 inputs loaded once per chunk, 4 no DPAS
template <int SM, int SR, int KC, int MODE, int ABL = 0, bool TL = false> struct XProd {
    static_assert(SEG % KC == 0, "chunks inside segments");
    const uint8_t *W; size_t rb, estride; int cols, nff;
    MoeGroups g; Super st;
    const uint16_t *P; ActOp op; uint16_t *Hp; float *Y; int ldy;
    sycl::local_accessor<bf, 1> bs; sycl::local_accessor<float, 1> stg;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<256>};
    }
    int rowbase(int rbk, int j) const { return MODE == 1 ? rbk * 32 + j * 16 : j * nff + rbk * 16; }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const {
        const int w = (int)it.get_group(0);
        if (w >= st.count[0]) return;
        const auto sg = it.get_sub_group();
        const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id(), li = (int)it.get_local_id(1);
        const int mt = sgi % SM, rbi = sgi / SM, rb0 = (int)it.get_group(1) * SR;
        const int t0 = st.t0[w], ntl = st.n[w], e = g.tile_exp[t0];
        const int t = t0 + mt, cnt = mt < ntl ? g.tile_n[t] : 0, nm = cnt > 8 ? 2 : cnt > 0 ? 1 : 0;
        const int steps = cols / 16, nch = (steps + KC - 1) / KC;
        const uint8_t *We = W + (size_t)e * estride;
        uint32_t *bw = reinterpret_cast<uint32_t *>(&bs[0]);
        constexpr int TILE = 128, BUF = SR * 2 * KC * TILE, NW = SM * SR * 16, U = SR * 2 * KC * 16;
        auto decode = [&](int c, int buf) {
            if (ABL & 1) return;
            if constexpr (TL) { // one sub-group per (row block, matrix, step): lane = row
                for (int u = sgi; u < SR * 2 * KC; u += SM * SR) {
                    const int kk = u % KC, j = (u / KC) % 2, r = u / (2 * KC), k = c * KC + kk, rbk = rb0 + r;
                    const int blk = MODE == 1 ? rbk * 2 + j : j * (nff / 16) + rbk;
                    if (k < steps) decode16t(We + ((size_t)blk * steps + k) * TB, ln, bw + buf * BUF + ((r * 2 + j) * KC + kk) * TILE + ln, 16);
                }
                return;
            }
            for (int u = li; u < U; u += NW) {
                const int n = u % 16, kk = (u / 16) % KC, j = (u / (16 * KC)) % 2, r = u / (32 * KC), k = c * KC + kk;
                if (k < steps) decode16(We + (size_t)(rowbase(rb0 + r, j) + n) * rb, cols, k, bw + buf * BUF + ((r * 2 + j) * KC + kk) * TILE + n, 16);
            }
        };
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, 8, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        C c1[2][2], c23[2][2], tot[2][2];
#pragma unroll
        for (int j = 0; j < 2; ++j)
#pragma unroll
            for (int m = 0; m < 2; ++m) jm::joint_matrix_fill(sg, tot[j][m], 0.0f);
        auto lp = [](auto &acc, size_t off) { return acc.template get_multi_ptr<sycl::access::decorated::no>() + off; };
        const size_t per = (size_t)16 * cols;
        const bf *Pt = reinterpret_cast<const bf *>(P) + (size_t)t * 3 * per;
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        // TL: each sub-group's units (row block, matrix, step) of a chunk; their bytes are read two chunks ahead
        constexpr int NU = (2 * KC + SM - 1) / SM;
        Raw raw[NU];
        auto unit = [&](int i, int c, int &k, int &slot) -> const uint8_t * {
            const int u = sgi + i * SM * SR;
            if (u >= SR * 2 * KC) return nullptr;
            const int kk = u % KC, j = (u / KC) % 2, r = u / (2 * KC), rbk = rb0 + r;
            const int blk = MODE == 1 ? rbk * 2 + j : j * (nff / 16) + rbk;
            k = c * KC + kk;
            slot = ((r * 2 + j) * KC + kk) * TILE;
            return k < steps ? We + ((size_t)blk * steps + k) * TB : nullptr;
        };
        auto fetch = [&](int c) {
#pragma unroll
            for (int i = 0; i < NU; ++i) { int k, sl; if (const uint8_t *tp = unit(i, c, k, sl)) raw[i] = fetch16t(tp, ln); }
        };
        auto put = [&](int c, int buf) {
#pragma unroll
            for (int i = 0; i < NU; ++i) { int k, sl; if (unit(i, c, k, sl)) decode_raw(raw[i], bw + buf * BUF + sl + ln, 16); }
        };
        // TL: the next chunk's bytes are read before this chunk's products and decoded after them
        if constexpr (TL && !(ABL & 1)) { fetch(0); put(0, 0); }
        else decode(0, 0);
        sycl::group_barrier(it.get_group());
        for (int c = 0; c < nch; ++c) {
            const int buf = c & 1;
            if constexpr (TL && !(ABL & 1)) { if (c + 1 < nch) fetch(c + 1); }
            else if (c + 1 < nch) decode(c + 1, buf ^ 1);
            if (nm > 0) {
#pragma unroll
                for (int kk = 0; kk < KC; ++kk) {
                    const int k = c * KC + kk;
                    if (k < steps) {
                        if (k % SEG == 0) {
#pragma unroll
                            for (int j = 0; j < 2; ++j)
#pragma unroll
                                for (int m = 0; m < 2; ++m) { jm::joint_matrix_fill(sg, c1[j][m], 0.0f); jm::joint_matrix_fill(sg, c23[j][m], 0.0f); }
                        }
                        B b[2];
#pragma unroll
                        for (int j = 0; j < 2; ++j)
                            jm::joint_matrix_load(sg, b[j], lp(bs, (size_t)buf * BUF * 2 + (size_t)((rbi * 2 + j) * KC + kk) * TILE * 2), 32);
#pragma unroll
                        for (int m = 0; m < 2; ++m) {
                            if (m < nm) {
                                A a0, a1, a2;
                                const bf *pa = Pt + (size_t)(m * 8) * cols + (size_t)(ABL & 2 ? c * KC : k) * 16;
                                jm::joint_matrix_load(sg, a0, gp(pa), cols);
                                jm::joint_matrix_load(sg, a1, gp(pa + per), cols);
                                jm::joint_matrix_load(sg, a2, gp(pa + 2 * per), cols);
#pragma unroll
                                for (int j = 0; j < 2; ++j) if constexpr (!(ABL & 4)) {
                                    jm::joint_matrix_mad(sg, c1[j][m], a0, b[j], c1[j][m]);
                                    jm::joint_matrix_mad(sg, c23[j][m], a1, b[j], c23[j][m]);
                                    jm::joint_matrix_mad(sg, c23[j][m], a2, b[j], c23[j][m]);
                                }
                            }
                        }
                        if (k % SEG == SEG - 1 || k == steps - 1) {
#pragma unroll
                            for (int j = 0; j < 2; ++j)
#pragma unroll
                                for (int m = 0; m < 2; ++m)
                                    if (m < nm) {
                                        jm::joint_matrix_apply(sg, c1[j][m], c23[j][m], [](float &x, float &y) { x = x + y; });
                                        jm::joint_matrix_apply(sg, tot[j][m], c1[j][m], [](float &x, float &y) { x = x + y; });
                                    }
                        }
                    }
                }
            }
            if constexpr (TL && !(ABL & 1)) { if (c + 1 < nch) put(c + 1, buf ^ 1); }
            sycl::group_barrier(it.get_group());
        }
        if (mt >= ntl) return;
        float *sp = &stg[0] + (size_t)sgi * 256; // 16 slots x 16 rows
        auto lps = [&](int off) { return stg.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)sgi * 256 + off; };
        const int rbk = rb0 + rbi;
        if constexpr (MODE == 0) {
            const bool sc = op.escale != nullptr;
            const float s = sc ? op.escale[e] : 1.0f, beta = op.beta, lb = op.lb;
#pragma unroll
            for (int m = 0; m < 2; ++m)
                if (m < nm) {
                    jm::joint_matrix_apply(sg, tot[0][m], tot[1][m], [=](float &x, float &y) { x = act(x, y, s, sc, beta, lb); });
                    jm::joint_matrix_store(sg, tot[0][m], lps(m * 128), 16, jm::layout::row_major);
                }
            sycl::group_barrier(sg);
            const size_t ph = (size_t)16 * nff;
            uint16_t *ho = Hp + (size_t)t * 3 * ph + rbk * 16 + ln;
            for (int r = 0; r < 16; ++r) {
                const float v = r < cnt ? sp[r * 16 + ln] : 0.0f;
                uint16_t a, b, d;
                split3(v, a, b, d);
                ho[(size_t)r * nff] = a; ho[ph + (size_t)r * nff] = b; ho[2 * ph + (size_t)r * nff] = d;
            }
        } else {
#pragma unroll
            for (int j = 0; j < 2; ++j) {
#pragma unroll
                for (int m = 0; m < 2; ++m)
                    if (m < nm) jm::joint_matrix_store(sg, tot[j][m], lps(m * 128), 16, jm::layout::row_major);
                sycl::group_barrier(sg);
                const int row = rowbase(rbk, j) + ln;
                for (int r = 0; r < cnt; ++r) {
                    const int slot = g.slots[g.tile_s0[t] + r];
                    Y[(size_t)slot * ldy + row] = sp[r * 16 + ln];
                }
                sycl::group_barrier(sg);
            }
        }
    }
};

template <int SM, int SR, int KC, int MODE, int ABL = 0, bool TL = false>
inline sycl::event prod(sycl::queue &q, const uint8_t *W, size_t rb, size_t estride, int cols, int nff, int nrb, MoeGroups g, Super st,
                        int stb, const uint16_t *P, ActOp op, uint16_t *Hp, float *Y, int ldy) {
    if (cols % 16 || nrb % SR || st.sm != SM) throw std::runtime_error("xm::prod: shapes");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<bf, 1> bs(2 * SR * 2 * KC * 256, h);
        sycl::local_accessor<float, 1> stg(SM * SR * 256, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)stb, (size_t)(nrb / SR) * SM * SR * 16), sycl::range<2>(1, SM * SR * 16)),
                       XProd<SM, SR, KC, MODE, ABL, TL>{W, rb, estride, cols, nff, g, st, P, op, Hp, Y, ldy, bs, stg});
    });
}

// XProd2: XProd on the tile layout with the loops arranged for the compiler: segments outermost (the sums zeroed and
// folded once per segment, outside the chunk loop), no tests inside a chunk's products, NM row tiles per sub-group
// fixed (NM = 2: 16 slots; a tile with fewer computes zero rows). steps % KC == 0. The same arithmetic, so the same
// bits as XProd.
template <int SM, int SR, int KC, int MODE, int NM = 2> struct XProd2 {
    static_assert(SEG % KC == 0 && (2 * KC) % SM == 0, "XProd2: shapes");
    const uint8_t *W; size_t estride; int cols, nff;
    MoeGroups g; Super st;
    const uint16_t *P; ActOp op; uint16_t *Hp; float *Y; int ldy;
    sycl::local_accessor<bf, 1> bs; sycl::local_accessor<float, 1> stg;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<256>};
    }
    int blkof(int rbk, int j) const { return MODE == 1 ? rbk * 2 + j : j * (nff / 16) + rbk; }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const {
        const int w = (int)it.get_group(0);
        if (w >= st.count[0]) return;
        const auto sg = it.get_sub_group();
        const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
        const int mt = sgi % SM, rbi = sgi / SM, rb0 = (int)it.get_group(1) * SR;
        const int t0 = st.t0[w], ntl = st.n[w], e = g.tile_exp[t0];
        const int t = t0 + mt;
        const bool active = mt < ntl;
        const int cnt = active ? g.tile_n[t] : 0;
        const int steps = cols / 16, nch = steps / KC;
        const uint8_t *We = W + (size_t)e * estride;
        uint32_t *bw = reinterpret_cast<uint32_t *>(&bs[0]);
        constexpr int TILE = 128, BUF = SR * 2 * KC * TILE, NU = 2 * KC / SM;
        Raw raw[NU];
        auto fetch = [&](int c) {
#pragma unroll
            for (int i = 0; i < NU; ++i) {
                const int u = sgi + i * SM * SR, kk = u % KC, j = (u / KC) % 2, r = u / (2 * KC);
                raw[i] = fetch16t(We + ((size_t)blkof(rb0 + r, j) * steps + c * KC + kk) * TB, ln);
            }
        };
        auto put = [&](int buf) {
#pragma unroll
            for (int i = 0; i < NU; ++i) {
                const int u = sgi + i * SM * SR, kk = u % KC, j = (u / KC) % 2, r = u / (2 * KC);
                decode_raw(raw[i], bw + buf * BUF + ((r * 2 + j) * KC + kk) * TILE + ln, 16);
            }
        };
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, 8, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, 8, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        C c1[2][NM], c23[2][NM], tot[2][NM];
#pragma unroll
        for (int j = 0; j < 2; ++j)
#pragma unroll
            for (int m = 0; m < NM; ++m) jm::joint_matrix_fill(sg, tot[j][m], 0.0f);
        auto lp = [](auto &acc, size_t off) { return acc.template get_multi_ptr<sycl::access::decorated::no>() + off; };
        const size_t per = (size_t)16 * cols;
        const bf *Pt = reinterpret_cast<const bf *>(P) + (size_t)t * 3 * per;
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        fetch(0);
        put(0);
        sycl::group_barrier(it.get_group());
        int c = 0;
        for (int s0 = 0; s0 < steps; s0 += SEG) {
            const int ce = sycl::min(steps, s0 + SEG) / KC;
#pragma unroll
            for (int j = 0; j < 2; ++j)
#pragma unroll
                for (int m = 0; m < NM; ++m) { jm::joint_matrix_fill(sg, c1[j][m], 0.0f); jm::joint_matrix_fill(sg, c23[j][m], 0.0f); }
            for (; c < ce; ++c) {
                const int buf = c & 1;
                if (c + 1 < nch) fetch(c + 1);
                if (active) {
#pragma unroll
                    for (int kk = 0; kk < KC; ++kk) {
                        const int k = c * KC + kk;
                        B b[2];
#pragma unroll
                        for (int j = 0; j < 2; ++j)
                            jm::joint_matrix_load(sg, b[j], lp(bs, (size_t)buf * BUF * 2 + (size_t)((rbi * 2 + j) * KC + kk) * TILE * 2), 32);
#pragma unroll
                        for (int m = 0; m < NM; ++m) {
                            A a0, a1, a2;
                            const bf *pa = Pt + (size_t)(m * 8) * cols + (size_t)k * 16;
                            jm::joint_matrix_load(sg, a0, gp(pa), cols);
                            jm::joint_matrix_load(sg, a1, gp(pa + per), cols);
                            jm::joint_matrix_load(sg, a2, gp(pa + 2 * per), cols);
#pragma unroll
                            for (int j = 0; j < 2; ++j) {
                                jm::joint_matrix_mad(sg, c1[j][m], a0, b[j], c1[j][m]);
                                jm::joint_matrix_mad(sg, c23[j][m], a1, b[j], c23[j][m]);
                                jm::joint_matrix_mad(sg, c23[j][m], a2, b[j], c23[j][m]);
                            }
                        }
                    }
                }
                if (c + 1 < nch) put(buf ^ 1);
                sycl::group_barrier(it.get_group());
            }
#pragma unroll
            for (int j = 0; j < 2; ++j)
#pragma unroll
                for (int m = 0; m < NM; ++m) {
                    jm::joint_matrix_apply(sg, c1[j][m], c23[j][m], [](float &x, float &y) { x = x + y; });
                    jm::joint_matrix_apply(sg, tot[j][m], c1[j][m], [](float &x, float &y) { x = x + y; });
                }
        }
        if (!active) return;
        float *sp = &stg[0] + (size_t)sgi * 256;
        auto lps = [&](int off) { return stg.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)sgi * 256 + off; };
        const int rbk = rb0 + rbi;
        if constexpr (MODE == 0) {
            const bool sc = op.escale != nullptr;
            const float sv = sc ? op.escale[e] : 1.0f, beta = op.beta, lb = op.lb;
#pragma unroll
            for (int m = 0; m < NM; ++m) {
                jm::joint_matrix_apply(sg, tot[0][m], tot[1][m], [=](float &x, float &y) { x = act(x, y, sv, sc, beta, lb); });
                jm::joint_matrix_store(sg, tot[0][m], lps(m * 128), 16, jm::layout::row_major);
            }
            sycl::group_barrier(sg);
            const size_t ph = (size_t)16 * nff;
            uint16_t *ho = Hp + (size_t)t * 3 * ph + rbk * 16 + ln;
            for (int r = 0; r < 16; ++r) {
                const float v = r < cnt ? sp[r * 16 + ln] : 0.0f;
                uint16_t a, b, d;
                split3(v, a, b, d);
                ho[(size_t)r * nff] = a; ho[ph + (size_t)r * nff] = b; ho[2 * ph + (size_t)r * nff] = d;
            }
        } else {
#pragma unroll
            for (int j = 0; j < 2; ++j) {
#pragma unroll
                for (int m = 0; m < NM; ++m) jm::joint_matrix_store(sg, tot[j][m], lps(m * 128), 16, jm::layout::row_major);
                sycl::group_barrier(sg);
                const int row = (MODE == 1 ? rbk * 32 + j * 16 : j * nff + rbk * 16) + ln;
                for (int r = 0; r < cnt; ++r) {
                    const int slot = g.slots[g.tile_s0[t] + r];
                    Y[(size_t)slot * ldy + row] = sp[r * 16 + ln];
                }
                sycl::group_barrier(sg);
            }
        }
    }
};

template <int SM, int SR, int KC, int MODE, int NM = 2>
inline sycl::event prod2(sycl::queue &q, const uint8_t *W, size_t estride, int cols, int nff, int nrb, MoeGroups g, Super st, int stb,
                         const uint16_t *P, ActOp op, uint16_t *Hp, float *Y, int ldy) {
    if (cols % (16 * KC) || nrb % SR || st.sm != SM) throw std::runtime_error("xm::prod2: shapes");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<bf, 1> bs(2 * SR * 2 * KC * 256, h);
        sycl::local_accessor<float, 1> stg(SM * SR * 256, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)stb, (size_t)(nrb / SR) * SM * SR * 16), sycl::range<2>(1, SM * SR * 16)),
                       XProd2<SM, SR, KC, MODE, NM>{W, estride, cols, nff, g, st, P, op, Hp, Y, ldy, bs, stg});
    });
}

// ---- steps of at most 8 tokens: tiles of at most M slots (M = 1, 2, 4, 8 rows; DPAS rows do not depend on each
// other, so any M gives XProd2's bits). One sub-group per (tile, row block, segment): its segment sums
// s = c1 + c23 go to S[(t * nseg + seg) * M + r][col]; small_fold adds a tile's segments in order (XProd2's totals)
// and finishes: MODE 0 act and H in parts, MODE 1 / 2 y[slot][col]. The inputs of tile t, part p, row r are at
// P + t * pt + p * pp + r * cols (pt = 0: every tile reads the same rows, one token).
template <int M, int MODE, int SR> struct XSmall {
    const uint8_t *W; size_t estride; int cols, nff, ncol;
    MoeGroups g; const uint16_t *P; size_t pt, pp; float *S;
    sycl::local_accessor<bf, 1> bs;
    int blkof(int rbk, int j) const { return MODE == 1 ? rbk * 2 + j : j * (nff / 16) + rbk; }
    int colof(int rbk, int j) const { return MODE == 1 ? rbk * 32 + j * 16 : j * nff + rbk * 16; }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const {
        const int t = (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        const auto sg = it.get_sub_group();
        const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
        const int steps = cols / 16, nseg = (steps + SEG - 1) / SEG;
        const int gi = (int)it.get_group(1), seg = gi % nseg, rbk = (gi / nseg) * SR + sgi;
        const uint8_t *We = W + (size_t)g.tile_exp[t] * estride;
        const uint8_t *w0 = We + (size_t)blkof(rbk, 0) * steps * TB, *w1 = We + (size_t)blkof(rbk, 1) * steps * TB;
        const bf *Pt = reinterpret_cast<const bf *>(P) + (size_t)t * pt;
        uint32_t *bw = reinterpret_cast<uint32_t *>(&bs[0]) + sgi * 512;
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, M, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, M, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        C c1[2], c23[2];
#pragma unroll
        for (int j = 0; j < 2; ++j) { jm::joint_matrix_fill(sg, c1[j], 0.0f); jm::joint_matrix_fill(sg, c23[j], 0.0f); }
        auto lp = [&](size_t off) { return bs.template get_multi_ptr<sycl::access::decorated::no>() + off; };
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        const int k0 = seg * SEG, k1 = sycl::min(steps, k0 + SEG);
        for (int k = k0; k < k1; ++k) {
            const int buf = k & 1;
            const Raw r0 = fetch16t(w0 + (size_t)k * TB, ln), r1 = fetch16t(w1 + (size_t)k * TB, ln);
            decode_raw(r0, bw + buf * 256 + ln, 16);
            decode_raw(r1, bw + buf * 256 + 128 + ln, 16);
            sycl::group_barrier(sg);
            B b0, b1;
            jm::joint_matrix_load(sg, b0, lp((size_t)sgi * 1024 + buf * 512), 32);
            jm::joint_matrix_load(sg, b1, lp((size_t)sgi * 1024 + buf * 512 + 256), 32);
            A a0, a1, a2;
            const bf *pa = Pt + (size_t)k * 16;
            jm::joint_matrix_load(sg, a0, gp(pa), cols);
            jm::joint_matrix_load(sg, a1, gp(pa + pp), cols);
            jm::joint_matrix_load(sg, a2, gp(pa + 2 * pp), cols);
            jm::joint_matrix_mad(sg, c1[0], a0, b0, c1[0]);
            jm::joint_matrix_mad(sg, c23[0], a1, b0, c23[0]);
            jm::joint_matrix_mad(sg, c23[0], a2, b0, c23[0]);
            jm::joint_matrix_mad(sg, c1[1], a0, b1, c1[1]);
            jm::joint_matrix_mad(sg, c23[1], a1, b1, c23[1]);
            jm::joint_matrix_mad(sg, c23[1], a2, b1, c23[1]);
        }
        float *so = S + (size_t)(t * nseg + seg) * M * ncol;
#pragma unroll
        for (int j = 0; j < 2; ++j) {
            jm::joint_matrix_apply(sg, c1[j], c23[j], [](float &x, float &y) { x = x + y; });
            jm::joint_matrix_store(sg, c1[j], sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(so + colof(rbk, j)),
                                   ncol, jm::layout::row_major);
        }
    }
};
template <int M, int MODE, int SR = 4>
inline sycl::event small_prod(sycl::queue &q, const uint8_t *W, size_t estride, int cols, int nff, int ncol, int nrb, MoeGroups g, int tiles,
                              const uint16_t *P, size_t pt, size_t pp, float *S) {
    const int nseg = (cols / 16 + SEG - 1) / SEG;
    if (cols % 16 || nrb % SR) throw std::runtime_error("xm::small_prod: shapes");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<bf, 1> bs(SR * 1024, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)tiles, (size_t)(nrb / SR) * nseg * SR * 16), sycl::range<2>(1, SR * 16)),
                       XSmall<M, MODE, SR>{W, estride, cols, nff, ncol, g, P, pt, pp, S, bs});
    });
}
// gate|up: H in parts for rows r < mr of each tile (zeros at r >= the tile's count): Hp[t][p][r][i]
inline sycl::event small_fold_act(sycl::queue &q, MoeGroups g, int tiles, int nseg, int m, const float *S, int nff, ActOp op, int mr, uint16_t *Hp) {
    return q.parallel_for(sycl::range<3>((size_t)tiles, (size_t)mr, (size_t)nff), [=](sycl::id<3> id) {
        const int t = (int)id[0], r = (int)id[1], i = (int)id[2];
        if (t >= g.ntiles[0]) return;
        float v = 0.0f;
        if (r < g.tile_n[t]) {
            float tg = 0.0f, tu = 0.0f;
            for (int s = 0; s < nseg; ++s) {
                const float *row = S + ((size_t)(t * nseg + s) * m + r) * 2 * nff;
                tg = tg + row[i];
                tu = tu + row[nff + i];
            }
            const bool sc = op.escale != nullptr;
            v = act(tg, tu, sc ? op.escale[g.tile_exp[t]] : 1.0f, sc, op.beta, op.lb);
        }
        uint16_t a, b, d;
        split3(v, a, b, d);
        const size_t ph = (size_t)mr * nff;
        uint16_t *o = Hp + (size_t)t * 3 * ph + (size_t)r * nff + i;
        o[0] = a; o[ph] = b; o[2 * ph] = d;
    });
}
// y[slot][col] = the sum of a tile's segments in order
inline sycl::event small_fold_out(sycl::queue &q, MoeGroups g, int tiles, int nseg, int m, const float *S, int ncol, float *Y, int ldy) {
    return q.parallel_for(sycl::range<3>((size_t)tiles, (size_t)m, (size_t)ncol), [=](sycl::id<3> id) {
        const int t = (int)id[0], r = (int)id[1], c = (int)id[2];
        if (t >= g.ntiles[0] || r >= g.tile_n[t]) return;
        float tot = 0.0f;
        for (int s = 0; s < nseg; ++s) tot = tot + S[((size_t)(t * nseg + s) * m + r) * ncol + c];
        Y[(size_t)g.slots[g.tile_s0[t] + r] * ldy + c] = tot;
    });
}
// P for one token from its lane-order row (xlane.hpp)
inline sycl::event split_row_l(sycl::queue &q, const float *xl, int cols, uint16_t *P) {
    return q.parallel_for(sycl::range<1>((size_t)cols), [=](sycl::id<1> i) {
        uint16_t a, b, d;
        split3(xl[xlane_at((int)i[0])], a, b, d);
        P[i] = a; P[cols + i] = b; P[2 * (size_t)cols + i] = d;
    });
}
// P for one token: its row split once (every tile reads it: pt = 0, pp = cols)
inline sycl::event split_row(sycl::queue &q, const float *x, int cols, uint16_t *P) {
    return q.parallel_for(sycl::range<1>((size_t)cols), [=](sycl::id<1> i) {
        uint16_t a, b, d;
        split3(x[i], a, b, d);
        P[i] = a; P[cols + i] = b; P[2 * (size_t)cols + i] = d;
    });
}

} // namespace ink::xm
