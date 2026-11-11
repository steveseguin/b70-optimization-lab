// Query-b offload ("qb-off-1", OWN_QB_OFF, 2026-11-11): two kernels for the one-token tensor-parallel step. On six
// cards the eight attention groups sit 1,1,2,1,1,2 per card, so cards 2 and 5 run 16 heads' query-b rows (8,192 x
// 1,280) and the other four 8 heads'; the light cards then wait ~22 us per layer at the output-a exchange. Query-b's
// input (the normed q_a output, s.qn) is replicated and bit-identical on every card, so each 16-head card's two
// light neighbours compute k of its heads' rows (the same per-row code, see Backend41::qbo_send), rope them with the
// heavy card's own rope kernel (RowsP<RopeRows>), and push them one way into the heavy card's s.q (kept in its
// arena while OWN_QB_OFF is on). The heavy card runs only its kept heads' rows; the wait for the pushes sits in its
// query rope launch (QbWaitRope), which comes before every attention form. Included after sycl_v41.hpp.
//
// Protocol (as XchgP / XchgPair): the sender's items store their vec4s into the peer's arena, release at system
// scope, barrier, then item 0 of work-group g stores seq into the peer's flag word fw + g (fw = 128 + 16 * sender:
// the flag area's words 0..80 are the all-card exchanges' 16 * card, 96 the poison word, nothing else uses 97..1023).
// The receiver polls its own flag words (relaxed system-scope atomics), acquires at system scope and barriers; the
// pushed rows are read only by LATER launches (the score / one-launch attention): xchg_direct_bench found that plain
// loads in the waiting kernel itself can return the previous round's cached lines. The heavy card never writes the
// pushed heads' lines itself (its q_b and rope cover only its kept heads), so no line of its own can be written back
// over them. Overwrite safety: a helper pushes layer L + 1's rows only after its output-a exchange of layer L has
// seen the heavy card's flag, which the heavy card raises after its layer-L attention (in-order queue).
// A wait past spin polls sets the poison word and err[0] = 1 + sender (the host's "exchange timed out" error).
// Peer pointers are direct kernel arguments only (DisableIndirectAccess=1).
#pragma once

namespace ops41sycl {

// one-way push of n4 vec4s from src (this card) to the peer arena at float offset doff, then the flags
struct QbPush {
    unsigned doff; // float offset of the first row in the peer's arena (16-byte aligned)
    unsigned n4;   // vec4s (rows / 4)
    unsigned fw;   // flag word of work-group 0 (uint32 index in the peer's arena); group g stores fw + g
    uint32_t seq;
    void operator()(sycl::nd_item<1> it, const float *src, float *peer) const {
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        const unsigned t = (unsigned)it.get_local_linear_id(), L = (unsigned)it.get_local_range(0);
        const unsigned g = (unsigned)it.get_group_linear_id(), G = (unsigned)it.get_group_range(0);
        for (unsigned k = g * L + t; k < n4; k += G * L)
            *reinterpret_cast<sycl::vec<float, 4> *>(peer + doff + (size_t)k * 4) =
                *reinterpret_cast<const sycl::vec<float, 4> *>(src + (size_t)k * 4);
        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
        if (t == 0) AR(reinterpret_cast<uint32_t *>(peer)[fw + g]).store(seq);
    }
};

// The heavy card's query rope (RowsP<RopeRows<A>>'s rows, one head per sub-group) after waiting for its two
// helpers' pushes: items t < 2 * G poll flag word 128 + 16 * (t < G ? from0 : from1) + t % G of this card's arena.
// Every work-group waits (the launch is one work-group of 16 rows at 16 kept heads). The rope rows run RopeRows'
// own row code on the card's kept heads only.
template <typename A> struct QbWaitRope {
    RopeRows<A> r;
    unsigned from0, from1, G;
    uint32_t seq;
    long spin;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, float *mine, uint32_t *err) const {
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        const unsigned t = (unsigned)it.get_local_linear_id();
        if (t < 2 * G) {
            const unsigned src = t < G ? from0 : from1;
            AR poison(reinterpret_cast<uint32_t *>(mine)[96]);
            AR f(reinterpret_cast<uint32_t *>(mine)[128 + 16 * src + t % G]);
            long s = 0;
            if (!poison.load())
                while (f.load() < seq && ++s < spin) {}
            if (s >= spin) {
                poison.store(1u);
                err[0] = 1u + src;
            }
        }
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
        const unsigned row = packed_row_id(it);
        if (row >= r.n()) return;
        sycl::sub_group sg = it.get_sub_group();
        r.row(sg, sg.get_local_linear_id(), row);
    }
};

