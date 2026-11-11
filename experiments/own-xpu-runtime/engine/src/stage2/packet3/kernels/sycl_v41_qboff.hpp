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

} // namespace ops41sycl
