// Sparse attention in one or two launches ("attn a1", 2026-11-11), BITWISE the same outputs and rope'd outputs as
// WindowAppendP + SparseScoreHG<512, 1> / SparseScoreP<512> + SparseSoftmaxP<n> + SparseOutJC<512, 16, 128>
// (sycl_v41.hpp; one token) and as ScoreM + SoftmaxM + OutMC<SparseOutJC> (blocks), the same ring row, window
// list and concatenated list as WindowAppendP, the same weights (kept slots). Included after sycl_v41.hpp.
// Bench: tools/bench/bench_attn_a1.cpp (production against these at the engine's shapes: 8 and 16 heads, 1-16
// tokens, 128-640 slots, normal and peaky data with skipped slots, stale NaN / inf in the score array; memcmp).
//
// The float operations per output and their order are production's:
//   score   (head, slot): acc += q[j] * bf16(k[j]) for j = 0 .. 511 in order, then acc * (1 / sqrt(float(hd)));
//   softmax (head):       the max over the sink and the kept slots, the xor butterfly, sum = exp(sink - mx) then
//                         + each kept slot's exp(v - mx) (a skipped one + 0) in slot order, then v / sum;
//   output  (head, col):  o += ok ? w * x : -0.0f in slot order, then the inverse rope's expressions.
// What changes (one token: four launches -> one (SparseOutF) or two; blocks: three -> one or two after the window
// append):
//  1. SparseScoreT: the score in tiles of 32 slots x HG heads per work-group. The 32 slots' key rows (1 KB each)
//     are block-loaded into local memory first (every row read from memory once per HG heads instead of once
//     per head; all loads in flight together), then each lane runs its slot's chain from local memory with the
//     next chunk's words loaded ahead. Production's chains wait a memory latency per 32-element chunk.
//     WIN (one token): WindowAppendP's work in the same launch: the lists from its formulas and cidx, widx / cat
//     stored by work-group 0, the token's own row (window slot win - 1) converted from kv into local memory (the
//     bytes WindowAppendP stores) and stored into the ring by one work-group.
//  2. SparseOutJE<HD, n, HG, SM>: SparseOutJC's split (work-group = HG heads x a 32-column span) with every slot's
//     64-byte piece loaded at once (one barrier instead of one per 128-slot chunk), stored as bf16 pairs (word
//     ((p / 4) * 32 + l) * 4 + p % 4: slots 2p (low half) and 2p + 1 (high half) of column base + l), 16-byte
//     local loads (8 slots each). SM: the softmax runs here, on the raw scores, while the row pieces are in
//     flight (each column span's work-group computes its heads' weights; att_softmax_regs is SparseSoftmaxP's
//     arithmetic). The score array then keeps the raw scores (nothing reads it after the output launch).
//  3. A skipped slot adds (w * x AND 0x80000000) instead of -0.0f; groups of 32 kept slots add w * x without it.
//     The same sums: o starts at +0 and a round-to-nearest sum is -0 only when both terms are -0, so o is never
//     -0; o + (+0) and o + (-0) are then both o (o = +0, nonzero, inf; a NaN o stays NaN either way), and
//     (w * x AND 0x80000000) is +0 or -0 for every product, NaN included.
//  4. bf16 -> f32 as one shift (low half of a word) or one and (high half): the bits ops41::bf16 makes.
//  5. SparseOutF (bottom): 1 and 2 in one launch. The score tiles come first; each output work-group loads its
//     row pieces while the tiles run, then waits on a device counter for them (see there). One token (WIN): the
//     window append in the same launch: one launch per layer instead of four.
#pragma once
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>

