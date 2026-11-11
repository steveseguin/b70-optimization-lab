// K7 (2026-11-11, OWN_K7; /home/steve/dsv41-work/k7, bench bench_k7.cpp): the stream mix's 25 dot rows over the
// cards' own model rows, computed before the h exchange that gathers the sublayer output and carried to every
// card beside it. One-token tensor-parallel steps only (Backend41::tp_phase cases 2 / 4 -> 3 / next layer's 0).
//
// Today (OWN_K7=0): after the h exchange every card runs HcPostPreP (the new streams, the pre-norm input) and then
// SkNormDotsW<8>: the 5,120 pre-norm on one work-group and the 25 dot rows (24 fn rows of 20,480 + the streams'
// sum of squares) on 25 more, each reading a whole fn row (2 MB per launch, 152 MB per step and card).
// K7: before the exchange card c holds the new sublayer output for its own model rows [r0, r1) (848 / 864 of
// 5,120) and the old streams in full, so it can form the new streams' 4 x (r1 - r0) values of those columns
// (HcPostPreP's expression, the same floats) and the 25 dot partials over them (XchgPK7, work-groups 1..25,
// beside XchgP's own work-group 0). Transport (k7-2): the partials travel exactly as XchgP's rows do. Each partial
// work-group stores its row into this card's own slot and raises the row's local flag; work-group 0 pushes the
// output rows and raises the h flags (XchgP, push only), waits for its 25 local rows, copies the slot into every
// peer's arena, fences, barriers and raises one K7 flag per peer (a word alone on its 64-byte line), then waits for
// the peers' h flags (XchgP, wait only). The receiving card waits for the peers' K7 flags in one extra work-group
// of its HcPostPreP launch (HcPostPreK7: HcPostPreP's work-groups run unchanged), and SkNormK7, the next launch,
// reads the slots: no wait in the reading launch. After HcPostPreP the receiving launch (SkNormK7) runs the
// norm alone on work-group 0 (SkNormSplit<5120, 16>, SkNormW's code) and on work-group 1 adds the six cards'
// partials, runs SkDotsFF's check on the sum and, where it fails, writes production's partials from the
// gathered streams (HcMixDotsP::row, as SkDotsFF's fallback).
// Why k7-1 failed on six cards (tg96, 2026-11-11: time-outs on every K7 run, the first traced step already off
// at layer 1's FFN mix): it broke the two rules of xchg_direct_bench / OWN_QB_OFF. Its SkNormK7 polled per-row
// flags and read (even prefetched into L1) the records in the same launch, so it could read the previous round's
// cached lines; and its records, flags and slots shared 64-byte lines across senders and with this card's own
// record stores and 125 atomic read-modify-write polls, so a line written back by the receiver could cover a peer's
// newer words (flags included). One card cannot show either (all writes come from one GPU; the bench ran the
// senders before the receivers). k7-2 keeps both rules: every line a peer writes is written by that peer only
// (slots and flags line-aligned, the receiver never stores or polls a data line), flags alone on their lines and
// polled with XchgP's own code, and the slots read only by a later launch than the wait.
//
// Why the finish's outputs are production's bit for bit. Notation: u = 2^-24, v = 2^-53, a row's terms x_i = b_i a_i
// (b: the fn value, or a itself for the sum of squares; a: a new stream value, the float HcPostPreP stores),
// s = sum x_i exactly, E = sum |x_i|. Production's chain (HcMixDotsP + the finish's sum of 8 segments) obeys
// |t_chain - s| <= gamma_91 E = 1.0103e-14 E (SkDotsFF's proof). K7's sum T:
//   - card c, item i: columns j..j+3 of its slice for the 4 streams = 16 exact-product terms in two float-float
//     blocks of K = 8 (streams 0-1, streams 2-3; SkDotsFF's block code): each block's low sum rounds by
//     <= K (K + 1) u^2 E_b; each block's (hi, lo) added in double: 4 double adds;
//   - the 32-lane xor tree (5 adds), the 8 sub-group partials in an xor tree (3), the six cards' T_c added in
//     card order on the receiver (<= 5): at most 4 + 5 + 3 + 5 = 17 double adds on any leaf-to-root path
//     (SkDotsFF: 30). So |T - s| <= K (K + 1) u^2 E + gamma_17 E (+ underflow: the same 20,480 terms and the same
//     per-term float operations as SkDotsFF, < 6e-41 in all);
//   - together |T - t_chain| <= (72 u^2 + gamma_17 + gamma_91) E = (2.5580e-13 + 1.887e-15 + 1.0103e-14) E
//     = 2.678e-13 E < CK E with SkDotsFF<8>'s CK = 2.8e-13, the constant its check already uses;
//   - E as SkDotsFF forms it, a float sum of |p| (p = fl(b a)), over at most 16 + 5 + 3 + 5 = 29 float adds on a
//     path: E_float >= E (1 - u)^30, so E <= E_float (1 + 1.8e-6) < E_up = E_float (1 + 1e-5) (SkDotsFF's E_up).
// So SkDotsFF<8>::check(r, T, E) proves float(t_chain) == float(T) (r < 24) and production's float rsqrt for
// r = 24, exactly as in SkNormDotsW; a passing row writes d[8 r] = T, d[8 r + 1 .. 7] = +0.0 (the finish's sum is
// exactly T, T != 0), a failing row production's 8 partials. Every card adds the same six partials in the same
// order, so every card writes the same 200 doubles. The fallback has every input it needs: the receiving launch
// runs after HcPostPreP in the card's in-order queue (the gathered new streams) and every card holds every fn row.
//
// Arena words (floats of every card's exchange arena, inside the flags block [0, 1024): words 16 d = XchgP's
// flags, 96 = the poison word, 128 + 16 d + g (g < 16) = OWN_QB_OFF's flags, sycl_v41_qboff.hpp): K7 uses words
// [K7_OFF, 1024) = [256, 1024): slot d (sender d) at K7_OFF + K7_SLOT d (112 words = 7 whole lines), row r's record
// at + 4 r: words 0, 1 = T_d(r) (double), 2 = E_d(r) (float bits), 3 = the row's local flag (the exchange's
// number; meaningful in the sender's own slot only, copied along); K7 flag of sender d at K7_FLAG + 16 d
// (K7_FLAG = 928, one 64-byte line each, written only by d with d's exchange number after its slot copy). Copied
// as 32-bit words, never as floats. Slot d of this card is rewritten by d's next K7 exchange only after d passed
// an exchange that waits for this card's flag, which this card publishes after its SkNormK7 (in-order queue;
// between two K7 exchanges every card runs at least one waiting exchange): the reads always come first (the
// argument the ob region's reuse rests on as well).
#pragma once
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>

