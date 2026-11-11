// Does card memory cost host RAM when several cards share ONE native Level Zero context? (lever L1, step 1)
//
// WHAT IT MEASURES
//   The engine today uses one context per card because a multi-card SYCL context made every byte allocated on a
//   card also cost a byte of host RAM on this 15 GiB host (notes/2026-11-09-dsv41-device-load-host-memory.md §1,
//   measured WITHOUT EnableDeferBacking=0). The older SC117 engine ran one native context over its cards with
//   NEOReadDebugKeys=1 EnableDeferBacking=0, which removed that shadow there (+8.00 -> +0.00 GiB GPUActive,
//   research/tp/direct-exchange-2026-10-28/RESULT.md "Step 1: host RAM"). This probe checks it on this host.
//   Plain Level Zero (no SYCL runtime in between): one native context over N cards (or one per card, the control),
//   device memory allocated card by card in steps and filled by the card (zeCommandListAppendMemoryFill), and after
//   EVERY allocation: host MemAvailable, GPUActive (/proc/meminfo), this process's RSS and, per card, this process's
//   xe fdinfo (where the driver says the memory lives: vram0 / system / gtt).
//   Options model the two other ways a shared context can touch host RAM:
//     --peer-resident  after each allocation, zeContextMakeMemoryResident() on every other card of the context: what
//                      a SYCL allocation in a multi-card context does under the Level Zero v2 adapter (packet194
//                      single_device.cpp:31-34), i.e. the engine port if it kept sycl::malloc_device;
//     --peer-touch     at the end, a 4 MiB arena per card and a 4 KiB copy from each card into the next card's arena,
//                      one card at a time, read back and checked: the peer import the exchange needs.
//
// SAFETY STOPS (checked after every single allocation, residency call and peer copy; exit 3, everything freed)
//   * MemAvailable fell by more than 0.5 GiB + 25 % of the bytes allocated on cards so far;
//   * MemAvailable below 4 GiB;
//   * before each allocation: MemAvailable minus the worst case of this allocation (step x number of cards it can
//     be made resident on) would go below 4 GiB.
//   The 1:1 case (default env, shared context) therefore stops by itself at about 0.75 GiB allocated.
//   Before anything is allocated each card's free memory is read (Sysman) and the probe refuses (exit 2) if a card
//   has less than cap + 1 GiB free: xe does not fail an allocation that does not fit, it evicts into host RAM (§1
//   cause B). Never "allocate until it fails". Host RAM, swap, power and driver settings are not touched.
//
// WHAT RESULT JUSTIFIES THE PORT
//   shared mode with EnableDeferBacking=0: MemAvailable / GPUActive move by < 5 % of the allocated bytes (ratio
//   printed as "host RAM per card byte") and fdinfo keeps the memory in vram0. Then a shared native context can hold
//   the 154 GiB model and xchg_direct_bench.cpp is the next step. Anything near 1.0 closes the lever on this host
//   (unless the engine keeps only small exchange arenas in the shared context, which this probe also answers with
//   --peer-touch).
//
// BUILD (host-only C++, no device code; nothing to compile ahead of time)
//   cd engine; S=/home/steve/dsv41-work/bin
//   nice -n 10 icpx -O2 -std=c++20 tools/bench/probe_shared_ctx_ram.cpp -o $S/probe_shared_ctx_ram -lze_loader
//   (g++ -O2 -std=c++20 ... -lze_loader works too)
// RUN (cards empty, no server up; one process at a time)
//   E="ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 ZES_ENABLE_SYSMAN=1"
//   env $E NEOReadDebugKeys=1 EnableDeferBacking=0 $S/probe_shared_ctx_ram shared 2 1024 256
//   env $E NEOReadDebugKeys=1 EnableDeferBacking=0 $S/probe_shared_ctx_ram shared 6 1024 256 --peer-touch
//   env $E NEOReadDebugKeys=1 EnableDeferBacking=0 $S/probe_shared_ctx_ram shared 2 1024 256 --peer-resident
//   env $E NEOReadDebugKeys=1 EnableDeferBacking=0 $S/probe_shared_ctx_ram percard 2 1024 256      (control)
//   env $E $S/probe_shared_ctx_ram shared 2 1024 256      (default env: expected to hit the stop near 0.75 GiB)
//   usage: probe_shared_ctx_ram <shared|shared-all|percard> [ncards=2] [cap_mib_per_card=1024] [step_mib=256]
//            [--cards=i,j,...] [--peer-resident] [--peer-touch] [--hold-s=N] [--skip-free-check]
//   shared     = zeContextCreateEx over exactly the chosen cards;  shared-all = zeContextCreate (every visible card,
//   as packet194 / SC117 did);  percard = zeContextCreateEx with one card each (the engine's rule today).
//   Exit: 0 done, 3 safety stop, 2 refused (setup / free memory / arguments), 1 Level Zero error.
#include <level_zero/ze_api.h>
#include <level_zero/zes_api.h>
#include <sys/resource.h>
#include <dirent.h>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <set>
#include <string>
#include <thread>
#include <vector>

