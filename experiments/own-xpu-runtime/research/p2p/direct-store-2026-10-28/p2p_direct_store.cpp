// Kernel-direct cross-card exchange on two B70s (2026-10-28).
//
// Question: can a producing kernel write its output straight into the peer card's device memory and signal one flag,
// so that a gather costs well under 5 us (the exact-TP revisit threshold in research/tp/2026-10-25-exact-tp-closeout.md)?
//
// A. ping-pong: one persistent single-work-group kernel per card. A stores a payload into B's inbox (peer USM), release
//    fence (system scope), plain store of a sequence number into B's flag word; B spins (bounded) on its local flag,
//    acquire fence, verifies every element, replies the same way. One-way latency = (T(K2) - T(K1)) / (2 (K2 - K1)).
// B. engine-like chain: per card, an in-order stream of [producer: compute own half-rows, store locally AND into the
//    peer's gathered buffer, last work-group signals the peer's flag] -> [consumer: wait (bounded) for the peer's flag,
//    read and verify the full gathered buffer]. 48 layers x 3 exchanges x T tokens, submitted ahead without host waits.
//    Each kernel also runs a calibrated ALU loop (~12 us, like a decode-layer kernel) so the device, not the host
//    enqueue rate, paces the chain (attempt 1's host-USM gate kernel never saw the host's store and was removed).
//    Variants: none (same kernels, no peer store/wait), direct, and
//    memcpy (peer half pulled by a SYCL memcpy that depends on the peer producer's event: the old engine path).
//    Added us per exchange = (T_variant - T_none) / exchanges.
// C. correctness: every received element is compared bitwise against a sequence-dependent F32 pattern.
//    Ping-pong payload reads use system-scope atomic loads: attempt 1 showed that plain loads inside one persistent
//    kernel keep returning the previous round's (cached) payload even after an acquire fence. Chain consumers are fresh
//    kernels and use plain loads, as an engine consumer would.
//
// Safety: every device wait is iteration-capped (caps derived from an on-device spin calibration, far below the 5 s xe job
// timeout); a chain consumer that times out sets a local abort word so later consumers skip waiting; every host wait
// has a deadline; peer pointers are passed only as allocation bases; the remote flag is a plain store (no remote atomics).
// Build/run: see build.sh and run_device_phase.sh next to this file.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>
#include <thread>
#include <vector>

using u32 = uint32_t;
using u64 = uint64_t;
using clk = std::chrono::steady_clock;
static double secs(clk::time_point a, clk::time_point b) { return std::chrono::duration<double>(b - a).count(); }

constexpr auto SYS = sycl::memory_scope::system;
constexpr auto DEV = sycl::memory_scope::device;
template <sycl::memory_scope S>
using aref = sycl::atomic_ref<u32, sycl::memory_order::relaxed, S, sycl::access::address_space::global_space>;

constexpr u32 WG = 256;        // work-group size everywhere
constexpr u32 GP = 8;          // producer work-groups
constexpr u32 GC = 8;          // consumer work-groups
constexpr u32 RING = 4;        // gathered-buffer slots
constexpr u32 NMAX = 163840 / 4;  // largest payload per direction, in u32
constexpr u32 LAYERS = 48, XPL = 3;
// flags[] word offsets (separate 64-byte lines)
constexpr u32 F_PING = 0, F_CHAIN = 16, F_CTR = 32, F_CAL = 48, F_WORDS = 64;
// stats[] slots
enum : u32 { S_OWN = 0, S_PEER, S_STALE, S_TIMEOUT, S_SKIP, S_GATE_TIMEOUT, S_GATE_SPINS, S_ABORT, S_LONGSPIN, S_BUDGET_ABORT, S_WORDS = 16 };
constexpr u64 LONG_WAIT = 1000;  // consumer waits above this many polls count against the per-chain budget

// Sequence-dependent finite F32 bit pattern: sign + 23 random mantissa bits, exponent fixed (values in +-[0.5, 1)).
static inline u32 pattern(u32 seq, u32 card, u32 i) {
  u32 x = seq * 0x9E3779B1u ^ (card + 1u) * 0x85EBCA77u ^ i * 0xC2B2AE3Du;
  x ^= x >> 15; x *= 0x2C1B3C6Du; x ^= x >> 12; x *= 0x297A2D39u; x ^= x >> 15;
  return (x & 0x807FFFFFu) | 0x3F000000u;
}

// ---------------------------------------------------------------- host helpers
static std::string g_halt, g_async;
static long g_log_since = 0;
static std::string g_log_lines;

static bool complete(const sycl::event& e) {
  return e.get_info<sycl::info::event::command_execution_status>() == sycl::info::event_command_status::complete;
}
// Wait with a deadline. On expiry, record a halt and keep waiting up to a hard limit so bounded kernels can expire
// (never abandon in-flight GPU work); past the hard limit, exit without further device calls.
static void wait_deadline(const std::vector<sycl::event>& es, double soft_s, const char* what) {
  auto t0 = clk::now();
  bool warned = false;
  for (auto& e : es) {
    while (!complete(e)) {
      double t = secs(t0, clk::now());
      if (t > soft_s && !warned) {
        warned = true;
        g_halt = std::string("host deadline exceeded: ") + what;
        std::fprintf(stderr, "HALT: %s after %.1f s; waiting for bounded kernels to expire\n", what, t);
      }
      if (t > soft_s + 300.0) {
        std::fprintf(stderr, "FATAL: %s still incomplete after %.0f s\n", what, t);
        std::fflush(nullptr);
        std::_Exit(12);
      }
      std::this_thread::yield();
    }
  }
}

