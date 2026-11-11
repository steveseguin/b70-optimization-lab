// Card-to-card exchange by DIRECT PEER STORES in one shared native Level Zero context (lever L1, step 2).
//
// WHAT IT MEASURES
//   Today every exchange (XchgPull, sycl_v41.hpp) is a launch + a flag round trip + a load round trip over PCIe,
//   ~12 us, with peers opened by IPC handles into one context per card. SC117 (four-card host) used one native context
//   for all cards: the producing kernel stored its rows straight into the peer's memory, release fence, flag store, and
//   the reader polled its OWN memory: 1.4-3.3 us added per exchange at 4-40 KB (research/p2p/direct-store-2026-10-28).
//   This bench measures both transports on this host with the same kernels, verified every round:
//     push  sender stores the payload into the receiver's inbox (peer memory), system-scope release fence, then the
//           sequence number into the receiver's flag word (peer memory); receiver polls its local flag, reads locally.
//     pull  today's method (XchgPull): sender stores into its own outbox, release fence, flag into the receiver's flag
//           word; receiver polls its local flag, then loads the payload from the sender's outbox (peer memory).
//   Topologies: pair (A->B, B->A ping-pong; --pairs), ring over all --cards (a token passes card to card), a2a (every
//   card sends its slice to every other card each round = the engine's all-gather).
//   Forms:
//     persist  ONE kernel per card runs K rounds (no launches, device time only; profiling timestamps). Payload reads
//              use system-scope atomic loads: SC117 attempt 1 found plain loads inside one persistent kernel return the
//              previous round's (cached) payload even after an acquire fence. pull+persist would need atomic loads OF
//              PEER MEMORY, so it runs only with --persist-pull (P2P atomics are printed below; SC117 had none).
//     fresh    one kernel per round, all submitted ahead on an in-order queue (the engine's shape: every exchange is
//              read by a new kernel, plain vector loads, as SC117's chain consumers and XchgPull). Includes the kernel
//              boundary on the critical path; host clock, the queues run ahead.
//   Every time is (T(K2) - T(K1)) / (K2 - K1) from medians of --reps alternating runs, so launch and start skew cancel.
//   pair/ring report the ONE-WAY time per hop (round / hops); a2a reports the time per all-gather round.
//   --ctx=ipc runs the identical kernels with today's setup (one native context per card, peers opened by IPC handles)
//   as the control; --ctx=shared (default) is the SC117 setup.
//
// FENCES AND ATOMICS (as the engine and SC117): data stores, then sycl::atomic_fence(release, system) by every item
//   (orders this work-group's peer stores before its count), a device-scope acq_rel counter per round parity picks the
//   last work-group, which fences (acq_rel, system), stores the flag(s) and fences (release, system). The flag store is
//   a plain volatile store by default (SC117: "no peer atomics", nothing atomic touches peer memory); --flag=atomic uses
//   atomic_ref<system>::store as XchgP / XchgPull do today. Polling is a relaxed system-scope atomic load of the
//   receiver's own memory (written over PCIe by the peer, so device scope is not enough), then an acquire fence at
//   system scope. Peer pointers reach the kernel only as direct kernel arguments (the engine runs with
//   DisableIndirectAccess=1; a pointer inside a by-value struct is not made resident and faulted, 2026-11-09 23:58).
//   Buffers alternate by round parity; a sender rewrites a parity only after a flag proving every reader is done.
//   What the compiler makes of it (AOT bmg_g31, oneAPI 2026.1, IGC dump of this file, 2026-11-11): every
//   memory_scope::system fence is a GPU-scope LSC fence (release = fence.ugm.none.gpu, acquire =
//   fence.ugm.invalidate.gpu; no system-scope fence is emitted), so cross-card ordering rests on PCIe posted-write
//   order, and the per-round check is the proof. atomic_ref::load() is an atomic_or RMW and atomic_ref::store() an
//   atomic_store: --flag=atomic, today's XchgP / XchgPull flag stores and --persist-pull are atomic operations ON PEER
//   MEMORY; the default plain flag store and pull's plain loads are not. The seven pointers are separate 8-byte kernel
//   arguments; no register spills.
//
// SAFETY
//   * every wait gives up after --cap polls (default 2^20), and each work-item polls at most --total-cap (2^22, ~0.6 s)
//     per kernel; a timeout sets the card's abort word (later waits skip) and an error count. Nothing can hang.
//   * persistent kernels are sized from two pilots (4 rounds, then <= ~0.02 s) so a kernel runs ~0.15 s and never more
//     than ~15x the second pilot (well under xe's 5 s job timeout).
//   * the kernel is built on every card, one card at a time, with zero rounds before the first exchange (a card still
//     building its module while a peer waits would time that wait out; the engine pre-builds for the same reason).
//   * the first timeout stops all further runs; refuses peers the driver says it cannot access; refuses a card with
//     < 1 GiB free (when ZES_ENABLE_SYSMAN=1 lets SYCL read it); stops if host MemAvailable < 4 GiB at any check.
//   * arenas are 4 MiB per card (~0.9 MiB used), so even a 1:1 host-RAM shadow is a few MiB. Run the host-RAM probe
//     (probe_shared_ctx_ram.cpp) first anyway; xe fdinfo per card is printed before and after.
//   Exit 1 on any wrong value or timeout, 2 on refused setup, 3 on a host-memory stop.
//
// WHAT RESULT JUSTIFIES PORTING
//   persist push pair one-way at 9,728 B under ~4 us (SC117: 1.6 us at 10 KB) AND fresh a2a push clearly below fresh
//   a2a pull at 3,456 / 9,728 B (today's XchgPull is ~12 us per exchange; ~160 exchanges per token on six cards: each
//   us saved per exchange is ~0.16 ms of the 11.7 ms token). If push in the shared context is no faster than in the
//   IPC control, the ~1 GB/s store rate is the fabric and L1 is closed.
//
// BUILD (one compile at a time, host RAM is small)
//   cd engine; S=/home/steve/dsv41-work/bin; export PATH=/opt/intel/oneapi/compiler/latest/bin:$PATH
//   nice -n 10 icpx -fsycl -fsycl-targets=intel_gpu_bmg_g31 -O2 -std=c++20 -Wno-deprecated-declarations \
//     tools/bench/xchg_direct_bench.cpp -o $S/xchg_direct_bench -lze_loader
// RUN (cards empty; probe_shared_ctx_ram first)
//   E="ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 ZES_ENABLE_SYSMAN=1 NEOReadDebugKeys=1 DisableIndirectAccess=1 EnableDeferBacking=0"
//   env $E $S/xchg_direct_bench --cards=0,1 --topos=pair --forms=persist --sizes=3456 --reps=3   (smoke, two cards)
//   env $E $S/xchg_direct_bench                                    (six cards: pair 0-1, ring, a2a, all sizes)
//   env $E $S/xchg_direct_bench --ctx=ipc                          (control: today's contexts and IPC peers)
//   options (defaults): --ctx=shared|ipc  --cards=0,..,N-1 (all visible, at most 6)  --pairs=0-1[,2-3,...]
//     --sizes=0,3456,9728,16384,65536 (bytes per message, multiples of 16, at most 65536; 0 = flag only)
//     --topos=pair,ring,a2a  --forms=persist,fresh  --methods=push,pull  --persist-pull  --flag=plain|atomic
//     --k1=200 --k2=2000 (persistent rounds, upper bounds)  --fk1=100 --fk2=500 (fresh rounds, upper bounds)
//     --reps=7  --wg=0 (work-groups per kernel; 0 = 1 per 8 KiB, at most 16)  --cap=1048576  --total-cap=4194304
//     --one-sycl-ctx (shared: one SYCL context for all queues instead of one per card over the same native context)
#include <sycl/sycl.hpp>
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <level_zero/ze_api.h>
#include <dirent.h>
#include <algorithm>
#include <atomic>
#include <barrier>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <string>
#include <thread>
#include <vector>