struct L0Error {};
#define ZE_CHECK(call)                                                                                          \
    do {                                                                                                        \
        ze_result_t r_ = (call);                                                                                \
        if (r_ != ZE_RESULT_SUCCESS) {                                                                          \
            std::fprintf(stderr, "%s failed: 0x%x (line %d)\n", #call, (unsigned)r_, __LINE__);                 \
            throw L0Error{};                                                                                    \
        }                                                                                                       \
    } while (0)

static constexpr double GiB = 1073741824.0;

// ------------------------------------------------------------------------------------------------ host readings
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
static long long rss_kib() {
    std::ifstream f("/proc/self/status");
    std::string line;
    while (std::getline(f, line))
        if (line.rfind("VmRSS:", 0) == 0) return std::atoll(line.c_str() + 6);
    return -1;
}
// this process's xe fdinfo, per PCI device: {"total-vram0": bytes, "resident-system": bytes, ...}
// (sizes are printed by the kernel in bytes, KiB or MiB; one record per DRM client)
static std::map<std::string, std::map<std::string, long long>> fdinfo_self() {
    std::map<std::string, std::map<std::string, long long>> out;
    std::set<std::string> seen;
    DIR *d = opendir("/proc/self/fdinfo");
    if (!d) return out;
    while (auto *e = readdir(d)) {
        if (e->d_name[0] == '.') continue;
        std::ifstream f(std::string("/proc/self/fdinfo/") + e->d_name);
        std::string line, pdev, client;
        std::map<std::string, long long> kv;
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
                kv[k.substr(4)] = n;
            }
        }
        if (!drm || pdev.empty() || !seen.insert(pdev + "/" + client).second) continue;
        for (auto &[k, n] : kv) out[pdev][k] += n;
    }
    closedir(d);
    return out;
}
static std::string fd_brief(const std::map<std::string, long long> &kv) {
    // "vram0 512/512 system 0/0 gtt 0/0" (MiB total/resident), every region the driver reports
    std::map<std::string, std::pair<long long, long long>> reg;
    for (auto &[k, n] : kv) {
        if (k.rfind("total-", 0) == 0) reg[k.substr(6)].first = n;
        else if (k.rfind("resident-", 0) == 0) reg[k.substr(9)].second = n;
    }
    std::string s;
    char b[96];
    for (auto &[r, tr] : reg) {
        std::snprintf(b, sizeof b, "%s%s %lld/%lld", s.empty() ? "" : " ", r.c_str(), tr.first >> 20, tr.second >> 20);
        s += b;
    }
    return s.empty() ? "-" : s;
}