static bool fault_line(const std::string& l) {
  static const char* keys[] = {"xe 0000:", "GuC", "CAT error", "Engine reset", "Faulted", "Timedout", "devcoredump",
                               "page fault", "i915"};
  for (auto k : keys)
    if (l.find(k) != std::string::npos) return true;
  return false;
}
// Read the kernel log since g_log_since; any xe/GuC/fault line halts all further device work.
static bool kernel_log_clean(const char* label) {
  char cmd[256];
  std::snprintf(cmd, sizeof cmd, "journalctl -k --since=@%ld --no-pager -o short-iso 2>&1", g_log_since);
  FILE* p = popen(cmd, "r");
  if (!p) { g_halt = "cannot run journalctl"; return false; }
  std::string out, hits;
  char buf[4096];
  while (std::fgets(buf, sizeof buf, p)) out += buf;
  int rc = pclose(p);
  size_t pos = 0;
  while (pos < out.size()) {
    size_t e = out.find('\n', pos);
    if (e == std::string::npos) e = out.size();
    std::string l = out.substr(pos, e - pos);
    if (fault_line(l)) hits += l + "\n";
    pos = e + 1;
  }
  std::printf("[kernel-log %s] since @%ld: %s\n", label, g_log_since, hits.empty() ? "clean" : "FAULT LINES");
  if (rc != 0) { g_halt = std::string("journalctl failed at ") + label; return false; }
  if (!hits.empty()) {
    g_log_lines += hits;
    g_halt = std::string("xe kernel-log lines after ") + label;
    std::fputs(hits.c_str(), stdout);
    return false;
  }
  return true;
}

// minimal JSON writer
struct J {
  std::string s;
  bool first = true;
  void sep() { if (!first) s += ","; first = false; }
  J& open(const char* k = nullptr) { sep(); if (k) { s += "\""; s += k; s += "\":"; } s += "{"; first = true; return *this; }
  J& close() { s += "}"; first = false; return *this; }
  J& arr(const char* k) { sep(); s += "\""; s += k; s += "\":["; first = true; return *this; }
  J& aclose() { s += "]"; first = false; return *this; }
  J& kv(const char* k, double v) { sep(); char b[64]; std::snprintf(b, sizeof b, "\"%s\":%.6g", k, v); s += b; return *this; }
  J& ku(const char* k, u64 v) { sep(); char b[64]; std::snprintf(b, sizeof b, "\"%s\":%llu", k, (unsigned long long)v); s += b; return *this; }
  J& ks(const char* k, const std::string& v) {
    sep(); s += "\""; s += k; s += "\":\"";
    for (char c : v) { if (c == '"' || c == '\\') { s += '\\'; s += c; } else if (c == '\n') s += "\\n"; else if ((unsigned char)c >= 32) s += c; }
    s += "\""; return *this;
  }
};

static double median(std::vector<double> v) {
  if (v.empty()) return -1;
  std::sort(v.begin(), v.end());
  size_t n = v.size();
  return n % 2 ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}

// ---------------------------------------------------------------- device state
struct Card {
  explicit Card(sycl::queue qq) : q(std::move(qq)) {}  // no default-constructed queue (it would open a default context)
  sycl::queue q;
  std::string bdf, name, driver;
  u32* lin = nullptr;     // ping inbox (written by peer)
  u32* flags = nullptr;   // F_PING/F_CHAIN written by peer; F_CTR, F_CAL local
  u32* gath = nullptr;    // RING x 2 halves x NMAX
  u32* stats = nullptr;   // S_WORDS
  u32* spinlog = nullptr; // exchanges x GC
  u32* sink = nullptr;    // GC
  u64* pout = nullptr;    // ping results (8)
  u64* calout = nullptr;  // calibration result
};
static u32 g_max_ex = 0;

// ---------------------------------------------------------------- kernels
// Calibration: spin N times on a flag that never reaches 1 (local device memory or host USM). Local-only, no peer.
static sycl::event calib_spin(sycl::queue& q, u32* flag, u64* out, u64 n) {
  return q.single_task([=] {
    aref<SYS> f(*flag);
    u64 c = 0;
    u32 v = f.load();
    while (v < 1u && c < n) { ++c; v = f.load(); }
    out[0] = c + v;  // v is 0; keeps the load live
  });
}

// Ping-pong persistent kernel. role 0 sends first; role 1 replies. lflags/rflags/lin/rin are allocation bases.
static sycl::event ping(sycl::queue& q, u32 role, u32 me, u32 peer, u32 n, u32 K, u32* lin, u32* rin, u32* lflags,
                        u32* rflags, u64* out, u64 cap0, u64 cap, u64 total_cap) {
  return q.submit([&](sycl::handler& h) {
    sycl::local_accessor<u32, 1> ok(sycl::range<1>(1), h);
    h.parallel_for(sycl::nd_range<1>(WG, WG), [=](sycl::nd_item<1> it) {
      auto g = it.get_group();
      const u32 lid = it.get_local_linear_id();
      u32 mism = 0, rounds = 0, timeout = 0;
      u64 spins = 0, maxspin = 0;
      for (u32 r = 0; r < K; ++r) {
        const u32 seq = r + 1;
        if (role == 0) {
          for (u32 i = lid; i < n; i += WG) rin[i] = pattern(seq, me, i);
          sycl::atomic_fence(sycl::memory_order::release, SYS);
          sycl::group_barrier(g);
          if (lid == 0) {
            *reinterpret_cast<volatile u32*>(rflags + F_PING) = seq;
            sycl::atomic_fence(sycl::memory_order::release, SYS);
          }
        }
        if (lid == 0) {
          aref<SYS> f(lflags[F_PING]);
          const u64 left = total_cap > spins ? total_cap - spins : 0;
          const u64 lim = (r == 0 ? cap0 : cap) < left ? (r == 0 ? cap0 : cap) : left;
          u64 c = 0;
          u32 v = f.load();
          while (v < seq && c < lim) { ++c; v = f.load(); }
          spins += c;
          maxspin = c > maxspin ? c : maxspin;
          ok[0] = v >= seq ? 1u : 0u;
          if (v >= seq) sycl::atomic_fence(sycl::memory_order::acquire, SYS);
        }
        sycl::group_barrier(g);
        const u32 good = ok[0];
        if (!good) { timeout = 1; break; }
        sycl::atomic_fence(sycl::memory_order::acquire, SYS);
        for (u32 i = lid; i < n; i += WG) mism += aref<SYS>(lin[i]).load() != pattern(seq, peer, i) ? 1u : 0u;
        if (role == 1) {
          for (u32 i = lid; i < n; i += WG) rin[i] = pattern(seq, me, i);
          sycl::atomic_fence(sycl::memory_order::release, SYS);
          sycl::group_barrier(g);
          if (lid == 0) {
            *reinterpret_cast<volatile u32*>(rflags + F_PING) = seq;
            sycl::atomic_fence(sycl::memory_order::release, SYS);
          }
        }
        sycl::group_barrier(g);
        rounds = r + 1;
      }
      const u32 total = sycl::reduce_over_group(g, mism, sycl::plus<u32>());
      if (lid == 0) { out[0] = total; out[1] = timeout; out[2] = rounds; out[3] = spins; out[4] = maxspin; }
    });
  });
}

