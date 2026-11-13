#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
// xchg2-1 (2026-11-12, OWN_XPUSH2; bench /home/steve/dsv41-work/xchg2/bench/xlat.cpp): the all-gather of a decode /
// check exchange as posted writes into the peers, ONE PEER AT A TIME.
//
// Why: a card's EU stores into a peer run at 16-40 GB/s into one peer but collapse to ~1 GB/s when the card writes
// to several peers at once (round19-ce sg / sq). XchgP / XchgPushM interleave all five peers per item; XchgPull
// reads (a PCIe round trip after the flag's trip). XchgQ walks the peers in the order me + 1, me + 2, .. (so each
// card also receives from one sender at a time), with its G work-groups kept on the same peer by an on-card counter.
//
// Body (G work-groups of L items step over this card's rows of every slot, vec4 by vec4):
//   phase p = 1 .. n - 1: store this card's rows [r0, r1) of every slot (nslot slots, stride floats apart, from arena
//   offset off: the words its producer left in its own arena) at the same offsets into peer (me + p) % n's arena;
//   with lock (more than one vec4 per item and peer), between phases every group waits until all G groups finished
//   the phase (device counter cnt[0], bounded; without it groups drift onto different peers: bench sk4 vs snk4);
//   then every item: system-scope release fence; group barrier; one item counts the group done (cnt[16]); the group
//   that completes the count resets both counters, and its items t < n store seq into peer t's flag word 16 * me
//   (XchgP's flags), then wait until every peer's flag in this card's arena is >= seq (XchgP's wait: poison word 96,
//   err[0] = 1 + peer on a timeout). The flag after the data: XchgP's order (stores, system release, barrier, flag;
//   round19-ce ord: 0 early words in thousands of rounds); across groups the device counter carries it (each group
//   fences before it counts, the last one stores the flags after it saw the count; xchg_tail's hand-off).
//
// Same bytes as every other form: pure 16-byte copies of the producer's words into the same offsets of every peer.
// Reuse rule (as XchgP's pushes): a card stores into a peer's region at exchange k only after its last waiting
// exchange (k - 1; k - 2 right after an engram push, mode 1) saw every peer's flag, and a peer raises a flag only
// after its in-order queue finished the launches before it, among them the readers of the region's previous contents
// (Backend41::x2_form's comment lists the sites: each region's readers run before the next exchange's producer, and
// no two exchanges in a row write the same region). The rows are 64-byte lines of their own (units of 16 floats,
// 64-byte aligned regions): no line holds two cards' rows. Readers read the gathered rows one launch after the wait (L1).
namespace ops41sycl {
struct XchgQ {
    int n, me;
    unsigned off, stride, nslot, r0, r1;
    uint32_t seq;
    long spin;
    unsigned lock; // 1: the groups wait for each other between peers (more than one vec4 per item and peer)
    void operator()(sycl::nd_item<1> it, float *p0, float *p1, float *p2, float *p3, float *p4, float *p5,
                    uint32_t *cnt, uint32_t *err) const {
        using AR = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::system,
                                    sycl::access::address_space::global_space>;
        using ARD = sycl::atomic_ref<uint32_t, sycl::memory_order::relaxed, sycl::memory_scope::device,
                                     sycl::access::address_space::global_space>;
        float *mine = XchgP::pick(me, p0, p1, p2, p3, p4, p5);
        const size_t g = it.get_group_linear_id(), G = it.get_group_range(0), t = it.get_local_linear_id(),
                     L = it.get_local_range(0);
        const unsigned n4 = (r1 - r0) / 4;
        const size_t tot = (size_t)nslot * n4;
        AR poison(reinterpret_cast<uint32_t *>(mine)[96]);
        for (int p = 1; p < n; ++p) {
            float *dst = XchgP::pick((me + p) % n, p0, p1, p2, p3, p4, p5);
            for (size_t k = g * L + t; k < tot; k += G * L) {
                const size_t o = (size_t)off + (size_t)(k / n4) * stride + r0 + (k % n4) * 4;
                *reinterpret_cast<sycl::vec<float, 4> *>(dst + o) = *reinterpret_cast<const sycl::vec<float, 4> *>(mine + o);
            }
            if (lock && p + 1 < n) { // every group on the same peer: wait for the phase's G arrivals
                sycl::group_barrier(it.get_group());
                if (t == 0) {
                    ARD c(cnt[0]);
                    c.fetch_add(1u);
                    long s = 0;
                    if (!poison.load())
                        while (c.load() < (uint32_t)(G * (size_t)p) && ++s < spin) {}
                    if (s >= spin) {
                        poison.store(1u);
                        err[0] = 1u + (uint32_t)me;
                    }
                }
                sycl::group_barrier(it.get_group());
            }
        }
        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
        if (G > 1) {
            uint32_t last = 0;
            if (t == 0) {
                ARD d(cnt[16]);
                last = d.fetch_add(1u) + 1u == (uint32_t)G ? 1u : 0u;
                if (last) { // every group passed every phase wait: both counters back to 0 for the next launch
                    d.store(0u);
                    ARD(cnt[0]).store(0u);
                }
            }
            last = sycl::group_broadcast(it.get_group(), last, 0);
            if (!last) return;
            sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::device);
        }
        if ((int)t < n && (int)t != me)
            AR(reinterpret_cast<uint32_t *>(XchgP::pick((int)t, p0, p1, p2, p3, p4, p5))[16 * me]).store(seq);
        if ((int)t < n && (int)t != me) { // XchgP's wait
            AR f(reinterpret_cast<uint32_t *>(mine)[16 * t]);
            long s = 0;
            if (!poison.load())
                while (f.load() < seq && ++s < spin) {}
            if (s >= spin) {
                poison.store(1u);
                err[0] = 1u + (uint32_t)t;
            }
        }
        sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
        sycl::group_barrier(it.get_group());
    }
};
} // namespace ops41sycl