namespace ops41sycl {

// SparseSoftmaxP<32 K>'s steps on one head held in registers (lane l: slot 32 k + l's raw score in v[k], ok[k]
// = index >= 0), branch-free: every lane's exp is computed (a skipped slot's e0 is 0 as in production and its
// value is never used). On return v[k] holds the kept slots' weights: the same max, exp arguments, serial sum in
// slot order and division as SparseSoftmaxP. IX: ok holds the slot indices themselves (kept: >= 0)
template <int K, bool IX = false>
[[gnu::always_inline]] inline void att_softmax_regs(sycl::sub_group sg, float (&v)[K], const int (&ok)[K], float sk) {
    const int lane = (int)sg.get_local_linear_id();
    auto kept = [&](int k) { return IX ? ok[k] >= 0 : ok[k] != 0; };
    float mx = sk;
#pragma unroll
    for (int k = 0; k < K; ++k) mx = (kept(k) && v[k] > mx) ? v[k] : mx;
    for (int w_ = 16; w_; w_ >>= 1) {
        const float o = sycl::select_from_group(sg, mx, lane ^ w_);
        mx = o > mx ? o : mx;
    }
    float sum = sycl::exp(sk - mx);
    float e0[K];
#pragma unroll
    for (int k = 0; k < K; ++k) {
        v[k] = sycl::exp(v[k] - mx);
        e0[k] = kept(k) ? v[k] : 0.0f;
    }
#pragma unroll
    for (int k = 0; k < K; ++k)
#pragma unroll
        for (int l2 = 0; l2 < 32; ++l2) sum += sycl::select_from_group(sg, e0[k], l2);
#pragma unroll
    for (int k = 0; k < K; ++k) v[k] = v[k] / sum;
}

// Score tiles (see the top). Work-group = 32 slots x HG heads: sub-group g = head hgi * HG + g, lane l = slot
// 32 sb + l; sub-group g block-loads rows g, g + HG, ... of the 32. Scores stored as SparseScoreHG stores them
// (head h, slot i at h * n_idx + i; skipped slots untouched). Grid: per token groups(n, heads) work-groups (token
// grp / gpt, head group (grp % gpt) / nib, slot block grp % nib; per-token strides qs, is, ss as ScoreM), WG
// items, SLM 32-bit words of local memory. WIN: one token (m = 1) with the window append (start_pos, nc: 512 or
// 0 compressed entries, win_rows = the window's rows).
template <unsigned HD, unsigned HG, bool WIN = false, typename A = ActF32> struct SparseScoreT {
    static constexpr unsigned RS = HD / 2 + 4, RPG = 32 / HG, NC = HD / 32, RW = HD / 64; // RS: words per row (+16 B)
    static constexpr size_t WG = 32 * (size_t)HG, SLM = 32 * (size_t)RS;
    static_assert(HD % 256 == 0 && 32 % HG == 0 && HG >= 1);
    int n_idx, heads, win_rows, hd; // hd == HD at run time (the scale's expression as production)
    unsigned m = 1;
    size_t qs = 0, is = 0, ss = 0;
    int start_pos = 0, nc = 0; // WIN
    static size_t groups(int n, int heads) { return (size_t)((heads + (int)HG - 1) / (int)HG) * (size_t)(n / 32); }
    // blocks (and one token without the window append): the lists in idxs
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *q, const uint16_t *kvw, const uint16_t *kvc,
                                     const int32_t *idxs, float *score, uint32_t *lm) const {
        run(it, q, const_cast<uint16_t *>(kvw), kvc, const_cast<int32_t *>(idxs), (const typename A::T *)nullptr, nullptr,
            nullptr, score, lm);
    }
    // WIN: ring = the window rows (kvw), cat = the concatenated list WindowAppendP writes
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *q, uint16_t *ring, const uint16_t *kvc,
                                     const typename A::T *kv, const int32_t *cidx, int32_t *widx, int32_t *cat,
                                     float *score, uint32_t *lm) const {
        run(it, q, ring, kvc, cat, kv, cidx, widx, score, lm);
    }
    [[gnu::always_inline]] inline void run(sycl::nd_item<1> it, const float *q, uint16_t *kvw, const uint16_t *kvc,
                                           int32_t *idxs, const typename A::T *kv, const int32_t *cidx, int32_t *widx,
                                           float *score, uint32_t *lm) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), g = sg.get_group_linear_id(), lid = (unsigned)it.get_local_linear_id();
        const unsigned nib = (unsigned)n_idx / 32, nhg = ((unsigned)heads + HG - 1) / HG, gpt = nib * nhg;
        const unsigned grp = (unsigned)it.get_group_linear_id(), t = grp / gpt, r0 = grp % gpt, hgi = r0 / nib, sb = r0 % nib;
        if (t >= m) return; // (the whole work-group)
        q += t * qs;
        idxs += t * is;
        score += t * ss;
        const int wr = win_rows, p = start_pos;
        auto slot_of = [&](int i) -> int {
            if constexpr (WIN) {
                if (i < wr) {
                    const int j = ((p % wr + 1) % wr + i) % wr; // WindowAppendP's j
                    return j > p ? -1 : j;
                }
                return cidx[i - wr];
            } else {
                return idxs[i];
            }
        };
        const int i = (int)(sb * 32 + lane);
        const int slot = slot_of(i);
        if constexpr (WIN) {
            if (grp == 0) { // WindowAppendP's widx / cat
                for (int x = (int)lid; x < wr; x += (int)WG) {
                    const int v = slot_of(x);
                    widx[x] = v;
                    idxs[x] = v;
                }
                for (int x = (int)lid; x < nc; x += (int)WG) idxs[wr + x] = cidx[x];
            }
        }
        const int h = (int)(hgi * HG + g);
        const bool act = h < heads;
        const float *qh = q + (size_t)(act ? h : 0) * HD;
        const int s0 = slot < 0 ? 0 : slot;
        const uintptr_t ra = reinterpret_cast<uintptr_t>(s0 < wr ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - wr) * HD);
        // 1. this sub-group's rows (block loads: element e of lane l = word 32 e + l), then the query (element c of
        //    lane l = q[32 c + l]), then the rows into local memory (row r at word r * RS)
        uint32_t rv[RPG][RW];