// Emulated layer work: a dependent ALU chain per work-item, independent of the payload and kept live.
static inline u32 busy(u32 h, u32 work) {
  for (u32 w = 0; w < work; ++w) h = (h ^ (h >> 7)) * 0x9E3779B1u + w;
  return h;
}
static sycl::event producer(sycl::queue& q, u32 me, u32 seq, u32 nh, u32 slot, u32* gl, u32* gr, u32* lflags,
                            u32* rflags, u32 direct, u32 work) {
  return q.parallel_for(sycl::nd_range<1>(GP * WG, WG), [=](sycl::nd_item<1> it) {
    const u32 gid = it.get_global_linear_id(), lid = it.get_local_linear_id();
    // salt is 0 unless the loop hits one value in 2^32; it makes the epilogue stores depend on the work, so the
    // compiler cannot hoist them above it (a nonzero salt would show up as mismatches, never hidden).
    const u32 salt = busy(gid ^ seq, work) == 0x7FFFFFFFu ? 1u : 0u;
    const u32 base = slot * 2u * NMAX + me * NMAX;
    for (u32 i = gid; i < nh; i += GP * WG) {
      const u32 v = pattern(seq, me, i) ^ salt;
      gl[base + i] = v;
      if (direct) gr[base + i] = v;
    }
    if (direct) {
      sycl::atomic_fence(sycl::memory_order::release, SYS);
      sycl::group_barrier(it.get_group());
      if (lid == 0) {
        aref<DEV> c(lflags[F_CTR]);
        const u32 old = c.fetch_add(1u, sycl::memory_order::acq_rel);
        if ((old + 1u) % GP == 0u) {
          sycl::atomic_fence(sycl::memory_order::acq_rel, SYS);
          *reinterpret_cast<volatile u32*>(rflags + F_CHAIN) = seq;
          sycl::atomic_fence(sycl::memory_order::release, SYS);
        }
      }
    }
  });
}

// Consumer: (direct) bounded wait on the local flag written by the peer, then read and verify the full gathered vector.
static sycl::event consumer(sycl::queue& q, u32 me, u32 seq, u32 xidx, u32 nh, u32 slot, u32* gl, u32* lflags,
                            u32* stats, u32* spinlog, u32* sink, u32 wait, u32 peer_slot, u64 cap, u32 budget, u32 work) {
  return q.parallel_for(sycl::nd_range<1>(GC * WG, WG), [=](sycl::nd_item<1> it) {
    auto g = it.get_group();
    const u32 gid = it.get_global_linear_id(), lid = it.get_local_linear_id(), grp = it.get_group_linear_id();
    if (wait) {
      if (lid == 0) {
        aref<DEV> ab(stats[S_ABORT]);
        u64 c = 0;
        if (ab.load() == 0u) {
          aref<SYS> f(lflags[F_CHAIN]);
          u32 v = f.load();
          while (v < seq && c < cap) { ++c; v = f.load(); }
          if (v < seq) { ab.store(1u); aref<DEV>(stats[S_TIMEOUT]).fetch_add(1u); }
          else sycl::atomic_fence(sycl::memory_order::acquire, SYS);
          if (c > LONG_WAIT) {  // rare: bound the chain's total waiting, whatever the per-exchange cap
            const u32 add = c < 0xffffffull ? u32(c) : 0xffffffu;
            if (aref<DEV>(stats[S_LONGSPIN]).fetch_add(add) + add > budget) { ab.store(1u); aref<DEV>(stats[S_BUDGET_ABORT]).store(1u); }
          }
        } else {
          aref<DEV>(stats[S_SKIP]).fetch_add(1u);
        }
        spinlog[xidx * GC + grp] = c < 0xffffffffull ? u32(c) : 0xffffffffu;
      }
      sycl::group_barrier(g);
      sycl::atomic_fence(sycl::memory_order::acquire, SYS);
    }
    const u32 base = slot * 2u * NMAX;
    u32 mo = 0, mp = 0, acc = 0;
    for (u32 j = gid; j < 2u * nh; j += GC * WG) {
      const u32 owner = j < nh ? 0u : 1u, i = j - owner * nh;
      const u32 v = gl[base + owner * NMAX + i];
      const u32 bad = v != pattern(seq, owner, i) ? 1u : 0u;
      if (owner == me) mo += bad; else mp += bad;
      acc ^= v;
    }
    if (busy(gid ^ seq ^ acc, work) == 0x7FFFFFFFu) acc ^= 1u;  // work after the read, like a layer's compute
    mo = sycl::reduce_over_group(g, mo, sycl::plus<u32>());
    mp = sycl::reduce_over_group(g, mp, sycl::plus<u32>());
    acc = sycl::reduce_over_group(g, acc, sycl::bit_xor<u32>());
    if (lid == 0) {
      aref<DEV>(stats[S_OWN]).fetch_add(mo);
      aref<DEV>(stats[peer_slot]).fetch_add(mp);
      sink[grp] = acc;
    }
  });
}

// ---------------------------------------------------------------- experiments
struct Caps { double ns_local = 0, ns_host = 0, ns_work = 0; u64 ping0 = 0, ping = 0, ping_total = 0, chain = 0, chain_budget = 0, gate = 0; u32 work = 0; };