namespace ops41sycl {

constexpr unsigned K7_OFF = 256, K7_SLOT = 112, K7_ROWS = 25, K7_FLAG = K7_OFF + 6 * K7_SLOT;

// row r's partial over the columns [r0, r1) (multiples of 4, r1 - r0 <= 4 * 256) of the new streams, one work-group
// of 256 items. Returns true on sub-group 0, whose lanes 0..7 then hold T (the row's double sum) and E (the float
// sum of |p|); the other sub-groups return false and must not touch lm again. lm: 24 words.
struct K7Part {
    static constexpr unsigned H = 5120, N = 4 * H, WG = 256, NSG = WG / 32;
    [[gnu::always_inline]] static inline bool run(sycl::nd_item<1> it, unsigned r, unsigned r0, unsigned r1,
                                                  const float *streams, const float *ob, const float *post,
                                                  const float *comb, const float *fn, uint32_t *lm, double &T,
                                                  float &E) {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), sgi = sg.get_group_linear_id();
        const unsigned i = (unsigned)it.get_local_linear_id(), ncg = (r1 - r0) / 4;
        double acc = 0;
        float ef = 0;
        if (i < ncg) {
            const unsigned j = r0 + 4 * i;
            sycl::vec<float, 4> o[4];
#pragma unroll
            for (unsigned k = 0; k < 4; ++k) o[k] = *reinterpret_cast<const sycl::vec<float, 4> *>(streams + k * H + j);
            const sycl::vec<float, 4> xv = *reinterpret_cast<const sycl::vec<float, 4> *>(ob + j);
            float a[4][4]; // a[s][m]: new stream s at column j + m, HcPostPreP's expression (no contraction)
#pragma unroll
            for (unsigned m = 0; m < 4; ++m) {
                const float xi = xv[m];
#pragma unroll
                for (unsigned s = 0; s < 4; ++s) {
                    float t = post[s] * xi;
#pragma unroll
                    for (unsigned k = 0; k < 4; ++k) t += comb[k * 4 + s] * o[k][m];
                    a[s][m] = t;
                }
            }
            float b[4][4];
            if (r < 24) {
#pragma unroll
                for (unsigned s = 0; s < 4; ++s) {
                    const sycl::vec<float, 4> f =
                        *reinterpret_cast<const sycl::vec<float, 4> *>(fn + (size_t)r * N + s * H + j);
#pragma unroll
                    for (unsigned m = 0; m < 4; ++m) b[s][m] = f[m];
                }
            } else {
#pragma unroll
                for (unsigned s = 0; s < 4; ++s)
#pragma unroll
                    for (unsigned m = 0; m < 4; ++m) b[s][m] = a[s][m];
            }
#pragma unroll
            for (unsigned blk = 0; blk < 2; ++blk) { // SkDotsFF's float-float block, K = 8 terms
                float hi = 0, lo = 0;
#pragma unroll
                for (unsigned s = 2 * blk; s < 2 * blk + 2; ++s)
#pragma unroll
                    for (unsigned m = 0; m < 4; ++m) {
                        const float p = b[s][m] * a[s][m];
                        const float e = sycl::fma(b[s][m], a[s][m], -p);
                        const float t = hi + p;
                        const float z = t - hi;
                        const float er = (hi - (t - z)) + (p - z);
                        hi = t;
                        lo = lo + (er + e);
                        ef = ef + sycl::fabs(p);
                    }
                acc = acc + double(hi);
                acc = acc + double(lo);
            }
        }
        for (int w = 16; w; w >>= 1) {
            acc += sycl::select_from_group(sg, acc, (int)lane ^ w);
            ef += sycl::select_from_group(sg, ef, (int)lane ^ w);
        }
        if (lane == 0) {
            sk_put(lm, (int)sgi, acc);
            lm[2 * NSG + sgi] = sycl::bit_cast<uint32_t>(ef);
        }
        sycl::group_barrier(it.get_group());
        if (sgi != 0) return false;
        T = lane < NSG ? sk_get(lm, (int)lane) : 0.0;
        E = lane < NSG ? sycl::bit_cast<float>(lm[2 * NSG + lane]) : 0.0f;
        for (int w = 1; w < (int)NSG; w <<= 1) {
            T += sycl::select_from_group(sg, T, (int)lane ^ w);
            E += sycl::select_from_group(sg, E, (int)lane ^ w);
        }
        return true;
    }
};