#pragma unroll
        for (unsigned rr = 0; rr < RPG; ++rr) {
            const unsigned r = g + HG * rr;
            bool own = false;
            if constexpr (WIN) own = sb == (unsigned)(wr - 1) / 32 && r == (unsigned)(wr - 1) % 32;
            if (own) { // the token's own row: WindowAppendP's bf16b(rd(kv[j])), two per word (low half: even j)
#pragma unroll
                for (unsigned e = 0; e < RW; ++e) {
                    const unsigned w = e * 32 + lane;
                    rv[rr][e] = (uint32_t)ops41::bf16b(A::rd(kv[2 * w])) | ((uint32_t)ops41::bf16b(A::rd(kv[2 * w + 1])) << 16);
                }
                if (hgi == 0) {
                    uint32_t *rrow = reinterpret_cast<uint32_t *>(kvw + (size_t)(p % wr) * HD);
#pragma unroll
                    for (unsigned e = 0; e < RW; ++e) rrow[e * 32 + lane] = rv[rr][e];
                }
            } else {
                const auto x = sg_bloadN<RW>(sg, reinterpret_cast<const uint32_t *>(sycl::select_from_group(sg, ra, r)));
#pragma unroll
                for (unsigned e = 0; e < RW; ++e) rv[rr][e] = x[e];
            }
        }
        float qv[NC];
#pragma unroll
        for (unsigned c0 = 0; c0 < NC; c0 += 8) {
            const auto x = sg_bloadN<8>(sg, qh + 32 * c0);
#pragma unroll
            for (unsigned e = 0; e < 8; ++e) qv[c0 + e] = x[e];
        }
#pragma unroll
        for (unsigned rr = 0; rr < RPG; ++rr)
#pragma unroll
            for (unsigned e = 0; e < RW; ++e) lm[(g + HG * rr) * RS + e * 32 + lane] = rv[rr][e];
        sycl::group_barrier(it.get_group());
        if (!act) return;
        // 2. lane l: slot 32 sb + l's chain over its row (words 16 c .. 16 c + 15 of chunk c, one chunk ahead)
        using V4 = sycl::vec<uint32_t, 4>;
        const V4 *b4 = reinterpret_cast<const V4 *>(lm + lane * RS);
        V4 cur[4], nxt[4];
#pragma unroll
        for (unsigned u = 0; u < 4; ++u) cur[u] = b4[u];
        float acc = 0;
#pragma unroll
        for (unsigned c = 0; c < NC; ++c) {
            if (c + 1 < NC) {
#pragma unroll
                for (unsigned u = 0; u < 4; ++u) nxt[u] = b4[4 * (c + 1) + u];
            }
#pragma unroll
            for (unsigned d = 0; d < 16; ++d) {
                const uint32_t w = cur[d / 4][d % 4];
                acc += sycl::select_from_group(sg, qv[c], 2 * d) * sycl::bit_cast<float>(w << 16);
                acc += sycl::select_from_group(sg, qv[c], 2 * d + 1) * sycl::bit_cast<float>(w & 0xffff0000u);
            }
            if (c + 1 < NC) {
#pragma unroll
                for (unsigned u = 0; u < 4; ++u) cur[u] = nxt[u];
            }
        }
        const float scale = 1.0f / sycl::sqrt(float(hd));
        if (slot >= 0) score[(size_t)h * n_idx + i] = acc * scale;
    }
};

// The output with every slot's piece loaded at once (see the top), NI = the list's slot count (n_idx == NI, a
// multiple of 32, 128 .. 640). Sub-group g loads the pieces of slot pairs g + HG r (r < NI / 2 / HG: lane r holds
// the pair's indices). SM: w holds the raw scores, the weights come from att_softmax_regs (sinks[h]); wout set:
// the column-span-0 work-groups also store the kept slots' weights there (a check; the engine leaves it unset).
// Launch as SparseOutJC: groups(heads) work-groups of WG items, SLM 32-bit words of local memory; run() has
// SparseOutJC's signature (OutMJ below is the block form).
template <unsigned HD, int NI, unsigned HG_ = 16, bool SM = true> struct SparseOutJE {
    static constexpr unsigned HG = HG_, PER_HEAD = HD / 32, NP = (unsigned)NI / 2, NPG = NP / HG, K = (unsigned)NI / 32;
    static constexpr size_t SLM = (size_t)NP * 32, WG = 32 * (size_t)HG;
    static_assert(HD % 64 == 0 && NI % 32 == 0 && NP % HG == 0 && NPG <= 32 && NP % 4 == 0);
    int n_idx, heads, win_rows;
    float *ry = nullptr; // the inverse rope'd copy (as SparseOutJC)
    const float *cosb = nullptr, *sinb = nullptr;
    const float *sinks = nullptr; // SM
    float *wout = nullptr;        // SM, optional
    static size_t groups(int heads) { return (size_t)PER_HEAD * (size_t)((heads + (int)HG - 1) / (int)HG); }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out, uint32_t *lm) const {
        run(it, (unsigned)it.get_group_linear_id(), kvw, kvc, idxs, w, out, lm);
    }
    [[gnu::always_inline]] inline void run(sycl::nd_item<1> it, unsigned grp, const uint16_t *kvw, const uint16_t *kvc,
                                           const int32_t *idxs, const float *w, float *out, uint32_t *lm) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), g = sg.get_group_linear_id();
        const unsigned base = (grp % PER_HEAD) * 32;
        const int h = (int)((grp / PER_HEAD) * HG + g);
        const bool act = h < heads;
        const int wr = win_rows;
        const float *wh = w + (size_t)(act ? h : 0) * NI;
        auto row_addr = [&](int slot) {
            const int s0 = slot < 0 ? 0 : slot;
            return (s0 < wr ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - wr) * HD) + base;
        };
        const unsigned pr = g + HG * lane;
        const int ia = lane < NPG ? idxs[2 * pr] : 0, ib = lane < NPG ? idxs[2 * pr + 1] : 0;
        int csl[K], ok[K];
        float cwl[K];