// ------------------------------------------------------------------------------------------------ devices
struct Card {
    int index = -1;
    ze_device_handle_t dev = nullptr;
    std::string bdf, name;
    uint64_t vram = 0;
    long long free_b = -1;
    ze_context_handle_t ctx = nullptr; // the context this card allocates from (shared or its own)
    ze_command_list_handle_t list = nullptr;
    std::vector<void *> blocks;
    void *arena = nullptr, *scratch = nullptr; // --peer-touch
};
static std::string bdf_str(uint32_t dom, uint32_t bus, uint32_t dev, uint32_t fn) {
    char b[32];
    std::snprintf(b, sizeof b, "%04x:%02x:%02x.%x", dom, bus, dev, fn);
    return b;
}
static long long mem_free_of(zes_device_handle_t s, long long *size_out) {
    uint32_t nm = 0;
    if (zesDeviceEnumMemoryModules(s, &nm, nullptr) != ZE_RESULT_SUCCESS || nm == 0) return -1;
    std::vector<zes_mem_handle_t> mods(nm);
    if (zesDeviceEnumMemoryModules(s, &nm, mods.data()) != ZE_RESULT_SUCCESS) return -1;
    long long fr = 0, sz = 0;
    bool any = false;
    for (auto m : mods) {
        zes_mem_properties_t mp{};
        mp.stype = ZES_STRUCTURE_TYPE_MEM_PROPERTIES;
        if (zesMemoryGetProperties(m, &mp) != ZE_RESULT_SUCCESS || mp.location != ZES_MEM_LOC_DEVICE) continue;
        zes_mem_state_t st{};
        st.stype = ZES_STRUCTURE_TYPE_MEM_STATE;
        if (zesMemoryGetState(m, &st) != ZE_RESULT_SUCCESS) continue;
        fr += (long long)st.free;
        sz += (long long)st.size;
        any = true;
    }
    if (size_out) *size_out = sz;
    return any ? fr : -1;
}
// free device memory per card (sees other processes). ZES_ENABLE_SYSMAN=1: core handles double as Sysman
// handles; otherwise zesInit and match by PCI address.
static bool read_free(std::vector<Card> &cards) {
    const char *legacy = std::getenv("ZES_ENABLE_SYSMAN");
    if (legacy && std::string(legacy) == "1") {
        for (auto &c : cards) c.free_b = mem_free_of((zes_device_handle_t)c.dev, nullptr);
    } else {
        if (zesInit(0) != ZE_RESULT_SUCCESS) return false;
        uint32_t nd = 0;
        if (zesDriverGet(&nd, nullptr) != ZE_RESULT_SUCCESS || !nd) return false;
        std::vector<zes_driver_handle_t> drv(nd);
        zesDriverGet(&nd, drv.data());
        for (auto dh : drv) {
            uint32_t n = 0;
            if (zesDeviceGet(dh, &n, nullptr) != ZE_RESULT_SUCCESS || !n) continue;
            std::vector<zes_device_handle_t> sd(n);
            zesDeviceGet(dh, &n, sd.data());
            for (auto s : sd) {
                zes_pci_properties_t pp{};
                pp.stype = ZES_STRUCTURE_TYPE_PCI_PROPERTIES;
                if (zesDevicePciGetProperties(s, &pp) != ZE_RESULT_SUCCESS) continue;
                const std::string b = bdf_str(pp.address.domain, pp.address.bus, pp.address.device, pp.address.function);
                for (auto &c : cards)
                    if (c.bdf == b) c.free_b = mem_free_of(s, nullptr);
            }
        }
    }
    for (auto &c : cards)
        if (c.free_b < 0) return false;
    return true;
}