static Caps calibrate(Card& a, sycl::queue& qa, u32* hostflag, J& j) {
  Caps c;
  auto timed = [&](u32* flag, u64 n) {
    auto t0 = clk::now();
    auto e = calib_spin(qa, flag, a.calout, n);
    wait_deadline({e}, 20.0, "calibration");
    return secs(t0, clk::now());
  };
  timed(a.flags + F_CAL, 100);  // warm
  const u64 nl = 20000, nh = 4000;
  double l1 = timed(a.flags + F_CAL, nl), l4 = timed(a.flags + F_CAL, 4 * nl);
  double h1 = timed(hostflag, nh), h4 = timed(hostflag, 4 * nh);
  c.ns_local = std::max(1.0, (l4 - l1) * 1e9 / double(3 * nl));
  c.ns_host = std::max(1.0, (h4 - h1) * 1e9 / double(3 * nh));
  auto cap = [](double ms, double ns, u64 lo, u64 hi) { return std::clamp<u64>(u64(ms * 1e6 / ns), lo, hi); };
  // Targets keep every kernel's worst case near or below ~0.4 s (xe job timeout is 5 s), even if polls ran 5x slower.
  c.ping0 = cap(200, c.ns_local, 10000, 20000000);  // first round also covers the peer kernel's launch skew
  c.ping = cap(20, c.ns_local, 2000, 2000000);
  c.ping_total = cap(300, c.ns_local, 10000, 30000000);  // all rounds of one persistent kernel together
  c.chain = cap(20, c.ns_local, 2000, 2000000);
  c.chain_budget = cap(300, c.ns_local, 10000, 16000000);  // long waits summed over one chain, per card
  c.gate = cap(400, c.ns_host, 2000, 4000000);
  std::printf("calibration: local flag poll %.1f ns/iter, host-USM flag poll %.1f ns/iter; caps ping0 %llu ping %llu chain %llu gate %llu\n",
              c.ns_local, c.ns_host, (unsigned long long)c.ping0, (unsigned long long)c.ping, (unsigned long long)c.chain,
              (unsigned long long)c.gate);
  j.open("calibration").kv("local_ns_per_poll", c.ns_local).kv("host_ns_per_poll", c.ns_host)
      .kv("local_t_20k_s", l1).kv("local_t_80k_s", l4).kv("host_t_4k_s", h1).kv("host_t_16k_s", h4)
      .ku("cap_ping_first_round", c.ping0).ku("cap_ping_round", c.ping).ku("cap_ping_total", c.ping_total)
      .ku("cap_chain_consumer", c.chain).ku("cap_chain_budget", c.chain_budget).ku("cap_gate", c.gate)
      .kv("cap_ping_first_round_ms", c.ping0 * c.ns_local * 1e-6).kv("cap_ping_round_ms", c.ping * c.ns_local * 1e-6)
      .kv("cap_ping_total_ms", c.ping_total * c.ns_local * 1e-6).kv("cap_chain_ms", c.chain * c.ns_local * 1e-6)
      .kv("cap_chain_budget_ms", c.chain_budget * c.ns_local * 1e-6).kv("cap_gate_ms", c.gate * c.ns_host * 1e-6).close();
  if (c.ns_local < 10 || c.ns_local > 20000 || c.ns_host < 50 || c.ns_host > 50000) g_halt = "implausible spin calibration";
  return c;
}

struct PingRes { double t = 0; u64 r[2][8] = {}; bool ok = false; };
static PingRes run_ping(Card& A, Card& B, u32 bytes, u32 K, const Caps& caps) {
  PingRes res;
  const u32 n = bytes / 4;
  std::vector<sycl::event> rs;
  for (Card* c : {&A, &B}) {
    rs.push_back(c->q.memset(c->flags, 0, F_WORDS * 4));
    rs.push_back(c->q.memset(c->lin, 0, NMAX * 4));
    rs.push_back(c->q.memset(c->pout, 0, 8 * 8));
  }
  wait_deadline(rs, 20.0, "ping reset");
  auto t0 = clk::now();
  auto eb = ping(B.q, 1, 1, 0, n, K, B.lin, A.lin, B.flags, A.flags, B.pout, caps.ping0, caps.ping, caps.ping_total);
  auto ea = ping(A.q, 0, 0, 1, n, K, A.lin, B.lin, A.flags, B.flags, A.pout, caps.ping0, caps.ping, caps.ping_total);
  wait_deadline({ea, eb}, 30.0, "ping kernels");
  res.t = secs(t0, clk::now());
  auto c1 = A.q.memcpy(res.r[0], A.pout, 64), c2 = B.q.memcpy(res.r[1], B.pout, 64);
  wait_deadline({c1, c2}, 20.0, "ping readback");
  res.ok = res.r[0][0] == 0 && res.r[1][0] == 0 && res.r[0][1] == 0 && res.r[1][1] == 0 && res.r[0][2] == K && res.r[1][2] == K;
  return res;
}
static void ping_json(J& j, const char* tag, u32 bytes, u32 K, const PingRes& p) {
  j.open().ks("tag", tag).ku("bytes", bytes).ku("rounds", K).kv("wall_s", p.t).kv("raw_one_way_us", K ? p.t * 1e6 / (2.0 * K) : 0)
      .ku("ok", p.ok);
  const char* nm[2] = {"cardA", "cardB"};
  for (int c = 0; c < 2; ++c)
    j.open(nm[c]).ku("mismatches", p.r[c][0]).ku("timeout", p.r[c][1]).ku("rounds_done", p.r[c][2])
        .ku("spin_sum", p.r[c][3]).ku("spin_max", p.r[c][4]).close();
  j.close();
}

enum Variant : u32 { V_NONE = 0, V_DIRECT = 1, V_MEMCPY = 2 };
static const char* vname(u32 v) { return v == V_NONE ? "none" : v == V_DIRECT ? "direct" : "memcpy"; }

