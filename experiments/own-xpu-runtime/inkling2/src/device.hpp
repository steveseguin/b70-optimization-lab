// device.hpp: one B70 card for the Inkling-2 engine. One SYCL context for this card only (a shared context spills
// card memory into host RAM on xe), one in-order queue. Weights go into arenas of at most ARENA bytes and are
// uploaded in PIECE-sized copies from a plain (not pinned) host buffer: single copies of 512 MiB or more read the
// runtime's temporary host mapping and faulted on these cards (lab note gpu-fault-20260916).
#pragma once
#include <filesystem>
#include <fstream>
#include <functional>
#include "gguf.hpp"
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fcntl.h>
#include <string>
#include <sycl/sycl.hpp>
#include <algorithm>
#include <map>
#include <tuple>
#include <unistd.h>
#include <vector>

namespace ink {

// per-label GPU time of the launches of a run (INK_PROF=1); add() is a no-op when off
struct Prof {
    bool on = std::getenv("INK_PROF") && std::atoi(std::getenv("INK_PROF"));
    std::vector<std::pair<std::string, sycl::event>> ev;
    struct Row { double ms = 0; long n = 0; };
    std::map<std::string, Row> rows;
    double busy_ms = 0, span_ms = 0;
    long steps = 0;
    void add(const std::string &label, sycl::event e) { if (on) ev.emplace_back(label, e); }
    void clear() { ev.clear(); }
    // fold the launches since the last collect into the table (after the queue has drained)
    void collect() {
        if (!on || ev.empty()) return;
        uint64_t first = UINT64_MAX, last = 0;
        // INK_PROF_GAPS=<n>: print this collect's n longest idle gaps between launches (with the labels on each side)
        static const int ngaps = std::getenv("INK_PROF_GAPS") ? std::atoi(std::getenv("INK_PROF_GAPS")) : 0;
        // INK_PROF_SEQ=<k>: print the k-th collect's launches in order (label, us, idle before)
        static const long seq = std::getenv("INK_PROF_SEQ") ? std::atol(std::getenv("INK_PROF_SEQ")) : -1;
        std::vector<std::tuple<uint64_t, uint64_t, const std::string *>> tl;
        for (auto &[l, e] : ev) {
            uint64_t a = e.get_profiling_info<sycl::info::event_profiling::command_start>();
            uint64_t b = e.get_profiling_info<sycl::info::event_profiling::command_end>();
            if (b < a) b = a; // a copy that the runtime timed as empty (the writing steps' embedding rows) reports junk
            rows[l].ms += (b - a) * 1e-6; rows[l].n++;
            busy_ms += (b - a) * 1e-6;
            if (b > a) { first = std::min(first, a); last = std::max(last, b); }
            if ((ngaps > 0 || seq == steps) && b > a) tl.emplace_back(a, b, &l);
        }
        if (seq == steps && !tl.empty()) {
            std::sort(tl.begin(), tl.end());
            uint64_t end = std::get<0>(tl[0]);
            for (auto &[a, b, l] : tl) {
                std::fprintf(stderr, "[seq] %-24s %9.2f us  idle %7.2f\n", l->c_str(), (b - a) * 1e-3, a > end ? (a - end) * 1e-3 : 0.0);
                end = std::max(end, b);
            }
        }
        if (ngaps > 0 && tl.size() > 1) {
            std::sort(tl.begin(), tl.end());
            std::vector<std::tuple<double, size_t>> gaps; // (us, index of the launch after the gap)
            uint64_t end = std::get<1>(tl[0]);
            double total = 0;
            for (size_t i = 1; i < tl.size(); ++i) {
                const uint64_t a = std::get<0>(tl[i]);
                if (a > end) { gaps.emplace_back((a - end) * 1e-3, i); total += (a - end) * 1e-3; }
                end = std::max(end, std::get<1>(tl[i]));
            }
            std::sort(gaps.begin(), gaps.end(), [](auto &x, auto &y) { return std::get<0>(x) > std::get<0>(y); });
            std::fprintf(stderr, "[gaps] %zu launches, %zu gaps, %.1f us idle in all\n", tl.size(), gaps.size(), total);
            for (int k = 0; k < ngaps && k < (int)gaps.size(); ++k) {
                const size_t i = std::get<1>(gaps[k]);
                std::fprintf(stderr, "[gaps] %10.1f us  #%zu  %s -> %s\n", std::get<0>(gaps[k]), i,
                             std::get<2>(tl[i - 1])->c_str(), std::get<2>(tl[i])->c_str());
            }
        }
        span_ms += (last - first) * 1e-6;
        steps++;
        ev.clear();
    }
    void report(FILE *f) const {
        if (!steps) return;
        std::vector<std::pair<std::string, Row>> v(rows.begin(), rows.end());
        std::sort(v.begin(), v.end(), [](auto &a, auto &b) { return a.second.ms > b.second.ms; });
        long launches = 0;
        for (auto &r : v) launches += r.second.n;
        std::fprintf(f, "[prof] %ld steps: span %.3f ms/step, kernels busy %.3f ms/step, %.1f launches/step\n", steps,
                     span_ms / steps, busy_ms / steps, (double)launches / steps);
        for (auto &[l, r] : v)
            std::fprintf(f, "[prof] %-28s %8.3f ms/step %6.1f launches/step %8.2f us each\n", l.c_str(), r.ms / steps,
                         (double)r.n / steps, 1e3 * r.ms / r.n);
    }
};

inline double now_s() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

// the Level Zero GPUs only (the OpenCL backend lists the same cards a second time)
inline std::vector<sycl::device> cards() {
    std::vector<sycl::device> v;
    for (auto &d : sycl::device::get_devices(sycl::info::device_type::gpu))
        if (d.get_backend() == sycl::backend::ext_oneapi_level_zero) v.push_back(d);
    return v;
}

struct Device {
    sycl::device dev;
    sycl::context ctx;
    sycl::queue q;
    int index = -1;
    std::string pci;
    std::vector<void *> owned;
    std::vector<size_t> owned_bytes; // the size of each owned allocation
    size_t allocated = 0;            // bytes in use (alloc minus release)

