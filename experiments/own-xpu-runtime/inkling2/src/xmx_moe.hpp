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
#include "bfsplit.hpp"
#include <sycl/ext/oneapi/experimental/prefetch.hpp>
#include <sycl/ext/oneapi/matrix/matrix.hpp>
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>

namespace ink::xm {
namespace jm = sycl::ext::oneapi::experimental::matrix;
using bf = sycl::ext::oneapi::bfloat16;
constexpr int SEG = 16; // steps of 16 inputs per segment

// bf_rn, bf_f, split3: bfsplit.hpp

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
// decode_raw with each half converted from its place in the word (no unpacking moves); the same values
inline void pair16(uint32_t w, int sh, float d, float &a, float &b) {
    const uint32_t m = sh >= 0 ? (w << sh) : (w >> -sh);
    const uint32_t s = sh + 3 >= 0 ? (w << (sh + 3)) : (w >> -(sh + 3));
    const uint32_t bits = (m & 0x0E000E00u) | (s & 0x80008000u);
    a = (float)sycl::bit_cast<sycl::half>((uint16_t)bits) * d;
    b = (float)sycl::bit_cast<sycl::half>((uint16_t)(bits >> 16)) * d;
}
inline void decode_raw16(const Raw &r, uint32_t *o, int os) {
    const uint32_t cw[2] = {(uint32_t)r.cw, (uint32_t)(r.cw >> 32)};
    const float d = pl::ue4m3_bits((uint8_t)r.sc) * 32768.0f;
    float v[16];
#pragma unroll
    for (int hh = 0; hh < 2; ++hh) {
        const uint32_t x = cw[hh];
        const int j0 = 4 * hh;
        pair16(x, 9, d, v[j0 + 0], v[j0 + 2]);
        pair16(x, 5, d, v[8 + j0 + 0], v[8 + j0 + 2]);
        pair16(x, 1, d, v[j0 + 1], v[j0 + 3]);
        pair16(x, -3, d, v[8 + j0 + 1], v[8 + j0 + 3]);
    }
#pragma unroll
    for (int j = 0; j < 8; ++j)
        o[j * os] = (sycl::bit_cast<uint32_t>(v[2 * j]) >> 16) | (sycl::bit_cast<uint32_t>(v[2 * j + 1]) & 0xFFFF0000u);
}
// decode_raw's 16 values in k order (lane n = column n of the B tile), not packed
inline void decode_vals(const Raw &r, float *v) {
    const uint32_t cw[2] = {(uint32_t)r.cw, (uint32_t)(r.cw >> 32)};
    const float d = pl::ue4m3_bits((uint8_t)r.sc) * 32768.0f;
#pragma unroll
    for (int hh = 0; hh < 2; ++hh) {
        const uint32_t x = cw[hh];
        const int j0 = 4 * hh;
        pl::NVFP4P::pair(x, 9, d, v[j0 + 0], v[j0 + 2]);
        pl::NVFP4P::pair(x, 5, d, v[8 + j0 + 0], v[8 + j0 + 2]);
        pl::NVFP4P::pair(x, 1, d, v[j0 + 1], v[j0 + 3]);
        pl::NVFP4P::pair(x, -3, d, v[8 + j0 + 1], v[8 + j0 + 3]);
    }
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
// ABL (timing only, wrong values): 1 no weight decode, 2 inputs loaded once per chunk, 4 no DPAS, 8 weight tiles
// loaded once per chunk
template <int SM, int SR, int KC, int MODE, int NM = 2, int ABL = 0> struct XProd2 {
    static_assert(SEG % KC == 0 && (2 * KC) % SM == 0, "XProd2: shapes");
    const uint8_t *W; size_t estride; int cols, nff;
    MoeGroups g; Super st;
    const uint16_t *P; ActOp op; uint16_t *Hp; float *Y; int ldy;
    sycl::local_accessor<bf, 1> bs;
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
                if constexpr (ABL == 0) {
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
                } else {
                if constexpr (!(ABL & 1)) { if (c + 1 < nch) fetch(c + 1); }
                if (active) {
                    B b[2];
                    A a0[NM], a1[NM], a2[NM];
#pragma unroll
                    for (int kk = 0; kk < KC; ++kk) {
                        const int k = c * KC + kk;
                        if (!(ABL & 8) || kk == 0)
#pragma unroll
                            for (int j = 0; j < 2; ++j)
                                jm::joint_matrix_load(sg, b[j], lp(bs, (size_t)buf * BUF * 2 + (size_t)((rbi * 2 + j) * KC + kk) * TILE * 2), 32);
#pragma unroll
                        for (int m = 0; m < NM; ++m) {
                            if (!(ABL & 2) || kk == 0) {
                                const bf *pa = Pt + (size_t)(m * 8) * cols + (size_t)k * 16;
                                jm::joint_matrix_load(sg, a0[m], gp(pa), cols);
                                jm::joint_matrix_load(sg, a1[m], gp(pa + per), cols);
                                jm::joint_matrix_load(sg, a2[m], gp(pa + 2 * per), cols);
                            }
                            if constexpr (!(ABL & 4))
#pragma unroll
                                for (int j = 0; j < 2; ++j) {
                                    jm::joint_matrix_mad(sg, c1[j][m], a0[m], b[j], c1[j][m]);
                                    jm::joint_matrix_mad(sg, c23[j][m], a1[m], b[j], c23[j][m]);
                                    jm::joint_matrix_mad(sg, c23[j][m], a2[m], b[j], c23[j][m]);
                                }
                        }
                    }
                }
                if constexpr (!(ABL & 1)) { if (c + 1 < nch) put(buf ^ 1); }
                }
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
        // The final chunk barrier above ends every read of bs. Reuse its first SM*SR*256 floats for the epilogue;
        // (2*KC) % SM == 0 implies that region is large enough. This saves a separate 16 KiB accessor at 4,4,4.
        float *sp = reinterpret_cast<float *>(&bs[0]) + (size_t)sgi * 256;
        auto lps = [&](int off) {
            return sycl::address_space_cast<sycl::access::address_space::local_space, sycl::access::decorated::no>(sp + off);
        };
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

template <int SM, int SR, int KC, int MODE, int NM = 2, int ABL = 0>
inline sycl::event prod2(sycl::queue &q, const uint8_t *W, size_t estride, int cols, int nff, int nrb, MoeGroups g, Super st, int stb,
                         const uint16_t *P, ActOp op, uint16_t *Hp, float *Y, int ldy) {
    if (cols % (16 * KC) || nrb % SR || st.sm != SM) throw std::runtime_error("xm::prod2: shapes");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<bf, 1> bs(2 * SR * 2 * KC * 256, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)stb, (size_t)(nrb / SR) * SM * SR * 16), sycl::range<2>(1, SM * SR * 16)),
                       XProd2<SM, SR, KC, MODE, NM, ABL>{W, estride, cols, nff, g, st, P, op, Hp, Y, ldy, bs});
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
// Steps of 1-8 tokens, second form: one work-group per (tile, block of 16 rows), one sub-group per segment. Each
// sub-group fetches its segment's weights for both B tiles PF steps ahead into registers, decodes step by step into
// local memory, runs the tile's rows with 1, 2, 4 or 8-row tiles by the tile's count (rows are independent: the bits
// do not depend on it) and stores its segment sum in local memory; then the work-group adds the segments in order (as
// small_fold_*: from 0) and writes H in parts (MODE 0: act, split) or y (MODE 1).
// Inputs: rows by the group's sorted position, P[p][tile_s0[t] + r][cols] (part stride pp; rows past a tile's count
// belong to the next tile or the padding and only feed rows that are not stored), or with XIN (one token) the one row
// x (lane order when xlo) split in the kernel. H goes to Hp[p][tile_s0[t] + r][nff] (part stride hpp).
// ABL (measurements only, wrong values): 1 no fold (no work-group barrier), 2 no weight decode, 4 no DPAS, 8 no input split
template <int MMAX, int MODE, bool XIN, int PF, int GRF, int ABL = 0> struct XSmall2 {
    const uint8_t *W; size_t estride; int cols, nff;
    MoeGroups g; const uint16_t *P; size_t pp; const float *x; bool xlo;
    ActOp op; uint16_t *Hp; size_t hpp; float *Y; int ldy;
    sycl::local_accessor<bf, 1> bs, as;
    sycl::local_accessor<float, 1> st;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<GRF>};
    }
    // PF steps per pass (unrolled), a runtime loop over the segment's ns / PF passes; the next pass's weights are
    // fetched before this pass's work (the last pass fetches its own again: no branch near the accumulators)
    template <int M>
    void body(sycl::sub_group sg, int sgi, int ln, const uint8_t *w0, const uint8_t *w1, int k0, int ns, size_t row0) const {
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, M, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, M, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        Raw r0[PF], r1[PF];
#pragma unroll
        for (int i = 0; i < PF; ++i) { r0[i] = fetch16t(w0 + (size_t)(k0 + i) * TB, ln); r1[i] = fetch16t(w1 + (size_t)(k0 + i) * TB, ln); }
        C c1[2], c23[2];
#pragma unroll
        for (int j = 0; j < 2; ++j) { jm::joint_matrix_fill(sg, c1[j], 0.0f); jm::joint_matrix_fill(sg, c23[j], 0.0f); }
        uint32_t *bw = reinterpret_cast<uint32_t *>(&bs[0]) + sgi * 512;
        auto lb = [&](size_t off) { return bs.template get_multi_ptr<sycl::access::decorated::no>() + off; };
        auto la = [&](size_t off) { return as.template get_multi_ptr<sycl::access::decorated::no>() + off; };
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        const bf *pa = XIN ? nullptr : reinterpret_cast<const bf *>(P) + row0 * cols + (size_t)k0 * 16;
        for (int b = 0; b < ns; b += PF) {
            Raw n0[PF], n1[PF];
            const int kn = k0 + sycl::min(b + PF, ns - PF);
#pragma unroll
            for (int i = 0; i < PF; ++i) { n0[i] = fetch16t(w0 + (size_t)(kn + i) * TB, ln); n1[i] = fetch16t(w1 + (size_t)(kn + i) * TB, ln); }
#pragma unroll
            for (int i = 0; i < PF; ++i) {
                const int buf = i & 1, kk = b + i;
                if constexpr (ABL & 2) {
                    bw[buf * 256 + ln] = (uint32_t)r0[i].cw ^ r0[i].sc;
                    bw[buf * 256 + 128 + ln] = (uint32_t)r1[i].cw ^ r1[i].sc;
                } else {
                    decode_raw(r0[i], bw + buf * 256 + ln, 16);
                    decode_raw(r1[i], bw + buf * 256 + 128 + ln, 16);
                }
                sycl::group_barrier(sg);
                B b0, b1;
                jm::joint_matrix_load(sg, b0, lb((size_t)sgi * 1024 + buf * 512), 32);
                jm::joint_matrix_load(sg, b1, lb((size_t)sgi * 1024 + buf * 512 + 256), 32);
                A x0, x1, x2;
                if constexpr (XIN) {
                    jm::joint_matrix_load(sg, x0, la((size_t)sgi * 768 + kk * 16), 16);
                    jm::joint_matrix_load(sg, x1, la((size_t)sgi * 768 + 256 + kk * 16), 16);
                    jm::joint_matrix_load(sg, x2, la((size_t)sgi * 768 + 512 + kk * 16), 16);
                } else {
                    jm::joint_matrix_load(sg, x0, gp(pa + kk * 16), cols);
                    jm::joint_matrix_load(sg, x1, gp(pa + pp + kk * 16), cols);
                    jm::joint_matrix_load(sg, x2, gp(pa + 2 * pp + kk * 16), cols);
                }
                if constexpr (!(ABL & 4)) {
                    jm::joint_matrix_mad(sg, c1[0], x0, b0, c1[0]);
                    jm::joint_matrix_mad(sg, c23[0], x1, b0, c23[0]);
                    jm::joint_matrix_mad(sg, c23[0], x2, b0, c23[0]);
                    jm::joint_matrix_mad(sg, c1[1], x0, b1, c1[1]);
                    jm::joint_matrix_mad(sg, c23[1], x1, b1, c23[1]);
                    jm::joint_matrix_mad(sg, c23[1], x2, b1, c23[1]);
                }
            }
#pragma unroll
            for (int i = 0; i < PF; ++i) { r0[i] = n0[i]; r1[i] = n1[i]; }
        }
#pragma unroll
        for (int j = 0; j < 2; ++j) {
            jm::joint_matrix_apply(sg, c1[j], c23[j], [](float &u, float &v) { u = u + v; });
            jm::joint_matrix_store(sg, c1[j], st.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)(sgi * 2 + j) * MMAX * 16, 16,
                                   jm::layout::row_major);
        }
    }
    void rows(sycl::sub_group sg, int sgi, int ln, const uint8_t *w0, const uint8_t *w1, int k0, int ns, size_t row0, int cnt) const {
        if constexpr (MMAX == 1) body<1>(sg, sgi, ln, w0, w1, k0, ns, row0);
        else {
            if (cnt <= 1) body<1>(sg, sgi, ln, w0, w1, k0, ns, row0);
            else if (cnt <= 2) body<2>(sg, sgi, ln, w0, w1, k0, ns, row0);
            else if (cnt <= 4) body<4>(sg, sgi, ln, w0, w1, k0, ns, row0);
            else body<8>(sg, sgi, ln, w0, w1, k0, ns, row0);
        }
    }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const {
        const int t = (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        const auto sg = it.get_sub_group();
        const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id(), rbk = (int)it.get_group(1);
        const int steps = cols / 16, nseg = (steps + SEG - 1) / SEG, k0 = sgi * SEG, ns = sycl::min(SEG, steps - k0);
        const int cnt = g.tile_n[t], s0 = g.tile_s0[t];
        const uint8_t *We = W + (size_t)g.tile_exp[t] * estride;
        const int bl0 = MODE == 1 ? rbk * 2 : rbk, bl1 = MODE == 1 ? rbk * 2 + 1 : nff / 16 + rbk;
        const uint8_t *w0 = We + (size_t)bl0 * steps * TB, *w1 = We + (size_t)bl1 * steps * TB;
        if constexpr (XIN && !(ABL & 8)) { // the one row's segment in parts (reads first; past the segment's end a repeat)
            uint16_t *ap = reinterpret_cast<uint16_t *>(&as[0]) + sgi * 768;
            float xv[SEG];
#pragma unroll
            for (int i = 0; i < SEG; ++i) {
                const int idx = (k0 + sycl::min(i, ns - 1)) * 16 + ln;
                xv[i] = x[xlo ? xlane_at(idx) : (size_t)idx];
            }
#pragma unroll
            for (int i = 0; i < SEG; ++i) {
                uint16_t a, b, c;
                split3(xv[i], a, b, c);
                ap[i * 16 + ln] = a; ap[256 + i * 16 + ln] = b; ap[512 + i * 16 + ln] = c;
            }
            sycl::group_barrier(sg);
        }
        rows(sg, sgi, ln, w0, w1, k0, ns, XIN ? 0 : (size_t)s0, cnt);
        if constexpr ((ABL & 1) != 0) return;
        sycl::group_barrier(it.get_group());
        const int lid = (int)it.get_local_linear_id(), wg = nseg * 16;
        const float *sp = &st[0];
        if constexpr (MODE == 0) {
            const bool sc = op.escale != nullptr;
            const float es = sc ? op.escale[g.tile_exp[t]] : 1.0f;
            for (int id = lid; id < cnt * 16; id += wg) {
                const int r = id / 16, c = id % 16;
                float tg = 0.0f, tu = 0.0f;
                for (int s = 0; s < nseg; ++s) {
                    tg = tg + sp[(size_t)(s * 2) * MMAX * 16 + r * 16 + c];
                    tu = tu + sp[(size_t)(s * 2 + 1) * MMAX * 16 + r * 16 + c];
                }
                uint16_t a, b, d;
                split3(act(tg, tu, es, sc, op.beta, op.lb), a, b, d);
                uint16_t *o = Hp + (size_t)(s0 + r) * nff + rbk * 16 + c;
                o[0] = a; o[hpp] = b; o[2 * hpp] = d;
            }
        } else {
            for (int id = lid; id < cnt * 32; id += wg) {
                const int r = id / 32, cc = id % 32, j = cc / 16, c = cc % 16;
                float tot = 0.0f;
                for (int s = 0; s < nseg; ++s) tot = tot + sp[(size_t)(s * 2 + j) * MMAX * 16 + r * 16 + c];
                Y[(size_t)g.slots[s0 + r] * ldy + rbk * 32 + cc] = tot;
            }
        }
    }
};
// MODE 0: gate|up (nrb = nff / 16), MODE 1: down (nrb = rows / 32). Segments of 16 steps, the last one 16 or 8.
template <int MMAX, int MODE, bool XIN, int PF = 2, int GRF = 128, int ABL = 0>
inline sycl::event small2(sycl::queue &q, const uint8_t *W, size_t estride, int cols, int nff, int nrb, MoeGroups g, int tiles,
                          const uint16_t *P, size_t pp, const float *x, bool xlo, ActOp op, uint16_t *Hp, size_t hpp, float *Y, int ldy) {
    const int steps = cols / 16, nseg = (steps + SEG - 1) / SEG;
    if (cols % 16 || (steps % SEG) % PF || SEG % PF || (XIN && (MODE != 0 || MMAX != 1)))
        throw std::runtime_error("xm::small2: shapes");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<bf, 1> bs((size_t)nseg * 1024, h), as(XIN ? (size_t)nseg * 768 : 1, h);
        sycl::local_accessor<float, 1> st((size_t)nseg * 2 * MMAX * 16, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)tiles, (size_t)nrb * nseg * 16), sycl::range<2>(1, (size_t)nseg * 16)),
                       XSmall2<MMAX, MODE, XIN, PF, GRF, ABL>{W, estride, cols, nff, g, P, pp, x, xlo, op, Hp, hpp, Y, ldy, bs, as, st});
    });
}
// Steps of 1-8 tokens, third form: XSmall's work-groups (SR blocks of 16 rows x one segment of one tile, so the SR
// sub-groups read the same inputs) with XSmall2's passes of PF steps (the next pass's weights fetched first) and rows
// per tile by its count; inputs and outputs by sorted position (compact: P[p][tile_s0[t] + r][cols], or row 0 for
// every tile with one); the segment sums go to S[(t nseg + seg) MMAX + r][ncol], added in order by small_fold_*_c.
// FUSE: the work-group that finishes a (tile, SR row blocks) last (a counter per pair, reset by it) adds the segments
// in order and writes H in parts (MODE 0, act, split: Hp[p][tile_s0[t] + r][i]) or y (MODE 1), as small_fold_*_c.
// DV 1: decode_raw16. HIN (MODE 1): the inputs from the gate|up segment sums Sg (not Hp): each work-group adds the
// 256 H values of its segment for the tile's rows in order, applies SITU and splits them into local memory (as
// small_fold_act_c), then reads its A tiles from there.
// DV 2: the B tiles built in registers by joint_matrix_apply from each lane's own decoded column (element e = k e,
// bench_xm3; the plain apply, after one load of zeros), no local memory for the weights.
template <int MMAX, int MODE, int SR, int PF, int FUSE, int DV = 0, bool HIN = false> struct XSmall3 {
    const uint8_t *W; size_t estride; int cols, nff, ncol;
    MoeGroups g; const uint16_t *P; size_t pp; bool one; float *S; int gridrb;
    int32_t *ctr; ActOp op; uint16_t *Hp; size_t hpp; float *Y; int ldy;
    const float *Sg; int ngu;
    sycl::local_accessor<bf, 1> bs, hs;
    int blkof(int rbk, int j) const { return MODE == 1 ? rbk * 2 + j : j * (nff / 16) + rbk; }
    int colof(int rbk, int j) const { return MODE == 1 ? rbk * 32 + j * 16 : j * nff + rbk * 16; }
    template <int M>
    void body(sycl::sub_group sg, int sgi, int ln, const uint8_t *w0, const uint8_t *w1, int k0, int ns, size_t row0, float *so, float *so1) const {
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, M, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, M, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        Raw r0[PF], r1[PF];
#pragma unroll
        for (int i = 0; i < PF; ++i) { r0[i] = fetch16t(w0 + (size_t)(k0 + i) * TB, ln); r1[i] = fetch16t(w1 + (size_t)(k0 + i) * TB, ln); }
        C c1[2], c23[2];
#pragma unroll
        for (int j = 0; j < 2; ++j) { jm::joint_matrix_fill(sg, c1[j], 0.0f); jm::joint_matrix_fill(sg, c23[j], 0.0f); }
        uint32_t *bw = reinterpret_cast<uint32_t *>(&bs[0]) + sgi * 512;
        auto lb = [&](size_t off) { return bs.template get_multi_ptr<sycl::access::decorated::no>() + off; };
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        const bf *pa = HIN ? nullptr : reinterpret_cast<const bf *>(P) + row0 * cols + (size_t)k0 * 16;
        B rb0, rb1; // DV 2: defined once (zeros), then every element written each step
        if constexpr (DV == 2) {
#pragma unroll
            for (int j = 0; j < 8; ++j) bw[j * 16 + ln] = 0u;
            sycl::group_barrier(sg);
            jm::joint_matrix_load(sg, rb0, lb((size_t)sgi * 1024), 32);
            jm::joint_matrix_load(sg, rb1, lb((size_t)sgi * 1024), 32);
        }
        for (int b = 0; b < ns; b += PF) {
            Raw n0[PF], n1[PF];
            const int kn = k0 + sycl::min(b + PF, ns - PF);
#pragma unroll
            for (int i = 0; i < PF; ++i) { n0[i] = fetch16t(w0 + (size_t)(kn + i) * TB, ln); n1[i] = fetch16t(w1 + (size_t)(kn + i) * TB, ln); }
#pragma unroll
            for (int i = 0; i < PF; ++i) {
                const int buf = i & 1, kk = b + i;
                B b0, b1;
                if constexpr (DV == 2) {
                    float v0[16], v1[16];
                    decode_vals(r0[i], v0);
                    decode_vals(r1[i], v1);
                    int e0 = 0, e1 = 0;
                    jm::joint_matrix_apply(sg, rb0, [&](bf &x) { x = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v0[e0]) >> 16)); ++e0; });
                    jm::joint_matrix_apply(sg, rb1, [&](bf &x) { x = sycl::bit_cast<bf>((uint16_t)(sycl::bit_cast<uint32_t>(v1[e1]) >> 16)); ++e1; });
                } else {
                    if constexpr (DV == 1) {
                        decode_raw16(r0[i], bw + buf * 256 + ln, 16);
                        decode_raw16(r1[i], bw + buf * 256 + 128 + ln, 16);
                    } else {
                        decode_raw(r0[i], bw + buf * 256 + ln, 16);
                        decode_raw(r1[i], bw + buf * 256 + 128 + ln, 16);
                    }
                    sycl::group_barrier(sg);
                    jm::joint_matrix_load(sg, b0, lb((size_t)sgi * 1024 + buf * 512), 32);
                    jm::joint_matrix_load(sg, b1, lb((size_t)sgi * 1024 + buf * 512 + 256), 32);
                }
                const B &bb0 = DV == 2 ? rb0 : b0, &bb1 = DV == 2 ? rb1 : b1;
                A x0, x1, x2;
                if constexpr (HIN) {
                    auto lh = hs.template get_multi_ptr<sycl::access::decorated::no>();
                    jm::joint_matrix_load(sg, x0, lh + kk * 16, 256);
                    jm::joint_matrix_load(sg, x1, lh + MMAX * 256 + kk * 16, 256);
                    jm::joint_matrix_load(sg, x2, lh + 2 * MMAX * 256 + kk * 16, 256);
                } else {
                    jm::joint_matrix_load(sg, x0, gp(pa + kk * 16), cols);
                    jm::joint_matrix_load(sg, x1, gp(pa + pp + kk * 16), cols);
                    jm::joint_matrix_load(sg, x2, gp(pa + 2 * pp + kk * 16), cols);
                }
                jm::joint_matrix_mad(sg, c1[0], x0, bb0, c1[0]);
                jm::joint_matrix_mad(sg, c23[0], x1, bb0, c23[0]);
                jm::joint_matrix_mad(sg, c23[0], x2, bb0, c23[0]);
                jm::joint_matrix_mad(sg, c1[1], x0, bb1, c1[1]);
                jm::joint_matrix_mad(sg, c23[1], x1, bb1, c23[1]);
                jm::joint_matrix_mad(sg, c23[1], x2, bb1, c23[1]);
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
        const int steps = cols / 16, nseg = (steps + SEG - 1) / SEG;
        const int gi = (int)it.get_group(1), seg = gi % nseg, rbk = (gi / nseg) * SR + sgi;
        const int k0 = seg * SEG, ns = sycl::min(SEG, steps - k0), cnt = g.tile_n[t];
        const uint8_t *We = W + (size_t)g.tile_exp[t] * estride;
        const uint8_t *w0 = We + (size_t)blkof(rbk, 0) * steps * TB, *w1 = We + (size_t)blkof(rbk, 1) * steps * TB;
        const size_t row0 = one ? 0 : (size_t)g.tile_s0[t];
        float *sb = S + (size_t)(t * nseg + seg) * MMAX * ncol, *so = sb + colof(rbk, 0), *so1 = sb + colof(rbk, 1);
        if constexpr (HIN) { // this segment's H values (nff inputs at k0 * 16) for rows r < cnt, in parts
            uint16_t *hp = reinterpret_cast<uint16_t *>(&hs[0]);
            const int lid = (int)it.get_local_linear_id(), n16 = ns * 16;
            const bool sc = op.escale != nullptr;
            const float es = sc ? op.escale[g.tile_exp[t]] : 1.0f;
            constexpr int NS = 9;
            for (int id = lid; id < cnt * n16; id += SR * 16) {
                const int r = id / n16, i = id % n16, hi = k0 * 16 + i;
                float tg = 0.0f, tu = 0.0f;
                if (ngu == NS) {
                    float vg[NS], vu[NS];
#pragma unroll
                    for (int s = 0; s < NS; ++s) {
                        const float *row = Sg + ((size_t)(t * NS + s) * MMAX + r) * 2 * nff;
                        vg[s] = row[hi]; vu[s] = row[nff + hi];
                    }
#pragma unroll
                    for (int s = 0; s < NS; ++s) { tg = tg + vg[s]; tu = tu + vu[s]; }
                } else
                    for (int s = 0; s < ngu; ++s) {
                        const float *row = Sg + ((size_t)(t * ngu + s) * MMAX + r) * 2 * nff;
                        tg = tg + row[hi];
                        tu = tu + row[nff + hi];
                    }
                split3_store(act(tg, tu, es, sc, op.beta, op.lb), hp + r * 256 + i, (size_t)MMAX * 256);
            }
            sycl::group_barrier(it.get_group());
        }
        if constexpr (MMAX == 1) body<1>(sg, sgi, ln, w0, w1, k0, ns, row0, so, so1);
        else {
            if (cnt <= 1) body<1>(sg, sgi, ln, w0, w1, k0, ns, row0, so, so1);
            else if (cnt <= 2) body<2>(sg, sgi, ln, w0, w1, k0, ns, row0, so, so1);
            else if (cnt <= 4) body<4>(sg, sgi, ln, w0, w1, k0, ns, row0, so, so1);
            else body<8>(sg, sgi, ln, w0, w1, k0, ns, row0, so, so1);
        }
        if constexpr (FUSE != 0) {
            // 1: release fence by every work-item, acq_rel counter, acquire fence, plain reads. 2: release fences, a
            // release counter, the sums read by device-scope atomic loads (from the shared cache). 3: as 2 with one
            // release fence per work-group, after its barrier
            if constexpr (FUSE != 3) sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::device);
            const auto wg = it.get_group();
            sycl::group_barrier(wg);
            const int lid = (int)it.get_local_linear_id(), rbg = gi / nseg;
            int last = 0;
            if (lid == 0) {
                if constexpr (FUSE == 3) sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::device);
                if constexpr (FUSE == 1) {
                    sycl::atomic_ref<int32_t, sycl::memory_order::acq_rel, sycl::memory_scope::device, sycl::access::address_space::global_space> a(
                        ctr[(size_t)t * gridrb + rbg]);
                    last = a.fetch_add(1) == nseg - 1;
                    if (last) a.store(0);
                } else {
                    sycl::atomic_ref<int32_t, sycl::memory_order::relaxed, sycl::memory_scope::device, sycl::access::address_space::global_space> a(
                        ctr[(size_t)t * gridrb + rbg]);
                    last = a.fetch_add(1, sycl::memory_order::release) == nseg - 1;
                    if (last) a.store(0);
                }
            }
            last = sycl::group_broadcast(wg, last, 0);
            if (!last) return;
            if constexpr (FUSE == 1) sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::device);
            auto ld = [](const float *p) {
                if constexpr (FUSE == 1) return *p;
                else return sycl::atomic_ref<float, sycl::memory_order::relaxed, sycl::memory_scope::device, sycl::access::address_space::global_space>(
                                *const_cast<float *>(p)).load();
            };
            const int rb = rbg * SR + lid / 16, c = lid % 16, s0 = g.tile_s0[t];
            if constexpr (MODE == 0) {
                const bool sc = op.escale != nullptr;
                const float es = sc ? op.escale[g.tile_exp[t]] : 1.0f;
                const int i = rb * 16 + c;
                for (int r = 0; r < cnt; ++r) {
                    float tg = 0.0f, tu = 0.0f;
                    for (int s = 0; s < nseg; ++s) {
                        const float *row = S + ((size_t)(t * nseg + s) * MMAX + r) * ncol;
                        tg = tg + ld(row + i);
                        tu = tu + ld(row + nff + i);
                    }
                    uint16_t a, b, d;
                    split3(act(tg, tu, es, sc, op.beta, op.lb), a, b, d);
                    uint16_t *o = Hp + (size_t)(s0 + r) * nff + i;
                    o[0] = a; o[hpp] = b; o[2 * hpp] = d;
                }
            } else {
                for (int r = 0; r < cnt; ++r) {
                    float *yo = Y + (size_t)g.slots[s0 + r] * ldy + rb * 32 + c;
#pragma unroll
                    for (int j = 0; j < 2; ++j) {
                        float tot = 0.0f;
                        for (int s = 0; s < nseg; ++s) tot = tot + ld(S + ((size_t)(t * nseg + s) * MMAX + r) * ncol + rb * 32 + j * 16 + c);
                        yo[j * 16] = tot;
                    }
                }
            }
        }
    }
};
// ctr (FUSE): tiles x nrb / SR counters, zero before the first launch (each launch leaves them zero)
template <int MMAX, int MODE, int SR = 4, int PF = 1, int FUSE = 0, int DV = 0, bool HIN = false>
inline sycl::event small3(sycl::queue &q, const uint8_t *W, size_t estride, int cols, int nff, int ncol, int nrb, MoeGroups g, int tiles,
                          const uint16_t *P, size_t pp, bool one, float *S, int32_t *ctr = nullptr, ActOp op = {}, uint16_t *Hp = nullptr,
                          size_t hpp = 0, float *Y = nullptr, int ldy = 0, const float *Sg = nullptr, int ngu = 0) {
    const int steps = cols / 16, nseg = (steps + SEG - 1) / SEG;
    if (cols % 16 || nrb % SR || (steps % SEG) % PF || SEG % PF) throw std::runtime_error("xm::small3: shapes");
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<bf, 1> bs(SR * 1024, h), hs(HIN ? (size_t)3 * MMAX * 256 : 1, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)tiles, (size_t)(nrb / SR) * nseg * SR * 16), sycl::range<2>(1, SR * 16)),
                       XSmall3<MMAX, MODE, SR, PF, FUSE, DV, HIN>{W, estride, cols, nff, ncol, g, P, pp, one, S, nrb / SR, ctr, op, Hp, hpp, Y, ldy,
                                                             Sg, ngu, bs, hs});
    });
}
// Steps of 1-8 tokens, fourth form: one sub-group per (tile, B tile of 16 rows) over all its inputs: per segment c1 and
// c23 from zero, then tot = tot + (c1 + c23) in registers (as XProd2 and the folds: the same additions in the same
// order); the weights PF steps ahead (across segments), the B tiles built in registers (bench_xm3). Rows per tile by
// its count. MODE 0: work-group = the gate and up tiles of 16 rows: SITU and split there, Hp[p][tile_s0[t] + r][i].
// MODE 1: work-group = SRF tiles of 16 rows; y[slots[tile_s0[t] + r]][row].
// PD > 0: every pass also asks the cache (HL 1: L1, 3: L3) for the weights PD steps ahead (one prefetch per lane,
// 64 bytes each; no registers held), the step loop unchanged.
template <int MMAX, int MODE, int PF, int SRF, int GRF, int PD = 0, int HL = 1, bool SWAP = false> struct XFull {
    const uint8_t *W; size_t estride; int cols, nff;
    MoeGroups g; const uint16_t *P; size_t pp; bool one;
    ActOp op; uint16_t *Hp; size_t hpp; float *Y; int ldy;
    sycl::local_accessor<float, 1> st;
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<GRF>};
    }
    template <int M> void body(sycl::sub_group sg, int sgi, int ln, const uint8_t *w, size_t row0) const {
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, M, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, M, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        const int steps = cols / 16;
        Raw r[PF];
#pragma unroll
        for (int i = 0; i < PF; ++i) r[i] = fetch16t(w + (size_t)i * TB, ln);
        C c1, c23, tot;
        jm::joint_matrix_fill(sg, tot, 0.0f);
        B rb;
        jm::joint_matrix_fill(sg, rb, bf(0.0f));
        const bf *pa = reinterpret_cast<const bf *>(P) + row0 * cols;
        for (int k0 = 0; k0 < steps; k0 += SEG) {
            const int ns = sycl::min(SEG, steps - k0);
            jm::joint_matrix_fill(sg, c1, 0.0f);
            jm::joint_matrix_fill(sg, c23, 0.0f);
            for (int b = 0; b < ns; b += PF) {
                const int kb = k0 + b, kn = sycl::min(kb + PF, steps - PF);
                Raw n[PF];
#pragma unroll
                for (int i = 0; i < PF; ++i) n[i] = fetch16t(w + (size_t)(kn + i) * TB, ln);
                if constexpr (PD > 0) {
                    namespace sx = sycl::ext::oneapi::experimental;
                    const int kp = sycl::min(kb + PD, steps - PF);
                    const uint8_t *pp8 = w + (size_t)kp * TB + (size_t)sycl::min(ln, PF * TB / 64) * 64;
                    if constexpr (HL == 1) sx::prefetch((void *)pp8, 64, sx::properties{sx::prefetch_hint_L1});
                    else sx::prefetch((void *)pp8, 64, sx::properties{sx::prefetch_hint_L3});
                }
#pragma unroll
                for (int i = 0; i < PF; ++i) {
                    float v[16];
                    decode_vals(r[i], v);
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
        jm::joint_matrix_store(sg, tot, st.template get_multi_ptr<sycl::access::decorated::no>() + (size_t)sgi * MMAX * 16, 16, jm::layout::row_major);
    }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const {
        // SWAP visits all row blocks of one expert before the next under the usual x-fastest group order.
        // It changes scheduling only; every sub-group's sums and stores stay in the same order.
        const int t = SWAP ? (int)it.get_group(1) : (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        const auto sg = it.get_sub_group();
        const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id();
        const int gi = SWAP ? (int)it.get_group(0) : (int)it.get_group(1);
        const int steps = cols / 16, cnt = g.tile_n[t], s0 = g.tile_s0[t];
        const int blk = MODE == 0 ? sgi * (nff / 16) + gi : gi * SRF + sgi; // tile layout block (16 rows)
        const uint8_t *w = W + (size_t)g.tile_exp[t] * estride + (size_t)blk * steps * TB;
        const size_t row0 = one ? 0 : (size_t)s0;
        if constexpr (MMAX == 1) body<1>(sg, sgi, ln, w, row0);
        else {
            if (cnt <= 1) body<1>(sg, sgi, ln, w, row0);
            else if (cnt <= 2) body<2>(sg, sgi, ln, w, row0);
            else if (cnt <= 4) body<4>(sg, sgi, ln, w, row0);
            else body<8>(sg, sgi, ln, w, row0);
        }
        const float *sp = &st[0];
        if constexpr (MODE == 0) {
            sycl::group_barrier(it.get_group());
            const int lid = (int)it.get_local_linear_id();
            const bool sc = op.escale != nullptr;
            const float es = sc ? op.escale[g.tile_exp[t]] : 1.0f;
            for (int id = lid; id < cnt * 16; id += 32) {
                const int r = id / 16, c = id % 16;
                split3_store(act(sp[r * 16 + c], sp[MMAX * 16 + r * 16 + c], es, sc, op.beta, op.lb), Hp + (size_t)(s0 + r) * nff + gi * 16 + c, hpp);
            }
        } else {
            sycl::group_barrier(sg);
            for (int r = 0; r < cnt; ++r) Y[(size_t)g.slots[s0 + r] * ldy + blk * 16 + ln] = sp[(size_t)sgi * MMAX * 16 + r * 16 + ln];
        }
    }
};
// MODE 0: gate|up (cols inputs, nff rows each), MODE 1: down (cols = nff inputs, rows outputs)
template <int MMAX, int MODE, int PF = 4, int SRF = 4, int GRF = 128, int PD = 0, int HL = 1, bool SWAP = false>
inline sycl::event full_prod(sycl::queue &q, const uint8_t *W, size_t estride, int cols, int nff, int rows, MoeGroups g, int tiles,
                             const uint16_t *P, size_t pp, bool one, ActOp op, uint16_t *Hp, size_t hpp, float *Y, int ldy) {
    const int steps = cols / 16;
    if (cols % 16 || steps % PF || SEG % PF || (steps % SEG) % PF || (MODE == 1 && (rows / 16) % SRF)) throw std::runtime_error("xm::full_prod: shapes");
    const int sgw = MODE == 0 ? 2 : SRF, ngr = MODE == 0 ? nff / 16 : rows / 16 / SRF;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> st((size_t)sgw * MMAX * 16, h);
        const size_t r0 = SWAP ? (size_t)ngr * sgw * 16 : (size_t)tiles;
        const size_t r1 = SWAP ? (size_t)tiles : (size_t)ngr * sgw * 16;
        const size_t l0 = SWAP ? (size_t)sgw * 16 : 1, l1 = SWAP ? 1 : (size_t)sgw * 16;
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>(r0, r1), sycl::range<2>(l0, l1)),
                       XFull<MMAX, MODE, PF, SRF, GRF, PD, HL, SWAP>{W, estride, cols, nff, g, P, pp, one, op, Hp, hpp, Y, ldy, st});
    });
}
// XFull with each (tile, 16 rows) split over KS sub-groups by consecutive segments: part 0 adds its segments into a
// total in registers (from 0), parts 1.. store each segment's sum (c1 + c23); after a barrier the total + those sums
// in segment order: the same additions in the same order as XFull, with KS times the sub-groups.
template <int MMAX, int MODE, int PF, int SRF, int KS> struct XFullK {
    const uint8_t *W; size_t estride; int cols, nff;
    MoeGroups g; const uint16_t *P; size_t pp; bool one;
    ActOp op; uint16_t *Hp; size_t hpp; float *Y; int ldy; int nsl;
    sycl::local_accessor<float, 1> st;
    sycl::local_accessor<bf, 1> zb;
    template <int M, bool STORE> void body(sycl::sub_group sg, int ln, const uint8_t *w, size_t row0, int ka, int ke, size_t so) const {
        using C = jm::joint_matrix<sycl::sub_group, float, jm::use::accumulator, M, 16>;
        using A = jm::joint_matrix<sycl::sub_group, bf, jm::use::a, M, 16, jm::layout::row_major>;
        using B = jm::joint_matrix<sycl::sub_group, bf, jm::use::b, 16, 16, jm::layout::ext_intel_packed>;
        auto gp = [](const bf *p) { return sycl::address_space_cast<sycl::access::address_space::global_space, sycl::access::decorated::no>(p); };
        Raw r[PF];
#pragma unroll
        for (int i = 0; i < PF; ++i) r[i] = fetch16t(w + (size_t)(ka + i) * TB, ln);
        C c1, c23, tot;
        if constexpr (!STORE) jm::joint_matrix_fill(sg, tot, 0.0f);
        B rb;
        jm::joint_matrix_load(sg, rb, zb.template get_multi_ptr<sycl::access::decorated::no>(), 32);
        const bf *pa = reinterpret_cast<const bf *>(P) + row0 * cols;
        size_t slot = so;
        for (int k0 = ka; k0 < ke; k0 += SEG) {
            const int ns = sycl::min(SEG, ke - k0);
            jm::joint_matrix_fill(sg, c1, 0.0f);
            jm::joint_matrix_fill(sg, c23, 0.0f);
            for (int b = 0; b < ns; b += PF) {
                const int kb = k0 + b, kn = sycl::min(kb + PF, ke - PF);
                Raw n[PF];
#pragma unroll
                for (int i = 0; i < PF; ++i) n[i] = fetch16t(w + (size_t)(kn + i) * TB, ln);
#pragma unroll
                for (int i = 0; i < PF; ++i) {
                    float v[16];
                    decode_vals(r[i], v);
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
            if constexpr (STORE) {
                jm::joint_matrix_store(sg, c1, st.template get_multi_ptr<sycl::access::decorated::no>() + slot, 16, jm::layout::row_major);
                slot += (size_t)MMAX * 16;
            } else jm::joint_matrix_apply(sg, tot, c1, [](float &u, float &v) { u = u + v; });
        }
        if constexpr (!STORE) jm::joint_matrix_store(sg, tot, st.template get_multi_ptr<sycl::access::decorated::no>() + so, 16, jm::layout::row_major);
    }
    template <bool STORE> void rows(sycl::sub_group sg, int ln, int cnt, const uint8_t *w, size_t row0, int ka, int ke, size_t so) const {
        if constexpr (MMAX == 1) body<1, STORE>(sg, ln, w, row0, ka, ke, so);
        else {
            if (cnt <= 1) body<1, STORE>(sg, ln, w, row0, ka, ke, so);
            else if (cnt <= 2) body<2, STORE>(sg, ln, w, row0, ka, ke, so);
            else if (cnt <= 4) body<4, STORE>(sg, ln, w, row0, ka, ke, so);
            else body<8, STORE>(sg, ln, w, row0, ka, ke, so);
        }
    }
    // the total of unit u (its part 0's registers' total + the other parts' segment sums in order), element e
    float total(int u, int nseg, size_t e) const {
        const size_t area = (size_t)nsl * MMAX * 16;
        float v = st[(size_t)u * KS * area + e];
#pragma unroll
        for (int p = 1; p < KS; ++p) {
            const int np = (p + 1) * nseg / KS - p * nseg / KS;
            const size_t base = (size_t)(u * KS + p) * area + e;
            for (int j = 0; j < np; ++j) v = v + st[base + (size_t)j * MMAX * 16];
        }
        return v;
    }
    [[sycl::reqd_sub_group_size(16)]] void operator()(sycl::nd_item<2> it) const {
        const int t = (int)it.get_group(0);
        if (t >= g.ntiles[0]) return;
        const auto sg = it.get_sub_group();
        const int sgi = (int)sg.get_group_linear_id(), ln = (int)sg.get_local_linear_id(), gi = (int)it.get_group(1);
        const int lid = (int)it.get_local_linear_id(), nl = (int)it.get_local_range(1);
        const int steps = cols / 16, nseg = (steps + SEG - 1) / SEG, cnt = g.tile_n[t], s0 = g.tile_s0[t];
        const int unit = sgi / KS, part = sgi % KS;
        const int blk = MODE == 0 ? unit * (nff / 16) + gi : gi * SRF + unit; // tile layout block (16 rows)
        const int ka = part * nseg / KS * SEG, ke = sycl::min((part + 1) * nseg / KS * SEG, steps);
        const uint8_t *w = W + (size_t)g.tile_exp[t] * estride + (size_t)blk * steps * TB;
        const size_t row0 = one ? 0 : (size_t)s0, so = (size_t)sgi * nsl * MMAX * 16;
        if (lid < 128) reinterpret_cast<uint32_t *>(&zb[0])[lid] = 0u; // the zero tile that defines B before its first apply
        sycl::group_barrier(it.get_group());
        if (part == 0) rows<false>(sg, ln, cnt, w, row0, ka, ke, so);
        else rows<true>(sg, ln, cnt, w, row0, ka, ke, so);
        sycl::group_barrier(it.get_group());
        if constexpr (MODE == 0) {
            const bool sc = op.escale != nullptr;
            const float es = sc ? op.escale[g.tile_exp[t]] : 1.0f;
            for (int id = lid; id < cnt * 16; id += nl) {
                const int r = id / 16, c = id % 16;
                const size_t e = (size_t)r * 16 + c;
                split3_store(act(total(0, nseg, e), total(1, nseg, e), es, sc, op.beta, op.lb), Hp + (size_t)(s0 + r) * nff + gi * 16 + c, hpp);
            }
        } else {
            for (int id = lid; id < cnt * 16 * SRF; id += nl) {
                const int u = id / (cnt * 16), rc = id % (cnt * 16), r = rc / 16, c = rc % 16;
                Y[(size_t)g.slots[s0 + r] * ldy + (gi * SRF + u) * 16 + c] = total(u, nseg, (size_t)r * 16 + c);
            }
        }
    }
};
template <int MMAX, int MODE, int PF = 4, int SRF = 2, int KS = 2>
inline sycl::event full_prodk(sycl::queue &q, const uint8_t *W, size_t estride, int cols, int nff, int rows, MoeGroups g, int tiles,
                              const uint16_t *P, size_t pp, bool one, ActOp op, uint16_t *Hp, size_t hpp, float *Y, int ldy) {
    const int steps = cols / 16, nseg = (steps + SEG - 1) / SEG;
    if (cols % 16 || steps % PF || SEG % PF || (steps % SEG) % PF || nseg < KS || (MODE == 1 && (rows / 16) % SRF))
        throw std::runtime_error("xm::full_prodk: shapes");
    const int sgw = (MODE == 0 ? 2 : SRF) * KS, ngr = MODE == 0 ? nff / 16 : rows / 16 / SRF, nsl = (nseg + KS - 1) / KS;
    return q.submit([&](sycl::handler &h) {
        sycl::local_accessor<float, 1> st((size_t)sgw * nsl * MMAX * 16, h);
        sycl::local_accessor<bf, 1> zb(256, h);
        h.parallel_for(sycl::nd_range<2>(sycl::range<2>((size_t)tiles, (size_t)ngr * sgw * 16), sycl::range<2>(1, (size_t)sgw * 16)),
                       XFullK<MMAX, MODE, PF, SRF, KS>{W, estride, cols, nff, g, P, pp, one, op, Hp, hpp, Y, ldy, nsl, st, zb});
    });
}
// gate|up: H in parts for each tile's rows r < count by sorted position: Hp[p][tile_s0[t] + r][i]
inline sycl::event small_fold_act_c(sycl::queue &q, MoeGroups g, int tiles, int nseg, int mmax, const float *S, int nff, ActOp op, uint16_t *Hp, size_t hpp) {
    return q.parallel_for(sycl::range<2>((size_t)tiles, (size_t)nff), [=](sycl::id<2> id) {
        const int t = (int)id[0], i = (int)id[1];
        if (t >= g.ntiles[0]) return;
        const int cnt = g.tile_n[t], s0 = g.tile_s0[t];
        const bool sc = op.escale != nullptr;
        const float es = sc ? op.escale[g.tile_exp[t]] : 1.0f;
        constexpr int NS = 9; // gate|up of 2,304 inputs: the reads first (unrolled), then the same additions in order
        for (int r = 0; r < cnt; ++r) {
            float tg = 0.0f, tu = 0.0f;
            if (nseg == NS) {
                float vg[NS], vu[NS];
#pragma unroll
                for (int s = 0; s < NS; ++s) {
                    const float *row = S + ((size_t)(t * NS + s) * mmax + r) * 2 * nff;
                    vg[s] = row[i]; vu[s] = row[nff + i];
                }
#pragma unroll
                for (int s = 0; s < NS; ++s) { tg = tg + vg[s]; tu = tu + vu[s]; }
            } else
                for (int s = 0; s < nseg; ++s) {
                    const float *row = S + ((size_t)(t * nseg + s) * mmax + r) * 2 * nff;
                    tg = tg + row[i];
                    tu = tu + row[nff + i];
                }
            uint16_t a, b, d;
            split3(act(tg, tu, es, sc, op.beta, op.lb), a, b, d);
            uint16_t *o = Hp + (size_t)(s0 + r) * nff + i;
            o[0] = a; o[hpp] = b; o[2 * hpp] = d;
        }
    });
}
// y[slot][col] = the sum of a tile's segments in order, rows r < count
inline sycl::event small_fold_out_c(sycl::queue &q, MoeGroups g, int tiles, int nseg, int mmax, const float *S, int ncol, float *Y, int ldy) {
    return q.parallel_for(sycl::range<2>((size_t)tiles, (size_t)ncol), [=](sycl::id<2> id) {
        const int t = (int)id[0], c = (int)id[1];
        if (t >= g.ntiles[0]) return;
        const int cnt = g.tile_n[t], s0 = g.tile_s0[t];
        for (int r = 0; r < cnt; ++r) {
            float tot = 0.0f;
            for (int s = 0; s < nseg; ++s) tot = tot + S[((size_t)(t * nseg + s) * mmax + r) * ncol + c];
            Y[(size_t)g.slots[s0 + r] * ldy + c] = tot;
        }
    });
}
// P[p][s][cols] for the group's sorted positions s < k (slot slots[s], token slot / ku), 8 columns per work-item
inline sycl::event split_gather_c(sycl::queue &q, MoeGroups g, int k, const float *x, int cols, int ku, int ldx, uint16_t *P, size_t pp) {
    return q.parallel_for(sycl::range<2>((size_t)k, (size_t)cols / 8), [=](sycl::id<2> id) {
        const int s = (int)id[0], c8 = (int)id[1] * 8;
        const float *row = x + (size_t)(g.slots[s] / ku) * ldx + c8;
        const sycl::float4 v0 = *reinterpret_cast<const sycl::float4 *>(row), v1 = *reinterpret_cast<const sycl::float4 *>(row + 4);
        sycl::vec<uint16_t, 8> a, b, c;
#pragma unroll
        for (int i = 0; i < 8; ++i) {
            uint16_t p0, p1, p2;
            split3(i < 4 ? v0[i] : v1[i - 4], p0, p1, p2);
            a[i] = p0; b[i] = p1; c[i] = p2;
        }
        uint16_t *o = P + (size_t)s * cols + c8;
        *reinterpret_cast<sycl::vec<uint16_t, 8> *>(o) = a;
        *reinterpret_cast<sycl::vec<uint16_t, 8> *>(o + pp) = b;
        *reinterpret_cast<sycl::vec<uint16_t, 8> *>(o + 2 * pp) = c;
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