struct ChainRes {
  u32 variant = 0, bytes = 0, ex = 0;
  double dev_s = 0, sub_s = 0;
  u32 st[2][S_WORDS] = {};
  u64 spin_sum[2] = {}, spin_max[2] = {}, spin_nonzero[2] = {};
  bool ok = false;
};
static ChainRes run_chain(Card& A, Card& B, u32* hostflag, u32 variant, u32 bytes, u32 tokens, u32 run_id, const Caps& caps) {
  ChainRes r;
  r.variant = variant; r.bytes = bytes;
  const u32 nh = bytes / 4, E = tokens * LAYERS * XPL;
  r.ex = E;
  if (E > g_max_ex) { g_halt = "chain too long for spinlog"; return r; }
  std::vector<sycl::event> rs;
  for (Card* c : {&A, &B}) {
    rs.push_back(c->q.memset(c->flags, 0, F_WORDS * 4));
    rs.push_back(c->q.memset(c->stats, 0, S_WORDS * 4));
    rs.push_back(c->q.memset(c->spinlog, 0, size_t(E) * GC * 4));
  }
  wait_deadline(rs, 20.0, "chain reset");
  (void)hostflag; (void)run_id;
  const u32 direct = variant == V_DIRECT ? 1u : 0u;
  const u32 peer_slot = variant == V_NONE ? S_STALE : S_PEER;
  auto ts0 = clk::now();
  sycl::event la, lb;
  for (u32 x = 0; x < E; ++x) {
    const u32 seq = x + 1, slot = x % RING;
    auto pa = producer(A.q, 0, seq, nh, slot, A.gath, B.gath, A.flags, B.flags, direct, caps.work);
    auto pb = producer(B.q, 1, seq, nh, slot, B.gath, A.gath, B.flags, A.flags, direct, caps.work);
    if (variant == V_MEMCPY) {
      const size_t base = size_t(slot) * 2 * NMAX;
      A.q.submit([&](sycl::handler& h) { h.depends_on(pb); h.memcpy(A.gath + base + NMAX, B.gath + base + NMAX, size_t(nh) * 4); });
      B.q.submit([&](sycl::handler& h) { h.depends_on(pa); h.memcpy(B.gath + base, A.gath + base, size_t(nh) * 4); });
    }
    la = consumer(A.q, 0, seq, x, nh, slot, A.gath, A.flags, A.stats, A.spinlog, A.sink, direct, peer_slot, caps.chain, u32(caps.chain_budget), caps.work);
    lb = consumer(B.q, 1, seq, x, nh, slot, B.gath, B.flags, B.stats, B.spinlog, B.sink, direct, peer_slot, caps.chain, u32(caps.chain_budget), caps.work);
  }
  auto ts1 = clk::now();
  r.sub_s = secs(ts0, ts1);
  wait_deadline({la, lb}, 30.0, "chain");
  r.dev_s = secs(ts0, clk::now());  // wall from first submit to both cards done; device-paced when sub_s << dev_s
  std::vector<u32> sl[2] = {std::vector<u32>(size_t(E) * GC), std::vector<u32>(size_t(E) * GC)};
  auto c1 = A.q.memcpy(r.st[0], A.stats, S_WORDS * 4), c2 = B.q.memcpy(r.st[1], B.stats, S_WORDS * 4);
  auto c3 = A.q.memcpy(sl[0].data(), A.spinlog, size_t(E) * GC * 4), c4 = B.q.memcpy(sl[1].data(), B.spinlog, size_t(E) * GC * 4);
  wait_deadline({c1, c2, c3, c4}, 20.0, "chain readback");
  for (int c = 0; c < 2; ++c)
    for (u32 v : sl[c]) { r.spin_sum[c] += v; r.spin_max[c] = std::max<u64>(r.spin_max[c], v); r.spin_nonzero[c] += v > 0; }
  r.ok = true;
  for (int c = 0; c < 2; ++c)
    r.ok = r.ok && r.st[c][S_OWN] == 0 && r.st[c][S_PEER] == 0 && r.st[c][S_TIMEOUT] == 0 && r.st[c][S_SKIP] == 0 &&
           r.st[c][S_BUDGET_ABORT] == 0;
  return r;
}
static void chain_json(J& j, const char* tag, const ChainRes& r) {
  j.open().ks("tag", tag).ks("variant", vname(r.variant)).ku("bytes_per_direction", r.bytes).ku("exchanges", r.ex)
      .kv("wall_s", r.dev_s).kv("us_per_exchange", r.ex ? r.dev_s * 1e6 / r.ex : 0).kv("submit_s", r.sub_s)
      .kv("submit_us_per_exchange", r.ex ? r.sub_s * 1e6 / r.ex : 0).ku("ok", r.ok);
  const char* nm[2] = {"cardA", "cardB"};
  for (int c = 0; c < 2; ++c)
    j.open(nm[c]).ku("own_mismatch", r.st[c][S_OWN]).ku("peer_mismatch", r.st[c][S_PEER])
        .ku("peer_stale_expected_in_none", r.st[c][S_STALE]).ku("timeouts", r.st[c][S_TIMEOUT]).ku("skipped", r.st[c][S_SKIP])
        .ku("abort", r.st[c][S_ABORT])
        .ku("long_wait_polls", r.st[c][S_LONGSPIN]).ku("budget_abort", r.st[c][S_BUDGET_ABORT])
        .ku("consumer_spin_sum", r.spin_sum[c]).ku("consumer_spin_max", r.spin_max[c]).ku("consumer_groups_that_spun", r.spin_nonzero[c])
        .close();
  j.close();
}

// ---------------------------------------------------------------- main
static void write_json(const std::string& path, J& j) {
  FILE* f = std::fopen(path.c_str(), "w");
  if (!f) { std::fprintf(stderr, "cannot write %s\n", path.c_str()); return; }
  std::fputs(j.s.c_str(), f);
  std::fclose(f);
}