using u32 = uint32_t;
static double now_s() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }

namespace xd {
constexpr u32 WG = 256;
constexpr u32 MAXC = 6;                       // cards in a group (six peer arguments)
constexpr u32 MAXB = 65536, MAXW = MAXB / 4;  // largest message
// arena layout (u32 words); every card's arena has the same layout
constexpr u32 A_FLAGS = 0;                            // flag written by group position s: word 16 * s (own 64-byte line)
constexpr u32 A_INBOX = 1024;                         // push: [parity 2][source MAXC][MAXW]
constexpr u32 A_OUTBOX = A_INBOX + 2 * MAXC * MAXW;   // pull: [parity 2][MAXW]
constexpr u32 A_WORDS = A_OUTBOX + 2 * MAXW;
constexpr size_t ARENA_BYTES = size_t(4) << 20;
static_assert(size_t(A_WORDS) * 4 <= ARENA_BYTES, "arena");
// per-card statistics (local device memory, never touched by a peer)
enum : u32 { S_MISM = 0, S_TIMEOUT = 1, S_ABORT = 2, S_MAXPOLL = 3, S_POLLED = 4, S_POLLSUM = 5, S_SKIP = 6,
             S_CTR0 = 16, S_CTR1 = 32, S_WORDS = 64 };

// changing data: depends on (sequence number, sending position, element)
static inline u32 pattern(u32 seq, u32 src, u32 i) {
    u32 x = seq * 0x9E3779B1u ^ (src + 1u) * 0x85EBCA77u ^ i * 0xC2B2AE3Du;
    x ^= x >> 15; x *= 0x2C1B3C6Du; x ^= x >> 12; x *= 0x297A2D39u; x ^= x >> 15;
    return x;
}

using V4 = sycl::vec<u32, 4>;
struct XK {
    u32 me, n, rounds, vec4s, seq0, cap, total_cap;
    u32 a2a, pull, atomic_read, flag_atomic, G;
    static u32 *pick(u32 d, u32 *a0, u32 *a1, u32 *a2, u32 *a3, u32 *a4, u32 *a5) {
        // a select chain, not an array (a pointer loaded from an indexed array counts as indirect access)
        return d == 0 ? a0 : d == 1 ? a1 : d == 2 ? a2 : d == 3 ? a3 : d == 4 ? a4 : a5;
    }
    void operator()(sycl::nd_item<1> it, u32 *a0, u32 *a1, u32 *a2, u32 *a3, u32 *a4, u32 *a5, u32 *st) const {
        using SYS = sycl::atomic_ref<u32, sycl::memory_order::relaxed, sycl::memory_scope::system, sycl::access::address_space::global_space>;
        using DEV = sycl::atomic_ref<u32, sycl::memory_order::relaxed, sycl::memory_scope::device, sycl::access::address_space::global_space>;
        auto g = it.get_group();
        const u32 lid = (u32)it.get_local_linear_id(), T = G * WG, gid = (u32)it.get_group_linear_id() * WG + lid;
        u32 *mine = pick(me, a0, a1, a2, a3, a4, a5);
        const u32 next = me + 1 == n ? 0u : me + 1, prev = me == 0 ? n - 1 : me - 1;
        u32 mism = 0, polled = 0;
        for (u32 r = 0; r < rounds; ++r) {
            const u32 seq = seq0 + r + 1, par = seq & 1u;
            // ---- send: payload, release, count, last work-group raises the flag(s)
            auto send = [&]() {
                if (pull) {
                    V4 *dst = reinterpret_cast<V4 *>(mine + A_OUTBOX + par * MAXW);
                    for (u32 k = gid; k < vec4s; k += T)
                        dst[k] = V4(pattern(seq, me, 4 * k), pattern(seq, me, 4 * k + 1), pattern(seq, me, 4 * k + 2), pattern(seq, me, 4 * k + 3));
                } else {
                    for (u32 d = 0; d < n; ++d) {
                        if (d == me || (!a2a && d != next)) continue;
                        V4 *dst = reinterpret_cast<V4 *>(pick(d, a0, a1, a2, a3, a4, a5) + A_INBOX + (par * MAXC + me) * MAXW);
                        for (u32 k = gid; k < vec4s; k += T)
                            dst[k] = V4(pattern(seq, me, 4 * k), pattern(seq, me, 4 * k + 1), pattern(seq, me, 4 * k + 2), pattern(seq, me, 4 * k + 3));
                    }
                }
                sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
                sycl::group_barrier(g);
                if (lid == 0) {
                    const u32 old = DEV(st[par ? S_CTR1 : S_CTR0]).fetch_add(1u, sycl::memory_order::acq_rel);
                    if ((old + 1u) % G == 0u) {
                        sycl::atomic_fence(sycl::memory_order::acq_rel, sycl::memory_scope::system);
                        for (u32 d = 0; d < n; ++d) {
                            if (d == me || (!a2a && d != next)) continue;
                            u32 *f = pick(d, a0, a1, a2, a3, a4, a5) + A_FLAGS + 16 * me;
                            if (flag_atomic) SYS(*f).store(seq);
                            else *reinterpret_cast<volatile u32 *>(f) = seq;
                        }
                        sycl::atomic_fence(sycl::memory_order::release, sycl::memory_scope::system);
                    }
                }
            };
            // ---- wait: ring: item 0 polls prev; a2a: item t polls source t. Bounded; uniform result per work-group.
            auto wait = [&]() -> bool {
                bool bad = false;
                const bool poller = a2a ? (lid < n && lid != me) : lid == 0;
                if (poller) {
                    const u32 s = a2a ? lid : prev;
                    if (DEV(st[S_ABORT]).load() != 0u) {
                        DEV(st[S_SKIP]).fetch_add(1u);
                        bad = true;
                    } else {
                        SYS f(mine[A_FLAGS + 16 * s]);
                        const u32 left = total_cap > polled ? total_cap - polled : 0u, lim = cap < left ? cap : left;
                        u32 c = 0, v = f.load();
                        while (v < seq && c < lim) { ++c; v = f.load(); }
                        polled += c;
                        if (c) {
                            DEV(st[S_POLLED]).fetch_add(1u);
                            DEV(st[S_POLLSUM]).fetch_add(c);
                            DEV(st[S_MAXPOLL]).fetch_max(c);
                        }
                        if (v < seq) {
                            DEV(st[S_ABORT]).store(1u);
                            DEV(st[S_TIMEOUT]).fetch_add(1u);
                            bad = true;
                        } else {
                            sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
                        }
                    }
                }
                bad = sycl::any_of_group(g, bad);
                sycl::group_barrier(g);
                if (!bad) sycl::atomic_fence(sycl::memory_order::acquire, sycl::memory_scope::system);
                return !bad;
            };
            // ---- verify every element received from position s
            auto verify = [&](u32 s) {
                u32 *src = pull ? pick(s, a0, a1, a2, a3, a4, a5) + A_OUTBOX + par * MAXW : mine + A_INBOX + (par * MAXC + s) * MAXW;
                for (u32 k = gid; k < vec4s; k += T) {
                    u32 v0, v1, v2, v3;
                    if (atomic_read) {
                        v0 = SYS(src[4 * k]).load(); v1 = SYS(src[4 * k + 1]).load();
                        v2 = SYS(src[4 * k + 2]).load(); v3 = SYS(src[4 * k + 3]).load();
                    } else {
                        const V4 v = reinterpret_cast<const V4 *>(src)[k];
                        v0 = v[0]; v1 = v[1]; v2 = v[2]; v3 = v[3];
                    }
                    mism += (v0 != pattern(seq, s, 4 * k) ? 1u : 0u) + (v1 != pattern(seq, s, 4 * k + 1) ? 1u : 0u) +
                            (v2 != pattern(seq, s, 4 * k + 2) ? 1u : 0u) + (v3 != pattern(seq, s, 4 * k + 3) ? 1u : 0u);
                }
            };
            bool ok;
            if (a2a) {
                send();
                ok = wait();
                if (ok)
                    for (u32 s = 0; s < n; ++s)
                        if (s != me) verify(s);
            } else {
                if (me == 0) send();
                ok = wait();
                if (ok) verify(prev);
                if (me != 0) send(); // also after a failed wait, so the next card's wait ends normally
            }
            sycl::group_barrier(g); // this round's reads are done before any later flag of this card
            if (!ok && rounds > 1) break; // persistent: stop at the first failed wait (the peers then time out, bounded)
        }
        mism = sycl::reduce_over_group(g, mism, sycl::plus<u32>());
        if (lid == 0 && mism) DEV(st[S_MISM]).fetch_add(mism);
    }
};
// the one launch site (one kernel for both forms; every pointer is its own direct kernel argument)
static sycl::event launch(sycl::queue &q, u32 G, const XK &k, u32 *a0, u32 *a1, u32 *a2, u32 *a3, u32 *a4, u32 *a5, u32 *st) {
    return q.parallel_for(sycl::nd_range<1>((size_t)G * WG, WG), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
        k(it, a0, a1, a2, a3, a4, a5, st);
    });
}
} // namespace xd
using namespace xd;