// ---- qb-off-2 (OWN_QB_OFF_M, 2026-11-11): the same offload in blocks of 2 .. 6 tokens (tpm_layer: guessing checks,
// small prompt blocks). A helper runs the k heads' rows for the block in a launch of its own BEFORE its own query-b
// (the same rows, the same WS form as its own 4,096-row launch: Backend41::qbm_send), into a staging region of its
// arena (token t at soff + t * k * hd), then QbmFlag publishes them as XchgPull does (system-scope release, flag seq
// into the heavy card's word fw = 128 + 16 * helper + 8; qb-off-1's push flags use + 0 .. 3). The heavy card's
// query-b launch carries the pull as its first rows (QbmHeavyK): one sub-group per (helper, token, head) polls its
// own flag word, acquires at system scope and copies the head's hd floats from the helper's staging into its query
// buffer by loads (XchgPull's direction: peer loads run at 25-37 GB/s, peer stores at ~1 GB/s), while its other
// sub-groups run its 16 - 2k heads' rows. Its rope launch comes after (in-order queue) and ropes all its heads as
// today, so the pulled rows are read only by a later launch. No row's value changes: the helper's rows are the same
// per-row code on the same packed bytes and the same replicated q_a norm output; the pull is a copy.
// Overwrite safety: a helper writes layer L + 1's staging only after its output-a exchange of layer L, which waits
// for the heavy card's flag, raised after that card's layer-L query-b launch (with the pull) in its in-order queue.
struct QbmFlag {
    unsigned fw; // flag word (uint32 index in the heavy card's arena)
    uint32_t seq;
    void operator()(sycl::nd_item<1> it, float *peer) const {
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
        if (it.get_local_linear_id() == 0) AR(reinterpret_cast<uint32_t *>(peer)[fw]).store(seq);
    }
};
// the heavy card's pull rows: row r = (side s = r / (m k), token t, head j); side 0 = the left helper (the card's
// first k heads, at d0[0] in a token's query row), 1 = the right one (its last k, at d0[1])
struct QbmPull {
    float *q;          // this card's block query buffer (token t at q + t * qs)
    size_t qs;
    unsigned d0[2];    // float offsets of each side's first head in a token's row
    unsigned soff, sts; // the helpers' staging: arena offset, floats per token (k * hd)
    unsigned fw[2];    // this card's flag words for the two helpers
    unsigned from[2];  // the helpers' card numbers (the error word)
    unsigned m, k, hd;
    uint32_t seq;
    long spin;
    unsigned n() const { return 2 * m * k; }
    [[gnu::always_inline]] inline void row(unsigned lane, unsigned r, float *mine, const float *pl, const float *pr,
                                           uint32_t *err) const {
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        const unsigned s = r / (m * k), t = r % (m * k) / k, j = r % k;
        AR poison(reinterpret_cast<uint32_t *>(mine)[96]);
        AR f(reinterpret_cast<uint32_t *>(mine)[fw[s]]);
        long n = 0;
        if (!poison.load())
            while (f.load() < seq && ++n < spin) {}
        if (n >= spin) {
            poison.store(1u);
            if (lane == 0) err[0] = 1u + from[s];
        }
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
        const float *src = (s ? pr : pl) + soff + (size_t)t * sts + (size_t)j * hd;
        float *dst = q + (size_t)t * qs + d0[s] + (size_t)j * hd;
        for (unsigned i = lane; i < hd / 4; i += 32)
            *reinterpret_cast<sycl::vec<float, 4> *>(dst + 4 * i) = *reinterpret_cast<const sycl::vec<float, 4> *>(src + 4 * i);
    }
};
// the heavy card's query-b rider (dense_m: rider type QbmHeavy<B>, B = the launch's own rider, NoRows or the mix's
// finish rows; WsTab's launch kind follows B). Its n() / row() are B's, so a generic launch would run only B: the
// backend launches it as QbmHeavyK (Backend41::qbm_heavy_launch, packed WS forms only)
template <typename B> struct QbmHeavy {
    B base;
    QbmPull pull;
    unsigned n() const { return base.n(); }
    void row(sycl::sub_group sg, unsigned lane, unsigned r) const { base.row(sg, lane, r); }
};
template <typename T> inline constexpr bool is_qbm_heavy_v = false;
template <typename B> inline constexpr bool is_qbm_heavy_v<QbmHeavy<B>> = true;
template <typename T> struct QbmBase { using type = T; };
template <typename B> struct QbmBase<QbmHeavy<B>> { using type = B; };
template <typename T> using qbm_base_t = typename QbmBase<T>::type;
// the WS forms of up to 6 tokens per group (the checks' forms; QbmHeavyK is built for these only)
template <typename T> inline constexpr bool qbm_ws_v = false;
template <typename W, unsigned T, unsigned R, unsigned XW, unsigned LOOP, unsigned PF>
inline constexpr bool qbm_ws_v<DenseRowsWS<W, T, R, XW, LOOP, PF>> = T <= 6;
// the pull rows first, then the launch's rows (RP = RowsPair<B, D>, as dense_m's launch)
template <typename RP> struct QbmHeavyK {
    QbmPull pl;
    RP rows;
    [[gnu::flatten]] void operator()(sycl::nd_item<1> it, float *mine, const float *pa, const float *pb, uint32_t *err) const {
        unsigned r = packed_row_id(it);
        sycl::sub_group sg = it.get_sub_group();
        const unsigned lane = sg.get_local_linear_id();
        if (r < pl.n()) {
            pl.row(lane, r, mine, pa, pb, err);
            return;
        }
        r -= pl.n();
        if (r >= rows.n()) return;
        rows.row(sg, lane, r);
    }
};
// the pull alone (qbm_heavy_launch's fallback when the launch's form is not one of the checks' WS forms)
struct QbmPullK {
    QbmPull pl;
    void operator()(sycl::nd_item<1> it, float *mine, const float *pa, const float *pb, uint32_t *err) const {
        const unsigned r = packed_row_id(it);
        if (r >= pl.n()) return;
        pl.row(it.get_sub_group().get_local_linear_id(), r, mine, pa, pb, err);
    }
};
// ws_rows<DK, WS_PLAIN> with the form WsTab picks for prows rows (the helper's 1,024 - 2,048 extra rows take the
// form of its own 4,096-row launch; any form gives the same values)
template <typename DK, typename F>
inline bool qbm_ws_rows(const DK &dk, unsigned prows, const uint8_t *w, const float *x, size_t xs, float *y, size_t ys,
                        unsigned mt, unsigned cap, F &&f) {
    using O = WsOf<DK>;
    using Tab = WsTab<O::fmt, O::cols, WS_PLAIN>;
    if constexpr (O::fmt == 0) return false;
    else {
        const unsigned id = Tab::pick(prows, mt);
        if (!id) return false;
        return ws_each(typename Tab::forms{}, [&](auto fm) {
            using FM = decltype(fm);
            if (FM::id != id || dk.xn % FM::r || (mt + FM::t - 1) / FM::t * FM::t > cap) return false;
            using WK = typename O::type;
            f(DenseRowsWS<WK, FM::t, FM::r, FM::xw, FM::loop, FM::pf>{WK{dk.rows, dk.xn}, w, x, xs, y, ys, mt,
                                                                        (mt + FM::t - 1) / FM::t});
            return true;
        });
    }
}

} // namespace ops41sycl