static Card* g_cards[2] = {nullptr, nullptr};
static int run_main(int argc, char** argv) {
  std::setvbuf(stdout, nullptr, _IOLBF, 0);
  std::string mode = "smoke", out = "result.json";
  u32 tokens = 10, reps = 7, k1_arg = 200, k2_arg = 2000;
  for (int i = 1; i + 1 < argc; i += 2) {
    std::string k = argv[i], v = argv[i + 1];
    if (k == "--mode") mode = v; else if (k == "--out") out = v; else if (k == "--log-since") g_log_since = std::atol(v.c_str());
    else if (k == "--tokens") tokens = std::atoi(v.c_str()); else if (k == "--reps") reps = std::atoi(v.c_str());
    else if (k == "--k1") k1_arg = std::atoi(v.c_str()); else if (k == "--k2") k2_arg = std::atoi(v.c_str());
    else { std::fprintf(stderr, "unknown arg %s\n", k.c_str()); return 2; }
  }
  if (g_log_since == 0) g_log_since = long(std::time(nullptr)) - 1;
  J j;
  j.open().ks("tool", "p2p_direct_store").ks("mode", mode).ku("started_epoch", u64(std::time(nullptr)));
  auto finish = [&](int rc) {
    j.ks("halt", g_halt).ks("async_errors", g_async).ks("kernel_log_fault_lines", g_log_lines).ku("rc", rc).close();
    write_json(out, j);
    std::printf("wrote %s rc=%d%s%s\n", out.c_str(), rc, g_halt.empty() ? "" : " HALT: ", g_halt.c_str());
    return rc;
  };

  // Select exactly cards 0000:23:00.0 (A) and 0000:47:00.0 (B); refuse anything else.
  std::vector<sycl::device> gpus = sycl::device::get_devices(sycl::info::device_type::gpu);
  sycl::device dA, dB;
  int found = 0;
  for (auto& d : gpus) {
    if (!d.has(sycl::aspect::ext_intel_pci_address)) continue;
    auto bdf = d.get_info<sycl::ext::intel::info::device::pci_address>();
    if (bdf == "0000:23:00.0") { dA = d; ++found; }
    else if (bdf == "0000:47:00.0") { dB = d; ++found; }
    else { std::printf("refusing: unexpected visible GPU %s\n", bdf.c_str()); g_halt = "unexpected GPU visible: " + bdf; return finish(3); }
  }
  if (found != 2 || gpus.size() != 2) { g_halt = "need exactly 23:00.0 and 47:00.0 visible"; return finish(3); }
  const bool acc_ab = dA.ext_oneapi_can_access_peer(dB, sycl::ext::oneapi::peer_access::access_supported);
  const bool acc_ba = dB.ext_oneapi_can_access_peer(dA, sycl::ext::oneapi::peer_access::access_supported);
  const bool atom_ab = dA.ext_oneapi_can_access_peer(dB, sycl::ext::oneapi::peer_access::atomics_supported);
  const bool atom_ba = dB.ext_oneapi_can_access_peer(dA, sycl::ext::oneapi::peer_access::atomics_supported);
  std::string en_ab = "ok", en_ba = "ok";
  if (acc_ab) try { dA.ext_oneapi_enable_peer_access(dB); } catch (const sycl::exception& e) { en_ab = e.what(); }
  if (acc_ba) try { dB.ext_oneapi_enable_peer_access(dA); } catch (const sycl::exception& e) { en_ba = e.what(); }
  auto handler = [](sycl::exception_list l) {
    for (auto& p : l) try { std::rethrow_exception(p); } catch (const sycl::exception& e) { g_async += e.what(); g_async += "; "; }
  };
  sycl::context ctx({dA, dB}, handler);
  static Card A(sycl::queue(ctx, dA, handler, sycl::property::queue::in_order{}));
  static Card B(sycl::queue(ctx, dB, handler, sycl::property::queue::in_order{}));
  g_cards[0] = &A; g_cards[1] = &B;
  for (auto [c, d] : {std::pair<Card*, sycl::device*>{&A, &dA}, {&B, &dB}}) {
    c->bdf = d->get_info<sycl::ext::intel::info::device::pci_address>();
    c->name = d->get_info<sycl::info::device::name>();
    c->driver = d->get_info<sycl::info::device::driver_version>();
  }
  std::printf("A %s %s | B %s %s | driver %s\npeer access A->B %d (atomics %d), B->A %d (atomics %d); enable: %s / %s\n",
              A.bdf.c_str(), A.name.c_str(), B.bdf.c_str(), B.name.c_str(), A.driver.c_str(), acc_ab, atom_ab, acc_ba, atom_ba,
              en_ab.c_str(), en_ba.c_str());
  j.open("devices").ks("A", A.bdf).ks("B", B.bdf).ks("name", A.name).ks("driver", A.driver).ku("peer_access_A_to_B", acc_ab)
      .ku("peer_access_B_to_A", acc_ba).ku("peer_atomics_A_to_B", atom_ab).ku("peer_atomics_B_to_A", atom_ba)
      .ks("enable_A_to_B", en_ab).ks("enable_B_to_A", en_ba).close();
  auto scopes = [](const std::vector<sycl::memory_scope>& v) {
    std::string r;
    for (auto m : v) r += m == sycl::memory_scope::system ? "system " : m == sycl::memory_scope::device ? "device " :
                          m == sycl::memory_scope::work_group ? "work_group " : m == sycl::memory_scope::sub_group ? "sub_group " : "work_item ";
    return r;
  };
  const std::string atom_scopes = scopes(dA.get_info<sycl::info::device::atomic_memory_scope_capabilities>());
  const std::string fence_scopes = scopes(dA.get_info<sycl::info::device::atomic_fence_scope_capabilities>());
  std::printf("atomic scopes: %s| fence scopes: %s\n", atom_scopes.c_str(), fence_scopes.c_str());
  j.open("atomic_capabilities").ks("atomic_memory_scopes", atom_scopes).ks("fence_scopes", fence_scopes).close();
  j.open("config").ku("WG", WG).ku("producer_groups", GP).ku("consumer_groups", GC).ku("ring_slots", RING).ku("layers", LAYERS)
      .ku("exchanges_per_layer", XPL).ku("tokens", tokens).ku("reps", reps).ku("k1", k1_arg).ku("k2", k2_arg).close();
  if (!acc_ab || !acc_ba) { g_halt = "peer access not supported: valid negative, no peer kernel run"; return finish(20); }

  // Allocate (sizes fixed for the whole process) and pre-build kernels for both devices.
  g_max_ex = 20 * LAYERS * XPL;
  for (Card* c : {&A, &B}) {
    c->lin = sycl::malloc_device<u32>(NMAX, c->q);
    c->flags = sycl::malloc_device<u32>(F_WORDS, c->q);
    c->gath = sycl::malloc_device<u32>(size_t(RING) * 2 * NMAX, c->q);
    c->stats = sycl::malloc_device<u32>(S_WORDS, c->q);
    c->spinlog = sycl::malloc_device<u32>(size_t(g_max_ex) * GC, c->q);
    c->sink = sycl::malloc_device<u32>(GC, c->q);
    c->pout = sycl::malloc_device<u64>(8, c->q);
    c->calout = sycl::malloc_device<u64>(1, c->q);
    if (!c->lin || !c->flags || !c->gath || !c->stats || !c->spinlog || !c->sink || !c->pout || !c->calout) {
      g_halt = "allocation failed"; return finish(4);
    }
  }
  u32* hostflag = sycl::malloc_host<u32>(16, ctx);
  std::memset(hostflag, 0, 64);
  {
    auto t0 = clk::now();
    auto kb = sycl::get_kernel_bundle<sycl::bundle_state::executable>(ctx, {dA, dB});
    (void)kb;
    std::printf("kernel bundle built for both devices in %.2f s\n", secs(t0, clk::now()));
  }
  std::vector<sycl::event> rs;
  for (Card* c : {&A, &B}) {
    rs.push_back(c->q.memset(c->lin, 0, NMAX * 4));
    rs.push_back(c->q.memset(c->flags, 0, F_WORDS * 4));
    rs.push_back(c->q.memset(c->gath, 0, size_t(RING) * 2 * NMAX * 4));
    rs.push_back(c->q.memset(c->stats, 0, S_WORDS * 4));
    rs.push_back(c->q.memset(c->sink, 0, GC * 4));
  }
  wait_deadline(rs, 20.0, "initial memset");

  Caps caps = calibrate(A, A.q, hostflag, j);
  if (!g_halt.empty()) return finish(12);
  if (!kernel_log_clean("calibration")) return finish(11);

  int bad = 0;
  auto check_async = [&] { A.q.throw_asynchronous(); B.q.throw_asynchronous(); if (!g_async.empty()) { g_halt = "async error"; return false; } return true; };

  if (mode == "smoke") {
    // Smallest peer exchange: one round trip of 4 KB each way.
    j.arr("ping");
    auto p = run_ping(A, B, 4096, 1, caps);
    ping_json(j, "smoke", 4096, 1, p);
    j.aclose();
    std::printf("smoke 4096 B, 1 round trip: wall %.1f us, mismatches A %llu B %llu, timeouts A %llu B %llu, rounds %llu/%llu, spins A %llu B %llu -> %s\n",
                p.t * 1e6, (unsigned long long)p.r[0][0], (unsigned long long)p.r[1][0], (unsigned long long)p.r[0][1],
                (unsigned long long)p.r[1][1], (unsigned long long)p.r[0][2], (unsigned long long)p.r[1][2],
                (unsigned long long)p.r[0][3], (unsigned long long)p.r[1][3], p.ok ? "OK" : "FAIL");
    if (!check_async()) return finish(13);
    if (!kernel_log_clean("smoke ping")) return finish(11);
    return finish(p.ok ? 0 : 10);
  }
  if (mode != "main") { g_halt = "unknown mode"; return finish(2); }
  {  // calibrate the emulated layer work on card A alone (no peer access): one producer launch, two loop lengths
    auto timed = [&](u32 w) {
      auto t0 = clk::now();
      auto e = producer(A.q, 0, 1, 1024, 0, A.gath, B.gath, A.flags, B.flags, 0u, w);
      wait_deadline({e}, 20.0, "work calibration");
      return secs(t0, clk::now());
    };
    timed(1000);
    const double t1 = timed(20000), t2 = timed(100000);
    caps.ns_work = std::max(0.05, (t2 - t1) * 1e9 / 80000.0);
    caps.work = u32(std::clamp(12000.0 / caps.ns_work, 100.0, 200000.0));  // ~12 us per kernel
    std::printf("work calibration: %.3f ns per loop iteration -> work=%u (~%.1f us per kernel)\n", caps.ns_work, caps.work,
                caps.work * caps.ns_work * 1e-3);
    j.open("work_calibration").kv("ns_per_iter", caps.ns_work).kv("t_20k_s", t1).kv("t_100k_s", t2).ku("work", caps.work)
        .kv("target_us_per_kernel", 12.0).close();
    if (!kernel_log_clean("work calibration")) return finish(11);
  }

  const u32 sizes[4] = {4096, 10240, 40960, 163840};
  u32 run_id = 0;
  // ---- phase 1: pre-scale (all sizes once, small) -- must be perfectly clean before scaling up
  j.arr("prescale_ping");
  for (u32 b : sizes) {
    auto p = run_ping(A, B, b, 10, caps);
    ping_json(j, "prescale", b, 10, p);
    std::printf("prescale ping %6u B K=10: %s (wall %.1f us)\n", b, p.ok ? "OK" : "FAIL", p.t * 1e6);
    if (!p.ok) ++bad;
    if (!g_halt.empty()) break;
  }
  j.aclose();
  if (!check_async() || !g_halt.empty()) return finish(13);
  j.arr("prescale_chain");
  for (u32 b : sizes) {
    for (u32 v : {V_NONE, V_DIRECT}) {
      auto r = run_chain(A, B, hostflag, v, b, 1, ++run_id, caps);
      chain_json(j, "prescale", r);
      std::printf("prescale chain %6u B %-6s E=%u: %s (%.2f us/exchange, submit %.2f us/exchange)\n", b, vname(v), r.ex,
                  r.ok ? "OK" : "FAIL", r.dev_s * 1e6 / r.ex, r.sub_s * 1e6 / r.ex);
      if (!r.ok) ++bad;
      if (!g_halt.empty()) break;
    }
  }
  j.aclose();
  if (!check_async()) return finish(13);
  if (!kernel_log_clean("prescale")) return finish(11);
  if (bad) { g_halt = "prescale correctness failure: not scaling up"; return finish(10); }

  // ---- phase 2: ping-pong latency
  j.arr("ping");
  std::vector<std::pair<u32, double>> ping_summary;
  J sum;
  sum.arr("ping_summary");
  for (u32 b : sizes) {
    std::vector<double> t1, t2;
    // fewer rounds for large payloads keeps each persistent kernel's spin total far inside its budget
    const u32 div = b <= 10240 ? 1u : b <= 40960 ? 2u : 4u, k1 = k1_arg / div, k2 = k2_arg / div;
    for (u32 r = 0; r < reps && g_halt.empty(); ++r) {
      for (int w = 0; w < 2; ++w) {
        const u32 K = ((r + w) % 2) ? k2 : k1;
        auto p = run_ping(A, B, b, K, caps);
        ping_json(j, "ping", b, K, p);
        if (!p.ok) ++bad;
        (K == k1 ? t1 : t2).push_back(p.t);
      }
    }
    const double one_way = (median(t2) - median(t1)) * 1e6 / (2.0 * (k2 - k1));
    std::printf("ping %6u B: median T(K=%u) %.1f us, T(K=%u) %.1f us -> one-way %.3f us (raw %.3f)\n", b, k1, median(t1) * 1e6, k2,
                median(t2) * 1e6, one_way, median(t2) * 1e6 / (2.0 * k2));
    sum.open().ku("bytes", b).ku("k1", k1).ku("k2", k2).kv("median_T_k1_us", median(t1) * 1e6).kv("median_T_k2_us", median(t2) * 1e6)
        .kv("one_way_us", one_way).kv("raw_one_way_us_k2", median(t2) * 1e6 / (2.0 * k2)).close();
  }
  sum.aclose();
  j.aclose();
  j.s += "," + sum.s;
  if (!check_async()) return finish(13);
  if (!kernel_log_clean("ping-pong")) return finish(11);

  // ---- phase 3: chain none vs direct (decision metric), then none vs memcpy (old path, same harness)
  auto chain_phase = [&](const char* name, u32 variant, u32 nreps) {
    J s2;
    s2.arr((std::string(name) + "_summary").c_str());
    j.arr(name);
    for (u32 b : sizes) {
      if (!g_halt.empty()) break;
      for (u32 v : {u32(V_NONE), variant}) { auto w = run_chain(A, B, hostflag, v, b, tokens, ++run_id, caps); chain_json(j, "warm", w); }
      std::vector<double> tn, tv, sn, sv;
      u32 ex = 0;
      for (u32 r = 0; r < nreps && g_halt.empty(); ++r) {
        for (int w = 0; w < 2; ++w) {
          const u32 v = ((r + w) % 2) ? variant : V_NONE;
          auto res = run_chain(A, B, hostflag, v, b, tokens, ++run_id, caps);
          chain_json(j, "timed", res);
          if (!res.ok) ++bad;
          ex = res.ex;
          (v == V_NONE ? tn : tv).push_back(res.dev_s);
          (v == V_NONE ? sn : sv).push_back(res.sub_s);
        }
      }
      if (!ex) break;
      const double pn = median(tn) * 1e6 / ex, pv = median(tv) * 1e6 / ex;
      std::printf("chain %6u B: none %.3f us/exchange, %s %.3f us/exchange -> added %.3f us per exchange (submit none %.2f, %s %.2f us/exchange)\n",
                  b, pn, vname(variant), pv, pv - pn, median(sn) * 1e6 / ex, vname(variant), median(sv) * 1e6 / ex);
      s2.open().ku("bytes_per_direction", b).ks("variant", vname(variant)).ku("exchanges", ex).kv("none_us_per_exchange", pn)
          .kv("variant_us_per_exchange", pv).kv("added_us_per_exchange", pv - pn)
          .kv("none_min_us_per_exchange", *std::min_element(tn.begin(), tn.end()) * 1e6 / ex)
          .kv("variant_min_us_per_exchange", *std::min_element(tv.begin(), tv.end()) * 1e6 / ex)
          .kv("none_max_us_per_exchange", *std::max_element(tn.begin(), tn.end()) * 1e6 / ex)
          .kv("variant_max_us_per_exchange", *std::max_element(tv.begin(), tv.end()) * 1e6 / ex)
          .kv("submit_none_us_per_exchange", median(sn) * 1e6 / ex).kv("submit_variant_us_per_exchange", median(sv) * 1e6 / ex).close();
    }
    j.aclose();
    s2.aclose();
    j.s += "," + s2.s;
  };
  chain_phase("chain_direct", V_DIRECT, reps);
  if (!check_async()) return finish(13);
  if (!kernel_log_clean("chain direct")) return finish(11);
  if (!g_halt.empty()) return finish(12);
  chain_phase("chain_memcpy", V_MEMCPY, 5);
  if (!check_async()) return finish(13);
  if (!kernel_log_clean("chain memcpy")) return finish(11);
  for (Card* c : {&A, &B}) {
    sycl::free(c->lin, c->q); sycl::free(c->flags, c->q); sycl::free(c->gath, c->q); sycl::free(c->stats, c->q);
    sycl::free(c->spinlog, c->q); sycl::free(c->sink, c->q); sycl::free(c->pout, c->q); sycl::free(c->calout, c->q);
  }
  sycl::free(hostflag, ctx);
  return finish(bad ? 10 : (g_halt.empty() ? 0 : 12));
}

// Any synchronous SYCL error: record it, then drain both in-order queues with a deadline (never exit with kernels in
// flight while they can still finish).
int main(int argc, char** argv) {
  try {
    return run_main(argc, argv);
  } catch (const std::exception& e) {
    std::fprintf(stderr, "EXCEPTION: %s\n", e.what());
    std::vector<sycl::event> es;
    for (Card* c : g_cards)
      if (c) try { es.push_back(c->q.ext_oneapi_submit_barrier()); } catch (...) {}
    try { wait_deadline(es, 30.0, "drain after exception"); } catch (...) {}
    std::fflush(nullptr);
    return 14;
  }
}