// ------------------------------------------------------------------------------------------------ main
int main(int argc, char **argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: %s <shared|shared-all|percard> [ncards=2] [cap_mib=1024] [step_mib=256] [--cards=i,j] "
                             "[--peer-resident] [--peer-touch] [--hold-s=N] [--skip-free-check]\n", argv[0]);
        return 2;
    }
    const std::string mode = argv[1];
    if (mode != "shared" && mode != "shared-all" && mode != "percard") { std::fprintf(stderr, "bad mode %s\n", mode.c_str()); return 2; }
    std::vector<long long> pos;
    std::vector<int> pick;
    bool peer_resident = false, peer_touch = false, skip_free = false;
    int hold_s = 0;
    for (int i = 2; i < argc; ++i) {
        std::string a = argv[i];
        if (a.rfind("--cards=", 0) == 0) {
            std::string s = a.substr(8);
            for (size_t p = 0; p < s.size();) {
                size_t q = s.find(',', p);
                if (q == std::string::npos) q = s.size();
                pick.push_back(std::atoi(s.substr(p, q - p).c_str()));
                p = q + 1;
            }
        } else if (a == "--peer-resident") peer_resident = true;
        else if (a == "--peer-touch") peer_touch = true;
        else if (a == "--skip-free-check") skip_free = true;
        else if (a.rfind("--hold-s=", 0) == 0) hold_s = std::atoi(a.c_str() + 9);
        else if (a.rfind("--", 0) == 0) { std::fprintf(stderr, "unknown option %s\n", a.c_str()); return 2; }
        else pos.push_back(std::atoll(a.c_str()));
    }
    const int ncards = pos.size() > 0 ? (int)pos[0] : 2;
    const long long cap = (pos.size() > 1 ? pos[1] : 1024) << 20, step = (pos.size() > 2 ? pos[2] : 256) << 20;
    if (ncards < 1 || ncards > 16 || step <= 0 || cap < step || cap % step) { std::fprintf(stderr, "bad sizes (cap must be a multiple of step)\n"); return 2; }
    if (mode == "percard" && (peer_resident || peer_touch)) { std::fprintf(stderr, "--peer-* need a shared context\n"); return 2; }
    if (pick.empty())
        for (int i = 0; i < ncards; ++i) pick.push_back(i);
    if ((int)pick.size() != ncards) { std::fprintf(stderr, "--cards lists %zu cards, ncards is %d\n", pick.size(), ncards); return 2; }

    auto env = [](const char *k) { const char *v = std::getenv(k); return std::string(v ? v : "(unset)"); };
    std::printf("env: NEOReadDebugKeys=%s EnableDeferBacking=%s DisableIndirectAccess=%s ZE_AFFINITY_MASK=%s "
                "ZE_ENABLE_PCI_ID_DEVICE_ORDER=%s ZES_ENABLE_SYSMAN=%s\n",
                env("NEOReadDebugKeys").c_str(), env("EnableDeferBacking").c_str(), env("DisableIndirectAccess").c_str(),
                env("ZE_AFFINITY_MASK").c_str(), env("ZE_ENABLE_PCI_ID_DEVICE_ORDER").c_str(), env("ZES_ENABLE_SYSMAN").c_str());
    const bool defer_off = env("NEOReadDebugKeys") == "1" && env("EnableDeferBacking") == "0";
    std::printf("EnableDeferBacking=0 is %s\n", defer_off ? "ACTIVE (NEOReadDebugKeys=1 and EnableDeferBacking=0 both set)"
                                                             : "NOT active: this is the default-backing run");
    if (mode != "percard" && !defer_off)
        std::printf("note: shared context with default backing is the known 1:1 case; the stop rule ends it near 0.75 GiB\n");
    {
        rlimit rl{};
        getrlimit(RLIMIT_NOFILE, &rl);
        std::printf("open-file limit %llu (SC117: a multi-card process holds a descriptor per shared buffer)\n", (unsigned long long)rl.rlim_cur);
    }

    const long long avail0 = meminfo_kib("MemAvailable"), gpua0 = meminfo_kib("GPUActive");
    if (avail0 < 0) { std::fprintf(stderr, "no MemAvailable\n"); return 2; }
    if (avail0 < 4LL * 1048576) { std::printf("STOP: MemAvailable %.2f GiB < 4 GiB before start\n", avail0 / 1048576.0); return 3; }

    int rc = 0;
    std::vector<Card> cards;
    ze_context_handle_t shared_ctx = nullptr;
    long long allocated = 0; // bytes on cards (all cards)
    const long long floor_kib = 4LL * 1048576;
    auto status = [&](const char *tag) {
        const long long av = meminfo_kib("MemAvailable"), ga = meminfo_kib("GPUActive");
        auto fd = fdinfo_self();
        std::printf("%-28s on cards %6.2f GiB | MemAvailable %6.2f GiB (%+6.2f) GPUActive %+6.2f GiB RSS %5.0f MiB |", tag,
                    allocated / GiB, av / 1048576.0, (av - avail0) / 1048576.0, ga >= 0 && gpua0 >= 0 ? (ga - gpua0) / 1048576.0 : 0.0,
                    rss_kib() / 1024.0);
        for (auto &c : cards) std::printf(" c%d[%s]", c.index, fd_brief(fd[c.bdf]).c_str());
        std::printf("\n");
        std::fflush(stdout);
        return av;
    };
    // the stop rule; true = stop
    auto must_stop = [&](long long av) {
        const double drop = (avail0 - av) / 1048576.0, lim = 0.5 + 0.25 * (allocated / GiB);
        if (drop > lim) {
            std::printf("STOP: MemAvailable fell %.2f GiB > 0.5 GiB + 25 %% of %.2f GiB allocated (%.2f)\n", drop, allocated / GiB, lim);
            return true;
        }
        if (av < floor_kib) {
            std::printf("STOP: MemAvailable %.2f GiB < 4 GiB\n", av / 1048576.0);
            return true;
        }
        return false;
    };
    try {
        ZE_CHECK(zeInit(ZE_INIT_FLAG_GPU_ONLY));
        uint32_t ndrv = 0;
        ZE_CHECK(zeDriverGet(&ndrv, nullptr));
        std::vector<ze_driver_handle_t> drivers(ndrv);
        ZE_CHECK(zeDriverGet(&ndrv, drivers.data()));
        ze_driver_handle_t driver = nullptr;
        std::vector<ze_device_handle_t> all;
        for (auto d : drivers) {
            uint32_t n = 0;
            if (zeDeviceGet(d, &n, nullptr) != ZE_RESULT_SUCCESS || !n) continue;
            all.resize(n);
            ZE_CHECK(zeDeviceGet(d, &n, all.data()));
            driver = d;
            break;
        }
        if (!driver) { std::fprintf(stderr, "no Level Zero GPU\n"); return 2; }
        std::printf("%zu cards visible\n", all.size());
        for (int i : pick) {
            if (i < 0 || i >= (int)all.size()) { std::fprintf(stderr, "card %d not visible\n", i); return 2; }
            Card c;
            c.index = i;
            c.dev = all[i];
            ze_device_properties_t dp{};
            dp.stype = ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES;
            ZE_CHECK(zeDeviceGetProperties(c.dev, &dp));
            c.name = dp.name;
            ze_pci_ext_properties_t pp{};
            pp.stype = ZE_STRUCTURE_TYPE_PCI_EXT_PROPERTIES;
            ZE_CHECK(zeDevicePciGetPropertiesExt(c.dev, &pp));
            c.bdf = bdf_str(pp.address.domain, pp.address.bus, pp.address.device, pp.address.function);
            uint32_t nm = 0;
            zeDeviceGetMemoryProperties(c.dev, &nm, nullptr);
            std::vector<ze_device_memory_properties_t> mp(nm);
            for (auto &m : mp) m.stype = ZE_STRUCTURE_TYPE_DEVICE_MEMORY_PROPERTIES;
            if (nm) zeDeviceGetMemoryProperties(c.dev, &nm, mp.data());
            for (auto &m : mp) c.vram += m.totalSize;
            cards.push_back(c);
        }
        if (!read_free(cards)) {
            if (!skip_free) {
                std::fprintf(stderr, "cannot read free card memory (set ZES_ENABLE_SYSMAN=1); refusing (--skip-free-check overrides)\n");
                return 2;
            }
            std::printf("WARNING: free card memory not read (--skip-free-check)\n");
        }
        const long long need = cap + (peer_touch ? (8LL << 20) : 0) + (1LL << 30);
        for (auto &c : cards) {
            std::printf("card %d %s %s vram %.2f GiB free %s\n", c.index, c.bdf.c_str(), c.name.c_str(), c.vram / GiB,
                        c.free_b >= 0 ? (std::to_string(c.free_b / GiB).substr(0, 5) + " GiB").c_str() : "?");
            if (c.free_b >= 0 && c.free_b < need) {
                std::fprintf(stderr, "card %d has %.2f GiB free, needs %.2f (cap + 1 GiB): refusing\n", c.index, c.free_b / GiB, need / GiB);
                return 2;
            }
        }
        // peer access among the chosen cards
        for (auto &a : cards)
            for (auto &b : cards) {
                if (&a == &b) continue;
                ze_bool_t can = 0;
                zeDeviceCanAccessPeer(a.dev, b.dev, &can);
                ze_device_p2p_properties_t p2p{};
                p2p.stype = ZE_STRUCTURE_TYPE_DEVICE_P2P_PROPERTIES;
                zeDeviceGetP2PProperties(a.dev, b.dev, &p2p);
                std::printf("peer %d->%d: canAccessPeer=%d p2p access=%d atomics=%d\n", a.index, b.index, (int)can,
                            (p2p.flags & ZE_DEVICE_P2P_PROPERTY_FLAG_ACCESS) ? 1 : 0, (p2p.flags & ZE_DEVICE_P2P_PROPERTY_FLAG_ATOMICS) ? 1 : 0);
            }
        // contexts
        ze_context_desc_t cd{};
        cd.stype = ZE_STRUCTURE_TYPE_CONTEXT_DESC;
        if (mode == "shared") {
            std::vector<ze_device_handle_t> ds;
            for (auto &c : cards) ds.push_back(c.dev);
            ZE_CHECK(zeContextCreateEx(driver, &cd, (uint32_t)ds.size(), ds.data(), &shared_ctx));
        } else if (mode == "shared-all") {
            ZE_CHECK(zeContextCreate(driver, &cd, &shared_ctx));
        }
        for (auto &c : cards) {
            if (shared_ctx) c.ctx = shared_ctx;
            else ZE_CHECK(zeContextCreateEx(driver, &cd, 1, &c.dev, &c.ctx));
            uint32_t ng = 0;
            ZE_CHECK(zeDeviceGetCommandQueueGroupProperties(c.dev, &ng, nullptr));
            std::vector<ze_command_queue_group_properties_t> gp(ng);
            for (auto &g : gp) g.stype = ZE_STRUCTURE_TYPE_COMMAND_QUEUE_GROUP_PROPERTIES;
            ZE_CHECK(zeDeviceGetCommandQueueGroupProperties(c.dev, &ng, gp.data()));
            uint32_t ord = UINT32_MAX;
            for (uint32_t g = 0; g < ng; ++g)
                if (gp[g].flags & ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COMPUTE) { ord = g; break; }
            if (ord == UINT32_MAX) { std::fprintf(stderr, "card %d: no compute queue group\n", c.index); throw L0Error{}; }
            ze_command_queue_desc_t qd{};
            qd.stype = ZE_STRUCTURE_TYPE_COMMAND_QUEUE_DESC;
            qd.ordinal = ord;
            qd.mode = ZE_COMMAND_QUEUE_MODE_SYNCHRONOUS;
            ZE_CHECK(zeCommandListCreateImmediate(c.ctx, c.dev, &qd, &c.list));
        }
        std::printf("mode %s: %s, %d cards, up to %.2f GiB per card in %.0f MiB steps%s%s\n", mode.c_str(),
                    shared_ctx ? "ONE native context" : "one native context per card", ncards, cap / GiB, step / 1048576.0,
                    peer_resident ? ", resident on every peer" : "", peer_touch ? ", peer touch at the end" : "");
        long long av = status("start (contexts open)");
        if (must_stop(av)) { rc = 3; throw 0; }

        const uint64_t sync_ns = 30ull * 1000000000ull;
        const int peers = peer_resident ? ncards - 1 : 0;
        for (long long done = 0; done < cap && rc == 0; done += step) {
            for (auto &c : cards) {
                av = meminfo_kib("MemAvailable");
                if (av - (step >> 10) * (1 + peers) < floor_kib) {
                    std::printf("STOP: the next %lld MiB (x%d worst case) would take MemAvailable below 4 GiB\n", step >> 20, 1 + peers);
                    rc = 3;
                    break;
                }
                ze_device_mem_alloc_desc_t md{};
                md.stype = ZE_STRUCTURE_TYPE_DEVICE_MEM_ALLOC_DESC;
                void *p = nullptr;
                ZE_CHECK(zeMemAllocDevice(c.ctx, &md, (size_t)step, 65536, c.dev, &p));
                c.blocks.push_back(p);
                allocated += step;
                const uint8_t pat = (uint8_t)(0x11 * (1 + c.blocks.size() % 15));
                ZE_CHECK(zeCommandListAppendMemoryFill(c.list, p, &pat, 1, (size_t)step, nullptr, 0, nullptr));
                ZE_CHECK(zeCommandListHostSynchronize(c.list, sync_ns));
                char tag[64];
                std::snprintf(tag, sizeof tag, "card %d +%lld MiB filled", c.index, step >> 20);
                av = status(tag);
                if (must_stop(av)) { rc = 3; break; }
                if (peer_resident) {
                    for (auto &o : cards) {
                        if (&o == &c) continue;
                        const ze_result_t r = zeContextMakeMemoryResident(c.ctx, o.dev, p, (size_t)step);
                        std::snprintf(tag, sizeof tag, "  resident on %d (0x%x)", o.index, (unsigned)r);
                        av = status(tag);
                        if (must_stop(av)) { rc = 3; break; }
                    }
                    if (rc) break;
                }
            }
        }
        if (rc == 0 && hold_s > 0) {
            std::printf("holding %d s\n", hold_s);
            for (int s = 0; s < hold_s && rc == 0; ++s) {
                std::this_thread::sleep_for(std::chrono::seconds(1));
                av = status("  hold");
                if (must_stop(av)) rc = 3;
            }
        }
        int wrong = 0;
        if (rc == 0 && peer_touch) {
            const size_t AB = 4u << 20, SB = 4096;
            for (auto &c : cards) {
                ze_device_mem_alloc_desc_t md{};
                md.stype = ZE_STRUCTURE_TYPE_DEVICE_MEM_ALLOC_DESC;
                ZE_CHECK(zeMemAllocDevice(c.ctx, &md, AB, 65536, c.dev, &c.arena));
                ZE_CHECK(zeMemAllocDevice(c.ctx, &md, SB, 4096, c.dev, &c.scratch));
                allocated += AB + SB;
                const uint8_t zero = 0, pat = (uint8_t)(0x40 + c.index);
                ZE_CHECK(zeCommandListAppendMemoryFill(c.list, c.arena, &zero, 1, AB, nullptr, 0, nullptr));
                ZE_CHECK(zeCommandListAppendMemoryFill(c.list, c.scratch, &pat, 1, SB, nullptr, 0, nullptr));
                ZE_CHECK(zeCommandListHostSynchronize(c.list, sync_ns));
            }
            av = status("peer arenas (4 MiB) filled");
            if (must_stop(av)) rc = 3;
            for (size_t i = 0; i < cards.size() && rc == 0; ++i) {
                Card &c = cards[i], &nx = cards[(i + 1) % cards.size()];
                if (&c == &nx) break;
                // card c's own command list writes into the next card's memory (a peer import of that arena)
                ZE_CHECK(zeCommandListAppendMemoryCopy(c.list, nx.arena, c.scratch, SB, nullptr, 0, nullptr));
                ZE_CHECK(zeCommandListHostSynchronize(c.list, sync_ns));
                std::vector<uint8_t> back(SB, 0);
                ZE_CHECK(zeCommandListAppendMemoryCopy(nx.list, back.data(), nx.arena, SB, nullptr, 0, nullptr));
                ZE_CHECK(zeCommandListHostSynchronize(nx.list, sync_ns));
                int bad = 0;
                for (uint8_t b : back) bad += b != (uint8_t)(0x40 + c.index);
                wrong += bad;
                char tag[64];
                std::snprintf(tag, sizeof tag, "peer copy %d->%d (%d wrong)", c.index, nx.index, bad);
                av = status(tag);
                if (must_stop(av)) rc = 3;
            }
        }
        if (rc == 0) {
            const long long avn = meminfo_kib("MemAvailable"), gan = meminfo_kib("GPUActive");
            const double drop = (avail0 - avn) / 1048576.0, ga = gan >= 0 && gpua0 >= 0 ? (gan - gpua0) / 1048576.0 : 0.0;
            const double ratio = allocated > 0 ? drop / (allocated / GiB) : 0.0;
            std::printf("RESULT mode=%s defer_backing_off=%d cards=%d on_cards=%.2f GiB MemAvailable_drop=%.2f GiB GPUActive=%+.2f GiB "
                        "host RAM per card byte=%.3f%s%s\n",
                        mode.c_str(), defer_off ? 1 : 0, ncards, allocated / GiB, drop, ga, ratio,
                        ratio < 0.05 ? " -> host RAM does NOT follow card memory" : " -> host RAM FOLLOWS card memory",
                        peer_touch ? (wrong ? " (peer copies WRONG)" : " (peer copies correct)") : "");
            if (peer_touch && wrong) rc = 1;
        }
    } catch (const L0Error &) {
        rc = 1;
    } catch (int) {
    }
    // free everything (also after a stop)
    for (auto &c : cards) {
        if (c.list) zeCommandListHostSynchronize(c.list, 30ull * 1000000000ull);
        for (void *p : c.blocks) zeMemFree(c.ctx, p);
        if (c.arena) zeMemFree(c.ctx, c.arena);
        if (c.scratch) zeMemFree(c.ctx, c.scratch);
        c.blocks.clear();
        c.arena = c.scratch = nullptr;
    }
    allocated = 0;
    status("freed");
    for (auto &c : cards) {
        if (c.list) zeCommandListDestroy(c.list);
        if (!shared_ctx && c.ctx) zeContextDestroy(c.ctx);
    }
    if (shared_ctx) zeContextDestroy(shared_ctx);
    std::printf("exit %d\n", rc);
    return rc;
}