    explicit Device(int idx) : index(idx) {
        auto all = cards();
        if (idx < 0 || idx >= (int)all.size())
            throw std::runtime_error("device: card " + std::to_string(idx) + " not found (" + std::to_string(all.size()) + " GPUs)");
        dev = all[idx];
        ctx = sycl::context(dev);
        // INK_PROF=1: kernel timestamps for the profiler (the queue stays in order)
        if (std::getenv("INK_PROF") && std::atoi(std::getenv("INK_PROF")))
            q = sycl::queue(ctx, dev, sycl::property_list{sycl::property::queue::in_order{}, sycl::property::queue::enable_profiling{}});
        else
            q = sycl::queue(ctx, dev, sycl::property::queue::in_order{});
        if (dev.has(sycl::aspect::ext_intel_pci_address)) pci = dev.get_info<sycl::ext::intel::info::device::pci_address>();
    }
    ~Device() {
        for (void *p : owned) sycl::free(p, ctx);
    }
    Device(const Device &) = delete;
    Device &operator=(const Device &) = delete;

    std::string name() const { return dev.get_info<sycl::info::device::name>(); }
    size_t total_mem() const { return dev.get_info<sycl::info::device::global_mem_size>(); }
    // the card's energy counter in joules (hwmon energy1_input of its PCI device, read-only), -1 if there is none. Under
    // the card's power limit (~275 W, clock 2.3-2.8 GHz) a long run's speed follows energy per result, not stalls
    double energy_j() const {
        static const std::string path = [this] {
            if (!dev.has(sycl::aspect::ext_intel_pci_address)) return std::string();
            const std::string dir = "/sys/bus/pci/devices/" + dev.get_info<sycl::ext::intel::info::device::pci_address>() + "/hwmon";
            std::error_code ec;
            for (const auto &e : std::filesystem::directory_iterator(dir, ec))
                if (std::filesystem::exists(e.path() / "energy1_input")) return (e.path() / "energy1_input").string();
            return std::string();
        }();
        if (path.empty()) return -1.0;
        std::ifstream f(path);
        unsigned long long uj = 0;
        return (f >> uj) ? (double)uj * 1e-6 : -1.0;
    }
    // free card memory; needs ZES_ENABLE_SYSMAN=1, else returns 0
    size_t free_mem() const {
        if (!dev.has(sycl::aspect::ext_intel_free_memory)) return 0;
        return dev.get_info<sycl::ext::intel::info::device::free_memory>();
    }