// The h exchange with the partials (replaces XchgP's launch_wg(c, 256, ...) at the K7 sites; 26 work-groups of 256).
// Work-group 1 + r: row r's partial (K7Part) over this card's rows [x.r0, x.r1) of the output in its own arena
// (x.off: the 5,120 output floats); lane 0 stores the row's three words into this card's own slot x.me, a release
// fence, then the row's local flag (word 3) = x.seq. Work-group 0: XchgP push only (x's rows into every peer, the h
// flags), then items t < 25 wait for the local flags (this card's own memory, written by this launch), acquire,
// barrier; items t < 100 read the slot's words (atomic loads: the lines were written by other work-groups of this
// launch) and store them into every peer's slot x.me; system release fence, barrier, items t < n (t != me) store
// x.seq into peer t's K7 flag K7_FLAG + 16 me (XchgP's flag code); then, for x.mode == 0, XchgP's wait for every
// peer's h flag (mode 2, the same seq). x.mode == 1 (bench): no wait. 128 registers, like XchgP; every pointer a
// direct kernel argument.
struct XchgPK7 {
    XchgP x;
    float *p0, *p1, *p2, *p3, *p4, *p5;
    uint32_t *err;
    const float *streams, *post, *comb, *fn;
    sycl::local_accessor<uint32_t, 1> lm; // 32 words
    void operator()(sycl::nd_item<1> it) const {
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        const unsigned g = (unsigned)it.get_group_linear_id();
        float *mine = XchgP::pick(x.me, p0, p1, p2, p3, p4, p5);
        uint32_t *own = reinterpret_cast<uint32_t *>(mine) + K7_OFF + K7_SLOT * (unsigned)x.me;
        if (g == 0) {
            XchgP xs = x;
            xs.mode = 1; // push this card's rows + the h flags
            xs(it, p0, p1, p2, p3, p4, p5, err);
            const unsigned t = (unsigned)it.get_local_linear_id();
            if (t < K7_ROWS) { // the 25 local rows (XchgP's wait form on this card's own words)
                AR poison(reinterpret_cast<uint32_t *>(mine)[96]);
                AR f(own[4 * t + 3]);
                long s = 0;
                if (!poison.load())
                    while (f.load() < x.seq && ++s < x.spin) {}
                if (s >= x.spin) {
                    poison.store(1u);
                    err[0] = 1u + (uint32_t)x.me;
                }
            }
            sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
            sycl::group_barrier(it.get_group());
            if (t < 4 * K7_ROWS) {
                const uint32_t v = AR(own[t]).load();
                for (int d = 0; d < x.n; ++d)
                    if (d != x.me)
                        reinterpret_cast<uint32_t *>(XchgP::pick(d, p0, p1, p2, p3, p4, p5))[K7_OFF +
                                                                                             K7_SLOT * (unsigned)x.me + t] = v;
            }
            sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
            sycl::group_barrier(it.get_group());
            if ((int)t < x.n && (int)t != x.me)
                AR(reinterpret_cast<uint32_t *>(XchgP::pick((int)t, p0, p1, p2, p3, p4, p5))[K7_FLAG + 16 * (unsigned)x.me])
                    .store(x.seq);
            if (x.mode == 0) {
                XchgP xw = x;
                xw.mode = 2; // wait for every peer's h flag (>= the same seq)
                xw(it, p0, p1, p2, p3, p4, p5, err);
            }
            return;
        }
        const unsigned r = g - 1;
        double T;
        float E;
        if (!K7Part::run(it, r, x.r0, x.r1, streams, mine + x.off, post, comb, fn, &lm[0], T, E)) return;
        sycl::sub_group sg = it.get_sub_group();
        if (sg.get_local_linear_id() == 0) {
            sk_put(own + 4 * r, 0, T);
            own[4 * r + 2] = sycl::bit_cast<uint32_t>(E);
            sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
            AR(own[4 * r + 3]).store(x.seq);
        }
    }
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<128>,
                                                           sycl::ext::oneapi::experimental::sub_group_size<32>};
    }
};

