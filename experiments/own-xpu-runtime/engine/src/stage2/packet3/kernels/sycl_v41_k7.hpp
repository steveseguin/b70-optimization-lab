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
// beside XchgP's own work-group 0, which runs XchgP unchanged). Each partial work-group pushes its row's partial
// to every card and raises that row's flag there. After HcPostPreP the receiving launch (SkNormK7) runs the
// norm alone on work-group 0 (SkNormSplit<5120, 16>, SkNormW's code) and on work-group 1 adds the six cards'
// partials, runs SkDotsFF's check on the sum and, where it fails, writes production's partials from the
// gathered streams (HcMixDotsP::row, as SkDotsFF's fallback). One card (bench_k7, cold, median): SkNormK7 3.4 us
// against SkNormDotsW<8>'s 6.0 (the norm alone 2.4); XchgPK7 2.7 us over XchgP's push (hidden while XchgP waits
// for its peers, ~5 us per exchange on every card in xw92).
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
// [K7_OFF, K7_OFF + 6 K7_SLOT) = [256, 856): slot d (sender d) row r at K7_OFF + K7_SLOT d + 4 r: words 0, 1 =
// T_d(r) (double), 2 = E_d(r) (float bits), 3 = the row's flag (the K7 exchange's number, stored after a system
// release fence). Copied as 32-bit words, never as floats. Slot d is rewritten by d's next K7 exchange only after d
// passed an exchange that waits for this card's flag, which this card publishes after its SkNormK7 (in-order
// queue; between two K7 exchanges every card runs at least one waiting exchange): the reads always come first
// (the argument the ob region's reuse rests on as well).
#pragma once
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>

namespace ops41sycl {

constexpr unsigned K7_OFF = 256, K7_SLOT = 100, K7_ROWS = 25;

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

// The h exchange with the partials (replaces XchgP's launch_wg(c, 256, ...) at the K7 sites; 26 work-groups of 256):
// work-group 0 runs XchgP (x, unchanged: push this card's rows, flags, wait for every peer's), work-group 1 + r row
// r's partial (K7Part) over this card's rows [x.r0, x.r1) of the output in its own arena (x.off: the 5,120 output
// floats); then lane d < n of its sub-group 0 stores the row's three words into card d's slot x.me (this card's own
// arena too), a system release fence, and (d != me) the row's flag x.seq. No counter, no last work-group: every row
// travels on its own. 128 registers, like XchgP; every pointer a direct kernel argument.
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
        if (g == 0) {
            x(it, p0, p1, p2, p3, p4, p5, err);
            return;
        }
        const unsigned r = g - 1;
        float *mine = XchgP::pick(x.me, p0, p1, p2, p3, p4, p5);
        double T;
        float E;
        if (!K7Part::run(it, r, x.r0, x.r1, streams, mine + x.off, post, comb, fn, &lm[0], T, E)) return;
        sycl::sub_group sg = it.get_sub_group();
        const int lane = (int)sg.get_local_linear_id();
        T = sycl::select_from_group(sg, T, 0);
        E = sycl::select_from_group(sg, E, 0);
        uint32_t *rec = nullptr;
        if (lane < x.n) {
            rec = reinterpret_cast<uint32_t *>(XchgP::pick(lane, p0, p1, p2, p3, p4, p5)) + K7_OFF +
                  K7_SLOT * (unsigned)x.me + 4 * r;
            sk_put(rec, 0, T);
            rec[2] = sycl::bit_cast<uint32_t>(E);
        }
        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
        if (lane < x.n && lane != x.me) AR(rec[3]).store(x.seq);
    }
    auto get(sycl::ext::oneapi::experimental::properties_tag) const {
        return sycl::ext::oneapi::experimental::properties{sycl::ext::intel::experimental::grf_size<128>,
                                                           sycl::ext::oneapi::experimental::sub_group_size<32>};
    }
};

// The receiving side (replaces SkNormDotsW<8>'s launch_wgl<64>(c, 26, 512, ...); 2 work-groups of 512):
// work-group 0 the 5,120 pre-norm (SkNormSplit<5120, 16>::run: SkNormW's and SkNormDotsW's work-group 0, the same
// y). Work-group 1: item L < 25 (n - 1) polls one (row, peer) flag (XchgP's wait: poll, poison, err = 1 + that peer;
// one round trip for all 125 instead of five in a row); items 128.. prefetch the six slots' and the 200 partials'
// cache lines meanwhile (a hint only: the data is read after the acquire); every item the system acquire, one
// barrier; then rows 0..23 on sub-group 0 and row 24 (the check with the double square root) on sub-group 1, in
// parallel: add the n cards' T_d(r) (doubles) and E_d(r) (floats) in card order, SkDotsFF<8>::check; a pass
// stores d[8 r] = T, d[8 r + 1 .. 7] = +0.0. After a second barrier the failing rows (and the rows in force, a
// bench-only mask: 0 in the engine) run as HcMixDotsP::row on the gathered streams (sub-groups 0..7 one failing
// row, 8..15 the next): production's partials; with no failing row the work-group ends there. mine: this card's
// arena.
struct SkNormK7 {
    int n, me;
    uint32_t seq;
    long spin;
    uint32_t force;
    const float *x, *w;
    float *y;
    const float *streams, *fn;
    double *out;
    float *mine;
    uint32_t *err;
    sycl::local_accessor<uint32_t, 1> lm; // 64 words
    void operator()(sycl::nd_item<1> it) const {
        namespace ex = sycl::ext::oneapi::experimental;
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id(), sgi = sg.get_group_linear_id();
        uint32_t *l = &lm[0];
        if (it.get_group_linear_id() == 0) {
            SkNormSplit<5120, 16>::run(it, sgi, l, 0, x, w, y);
            return;
        }
        uint32_t *m32 = reinterpret_cast<uint32_t *>(mine);
        const unsigned L = 32 * sgi + lane, np = (unsigned)n - 1;
        constexpr unsigned SLOT_LINES = (6 * K7_SLOT * 4 + 63) / 64;
        if (L >= 128 && L < 128 + SLOT_LINES)
            ex::prefetch((void *)(m32 + K7_OFF + 16 * (L - 128)), ex::properties{ex::prefetch_hint_L1});
        if (L >= 192 && L < 192 + K7_ROWS)
            ex::prefetch((void *)(out + 8 * (L - 192)), ex::properties{ex::prefetch_hint_L1});
        if (L < K7_ROWS * np) {
            const unsigned r = L / np, k = L % np;
            const int d = (int)k < me ? (int)k : (int)k + 1;
            AR poison(m32[96]);
            AR f(m32[K7_OFF + K7_SLOT * (unsigned)d + 4 * r + 3]);
            long s = 0;
            if (!poison.load())
                while (f.load() < seq && ++s < spin) {}
            if (s >= spin) {
                poison.store(1u);
                err[0] = 1u + (uint32_t)d;
            }
        }
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
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