    // xe does not fail an allocation past the card's memory: it moves memory out to host RAM. alloc() refuses to go
    // past the card's size minus INK_MEM_RESERVE_MB (default 512; was 1024) instead. The runtime itself holds ~0.26 GiB
    // beside our allocations (driver free memory at the end of runs from 3K to 515K positions, with and without the
    // drafter), so 512 MiB leaves ~0.25 GiB untouched (515K needle prompt: 0.50 GiB free at the end)
    size_t limit() const {
        static const size_t reserve = (size_t)(std::getenv("INK_MEM_RESERVE_MB") ? std::atol(std::getenv("INK_MEM_RESERVE_MB")) : 512) << 20;
        return total_mem() > reserve ? total_mem() - reserve : 0;
    }
    // hold: bytes alloc() keeps free as well while something is sized to what fits (ink_run: the drafter's room while
    // the engine tries a step size above 512); limit() (the engine's score-row sizing) does not count it
    size_t hold = 0;
    // the allocations made since mark() (the number of owned allocations then), freed newest first
    size_t mark() const { return owned.size(); }
    void release_to(size_t m) {
        while (owned.size() > m) release(owned.back());
    }
    template <class T = uint8_t> T *alloc(size_t count) {
        size_t bytes = count * sizeof(T);
        const size_t limit = this->limit();
        if (allocated + bytes + hold > limit)
            throw std::runtime_error("device: " + std::to_string(bytes >> 20) + " MiB more would pass the card's memory (" +
                                     std::to_string(allocated >> 20) + " MiB in use, limit " + std::to_string(limit >> 20) +
                                     " MiB" + (hold ? ", " + std::to_string(hold >> 20) + " MiB held" : std::string()) + ")");
        void *p = sycl::malloc_device(bytes ? bytes : 1, dev, ctx);
        if (!p) throw std::runtime_error("device: allocation of " + std::to_string(bytes) + " bytes failed");
        static const long log_mib = std::getenv("INK_MEM_LOG") ? std::atol(std::getenv("INK_MEM_LOG")) : -1; // allocations >= this many MiB
        if (log_mib >= 0 && (long)(bytes >> 20) >= log_mib)
            std::fprintf(stderr, "[mem] %8.1f MiB  (in use %8.1f MiB)\n", bytes / 1048576.0, (allocated + bytes) / 1048576.0);
        owned.push_back(p);
        owned_bytes.push_back(bytes);
        allocated += bytes;
        return (T *)p;
    }
    // free one allocation made by alloc()
    void release(void *p) {
        auto it = std::find(owned.begin(), owned.end(), p);
        if (it == owned.end()) throw std::runtime_error("device: release of a pointer it does not own");
        sycl::free(p, ctx);
        allocated -= owned_bytes[it - owned.begin()];
        owned_bytes.erase(owned_bytes.begin() + (it - owned.begin()));
        owned.erase(it);
    }
    template <class T> T *alloc_zero(size_t count) {
        T *p = alloc<T>(count);
        q.memset(p, 0, count * sizeof(T)).wait();
        return p;
    }
    template <class T> void put(T *dst, const T *src, size_t count) { q.memcpy(dst, src, count * sizeof(T)).wait(); }
    template <class T> void get(T *dst, const T *src, size_t count) { q.memcpy(dst, src, count * sizeof(T)).wait(); }
};

// Weights on the card: every tensor of the GGUF in arenas, at 256-byte aligned offsets.
struct Weights {
    static constexpr size_t ARENA = (size_t)1 << 30;  // bytes per arena allocation
    static constexpr size_t PIECE = (size_t)32 << 20; // bytes per host-to-card copy
    std::map<std::string, uint8_t *> ptr;
    size_t bytes = 0;
    double seconds = 0;