// The receiving card's HcPostPreP launch at a K7 site (replaces launch(c, h, 64, HcPostPreP{h}, ...); nmain + 1
// work-groups of 64): work-groups [0, nmain) run HcPostPreP exactly as launched alone (the same items, the same
// global ids, the same code: the same new streams and pre-norm input); work-group nmain's items t < n (t != me)
// wait for peer t's K7 flag (word K7_FLAG + 16 t of this card's arena >= seq; XchgP's wait: poll, poison,
// err = 1 + t), acquire, barrier. The slots are read by SkNormK7, the next launch. mine: this card's arena.
template <typename A> struct HcPostPreK7 {
    HcPostPreP<A> k;
    unsigned nmain;
    int n, me;
    uint32_t seq;
    long spin;
    void operator()(sycl::nd_item<1> it, typename A::T *streams, const typename A::T *x, const float *post,
                    const float *comb, const float *pre_src, float *pre_dst, const float *mix, typename A::T *out,
                    float *mine, uint32_t *err) const {
        if ((unsigned)it.get_group_linear_id() < nmain) {
            k(it, streams, x, post, comb, pre_src, pre_dst, mix, out);
            return;
        }
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        const unsigned t = (unsigned)it.get_local_linear_id();
        if ((int)t < n && (int)t != me) {
            AR poison(reinterpret_cast<uint32_t *>(mine)[96]);
            AR f(reinterpret_cast<uint32_t *>(mine)[K7_FLAG + 16 * t]);
            long s = 0;
            if (!poison.load())
                while (f.load() < seq && ++s < spin) {}
            if (s >= spin) {
                poison.store(1u);
                err[0] = 1u + t;
            }
        }
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
    }
};