// ------------------------------------------------------------------------------------------------ host helpers
static long long meminfo_kib(const char *key) {
    std::ifstream f("/proc/meminfo");
    std::string k, unit;
    long long v;
    while (f >> k >> v) {
        std::getline(f, unit);
        if (k == std::string(key) + ":") return v;
    }
    return -1;
}
// this process's xe fdinfo per PCI device: "vram0 T/R system T/R ..." in MiB (total/resident)
static std::map<std::string, std::string> fdinfo_brief() {
    std::map<std::string, std::map<std::string, std::pair<long long, long long>>> reg;
    std::set<std::string> seen;
    DIR *d = opendir("/proc/self/fdinfo");
    if (d) {
        while (auto *e = readdir(d)) {
            if (e->d_name[0] == '.') continue;
            std::ifstream f(std::string("/proc/self/fdinfo/") + e->d_name);
            std::string line, pdev, client;
            std::vector<std::pair<std::string, long long>> kv;
            bool drm = false;
            while (std::getline(f, line)) {
                const size_t c = line.find(':');
                if (c == std::string::npos) continue;
                const std::string k = line.substr(0, c);
                std::string v = line.substr(c + 1);
                v.erase(0, v.find_first_not_of(" \t"));
                if (k == "drm-driver") drm = true;
                else if (k == "drm-pdev") pdev = v;
                else if (k == "drm-client-id") client = v;
                else if (k.rfind("drm-total-", 0) == 0 || k.rfind("drm-resident-", 0) == 0) {
                    char *end = nullptr;
                    long long n = std::strtoll(v.c_str(), &end, 10);
                    std::string unit = end ? end : "";
                    unit.erase(0, unit.find_first_not_of(" \t"));
                    if (unit.rfind("KiB", 0) == 0) n <<= 10;
                    else if (unit.rfind("MiB", 0) == 0) n <<= 20;
                    else if (unit.rfind("GiB", 0) == 0) n <<= 30;
                    kv.push_back({k.substr(4), n});
                }
            }
            if (!drm || pdev.empty() || !seen.insert(pdev + "/" + client).second) continue;
            for (auto &[k, n] : kv) {
                if (k.rfind("total-", 0) == 0) reg[pdev][k.substr(6)].first += n;
                else reg[pdev][k.substr(9)].second += n;
            }
        }
        closedir(d);
    }
    std::map<std::string, std::string> out;
    for (auto &[pdev, m] : reg) {
        std::string s;
        char b[96];
        for (auto &[r, tr] : m) {
            std::snprintf(b, sizeof b, "%s%s %.1f/%.1f", s.empty() ? "" : " ", r.c_str(), tr.first / 1048576.0, tr.second / 1048576.0);
            s += b;
        }
        out[pdev] = s;
    }
    return out;
}
static std::vector<std::string> split(const std::string &s, char c) {
    std::vector<std::string> v;
    for (size_t p = 0; p <= s.size();) {
        size_t q = s.find(c, p);
        if (q == std::string::npos) q = s.size();
        if (q > p) v.push_back(s.substr(p, q - p));
        p = q + 1;
    }
    return v;
}
static double median(std::vector<double> v) {
    std::sort(v.begin(), v.end());
    const size_t n = v.size();
    return n == 0 ? 0.0 : n % 2 ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}