#pragma unroll
        for (unsigned k = 0; k < K; ++k) {
            csl[k] = idxs[32 * k + lane];
            ok[k] = csl[k] >= 0 ? 1 : 0;
            cwl[k] = wh[32 * k + lane];
        }
        uint16_t pa[NPG], pb[NPG];
#pragma unroll
        for (unsigned r = 0; r < NPG; ++r) {
            pa[r] = sg_bloadN<1>(sg, row_addr(sycl::select_from_group(sg, ia, r)))[0];
            pb[r] = sg_bloadN<1>(sg, row_addr(sycl::select_from_group(sg, ib, r)))[0];
        }
        if constexpr (SM) {
            if (act) {
                att_softmax_regs<(int)K>(sg, cwl, ok, sinks[h]);
                if (wout && grp % PER_HEAD == 0)
#pragma unroll
                    for (unsigned k = 0; k < K; ++k)
                        if (ok[k]) wout[(size_t)h * NI + 32 * k + lane] = cwl[k];
            }
        }
#pragma unroll
        for (unsigned r = 0; r < NPG; ++r) {
            const unsigned pp = g + HG * r;
            lm[((pp / 4) * 32 + lane) * 4 + pp % 4] = (uint32_t)pa[r] | ((uint32_t)pb[r] << 16);
        }
        sycl::group_barrier(it.get_group());
        float o = 0;
        using V4 = sycl::vec<uint32_t, 4>;
        const V4 *b4 = reinterpret_cast<const V4 *>(lm);
        if (act) {
#pragma unroll
            for (unsigned k = 0; k < K; ++k) {
                const bool all = sycl::all_of_group(sg, csl[k] >= 0);
                const uint32_t ml = csl[k] >= 0 ? 0xffffffffu : 0x80000000u;
                V4 x[4];
#pragma unroll
                for (unsigned qd = 0; qd < 4; ++qd) x[qd] = b4[(4 * k + qd) * 32 + lane];
                auto xv = [&](unsigned u) { // slot 32 k + u of this lane's column
                    const uint32_t wd = x[u / 8][(u / 2) % 4];
                    return sycl::bit_cast<float>((u & 1) ? (wd & 0xffff0000u) : (wd << 16));
                };
                if (all) {
#pragma unroll
                    for (unsigned u = 0; u < 32; ++u) o += sycl::select_from_group(sg, cwl[k], u) * xv(u);
                } else {
#pragma unroll
                    for (unsigned u = 0; u < 32; ++u) {
                        const float p0 = sycl::select_from_group(sg, cwl[k], u) * xv(u);
                        o += sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p0) & sycl::select_from_group(sg, ml, u));
                    }
                }
            }
        }
        const float prv = sycl::select_from_group(sg, o, lane ^ 1u);
        if (!act) return;
        out[(size_t)h * HD + base + lane] = o;
        if (ry) { // SparseOutJC's inverse rope on the last 64 columns: pair (2i, 2i + 1) = lanes 2i, 2i + 1
            float a = o;
            if (base >= HD - 64) {
                const unsigned i = (base - (HD - 64) + lane) / 2;
                const float cs = cosb[i], sn = -sinb[i];
                if (lane & 1) {
                    const float re = prv, im = o;
                    a = re * sn + im * cs;
                } else {
                    const float re = o, im = prv;
                    a = re * cs - im * sn;
                }
            }
            ry[(size_t)h * HD + base + lane] = a;
        }
    }
};

// OutMC for SparseOutJE (M tokens; per-token strides is (list), ws (scores, and wout), os (out), rs (ry))
template <typename K> struct OutMJ {
    K k;
    unsigned gpt, m;
    size_t is, ws, os, rs;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const uint16_t *kvw, const uint16_t *kvc, const int32_t *idxs,
                                     const float *w, float *out, uint32_t *lm) const {
        const unsigned grp = (unsigned)it.get_group_linear_id(), t = grp / gpt;
        if (t >= m) return;
        K k2 = k;
        if (k2.ry) {
            k2.ry += t * rs;
            k2.cosb += t * 32;
            k2.sinb += t * 32;
        }
        if (k2.wout) k2.wout += t * ws;
        k2.run(it, grp % gpt, kvw, kvc, idxs + t * is, w + t * ws, out + t * os, lm);
    }
};


