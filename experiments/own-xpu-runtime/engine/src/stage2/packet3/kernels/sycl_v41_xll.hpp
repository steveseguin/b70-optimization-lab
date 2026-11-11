// XLL (2026-11-11, OWN_XLL; /home/steve/dsv41-work/xll, bench xll_bench.cpp): the pull exchange in one PCIe round trip.
//
// Today (XchgPull, sycl_v41.hpp) every card stores its exchange number into each peer's flag word (a posted write,
// ~2.3 us one way on this host), polls its own flag words until every peer's number is there, and only then loads
// the peers' rows (a read round trip, ~5 us with the bytes). After the last card arrives an exchange still pays the
// flag's trip and then the data's trip (e81b: 11.9 us = launch 2.4 + flags 2.3 + copy 5.0 + the rest).
//
// XchgPullL: the data carry their exchange number, so a reader takes them as soon as they are there.
//   - publish: the card packs its own rows of every slot (the words its producer launch left in its arena, the
//     words XchgPull lets the peers load) into its outbox, a second copy in its own arena: U-byte units of U / 4 - 1
//     data words and then the exchange number seq. U = 16: 3 data words + seq per 16-byte vector. U = 64: 15 + seq
//     per 64-byte line, its four 16-byte pieces stored and loaded by four neighbouring lanes in one message.
//   - pull: every card loads every peer's units at once (16-byte loads, one d32x4 message per sub-group), takes a
//     unit whose last word reads seq (U = 64: the tag of the unit's last piece, from the same load message) and
//     stores its data words where XchgPull would have stored them, and loads the other units again after an
//     acquire fence (HINT 3: fence.ugm.invalidate, so a re-read cannot come from this card's L1): POL 0 at once
//     until they are fresh (unbounded PCIe polling of a late peer: bench only); POL 2 `quick` passes at once, then
//     only after that peer's flag (still raised, after the outbox) is in this card's own memory, so a late peer is
//     waited for by local polls as today.
//   - the flags are still raised (after the outbox; xchg_tail's form: barrier, then one item fences and counts, the
//     last work-group stores the numbers), so every exchange that waits on flags (XchgP, XchgPull, a mode-1
//     publish that a later wait covers) keeps its meaning; at its end the pull waits (work-group 0, local polls)
//     until every peer's flag is >= seq - 1 (>= seq for a peer with no units in this exchange), which covers whatever
//     earlier exchanges left for a later wait to cover exactly as XchgPull's own wait did (those flags are normally
//     in place long before). A peer's fresh unit numbered seq means that peer has started this exchange's launch, so
//     it has finished every earlier one: what XchgPull's flag >= seq told.
//   - a second region (OWN_MT_DSPLIT's partials, as XchgPull2: rows c0 / c1 of nslot2 slots) rides the same launch
//     with its own outbox; both regions' units are one list.
//
// Why a unit is safe to take:
//   - it is written by its owner only, in the owner's own memory, one store per 16-byte piece (L1 uncached, so it is
//     in the owner's L3 at once); a reader takes it only when its tag reads seq in the same load (U = 16) or in the
//     same load message as the unit's other pieces (U = 64). That needs a 16-byte (64-byte) piece to be seen whole by
//     a PCIe peer read. Nothing promises it; xll_bench classifies every word of every unit it loads, under load.
//   - stale lines can only delay, never mislead: a stale unit carries an older number and is not taken. Re-reads
//     follow an L1 invalidate (HINT 3). The read hints (HINT 1, 2: annotated_ptr read_hint) do not reach the ISA on
//     icpx 2026.1 (sycl::vec / clang vector loads: no decoration; per-word scalar loads: merged into a plain d32x4),
//     so those forms are plain loads (the bench's controls). Peer memory is not held in this card's L3 across
//     launches (XchgPull re-reads the same peer addresses with new data every layer, bitwise exact).
//   - reuse: a region's outbox is rewritten at that region's next exchange. XchgPull's rule holds: a card rewrites a
//     region only after a later exchange completed, and a peer publishes (units or flag) for that later exchange only
//     after its launch of the earlier one ended (in-order queue), i.e. after all its loads of the old outbox came
//     back. A unit numbered above seq means the rule broke: the launch stops waiting and reports err = 0x100 + peer.
//   - the same bits: pure 32-bit copies of the producer's words (XchgPull moves the same words as float vectors).
//
// Arena words: flags 16 d and the poison word 96 as XchgPull. Outboxes (ob, ob2: multiples of 16 words, the same
// offsets on every card) lie outside every region. Items take the units v = gid, gid + T, ... of the list of all
// peers' units (each peer's padded to 32: a unit's pieces sit on neighbouring lanes), copy_seq's assignment.
// Work-groups past ng are not the exchange's (a bench's riders). A wait or a pass count past its bound sets the
// poison word and err[0]: 1 + d (d's units never fresh), 0x200 + d (d's flag never came), 0x300 + d (d's flag of the
// exchange before never came), 0x100 + d (a unit of d numbered above seq: the overwrite rule broke).
#pragma once
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/experimental/annotated_ptr/annotated_ptr.hpp>
#include <sycl/ext/intel/experimental/cache_control_properties.hpp>
#include <cstdint>
#include <type_traits>
#include "stage2/packet3/kernels/sycl_v41.hpp" // XchgP::pick (the six peer pointers)