// poll an event (no blocking wait inside the runtime); yield keeps the host-side latency at a few us
static void wait_event(const sycl::event &e, const char *what) {
    const double t0 = now_s();
    bool warned = false;
    while (e.get_info<sycl::info::event::command_execution_status>() != sycl::info::event_command_status::complete) {
        if (!warned && now_s() - t0 > 20.0) {
            warned = true;
            std::fprintf(stderr, "WARNING: %s still running after 20 s (every wait is bounded; waiting on)\n", what);
        }
        std::this_thread::yield();
    }
}

struct Card {
    int index = -1;
    sycl::device dev;
    ze_device_handle_t zd = nullptr;
    ze_context_handle_t zc = nullptr; // its native context (the shared one, or its own in ipc mode)
    std::string bdf;
    std::shared_ptr<sycl::context> ctx;
    std::unique_ptr<sycl::queue> qp, qn; // profiling (persist) / plain (fresh) in-order queues
    u32 *arena = nullptr, *st = nullptr;
    std::vector<u32 *> view; // view[d]: card d's arena as this card's kernels must address it
};

struct Cfg {
    bool persist, pull, a2a;
    std::vector<int> cards; // group position -> index into the card table
    u32 bytes;
};
struct Totals { u32 mism = 0, timeouts = 0, skips = 0, maxpoll = 0; };