    // skip: tensors left in the file (their card layout is made elsewhere from fetch(), e.g. planarize's decode copies)
    void upload(Device &d, const GGUF &g, bool verbose = true, const std::function<bool(const Tensor &)> &skip = {}) {
        double t0 = now_s();
        // place tensors into arenas in file order
        struct Slot { const Tensor *t; size_t arena, off; };
        std::vector<Slot> slots;
        std::vector<size_t> arena_sz;
        size_t nskip = 0, skipped = 0;
        for (auto &t : g.tensors) {
            if (skip && skip(t)) { ++nskip; skipped += t.bytes; continue; }
            size_t padded = (t.bytes + 255) & ~(size_t)255;
            if (padded > ARENA) throw std::runtime_error("weights: tensor larger than an arena: " + t.name);
            if (arena_sz.empty() || arena_sz.back() + padded > ARENA) arena_sz.push_back(0);
            slots.push_back({&t, arena_sz.size() - 1, arena_sz.back()});
            arena_sz.back() += padded;
        }
        std::vector<uint8_t *> arenas;
        for (size_t s : arena_sz) arenas.push_back(d.alloc<uint8_t>(s));
        std::vector<std::pair<const Tensor *, uint8_t *>> list;
        for (auto &s : slots) list.push_back({s.t, arenas[s.arena] + s.off});
        copy_in(d, g, list);
        for (auto &s : slots) ptr[s.t->name] = arenas[s.arena] + s.off;
        seconds = now_s() - t0;
        if (verbose)
            std::fprintf(stderr, "[ink] uploaded %zu tensors, %.2f GB in %zu arenas, %.1f s (%.2f GB/s)%s\n", slots.size(),
                         bytes / 1e9, arenas.size(), seconds, bytes / 1e9 / seconds,
                         nskip ? (", " + std::to_string(nskip) + " tensors (" + std::to_string(skipped / 1000000) +
                                  " MB) left for their own layout").c_str() : "");
    }
    // one tensor's file bytes to dst on the card (waits)
    void fetch(Device &d, const GGUF &g, const Tensor &t, uint8_t *dst) { copy_in(d, g, {{&t, dst}}); }
    // file bytes of each tensor to its card address: two staging buffers so a read overlaps the previous copy
    void copy_in(Device &d, const GGUF &g, const std::vector<std::pair<const Tensor *, uint8_t *>> &list) {
        uint8_t *stage[2] = {(uint8_t *)aligned_alloc(4096, PIECE + 8192), (uint8_t *)aligned_alloc(4096, PIECE + 8192)};
        if (!stage[0] || !stage[1]) throw std::runtime_error("weights: staging allocation failed");
        int dfd = ::open(g.path.c_str(), O_RDONLY | O_DIRECT); // bulk reads bypass the page cache when possible
        sycl::event pending[2];
        int cur = 0;
        for (auto &[t, dst] : list) {
            uint64_t fbase = g.data_off + t->off;
            for (size_t done = 0; done < t->bytes;) {
                size_t n = std::min(PIECE, (size_t)t->bytes - done);
                pending[cur].wait(); // the buffer we are about to fill is free again
                uint64_t fo = fbase + done, a0 = fo & ~(uint64_t)4095;
                size_t lead = (size_t)(fo - a0), want = (lead + n + 4095) & ~(size_t)4095;
                bool ok = false;
                if (dfd >= 0) {
                    ssize_t got = ::pread(dfd, stage[cur], want, (off_t)a0);
                    ok = got >= (ssize_t)(lead + n);
                }
                if (!ok) { g.read_at(stage[cur], n, fo); lead = 0; }
                pending[cur] = d.q.memcpy(dst + done, stage[cur] + lead, n);
                done += n;
                bytes += n;
                cur ^= 1;
            }
        }
        pending[0].wait();
        pending[1].wait();
        if (dfd >= 0) ::close(dfd);
        free(stage[0]);
        free(stage[1]);
    }
    uint8_t *operator[](const std::string &n) const {
        auto it = ptr.find(n);
        if (it == ptr.end()) throw std::runtime_error("weights: not on the card: " + n);
        return it->second;
    }
    bool has(const std::string &n) const { return ptr.count(n) != 0; }
};

} // namespace ink