// ---- one launch (SparseOutF): the score tiles and the output in the same launch -------------------------------
// Work-groups [0, m * nst) are SparseScoreT<HD, 16, WIN>'s tiles (token t = grp / gpt, as SparseScoreT), then m *
// nout output work-groups (SparseOutJE's split: 16 heads x a 32-column span; token t = og / nout). A tile stores
// its scores, fences (release, device scope), and its item 0 adds 1 to the card's counter cnt[0]. An output work-
// group first loads its list and every slot's 16-byte pieces of its columns (the rows do not depend on the
// scores), stores them into local memory as bf16 pairs, then its item 0 waits until cnt[0] reaches `target` (the
// host's running count: the counts of every earlier launch on this card plus this launch's m * nst), then the
// work-group fences (acquire, device scope), reads the raw scores, runs att_softmax_regs and the output chain.
// Progress: the tiles have the lower work-group ids; the card dispatches work-groups in id order, so every tile is
// dispatched (and finishes) before any output work-group can wait for it, resident or not. A wait past `spin`
// polls stores 1 into err[0] (host memory; the engine fails the step) and the launch goes on with what it read.
// The float operations per output and their order are those of SparseScoreT + att_softmax_regs + SparseOutJE
// (above; bitwise production's). WIN (one token, m = 1, win_rows = 128): WindowAppendP's work as well: the tiles
// compute the list (formula + cidx) and convert the token's own row (window slot 127) from kv into local memory;
// the output work-groups take the own row's piece from kv too, and at their end store WindowAppendP's widx and
// concatenated list (output work-group 0) and the ring row (head group 0: each column span its 32 columns), which
// nothing in this launch reads (the own slot is always taken from kv). n slots: NI (128 .. 640, multiples of 32).
// SHG: heads per score tile, 16 or 8 (8: sub-groups 8-15 only load rows, so a 16-head card runs one score chain per
// vector engine instead of two; twice the tiles). Which SHG and register file the engine launches: att_f_s8 / att_f_grf.
// The kernel arguments: every pointer is a direct argument (SparseOutFK's fields; no pointer inside a struct).
template <int K0, int K, typename T> [[gnu::always_inline]] inline void att_bload_k(sycl::sub_group sg, const T *p, T (&x)[K]) {
    if constexpr (K0 < K) { // x[k] of lane l = p[32 k + l], block loads of 8 / 4 / 2 / 1 elements
        constexpr int R = K - K0, C = R >= 8 ? 8 : R >= 4 ? 4 : R >= 2 ? 2 : 1;
        const auto v = sg_bloadN<C>(sg, p + 32 * K0);
#pragma unroll
        for (int e = 0; e < C; ++e) x[K0 + e] = v[e];
        att_bload_k<K0 + C>(sg, p, x);
    }
}
template <unsigned HD, int NI, bool WIN = false, typename A = ActF32, unsigned SHG = 16> struct SparseOutF {
    using ST = SparseScoreT<HD, 16, WIN, A>;  // (its row layout and local memory)
    using STG = SparseScoreT<HD, SHG, WIN, A>; // (its tile count)
    using AT = A;
    static constexpr unsigned RS = ST::RS, NC = HD / 32, K = (unsigned)NI / 32, PER_HEAD = HD / 32, NP = (unsigned)NI / 2;
    static constexpr unsigned NJ = (4 * K + 15) / 16; // output: 16-byte piece jobs per sub-group (4 K jobs)
    static constexpr size_t WG = 512, SLM_O = (size_t)NP * 32, SLM = ST::SLM > SLM_O ? ST::SLM : SLM_O;
    static constexpr int WR = 128; // WIN: the window's rows (the token's own row: slot 127, tile 3, row 31)
    static_assert(HD == 512 && NI % 32 == 0 && NI >= 128 && NI <= 640 && NP % 4 == 0 && (SHG == 16 || SHG == 8));
    int heads, win_rows, hd; // hd == HD at run time (the scale's expression as production)
    unsigned m = 1;
    size_t qs = 0, is = 0, ss = 0, os = 0, rs = 0; // per-token strides: query, list, scores (and wout), out, ry
    int start_pos = 0, nc = 0;                       // WIN
    uint32_t target = 0;
    long spin = 1L << 22;
    static size_t nst(int heads) { return STG::groups(NI, heads); }
    static size_t nout(int heads) { return (size_t)PER_HEAD * (size_t)((heads + 15) / 16); }
    static size_t groups(int heads, unsigned m) { return (size_t)m * (nst(heads) + nout(heads)); }
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, const float *q, uint16_t *kvw, const uint16_t *kvc, int32_t *idxs,
                                     const typename A::T *kv, const int32_t *cidx, int32_t *widx, float *score, float *out,
                                     float *ry, const float *cosb, const float *sinb, const float *sinks, float *wout,
                                     uint32_t *cnt, uint32_t *err, uint32_t *lm) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), g = sg.get_group_linear_id(), lid = (unsigned)it.get_local_linear_id();
        const unsigned grp = (unsigned)it.get_group_linear_id();
        const unsigned nib = K, nhg = ((unsigned)heads + SHG - 1) / SHG, gpt = nib * nhg;
        const int wr = WIN ? WR : win_rows, p = start_pos;
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::device,
                                    sycl::access::address_space::global_space>;
        using V4 = sycl::vec<uint32_t, 4>;
        // WindowAppendP's list entry x (WIN): the window's slot from its formula, then cidx
        auto win_slot = [&](int x) -> int {
            const int cv = cidx ? cidx[x < WR ? 0 : x - WR] : -1; // (loaded either way: no branch)
            const int j = (p + 1 + x) & (WR - 1);                 // ((p % 128 + 1) % 128 + x) % 128
            return x < WR ? (j > p ? -1 : j) : cv;
        };
        if (grp < m * gpt) { // ---- a score tile: SparseScoreT<HD, 16, WIN>'s arithmetic
            const unsigned t = grp / gpt, r0 = grp % gpt, hgi = r0 / nib, sb = r0 % nib;
            const float *qt = q + t * qs;
            float *sc = score + t * ss;
            const int i = (int)(sb * 32 + lane);
            int slot;
            if constexpr (WIN) slot = win_slot(i);
            else slot = idxs[t * is + i];
            const int h = (int)(hgi * SHG + g);
            const bool act = g < SHG && h < heads; // (SHG 8: sub-groups 8-15 load rows only)
            const float *qh = qt + (size_t)(act ? h : 0) * HD;
            const int s0 = slot < 0 ? 0 : slot;
            const uintptr_t ra = reinterpret_cast<uintptr_t>(s0 < wr ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - wr) * HD);
            // 1. rows g and g + 16 of the 32 (block loads; WIN: the own row's load reads the ring's stale row, not
            //    used), the query, then the rows into local memory (the own row from kv: WindowAppendP's
            //    bf16b(rd(kv[2 w])) | bf16b(rd(kv[2 w + 1])) << 16, words 16 g + l by sub-group g)
            uint32_t rv[2][HD / 64];