int main(int argc, char **argv) {
    std::map<std::string, std::string> opt;
    std::set<std::string> flags;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a.rfind("--", 0) != 0) { std::fprintf(stderr, "bad argument %s\n", a.c_str()); return 2; }
        const size_t eq = a.find('=');
        if (eq == std::string::npos) flags.insert(a.substr(2));
        else opt[a.substr(2, eq - 2)] = a.substr(eq + 1);
    }
    auto get = [&](const char *k, const char *d) { auto it = opt.find(k); return it == opt.end() ? std::string(d) : it->second; };
    auto getu = [&](const char *k, unsigned long d) { auto it = opt.find(k); return it == opt.end() ? d : std::strtoul(it->second.c_str(), nullptr, 0); };
    static const std::set<std::string> known = {"ctx", "cards", "pairs", "sizes", "topos", "forms", "methods", "flag", "k1", "k2",
                                                "fk1", "fk2", "reps", "wg", "cap", "total-cap"};
    for (auto &[k, v] : opt)
        if (!known.count(k)) { std::fprintf(stderr, "unknown option --%s\n", k.c_str()); return 2; }
    for (auto &f : flags)
        if (f != "persist-pull" && f != "one-sycl-ctx") { std::fprintf(stderr, "unknown flag --%s\n", f.c_str()); return 2; }
    const std::string ctxmode = get("ctx", "shared");
    if (ctxmode != "shared" && ctxmode != "ipc") { std::fprintf(stderr, "--ctx=shared|ipc\n"); return 2; }
    const bool shared = ctxmode == "shared";
    const u32 cap = (u32)getu("cap", 1u << 20), total_cap = (u32)getu("total-cap", 1u << 22);
    const u32 k1max = (u32)getu("k1", 200), k2max = (u32)getu("k2", 2000), fk1max = (u32)getu("fk1", 100), fk2max = (u32)getu("fk2", 500);
    const int reps = (int)getu("reps", 7);
    const u32 wg_opt = (u32)getu("wg", 0);
    const bool flag_atomic = get("flag", "plain") == "atomic", persist_pull = flags.count("persist-pull") > 0;
    if (cap == 0 || total_cap < cap || reps < 1 || k1max < 4 || k2max <= k1max || k2max < 16 || fk1max < 8 || fk2max <= fk1max || fk2max < 32 ||
        wg_opt > 16) {
        std::fprintf(stderr, "bad numbers\n");
        return 2;
    }
    std::vector<u32> sizes;
    for (auto &s : split(get("sizes", "0,3456,9728,16384,65536"), ',')) {
        const u32 b = (u32)std::strtoul(s.c_str(), nullptr, 10);
        if (b % 16 || b > MAXB) { std::fprintf(stderr, "size %u: multiples of 16 up to %u\n", b, MAXB); return 2; }
        sizes.push_back(b);
    }
    const std::vector<std::string> topos = split(get("topos", "pair,ring,a2a"), ','), forms = split(get("forms", "persist,fresh"), ','),
                                   methods = split(get("methods", "push,pull"), ',');

    auto env = [](const char *k) { const char *v = std::getenv(k); return std::string(v ? v : "(unset)"); };
    std::printf("env: NEOReadDebugKeys=%s EnableDeferBacking=%s DisableIndirectAccess=%s ZE_AFFINITY_MASK=%s ZE_ENABLE_PCI_ID_DEVICE_ORDER=%s\n",
                env("NEOReadDebugKeys").c_str(), env("EnableDeferBacking").c_str(), env("DisableIndirectAccess").c_str(),
                env("ZE_AFFINITY_MASK").c_str(), env("ZE_ENABLE_PCI_ID_DEVICE_ORDER").c_str());
    if (shared && !(env("NEOReadDebugKeys") == "1" && env("EnableDeferBacking") == "0"))
        std::printf("WARNING: shared context without NEOReadDebugKeys=1 EnableDeferBacking=0 (arenas are small, but this is not the SC117 setup)\n");
    const long long avail0 = meminfo_kib("MemAvailable");
    if (avail0 < 4LL * 1048576) { std::printf("STOP: MemAvailable %.2f GiB < 4 GiB\n", avail0 / 1048576.0); return 3; }

    std::vector<sycl::device> l0;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_platform().get_backend() == sycl::backend::ext_oneapi_level_zero) l0.push_back(d);
    std::vector<int> sel;
    if (opt.count("cards")) {
        for (auto &s : split(opt["cards"], ',')) sel.push_back(std::atoi(s.c_str()));
    } else {
        for (int i = 0; i < (int)l0.size() && i < (int)MAXC; ++i) sel.push_back(i);
    }
    if (sel.size() < 2 || sel.size() > MAXC) { std::fprintf(stderr, "need 2..6 cards (%zu visible)\n", l0.size()); return 2; }
    for (int i : sel)
        if (i < 0 || i >= (int)l0.size() || std::count(sel.begin(), sel.end(), i) != 1) { std::fprintf(stderr, "bad card %d\n", i); return 2; }
    std::vector<std::pair<int, int>> pairs;
    for (auto &p : split(get("pairs", (std::to_string(sel[0]) + "-" + std::to_string(sel[1])).c_str()), ',')) {
        auto ab = split(p, '-');
        if (ab.size() != 2) { std::fprintf(stderr, "bad pair %s\n", p.c_str()); return 2; }
        const int a = std::atoi(ab[0].c_str()), b = std::atoi(ab[1].c_str());
        auto ia = std::find(sel.begin(), sel.end(), a), ib = std::find(sel.begin(), sel.end(), b);
        if (a == b || ia == sel.end() || ib == sel.end()) { std::fprintf(stderr, "pair %s: both cards must be in --cards\n", p.c_str()); return 2; }
        pairs.push_back({int(ia - sel.begin()), int(ib - sel.begin())});
    }

    const int N = (int)sel.size();
    std::vector<Card> cards(N);
    ze_context_handle_t shared_zc = nullptr;
    int rc = 0;
    Totals all;
    struct Res { bool persist, pull; std::string topo, cards; u32 bytes; double us; };
    std::vector<Res> results;
    try {
        auto zdrv = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(l0[sel[0]].get_platform());
        std::vector<sycl::device> devs;
        std::vector<ze_device_handle_t> zds;
        for (int c = 0; c < N; ++c) {
            cards[c].index = sel[c];
            cards[c].dev = l0[sel[c]];
            cards[c].zd = sycl::get_native<sycl::backend::ext_oneapi_level_zero>(cards[c].dev);
            cards[c].bdf = cards[c].dev.has(sycl::aspect::ext_intel_pci_address)
                               ? cards[c].dev.get_info<sycl::ext::intel::info::device::pci_address>() : "?";
            devs.push_back(cards[c].dev);
            zds.push_back(cards[c].zd);
            std::string fr = "not readable (set ZES_ENABLE_SYSMAN=1)";
            if (cards[c].dev.has(sycl::aspect::ext_intel_free_memory)) {
                const double f = cards[c].dev.get_info<sycl::ext::intel::info::device::free_memory>() / 1073741824.0;
                char b[64];
                std::snprintf(b, sizeof b, "%.2f GiB", f);
                fr = b;
                if (f < 1.0) { std::fprintf(stderr, "card %d has %.2f GiB free (in use?): refusing\n", sel[c], f); return 2; }
            }
            std::printf("card %d %s %s free %s\n", sel[c], cards[c].bdf.c_str(), cards[c].dev.get_info<sycl::info::device::name>().c_str(), fr.c_str());
        }
        bool all_access = true, all_atomics = true;
        for (int a = 0; a < N; ++a)
            for (int b = 0; b < N; ++b) {
                if (a == b) continue;
                ze_bool_t can = 0;
                zeDeviceCanAccessPeer(cards[a].zd, cards[b].zd, &can);
                ze_device_p2p_properties_t p2p{};
                p2p.stype = ZE_STRUCTURE_TYPE_DEVICE_P2P_PROPERTIES;
                zeDeviceGetP2PProperties(cards[a].zd, cards[b].zd, &p2p);
                const bool acc = p2p.flags & ZE_DEVICE_P2P_PROPERTY_FLAG_ACCESS, atom = p2p.flags & ZE_DEVICE_P2P_PROPERTY_FLAG_ATOMICS;
                const bool sacc = cards[a].dev.ext_oneapi_can_access_peer(cards[b].dev, sycl::ext::oneapi::peer_access::access_supported);
                const bool satom = cards[a].dev.ext_oneapi_can_access_peer(cards[b].dev, sycl::ext::oneapi::peer_access::atomics_supported);
                std::printf("peer %d->%d: zeDeviceCanAccessPeer=%d p2p access=%d atomics=%d | sycl access=%d atomics=%d\n", sel[a], sel[b],
                            (int)can, acc, atom, sacc, satom);
                all_access = all_access && can;
                all_atomics = all_atomics && atom;
            }
        if (!all_access) { std::fprintf(stderr, "the driver says some card cannot access a peer: refusing\n"); return 2; }
        if (persist_pull && !all_atomics)
            std::printf("WARNING: --persist-pull issues system-scope atomic loads on peer memory, and the driver reports no P2P atomics\n");

        ze_context_desc_t cd{};
        cd.stype = ZE_STRUCTURE_TYPE_CONTEXT_DESC;
        auto handler = [](sycl::exception_list el) {
            for (auto &e : el) {
                try { std::rethrow_exception(e); } catch (const sycl::exception &x) { std::fprintf(stderr, "async SYCL error: %s\n", x.what()); }
            }
        };
        if (shared) {
            if (zeContextCreateEx(zdrv, &cd, (uint32_t)zds.size(), zds.data(), &shared_zc) != ZE_RESULT_SUCCESS) {
                std::fprintf(stderr, "zeContextCreateEx over %d cards failed\n", N);
                return 2;
            }
            std::shared_ptr<sycl::context> one;
            if (flags.count("one-sycl-ctx"))
                one = std::make_shared<sycl::context>(sycl::make_context<sycl::backend::ext_oneapi_level_zero>(
                    {shared_zc, devs, sycl::ext::oneapi::level_zero::ownership::keep}, handler));
            for (int c = 0; c < N; ++c) {
                cards[c].zc = shared_zc;
                // one SYCL context per card over the SAME native context (packet194 OWNRT_TP_CARD_CONTEXT=1: libsycl's
                // kernel cache cannot hold one kernel for two devices of one SYCL context)
                cards[c].ctx = one ? one : std::make_shared<sycl::context>(sycl::make_context<sycl::backend::ext_oneapi_level_zero>(
                                               {shared_zc, devs, sycl::ext::oneapi::level_zero::ownership::keep}, handler));
            }
            for (int a = 0; a < N; ++a) // SYCL's peer-access switch (SC117 called it; a no-op on Level Zero, kept for parity)
                for (int b = 0; b < N; ++b)
                    if (a != b) try { cards[a].dev.ext_oneapi_enable_peer_access(cards[b].dev); } catch (const sycl::exception &e) {
                            std::printf("note: enable_peer_access %d->%d: %s\n", sel[a], sel[b], e.what());
                        }
        } else {
            for (int c = 0; c < N; ++c) {
                if (zeContextCreateEx(zdrv, &cd, 1, &cards[c].zd, &cards[c].zc) != ZE_RESULT_SUCCESS) { std::fprintf(stderr, "zeContextCreateEx failed\n"); return 2; }
                cards[c].ctx = std::make_shared<sycl::context>(sycl::make_context<sycl::backend::ext_oneapi_level_zero>(
                    {cards[c].zc, {cards[c].dev}, sycl::ext::oneapi::level_zero::ownership::keep}, handler));
            }
        }
        for (int c = 0; c < N; ++c) {
            cards[c].qp = std::make_unique<sycl::queue>(*cards[c].ctx, cards[c].dev, handler,
                                                        sycl::property_list{sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
            cards[c].qn = std::make_unique<sycl::queue>(*cards[c].ctx, cards[c].dev, handler, sycl::property_list{sycl::property::queue::in_order{}});
            ze_device_mem_alloc_desc_t md{};
            md.stype = ZE_STRUCTURE_TYPE_DEVICE_MEM_ALLOC_DESC;
            void *p = nullptr, *s = nullptr;
            if (zeMemAllocDevice(cards[c].zc, &md, ARENA_BYTES, 65536, cards[c].zd, &p) != ZE_RESULT_SUCCESS ||
                zeMemAllocDevice(cards[c].zc, &md, S_WORDS * 4, 4096, cards[c].zd, &s) != ZE_RESULT_SUCCESS) {
                std::fprintf(stderr, "zeMemAllocDevice failed on card %d\n", sel[c]);
                throw 1;
            }
            cards[c].arena = (u32 *)p;
            cards[c].st = (u32 *)s;
            cards[c].qn->memset(p, 0, ARENA_BYTES).wait();
            cards[c].qn->memset(s, 0, S_WORDS * 4).wait();
        }
        for (int c = 0; c < N; ++c) {
            cards[c].view.assign(N, nullptr);
            for (int d = 0; d < N; ++d) {
                if (d == c || shared) { cards[c].view[d] = cards[d].arena; continue; } // shared: the raw pointer, translated by the driver
                ze_ipc_mem_handle_t h;
                void *p = nullptr;
                if (zeMemGetIpcHandle(cards[d].zc, cards[d].arena, &h) != ZE_RESULT_SUCCESS ||
                    zeMemOpenIpcHandle(cards[c].zc, cards[c].zd, h, 0, &p) != ZE_RESULT_SUCCESS || !p) {
                    std::fprintf(stderr, "IPC open %d->%d failed\n", sel[c], sel[d]);
                    throw 1;
                }
                cards[c].view[d] = (u32 *)p;
            }
        }
        auto show_fd = [&](const char *tag) {
            auto fd = fdinfo_brief();
            const long long av = meminfo_kib("MemAvailable");
            std::printf("[%s] MemAvailable %.2f GiB (%+.2f since start); xe fdinfo MiB total/resident:\n", tag, av / 1048576.0, (av - avail0) / 1048576.0);
            for (auto &c : cards) std::printf("  card %d %s: %s\n", c.index, c.bdf.c_str(), fd[c.bdf].c_str());
            return av;
        };
        if (show_fd("after setup") < 4LL * 1048576) { std::printf("STOP: MemAvailable < 4 GiB\n"); rc = 3; throw 0; }
        std::printf("ctx=%s%s flag=%s cap=%u total_cap=%u reps=%d\n", ctxmode.c_str(),
                    shared ? (flags.count("one-sycl-ctx") ? " (one SYCL context)" : " (one SYCL context per card, same native context)") : " (IPC peers)",
                    flag_atomic ? "atomic" : "plain", cap, total_cap, reps);

        u32 g_seq = 1; // global, monotonic: a flag left by any earlier run is always below every new run's numbers
        bool stop = false;
        // one run of a configuration with K rounds; returns per-card device seconds (persist) or host seconds (fresh)
        auto run = [&](const Cfg &cf, u32 K, u32 G, std::vector<double> &dev_s, std::vector<double> &host_s, std::vector<double> &enq_s,
                       Totals &tot) -> bool {
            const int n = (int)cf.cards.size();
            const u32 seq0 = g_seq;
            g_seq += K + 2;
            dev_s.assign(n, 0.0);
            host_s.assign(n, 0.0);
            enq_s.assign(n, 0.0);
            std::barrier sync(n);
            std::mutex emu;
            std::string err;
            auto body = [&](int p) {
                Card &C = cards[cf.cards[p]];
                bool ready = true;
                try {
                    C.qn->memset(C.st, 0, S_WORDS * 4).wait();
                } catch (const std::exception &e) {
                    std::lock_guard<std::mutex> l(emu);
                    err = e.what();
                    ready = false;
                }
                sync.arrive_and_wait(); // every thread arrives, also after an error (no barrier deadlock)
                if (!ready) return;     // the peers' kernels then time out (bounded) and the run is reported failed
                try {
                    u32 *A[MAXC] = {nullptr, nullptr, nullptr, nullptr, nullptr, nullptr};
                    for (int k = 0; k < n; ++k) A[k] = C.view[cf.cards[k]];
                    u32 *a0 = A[0], *a1 = A[1], *a2 = A[2], *a3 = A[3], *a4 = A[4], *a5 = A[5], *st = C.st;
                    XK k{(u32)p, (u32)n, 0, cf.bytes / 16, 0, cap, total_cap, cf.a2a ? 1u : 0u, cf.pull ? 1u : 0u,
                         cf.persist ? 1u : 0u, flag_atomic ? 1u : 0u, G};
                    const double t0 = now_s();
                    sycl::event last;
                    if (cf.persist) {
                        k.rounds = K;
                        k.seq0 = seq0;
                        last = launch(*C.qp, G, k, a0, a1, a2, a3, a4, a5, st);
                    } else {
                        k.rounds = 1;
                        for (u32 r = 0; r < K; ++r) {
                            k.seq0 = seq0 + r;
                            last = launch(*C.qn, G, k, a0, a1, a2, a3, a4, a5, st);
                        }
                    }
                    enq_s[p] = now_s() - t0;
                    wait_event(last, "exchange kernel");
                    host_s[p] = now_s() - t0;
                    if (cf.persist)
                        dev_s[p] = (last.get_profiling_info<sycl::info::event_profiling::command_end>() -
                                    last.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-9;
                } catch (const std::exception &e) {
                    std::lock_guard<std::mutex> l(emu);
                    err = e.what();
                }
            };
            std::vector<std::thread> th;
            for (int p = 0; p < n; ++p) th.emplace_back(body, p);
            for (auto &t : th) t.join();
            for (int p = 0; p < n; ++p) {
                u32 h[S_WORDS];
                cards[cf.cards[p]].qn->memcpy(h, cards[cf.cards[p]].st, sizeof h).wait();
                tot.mism += h[S_MISM];
                tot.timeouts += h[S_TIMEOUT];
                tot.skips += h[S_SKIP];
                tot.maxpoll = std::max(tot.maxpoll, h[S_MAXPOLL]);
            }
            if (!err.empty()) { std::fprintf(stderr, "run failed: %s\n", err.c_str()); return false; }
            return true;
        };
        auto label = [&](const Cfg &cf) {
            std::string s;
            for (size_t i = 0; i < cf.cards.size(); ++i) s += (i ? "," : "") + std::to_string(sel[cf.cards[i]]);
            return s;
        };
        // measure one configuration: pilot, then reps x (K1, K2), median difference
        auto measure = [&](const Cfg &cf, const char *topo) {
            if (stop) return;
            const int n = (int)cf.cards.size();
            const u32 words = cf.bytes / 4;
            const u32 G = wg_opt ? wg_opt : std::clamp<u32>((words + 2047) / 2048, 1, 16);
            Totals tot;
            std::vector<double> d, h, e;
            const u32 KP = cf.persist ? 4 : 8;
            if (!run(cf, KP, G, d, h, e, tot) || tot.timeouts) {
                std::printf("%-7s %-4s %-4s %-12s %6u B  pilot FAILED (timeouts %u, wrong %u)\n", cf.persist ? "persist" : "fresh",
                            cf.pull ? "pull" : "push", topo, label(cf).c_str(), cf.bytes, tot.timeouts, tot.mism);
                stop = true;
                all.timeouts += tot.timeouts;
                all.mism += tot.mism;
                return;
            }
            const double tp = cf.persist ? *std::max_element(d.begin(), d.end()) : *std::max_element(h.begin(), h.end());
            double est = tp / KP; // per round, an upper bound (includes the cards' start skew)
            u32 K2, K1;
            if (cf.persist) {
                // second pilot sized to <= ~0.02 s from the upper bound, then the per-round time by difference, so a long
                // start skew in the first pilot does not shrink K; K2 also stays <= 15 x the second pilot (kernel time
                // stays ~0.15-0.3 s, far below xe's job timeout, whatever the estimate's noise)
                const u32 Ka = std::clamp<u32>((u32)std::min(1e9, 0.02 / std::max(est, 1e-7)), 8, k2max);
                if (!run(cf, Ka, G, d, h, e, tot) || tot.timeouts) {
                    std::printf("%-7s %-4s %-4s %-12s %6u B  second pilot FAILED (timeouts %u, wrong %u)\n", "persist", cf.pull ? "pull" : "push", topo,
                                label(cf).c_str(), cf.bytes, tot.timeouts, tot.mism);
                    stop = true;
                    all.timeouts += tot.timeouts;
                    all.mism += tot.mism;
                    return;
                }
                const double ta = *std::max_element(d.begin(), d.end());
                if (Ka > KP && ta > tp) est = std::min(est, (ta - tp) / (Ka - KP));
                K2 = std::clamp<u32>((u32)std::min(1e9, 0.15 / std::max(est, 1e-7)), 16, std::max<u32>(16, std::min<u32>(k2max, 15 * Ka)));
                K1 = std::clamp<u32>(std::min(k1max, K2 / 8), 4, K2 / 2);
            } else {
                K2 = std::clamp<u32>((u32)std::min(1e9, 0.2 / std::max(est, 1e-7)), 32, fk2max);
                K1 = std::clamp<u32>(std::min(fk1max, K2 / 5), 8, K2 / 2);
            }
            std::vector<double> t1, t2, h1, h2;
            double enq2 = 0;
            for (int r = 0; r < reps && !stop; ++r) {
                for (int which = 0; which < 2; ++which) {
                    if (!run(cf, which ? K2 : K1, G, d, h, e, tot) || tot.timeouts) { stop = true; break; }
                    const double dm = *std::max_element(d.begin(), d.end()), hm = *std::max_element(h.begin(), h.end());
                    (which ? t2 : t1).push_back(cf.persist ? dm : hm);
                    (which ? h2 : h1).push_back(hm);
                    if (which) enq2 = std::max(enq2, *std::max_element(e.begin(), e.end()));
                }
            }
            all.mism += tot.mism;
            all.timeouts += tot.timeouts;
            all.skips += tot.skips;
            all.maxpoll = std::max(all.maxpoll, tot.maxpoll);
            if (t1.size() != (size_t)reps || t2.size() != (size_t)reps) {
                std::printf("%-7s %-4s %-4s %-12s %6u B  stopped before timing finished (wrong %u, timeouts %u)\nSTOP: no further runs\n",
                            cf.persist ? "persist" : "fresh", cf.pull ? "pull" : "push", topo, label(cf).c_str(), cf.bytes, tot.mism, tot.timeouts);
                stop = true;
                return;
            }
            const double hops = cf.a2a ? 1.0 : (double)n;
            const double per = (median(t2) - median(t1)) / (K2 - K1), hper = (median(h2) - median(h1)) / (K2 - K1);
            const double us = per / hops * 1e6, hus = hper / hops * 1e6;
            const double sent = cf.a2a ? (double)cf.bytes * (n - 1) : (double)cf.bytes; // bytes a card sends per step reported
            char line[320];
            std::snprintf(line, sizeof line, "%-7s %-4s %-4s %-12s %6u B  G=%-2u K=%4u/%-5u %s %8.2f us  (host %8.2f)  %6.2f GB/s  wrong %u  timeouts %u  max polls %u%s",
                          cf.persist ? "persist" : "fresh", cf.pull ? "pull" : "push", topo, label(cf).c_str(), cf.bytes, G, K1, K2,
                          cf.a2a ? "round  " : "one-way", us, hus, us > 0 ? sent / (us * 1e3) : 0.0, tot.mism, tot.timeouts, tot.maxpoll,
                          (!cf.persist && enq2 > 0.8 * median(h2)) ? "  (host-paced: enqueue ~ run time)" : "");
            std::printf("%s\n", line);
            std::fflush(stdout);
            results.push_back({cf.persist, cf.pull, topo, label(cf), cf.bytes, us});
            if (stop) std::printf("STOP: a wait timed out; no further runs\n");
            if (meminfo_kib("MemAvailable") < 4LL * 1048576) { std::printf("STOP: MemAvailable < 4 GiB\n"); stop = true; rc = 3; }
        };

        // warm-up, one card at a time: build the kernel on every card (and let the driver import every peer arena) with
        // zero rounds, so no card is still building while a peer already waits in an exchange (the engine does the same)
        for (int c = 0; c < N; ++c) {
            std::vector<u32 *> A(MAXC, nullptr);
            for (int d = 0; d < N; ++d) A[d] = cards[c].view[d];
            const XK k0{(u32)c, (u32)N, 0, 0, 0, cap, total_cap, 1, 0, 0, 0, 1};
            const double t0 = now_s();
            sycl::event e1 = launch(*cards[c].qp, 1, k0, A[0], A[1], A[2], A[3], A[4], A[5], cards[c].st);
            wait_event(e1, "warm-up");
            sycl::event e2 = launch(*cards[c].qn, 1, k0, A[0], A[1], A[2], A[3], A[4], A[5], cards[c].st);
            wait_event(e2, "warm-up");
            std::printf("warm-up card %d: %.1f ms\n", sel[c], (now_s() - t0) * 1e3);
        }
        show_fd("after warm-up (peer arenas imported)");
        // smoke: one round trip, then go
        {
            Totals tot;
            std::vector<double> d, h, e;
            Cfg sm{true, false, false, {pairs[0].first, pairs[0].second}, 3456};
            const bool ok = run(sm, 1, 1, d, h, e, tot) && !tot.timeouts && !tot.mism;
            std::printf("smoke (persist push pair %s, 3456 B, one round trip): %s (wrong %u, timeouts %u)\n", label(sm).c_str(), ok ? "PASS" : "FAIL",
                        tot.mism, tot.timeouts);
            if (!ok) { all.mism += tot.mism; all.timeouts += tot.timeouts; stop = true; }
        }
        std::printf("%-7s %-4s %-4s %-12s %8s  %-4s %-12s %s\n", "form", "how", "topo", "cards", "bytes", "WGs", "K1/K2", "time per hop (pair/ring) or per all-gather round (a2a)");
        auto has = [](const std::vector<std::string> &v, const char *s) { return std::find(v.begin(), v.end(), s) != v.end(); };
        std::vector<std::pair<std::string, std::vector<int>>> groups;
        if (has(topos, "pair"))
            for (auto &pr : pairs) groups.push_back({"pair", {pr.first, pr.second}});
        std::vector<int> everyone(N);
        for (int c = 0; c < N; ++c) everyone[c] = c;
        if (has(topos, "ring") && N >= 3) groups.push_back({"ring", everyone});
        if (has(topos, "a2a")) groups.push_back({"a2a", everyone});
        for (auto &[topo, grp] : groups)
            for (auto &form : forms)
                for (auto &method : methods) {
                    const bool persist = form == "persist", pull = method == "pull";
                    if (persist && pull && !persist_pull) continue;
                    for (u32 b : sizes) measure(Cfg{persist, pull, topo == "a2a", grp, b}, topo.c_str());
                }
        show_fd("after runs");
    } catch (const sycl::exception &e) {
        std::fprintf(stderr, "SYCL exception: %s\n", e.what());
        rc = 1;
    } catch (int code) {
        if (code == 1) rc = 1;
    }
    // teardown: queues drained, IPC views closed, memory freed, SYCL wrappers before the native contexts
    for (auto &c : cards) {
        try { if (c.qp) c.qp->wait(); if (c.qn) c.qn->wait(); } catch (...) {}
    }
    for (int c = 0; c < N; ++c)
        for (int d = 0; d < N; ++d)
            if (!shared && c != d && (int)cards[c].view.size() == N && cards[c].view[d]) zeMemCloseIpcHandle(cards[c].zc, cards[c].view[d]);
    for (auto &c : cards) {
        if (c.arena) zeMemFree(c.zc, c.arena);
        if (c.st) zeMemFree(c.zc, c.st);
        c.qp.reset();
        c.qn.reset();
        c.ctx.reset();
    }
    if (shared_zc) zeContextDestroy(shared_zc);
    else
        for (auto &c : cards)
            if (c.zc) zeContextDestroy(c.zc);
    if (rc == 0 && (all.mism || all.timeouts)) rc = 1;
    // plain verdict (first pair; the a2a rows are the engine's exchange)
    auto find = [&](bool persist, bool pull, const char *topo, u32 bytes) -> double {
        for (auto &r : results)
            if (r.persist == persist && r.pull == pull && r.topo == topo && r.bytes == bytes) return r.us;
        return -1;
    };
    std::printf("VERDICT (ctx=%s)\n", ctxmode.c_str());
    const double p97 = find(true, false, "pair", 9728);
    if (p97 > 0)
        std::printf("  direct store, card to card, 9,728 B, no launch: %.2f us one way -> %s (bar ~4 us; SC117 four-card host 1.6 us at 10 KB)\n",
                    p97, p97 < 4.0 ? "FAST ENOUGH" : "TOO SLOW");
    for (u32 b : {3456u, 9728u}) {
        const double fp = find(false, false, "a2a", b), fl = find(false, true, "a2a", b);
        if (fp > 0 && fl > 0)
            std::printf("  engine-shaped all-gather, %u B per card, one kernel per exchange: push %.2f us vs pull (today) %.2f us -> %+.2f us per exchange\n",
                        b, fp, fl, fp - fl);
    }
    if (rc != 0) std::printf("  (the run did not pass: the numbers above are not usable)\n");
    std::printf("TOTAL wrong values %u, timeouts %u, skipped waits %u, max polls in one wait %u -> %s\n", all.mism, all.timeouts, all.skips, all.maxpoll,
                rc == 0 ? "PASS" : rc == 3 ? "HOST-MEMORY STOP" : "FAIL");
    return rc;
}