// The receiving side (replaces SkNormDotsW<8>'s launch_wgl<64>(c, 26, 512, ...); 2 work-groups of 512), the launch
// after HcPostPreK7 (which waited for every peer's K7 flag): work-group 0 the 5,120 pre-norm (SkNormSplit<5120,
// 16>::run: SkNormW's and SkNormDotsW's work-group 0, the same y). Work-group 1: rows 0..23 on sub-group 0 and
// row 24 (the check with the double square root) on sub-group 1, in parallel: add the n cards' T_d(r) (doubles) and
// E_d(r) (floats) in card order, SkDotsFF<8>::check; a pass stores d[8 r] = T, d[8 r + 1 .. 7] = +0.0. After a
// barrier the failing rows (and the rows in force, a bench-only mask: 0 in the engine) run as HcMixDotsP::row on
// the gathered streams (sub-groups 0..7 one failing row, 8..15 the next): production's partials; with no failing
// row the work-group ends there. mine: this card's arena (the slots, read only here).
struct SkNormK7 {
    int n;
    uint32_t force;
    const float *x, *w;
    float *y;
    const float *streams, *fn;
    double *out;
    const float *mine;
    sycl::local_accessor<uint32_t, 1> lm; // 64 words
    void operator()(sycl::nd_item<1> it) const {
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), sgi = sg.get_group_linear_id();
        uint32_t *l = &lm[0];
        if (it.get_group_linear_id() == 0) {
            SkNormSplit<5120, 16>::run(it, sgi, l, 0, x, w, y);
            return;
        }
        const uint32_t *m32 = reinterpret_cast<const uint32_t *>(mine);
        if (sgi < 2) {
            const bool row = sgi == 0 ? lane < 24 : lane == 0;
            const unsigned r = sgi == 0 ? lane : 24u;
            bool ok = false;
            if (row) {
                const uint32_t *b = m32 + K7_OFF + 4 * r;
                double T = sk_get(b, 0);
                float E = sycl::bit_cast<float>(b[2]);
                for (int d = 1; d < n; ++d) {
                    T = T + sk_get(b + K7_SLOT * (unsigned)d, 0);
                    E = E + sycl::bit_cast<float>(b[K7_SLOT * (unsigned)d + 2]);
                }
                ok = !((force >> r) & 1u) && SkDotsFF<8>::check(r, T, E);
                if (ok)
#pragma unroll
                    for (unsigned k = 0; k < 8; ++k) out[r * 8 + k] = k == 0 ? T : 0.0;
            }
            const uint32_t fl = sycl::reduce_over_group(sg, row && !ok ? 1u << r : 0u, sycl::bit_or<uint32_t>());
            if (lane == 0) l[sgi] = fl;
        }
        sycl::group_barrier(it.get_group());
        const uint32_t fail = l[0] | l[1];
        if (fail == 0) return;
        unsigned q = 0;
        for (unsigned r = 0; r < K7_ROWS; ++r)
            if ((fail >> r) & 1u) {
                if ((q & 1u) == (sgi >> 3)) HcMixDotsP<5120, 8>::row(sg, lane, r * 8 + (sgi & 7u), streams, fn, out);
                ++q;
            }
    }
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<128>,
                                                           sycl::ext::oneapi::experimental::sub_group_size<32>};
    }
};

} // namespace ops41sycl