#pragma unroll
            for (unsigned rr = 0; rr < 2; ++rr) {
                const auto x = sg_bloadN<HD / 64>(sg, reinterpret_cast<const uint32_t *>(sycl::select_from_group(sg, ra, g + 16 * rr)));
#pragma unroll
                for (unsigned e = 0; e < HD / 64; ++e) rv[rr][e] = x[e];
            }
            uint32_t ownw = 0;
            if constexpr (WIN) {
                const unsigned w = 16 * g + (lane & 15u);
                ownw = (uint32_t)ops41::bf16b(A::rd(kv[2 * w])) | ((uint32_t)ops41::bf16b(A::rd(kv[2 * w + 1])) << 16);
            }
            float qv[NC];
#pragma unroll
            for (unsigned c0 = 0; c0 < NC; c0 += 8) {
                const auto x = sg_bloadN<8>(sg, qh + 32 * c0);
#pragma unroll
                for (unsigned e = 0; e < 8; ++e) qv[c0 + e] = x[e];
            }
            const bool own_tile = WIN && sb == (unsigned)(WR - 1) / 32;
#pragma unroll
            for (unsigned rr = 0; rr < 2; ++rr) {
                const bool skip = own_tile && g + 16 * rr == (unsigned)(WR - 1) % 32;
#pragma unroll
                for (unsigned e = 0; e < HD / 64; ++e)
                    if (!skip) lm[(g + 16 * rr) * RS + e * 32 + lane] = rv[rr][e];
            }
            if (own_tile && lane < 16) lm[((WR - 1) % 32) * RS + 16 * g + lane] = ownw;
            sycl::group_barrier(it.get_group());
            // 2. lane l: slot 32 sb + l's chain over its row (SparseScoreT's)
            if (act) {
                const V4 *b4 = reinterpret_cast<const V4 *>(lm + lane * RS);
                V4 cur[4], nxt[4];
#pragma unroll
                for (unsigned u = 0; u < 4; ++u) cur[u] = b4[u];
                float acc = 0;
#pragma unroll
                for (unsigned c = 0; c < NC; ++c) {
                    if (c + 1 < NC) {
#pragma unroll
                        for (unsigned u = 0; u < 4; ++u) nxt[u] = b4[4 * (c + 1) + u];
                    }
#pragma unroll
                    for (unsigned d = 0; d < 16; ++d) {
                        const uint32_t w = cur[d / 4][d % 4];
                        acc += sycl::select_from_group(sg, qv[c], 2 * d) * sycl::bit_cast<float>(w << 16);
                        acc += sycl::select_from_group(sg, qv[c], 2 * d + 1) * sycl::bit_cast<float>(w & 0xffff0000u);
                    }
                    if (c + 1 < NC) {
#pragma unroll
                        for (unsigned u = 0; u < 4; ++u) cur[u] = nxt[u];
                    }
                }
                const float scale = 1.0f / sycl::sqrt(float(hd));
                if (slot >= 0) sc[(size_t)h * NI + i] = acc * scale;
            }
            // 3. done: release this tile's scores, then count it
            sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::device);
            sycl::group_barrier(it.get_group());
            if (lid == 0) AR(*cnt).fetch_add(1u);
            return;
        }
        // ---- an output work-group: SparseOutJE<HD, NI, 16, true>'s arithmetic
        const unsigned og = grp - m * gpt, gpo = (unsigned)nout(heads), t = og / gpo, oj = og % gpo;
        const int32_t *ix = idxs + t * is;
        const unsigned base = (oj % PER_HEAD) * 32;
        const int h = (int)((oj / PER_HEAD) * 16 + g);
        const bool act = h < heads;
        auto row_addr = [&](int slot) {
            const int s0 = slot < 0 ? 0 : slot;
            return (s0 < wr ? kvw + (size_t)s0 * HD : kvc + (size_t)(s0 - wr) * HD) + base;
        };
        int cv0 = 0, cv1 = 0; // WIN, output work-group 0: WindowAppendP's list entries lid and 512 + lid
        if constexpr (WIN) {
            if (og == 0) {
                auto wl = [&](int x) -> int {
                    if (x < WR) {
                        const int j = (p + 1 + x) & (WR - 1);
                        return j > p ? -1 : j;
                    }
                    return x < WR + nc ? cidx[x - WR] : 0;
                };
                cv0 = wl((int)lid);
                cv1 = wl(512 + (int)lid);
            }
        }
        // 1. the list (lane l: slot 32 k + l in csl[k]; kept: >= 0)
        int csl[K];
        if constexpr (WIN) {
#pragma unroll
            for (unsigned k = 0; k < K; ++k) {
                const int i = (int)(32 * k + lane);
                if (32 * k < (unsigned)WR) {
                    const int j = (p + 1 + i) & (WR - 1);
                    csl[k] = j > p ? -1 : j;
                } else {
                    csl[k] = cidx[i - WR];
                }
            }
        } else {
            att_bload_k<0>(sg, ix, csl);
        }
        // 2. the row pieces: 4 K jobs (32-slot block k = jb / 4, 16-byte piece pj = jb % 4); sub-group g takes jobs
        //    g + 16 it; lane l loads slot 32 k + l's columns base + 8 pj .. + 7 (the slot index read again here,
        //    not taken from csl: no per-block selects between the loads). WIN: the own slot (127, job 12 + pj, run
        //    by sub-group 12 + pj) takes its piece from kv
        uint32_t ownc[4] = {};
        if constexpr (WIN) {
            const typename A::T *kp = kv + base + 8 * (g % 4);
#pragma unroll
            for (unsigned e = 0; e < 4; ++e)
                ownc[e] = (uint32_t)ops41::bf16b(A::rd(kp[2 * e])) | ((uint32_t)ops41::bf16b(A::rd(kp[2 * e + 1])) << 16);
        }
        V4 xr[NJ];
