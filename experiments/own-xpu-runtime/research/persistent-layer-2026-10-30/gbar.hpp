// Bounded device-wide (grid) barrier for a persistent kernel on one B70 (persistent-layer study, 2026-10-30).
//
// Every spin is bounded: a leader that polls more than `limit` times, or sees another group's error, sets the error
// word and returns false; callers then leave the kernel. No wait in this file can hang the card. The kernel must be
// launched with every work-group co-resident (checked by the caller against the measured limit); if it is not, the
// waiting groups time out, record the error and exit, and the late groups see the error and exit too.
//
// The barrier needs no reset between launches: the host passes `base`, the value the arrival counter (counter kind)
// or the generation word (flag kind) has at kernel entry, and advances it by the number of barriers the launch ran.
#pragma once
#include <sycl/sycl.hpp>
#include <cstdint>

namespace pl {
using u32 = std::uint32_t;
using u64 = std::uint64_t;

// Control block word indices (u32), 128 bytes apart.
constexpr u32 CNT = 0, GEN = 32, ERR = 64, MAXPOLL = 96, SUB = 128, SUBS = 64, CTL_WORDS = SUB + SUBS * 32;
constexpr u32 FANIN = 16;  // tree kind: groups per sub-counter

template <class T>
using dref = sycl::atomic_ref<T, sycl::memory_order::relaxed, sycl::memory_scope::device,
                              sycl::access::address_space::global_space>;

// counter: one monotonic arrival counter, everyone polls it until it reaches base + (epoch+1)*nwg.
// flag:    arrival counter reset by the last arriver, which then bumps a generation word that the others poll.
// tree:    groups arrive at one of ceil(nwg/16) monotonic sub-counters (own lines); the last arriver of each
//          sub-counter arrives at the top counter, which everyone polls. base = barriers run so far.
enum class Kind { counter = 0, flag = 1, tree = 2 };
// wg:     work-group barriers with work-group fence scope around the leader's device-scope acq_rel atomics.
// device: work-group barriers with device fence scope (every work-item releases / acquires at device scope).
enum class Fence { wg = 0, device = 1 };

struct Bar {
  u32* ctl;
  u32 nwg;
  u32 base;   // counter or generation value at kernel entry
  u32 limit;  // max polls per barrier per leader
  u32 epoch = 0;
  u32 maxpolls = 0;  // largest poll count this group needed (leader only)
};

template <Kind K, Fence F>
inline bool gbar(const sycl::nd_item<1>& it, Bar& b) {
  auto g = it.get_group();
  if constexpr (F == Fence::device) sycl::group_barrier(g, sycl::memory_scope::device);
  else sycl::group_barrier(g);
  u32 ok = 1;
  if (g.leader()) {
    dref<u32> cnt(b.ctl[CNT]), gen(b.ctl[GEN]), err(b.ctl[ERR]);
    u32 polls = 0;
    if constexpr (K == Kind::counter) {
      const u32 target = b.base + (b.epoch + 1u) * b.nwg;
      u32 v = cnt.fetch_add(1u, sycl::memory_order::acq_rel) + 1u;
      while (int(v - target) < 0) {
        if (++polls > b.limit) { ok = 0; break; }
        if ((polls & 63u) == 0u && err.load() != 0u) { ok = 0; break; }
        v = cnt.load(sycl::memory_order::acquire);
      }
    } else if constexpr (K == Kind::tree) {
      const u32 E = b.base + b.epoch + 1u, g_id = u32(g.get_group_linear_id()), s_id = g_id / FANIN;
      const u32 nsub = (b.nwg + FANIN - 1u) / FANIN;
      const u32 ssize = s_id + 1u < nsub ? FANIN : b.nwg - s_id * FANIN;
      dref<u32> sub(b.ctl[SUB + s_id * 32u]);
      const u32 v = sub.fetch_add(1u, sycl::memory_order::acq_rel) + 1u;
      if (v == E * ssize) cnt.fetch_add(1u, sycl::memory_order::acq_rel);
      const u32 target = E * nsub;
      u32 t = cnt.load(sycl::memory_order::acquire);
      while (int(t - target) < 0) {
        if (++polls > b.limit) { ok = 0; break; }
        if ((polls & 63u) == 0u && err.load() != 0u) { ok = 0; break; }
        t = cnt.load(sycl::memory_order::acquire);
      }
    } else {
      const u32 mine = b.base + b.epoch;  // generation of this barrier instance
      const u32 old = cnt.fetch_add(1u, sycl::memory_order::acq_rel);
      if (old == b.nwg - 1u) {
        cnt.store(0u);
        gen.store(mine + 1u, sycl::memory_order::release);
      } else {
        while (gen.load(sycl::memory_order::acquire) == mine) {
          if (++polls > b.limit) { ok = 0; break; }
          if ((polls & 63u) == 0u && err.load() != 0u) { ok = 0; break; }
        }
      }
    }
    if (!ok) err.fetch_or(1u);
    if (polls > b.maxpolls) b.maxpolls = polls;
  }
  ok = sycl::group_broadcast(g, ok, 0);
  if constexpr (F == Fence::device) sycl::group_barrier(g, sycl::memory_scope::device);
  ++b.epoch;
  return ok != 0u;
}

// Host side: value of `base` for the next launch after one that ran `nbar` barriers with `nwg` groups.
template <Kind K>
inline u32 next_base(u32 base, u32 nbar, u32 nwg) {
  if constexpr (K == Kind::counter) return base + nbar * nwg;
  else return base + nbar;  // flag: generation; tree: barrier count
}

// At kernel end each leader publishes its largest poll count (one atomic per group per launch).
inline void publish_polls(const sycl::nd_item<1>& it, const Bar& b) {
  if (it.get_group().leader()) dref<u32>(b.ctl[MAXPOLL]).fetch_max(b.maxpolls);
}
}  // namespace pl