namespace ops41sycl {

// 16-byte loads / stores with cache controls. annotated_ptr<sycl::vec> loses the controls (no decoration in the
// module, plain load.ugm.d32x4), so the access goes through a clang vector type of the same 16 bytes.
using xll_u4 = uint32_t __attribute__((ext_vector_type(4)));
// loads: HINT 0 plain, 1 L1 uncached (the L3's default), 2 L1 and L3 uncached (per 32-bit word: the controls reach
// the ISA only for scalar types here; IGC is expected to merge the four into one d32x4 message, see the ISA dump),
// 3 plain loads after an acquire fence (fence.ugm.invalidate: the L1 is dropped before every re-read pass)
template <int HINT> [[gnu::always_inline]] inline sycl::vec<uint32_t, 4> xll_ld(const sycl::vec<uint32_t, 4> *p) {
    namespace sx = sycl::ext::oneapi::experimental;
    namespace ix = sycl::ext::intel::experimental;
    if constexpr (HINT == 1 || HINT == 2) {
        using PR1 = decltype(sx::properties{ix::read_hint<ix::cache_control<ix::cache_mode::uncached, sx::cache_level::L1>>});
        using PR2 = decltype(sx::properties{
            ix::read_hint<ix::cache_control<ix::cache_mode::uncached, sx::cache_level::L1, sx::cache_level::L3>>});
        sx::annotated_ptr<uint32_t, std::conditional_t<HINT == 1, PR1, PR2>> a{reinterpret_cast<uint32_t *>(const_cast<sycl::vec<uint32_t, 4> *>(p))};
        const uint32_t w0 = a[0], w1 = a[1], w2 = a[2], w3 = a[3];
        return sycl::vec<uint32_t, 4>(w0, w1, w2, w3);
    } else {
        const xll_u4 r = *reinterpret_cast<const xll_u4 *>(p);
        return sycl::vec<uint32_t, 4>(r[0], r[1], r[2], r[3]);
    }
}
// a store past the L1 (write hint L1 uncached; the L3's default), as att_st_l3; xll_st1: one 32-bit word
[[gnu::always_inline]] inline void xll_st1(uint32_t *p, uint32_t v) {
    namespace sx = sycl::ext::oneapi::experimental;
    namespace ix = sycl::ext::intel::experimental;
    sx::annotated_ptr<uint32_t, decltype(sx::properties{ix::write_hint<ix::cache_control<ix::cache_mode::uncached, sx::cache_level::L1>>})> a{p};
    a[0] = v;
}
[[gnu::always_inline]] inline void xll_st(sycl::vec<uint32_t, 4> *p, const sycl::vec<uint32_t, 4> &v) {
    namespace sx = sycl::ext::oneapi::experimental;
    namespace ix = sycl::ext::intel::experimental;
    xll_u4 w = {v[0], v[1], v[2], v[3]};
    sx::annotated_ptr<xll_u4, decltype(sx::properties{ix::write_hint<ix::cache_control<ix::cache_mode::uncached, sx::cache_level::L1>>})> a{
        reinterpret_cast<xll_u4 *>(p)};
    a[0] = w;
}

// one card's slice of one region: words off + s * stride + r0 + r (s < nslot, r < nd); its units at src (peer) + ob
struct XllGeo {
    const uint32_t *src;
    unsigned off, stride, nslot, r0, nd;
};
// hooks for the bench (the engine uses XllNoHook: no code); split: the bench's positive control, see pack
struct XllNoHook {
    static constexpr bool split = false;
    template <typename X> static void pre(sycl::nd_item<1>, const X &, uint32_t *) {}
    template <typename X>
    static void piece(const X &, sycl::sub_group, bool, uint32_t, unsigned, const XllGeo &, unsigned, const sycl::vec<uint32_t, 4> &,
                      uint32_t *) {}
};

template <unsigned U, int POL = 2, int HINT = 1, typename H = XllNoHook> struct XchgPullL {
    static_assert(U == 16 || U == 64, "XchgPullL: 16- or 64-byte units");
    static constexpr unsigned P = U / 16, W = U / 4, D = W - 1, E = 2; // pieces, words, data words per unit; entries per round
    using V4 = sycl::vec<uint32_t, 4>;
    int n, me;
    unsigned off, stride, nslot;
    unsigned b0[6], b1[6]; // every card's rows (multiples of 4, as XchgPull)
    unsigned ob;           // the region's outbox (32-bit words from the arena's start; a multiple of 16)
    unsigned off2 = 0, stride2 = 0, nslot2 = 0; // a second region (nslot2 == 0: none), as XchgPull2
    unsigned c0[6] = {}, c1[6] = {};
    unsigned ob2 = 0;
    unsigned ng;  // the exchange's work-groups
    uint32_t seq;
    long spin;    // local flag polls before a time-out (XchgPull's)
    long passes;  // passes over the peers' units before a time-out
    long quick = 0; // POL 2: re-read passes at once before a late peer's flag is waited for (0: the flag after the
                    // first pass; each pass is one PCIe read round trip of the pending units: bounded extra traffic)
    int mode = 0; // 0 publish + pull, 1 publish only, 2 pull only (seq: that exchange's number)
    // 16-byte pieces of a slice of ns x nd words; outbox words for it
    static unsigned pieces(unsigned ns, unsigned nd) { return (ns * nd + D - 1) / D * P; }
    static unsigned outbox_words(unsigned ns, unsigned nd) { return pieces(ns, nd) * 4; }

    // stream q < 12: region q / 6 of card q % 6 (q is the same on every lane of a sub-group: scalar selects)
    [[gnu::always_inline]] XllGeo geo(unsigned q, float *p0, float *p1, float *p2, float *p3, float *p4, float *p5) const {
        XllGeo g{nullptr, 0, 0, 0, 0, 0};
#pragma unroll
        for (unsigned s = 0; s < 12; ++s)
            if (s == q) {
                const int d = (int)(s % 6);
                const uint32_t *a = reinterpret_cast<const uint32_t *>(XchgP::pick(d, p0, p1, p2, p3, p4, p5));
                if (s < 6) g = {a + ob, off, stride, nslot, b0[d], b1[d] - b0[d]};
                else g = {a + ob2, off2, stride2, nslot2, c0[d], c1[d] - c0[d]};
            }
        return g;
    }
    // piece k of a slice: its data words -> mw at the slice's places
    [[gnu::always_inline]] static void unpack(uint32_t *mw, const XllGeo &g, unsigned k, const V4 &v) {
        const unsigned F = g.nslot * g.nd, u = k / P, q = k % P;
        unsigned f = u * D + 4 * q, s = f / g.nd, r = f % g.nd;
#pragma unroll
        for (unsigned e = 0; e < 4; ++e) {
            if (4 * q + e == W - 1 || f >= F) break;
            mw[g.off + s * g.stride + g.r0 + r] = v[e];
            ++f;
            if (++r == g.nd) r = 0, ++s;
        }
    }
    // this card's slice of one region -> its outbox at o (pieces gid, gid + T, ...)
    [[gnu::always_inline]] void pack(const uint32_t *mw, V4 *o, unsigned offr, unsigned strider, unsigned ns, unsigned r0,
                                     unsigned nd, unsigned gid, unsigned T) const {
        const unsigned F = ns * nd, NP = pieces(ns, nd);
        for (unsigned k = gid; k < NP; k += T) {
            const unsigned u = k / P, q = k % P;
            unsigned f = u * D + 4 * q, s = f / nd, r = f % nd;
            V4 w(0u);
#pragma unroll
            for (unsigned e = 0; e < 4; ++e) {
                if (4 * q + e == W - 1) {
                    w[e] = seq;
                } else if (f < F) {
                    w[e] = mw[offr + s * strider + r0 + r];
                    ++f;
                    if (++r == nd) r = 0, ++s;
                }
            }
            if constexpr (H::split) { // (bench control only: the number first, the row words ~1 us later, one word per
                                      // store, so a reader can catch a unit torn; xll_bench must count it)
                uint32_t *ow = reinterpret_cast<uint32_t *>(o + k);
                if (q == P - 1) xll_st1(ow + 3, w[3]);
                uint32_t z = w[0];
                for (unsigned i = 0; i < 400u; ++i) z = z * 1664525u + 1013904223u;
                xll_st1(ow + 0, z == 0x9E3779B1u && w[1] == 0x85EBCA77u ? 0u : w[0]); // (keeps the delay; ~never 0)
                xll_st1(ow + 1, w[1]);
                xll_st1(ow + 2, w[2]);
                if (q != P - 1) xll_st1(ow + 3, w[3]);
            } else {
                xll_st(o + k, w);
            }
        }
    }

    // a wait past its bound or a newer unit: the poison word, err[0] = code (XchgPull's word), err[2] / err[3] = the
    // first such code on this card and its exchange number (plain stores: a diagnosis, races only blur it)
    template <typename A> [[gnu::always_inline]] void fail(A &poison, uint32_t *err, uint32_t code) const {
        poison.store(1u);
        err[0] = code;
        if (!err[2]) err[2] = code, err[3] = seq;
    }
    void operator()(sycl::nd_item<1> it, float *p0, float *p1, float *p2, float *p3, float *p4, float *p5, uint32_t *cnt,
                    uint32_t *err, uint32_t *st) const {
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        using ARD = sycl::atomic_ref<uint32_t, sycl::memory_order::acq_rel, sycl::memory_scope::device,
                                     sycl::access::address_space::global_space>;
        const unsigned grp = (unsigned)it.get_group_linear_id();
        if (grp >= ng) return;
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = (unsigned)sg.get_local_linear_id(), t = (unsigned)it.get_local_linear_id();
        const unsigned L = (unsigned)it.get_local_range(0), T = ng * L, gid = grp * L + t;
        uint32_t *mw = reinterpret_cast<uint32_t *>(XchgP::pick(me, p0, p1, p2, p3, p4, p5));
        H::pre(it, *this, st);
        if (mode != 2) { // ---- publish: this card's slices, D words + seq per unit
            pack(mw, reinterpret_cast<V4 *>(mw + ob), off, stride, nslot, b0[me], b1[me] - b0[me], gid, T);
            if (nslot2) pack(mw, reinterpret_cast<V4 *>(mw + ob2), off2, stride2, nslot2, c0[me], c1[me] - c0[me], gid, T);
            // the flags once every work-group's pieces are out (xchg_tail's form: barrier, then item 0 fences)
            sycl::group_barrier(it.get_group());
            if (t == 0) {
                sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
                ARD c(*cnt);
                if (c.fetch_add(1u) + 1u == ng) {
                    c.store(0u, sycl::memory_order::relaxed); // the next launch comes after this one ends
                    sycl::atomic_fence(sycl::memory_order::acq_rel, sycl::memory_scope::system);
                    for (int d = 0; d < n; ++d)
                        if (d != me) AR(reinterpret_cast<uint32_t *>(XchgP::pick(d, p0, p1, p2, p3, p4, p5))[16 * me]).store(seq);
                }
            }
        }
        if (mode == 1) return;
        // ---- pull: the list of all streams' pieces (stream q: region q / 6 of peer q % 6, padded to 32 pieces);
        // this item's entries are list places gid + m T (m < MM). A sub-group's 32 places are one aligned block, so
        // the stream is the sub-group's (and a 64-byte unit's four pieces sit on four neighbouring lanes).
        AR poison(mw[96]);
        const bool dead = poison.load() != 0u;
        unsigned base[13];
        base[0] = 0;
#pragma unroll
        for (unsigned q = 0; q < 12; ++q) {
            const int d = (int)(q % 6);
            const bool on = d < n && d != me && (q < 6 || nslot2);
            const unsigned np = !on ? 0u : q < 6 ? pieces(nslot, b1[d] - b0[d]) : pieces(nslot2, c1[d] - c0[d]);
            base[q + 1] = base[q] + (np + 31u) / 32u * 32u;
        }
        const unsigned V = base[12], MM = (V + T - 1) / T;
        const unsigned sgb = sycl::group_broadcast(sg, gid - lane, 0); // the sub-group's first place
        uint32_t seen = 0; // POL 2: peers whose flag this sub-group has seen
        for (unsigned m0 = 0; m0 < MM; m0 += E) {
            XllGeo g[E];
            unsigned eq[E], ek[E];
            uint32_t pend = 0;
#pragma unroll
            for (unsigned e = 0; e < E; ++e) {
                const unsigned vb = sgb + (m0 + e) * T; // (sub-group uniform)
                unsigned q = 0, bq = 0;
#pragma unroll
                for (unsigned s = 1; s < 12; ++s)
                    if (vb >= base[s]) q = s, bq = base[s];
                eq[e] = q;
                ek[e] = vb - bq + lane;
                g[e] = geo(q, p0, p1, p2, p3, p4, p5);
                if (m0 + e < MM && vb < V && ek[e] < pieces(g[e].nslot, g[e].nd)) pend |= 1u << e;
            }
            long s = 0;
            for (;;) {
                if (!sycl::any_of_group(sg, pend != 0u)) break;
                if constexpr (HINT == 3)
                    if (s) sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
                V4 v[E];
#pragma unroll
                for (unsigned e = 0; e < E; ++e)
                    v[e] = (pend >> e & 1u) ? xll_ld<HINT>(reinterpret_cast<const V4 *>(g[e].src) + ek[e]) : V4(0u);
#pragma unroll
                for (unsigned e = 0; e < E; ++e) {
                    const bool want = pend >> e & 1u;
                    uint32_t tag = v[e][3];
                    if constexpr (P > 1) tag = sycl::select_from_group(sg, tag, lane | (P - 1));
                    H::piece(*this, sg, want, tag, eq[e] % 6, g[e], ek[e], v[e], st);
                    if (want && tag == seq) {
                        unpack(mw, g[e], ek[e], v[e]);
                        pend &= ~(1u << e);
                    } else if (want && tag > seq) { // a later exchange's unit: the overwrite rule broke
                        fail(poison, err, 0x100u + eq[e] % 6);
                        pend &= ~(1u << e);
                    }
                }
                if (!sycl::any_of_group(sg, pend != 0u)) break;
                if (dead || ++s >= passes) { // (s is the same on every lane: one pass per round of this loop)
                    if (pend && !dead) {
                        unsigned d = 0;
#pragma unroll
                        for (int e = E - 1; e >= 0; --e)
                            if (pend >> e & 1u) d = eq[e] % 6;
                        fail(poison, err, 1u + d);
                    }
                    break;
                }
                if constexpr (POL == 2) { // the peers still behind: their flag in this card's own memory first
                    if (s > quick) {
                        uint32_t pm = 0;
#pragma unroll
                        for (unsigned e = 0; e < E; ++e)
                            if (pend >> e & 1u) pm |= 1u << (eq[e] % 6);
                        pm = sycl::reduce_over_group(sg, pm, sycl::bit_or<uint32_t>()) & ~seen;
                        if (pm) {
                            if (lane < 6 && (pm >> lane & 1u)) {
                                AR f(mw[16 * lane]);
                                long q = 0;
                                if (!poison.load())
                                    while (f.load() < seq && ++q < spin) {}
                                if (q >= spin) fail(poison, err, 0x200u + lane); // (0x200 + d: d's flag never came)
                            }
                            sycl::group_barrier(sg);
                            seen |= pm;
                        }
                    }
                }
            }
        }
        // ---- what earlier exchanges left for this wait to cover: every peer's flag >= seq - 1 (local polls); a peer
        // with no units here: >= seq, as XchgPull (a completed exchange then still means every peer reached it)
        if (grp == 0 && (int)t < n && (int)t != me && !dead) {
            const unsigned np = pieces(nslot, b1[t] - b0[t]) + (nslot2 ? pieces(nslot2, c1[t] - c0[t]) : 0u);
            const uint32_t want = np ? seq - 1u : seq;
            AR f(mw[16 * t]);
            long q = 0;
            while (f.load() < want && ++q < spin) {}
            if (q >= spin) fail(poison, err, 0x300u + t); // (0x300 + d: an earlier exchange's flag of d never came)
        }
    }
};

} // namespace ops41sycl