#pragma unroll
        for (unsigned it2 = 0; it2 < NJ; ++it2) {
            const unsigned jb = g + 16 * it2, k = jb < 4 * K ? jb / 4 : 0, pj = jb % 4;
            const int i = (int)(32 * k + lane);
            int sl;
            if constexpr (WIN) sl = win_slot(i);
            else sl = ix[i];
            V4 x = *reinterpret_cast<const V4 *>(row_addr(sl) + 8 * pj);
            if constexpr (WIN) {
                const bool own = i == WR - 1;
#pragma unroll
                for (unsigned e = 0; e < 4; ++e) x[e] = own ? ownc[e] : (uint32_t)x[e];
            }
            xr[it2] = x;
        }
        // 3. into local memory as bf16 pairs (SparseOutJE's layout: word ((p / 4) * 32 + c) * 4 + p % 4 holds slots
        //    2 p (low half) and 2 p + 1 (high half) of column base + c); lane pairs swap halves
        const bool odd = lane & 1u;
#pragma unroll
        for (unsigned it2 = 0; it2 < NJ; ++it2) {
            const unsigned jb = g + 16 * it2;
            if (jb < 4 * K) {
                const unsigned k = jb / 4, pj = jb % 4;
                const V4 x = xr[it2];
                const unsigned pp = 16 * k + lane / 2;
#pragma unroll
                for (unsigned e = 0; e < 4; ++e) {
                    const uint32_t y = sycl::permute_group_by_xor(sg, (uint32_t)x[e], 1u);
                    const uint32_t wd = odd ? ((y >> 16) | (x[e] & 0xffff0000u)) : ((x[e] & 0xffffu) | (y << 16));
                    const unsigned c = 8 * pj + 2 * e + (odd ? 1u : 0u);
                    lm[((pp / 4) * 32 + c) * 4 + pp % 4] = wd;
                }
            }
        }
        // 4. wait for this launch's score tiles
        if (lid == 0) {
            AR c(*cnt);
            long s_ = 0;
            while ((int32_t)(c.load() - target) < 0 && ++s_ < spin) {}
            if (s_ >= spin) err[0] = 1u;
        }
        sycl::group_barrier(it.get_group());
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::device);
        // 5. the softmax on the raw scores (att_softmax_regs), then the chain (SparseOutJE's)
        const float *wh = score + t * ss + (size_t)(act ? h : 0) * NI;
        float cwl[K];
        att_bload_k<0>(sg, wh, cwl);
        if (act) {
            att_softmax_regs<(int)K, true>(sg, cwl, csl, sinks[h]);
            if (wout && oj % PER_HEAD == 0)
#pragma unroll
                for (unsigned k = 0; k < K; ++k)
                    if (csl[k] >= 0) wout[t * ss + (size_t)h * NI + 32 * k + lane] = cwl[k];
        }
        float o = 0;
        const V4 *b4 = reinterpret_cast<const V4 *>(lm);
        if (act) {
#pragma unroll
            for (unsigned k = 0; k < K; ++k) {
                const bool all = sycl::all_of_group(sg, csl[k] >= 0);
                const uint32_t ml = csl[k] >= 0 ? 0xffffffffu : 0x80000000u;
                V4 x[4];
#pragma unroll
                for (unsigned qd = 0; qd < 4; ++qd) x[qd] = b4[(4 * k + qd) * 32 + lane];
                auto xv = [&](unsigned u) {
                    const uint32_t wd = x[u / 8][(u / 2) % 4];
                    return sycl::bit_cast<float>((u & 1) ? (wd & 0xffff0000u) : (wd << 16));
                };
                if (all) {
#pragma unroll
                    for (unsigned u = 0; u < 32; ++u) o += sycl::select_from_group(sg, cwl[k], u) * xv(u);
                } else {
#pragma unroll
                    for (unsigned u = 0; u < 32; ++u) {
                        const float p0 = sycl::select_from_group(sg, cwl[k], u) * xv(u);
                        o += sycl::bit_cast<float>(sycl::bit_cast<uint32_t>(p0) & sycl::select_from_group(sg, ml, u));
                    }
                }
            }
        }
        // 6. WIN: WindowAppendP's stores (nothing in this launch reads them)
        if constexpr (WIN) {
            if (og == 0) {
                if ((int)lid < WR) widx[lid] = cv0;
                if ((int)lid < WR + nc) idxs[lid] = cv0;
                if (512 + (int)lid < WR + nc) idxs[512 + lid] = cv1;
            }
            if (oj / PER_HEAD == 0 && g == 0) // head group 0: this span's 32 columns of the token's own ring row
                kvw[(size_t)(p % WR) * HD + base + lane] = ops41::bf16b(A::rd(kv[base + lane]));
        }
        // 7. the output and its inverse rope'd copy (SparseOutJC's expressions)
        const float prv = sycl::select_from_group(sg, o, lane ^ 1u);
        if (!act) return;
        out[t * os + (size_t)h * HD + base + lane] = o;
        if (ry) {
            float a = o;
            if (base >= HD - 64) {
                const unsigned i = (base - (HD - 64) + lane) / 2;
                const float cs = cosb[t * 32 + i], sn = -sinb[t * 32 + i];
                if (lane & 1) {
                    const float re = prv, im = o;
                    a = re * sn + im * cs;
                } else {
                    const float re = o, im = prv;
                    a = re * cs - im * sn;
                }
            }
            ry[t * rs + (size_t)h * HD + base + lane] = a;
        }
    }
};
// The forms the engine launches (card 3, bench_attn_a1 between 128-register kernels as in the engine, whose decode
// kernels all run at 128 registers: a 256-register launch costs two register-mode changes, ~1.3 us each).
// Registers: 128 up to 288 slots with the window append (320+: 15.4 vs 13.7 us at 256) and up to 512 slots without it
// (640: 24.9 vs 21.3 us at 256). Score tiles of 8 heads (sub-groups 8-15 load rows only; on a 16-head card one chain
// per vector engine instead of two): -0.5..-0.7 us on 16 heads at one token up to 448 slots (with the window append)
// or 384 (blocks of 1) and in blocks of 2 up to 192 slots; 16 heads per tile elsewhere (fewer tiles, fewer rows)
template <int NI, bool WIN> constexpr unsigned att_f_grf() { return WIN ? (NI <= 288 ? 128u : 256u) : (NI <= 512 ? 128u : 256u); }
inline bool att_f_s8(int ni, bool win, unsigned m) { return win ? ni <= 448 : ((m == 1 && ni <= 384) || (m <= 2 && ni <= 192)); }
// SparseOutF's kernel: the pointers as direct kernel arguments, the register file size GRF (128 or 256; the build's
// auto mode would pick per kernel) and 32-lane sub-groups
template <typename K, unsigned GRF> struct SparseOutFK {
    K k;
    const float *q;
    uint16_t *kvw;
    const uint16_t *kvc;
    int32_t *idxs;
    const typename K::AT::T *kv;
    const int32_t *cidx;
    int32_t *widx;
    float *score, *out, *ry;
    const float *cosb, *sinb, *sinks;
    float *wout;
    uint32_t *cnt, *err;
    sycl::local_accessor<uint32_t, 1> lt;
    void operator()(sycl::nd_item<1> it) const {
        k(it, q, kvw, kvc, idxs, kv, cidx, widx, score, out, ry, cosb, sinb, sinks, wout, cnt, err, &lt[0]);
    }
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<GRF>,
                                                           sycl::ext::oneapi::experimental::sub_group_size<32>};
    }
};

} // namespace ops41sycl
