// device.hpp: one B70 card for the Inkling-2 engine. One SYCL context for this card only (a shared context spills
// card memory into host RAM on xe), one in-order queue. Weights go into arenas of at most ARENA bytes and are
// uploaded in PIECE-sized copies from a plain (not pinned) host buffer: single copies of 512 MiB or more read the
// runtime's temporary host mapping and faulted on these cards (lab note gpu-fault-20260916).
#pragma once
#include "gguf.hpp"
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fcntl.h>
#include <string>
#include <sycl/sycl.hpp>
#include <unistd.h>
#include <vector>

namespace ink {

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
    size_t allocated = 0;

    explicit Device(int idx) : index(idx) {
        auto all = cards();
        if (idx < 0 || idx >= (int)all.size())
            throw std::runtime_error("device: card " + std::to_string(idx) + " not found (" + std::to_string(all.size()) + " GPUs)");
        dev = all[idx];
        ctx = sycl::context(dev);
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
    // free card memory; needs ZES_ENABLE_SYSMAN=1, else returns 0
    size_t free_mem() const {
        if (!dev.has(sycl::aspect::ext_intel_free_memory)) return 0;
        return dev.get_info<sycl::ext::intel::info::device::free_memory>();
    }

    template <class T = uint8_t> T *alloc(size_t count) {
        size_t bytes = count * sizeof(T);
        void *p = sycl::malloc_device(bytes ? bytes : 1, dev, ctx);
        if (!p) throw std::runtime_error("device: allocation of " + std::to_string(bytes) + " bytes failed");
        owned.push_back(p);
        allocated += bytes;
        return (T *)p;
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

    void upload(Device &d, const GGUF &g, bool verbose = true) {
        double t0 = now_s();
        // place tensors into arenas in file order
        struct Slot { const Tensor *t; size_t arena, off; };
        std::vector<Slot> slots;
        std::vector<size_t> arena_sz;
        for (auto &t : g.tensors) {
            size_t padded = (t.bytes + 255) & ~(size_t)255;
            if (padded > ARENA) throw std::runtime_error("weights: tensor larger than an arena: " + t.name);
            if (arena_sz.empty() || arena_sz.back() + padded > ARENA) arena_sz.push_back(0);
            slots.push_back({&t, arena_sz.size() - 1, arena_sz.back()});
            arena_sz.back() += padded;
        }
        std::vector<uint8_t *> arenas;
        for (size_t s : arena_sz) arenas.push_back(d.alloc<uint8_t>(s));
        // two staging buffers so a read overlaps the previous copy
        uint8_t *stage[2] = {(uint8_t *)aligned_alloc(4096, PIECE + 8192), (uint8_t *)aligned_alloc(4096, PIECE + 8192)};
        if (!stage[0] || !stage[1]) throw std::runtime_error("weights: staging allocation failed");
        int dfd = ::open(g.path.c_str(), O_RDONLY | O_DIRECT); // bulk reads bypass the page cache when possible
        sycl::event pending[2];
        int cur = 0;
        for (auto &s : slots) {
            uint8_t *dst = arenas[s.arena] + s.off;
            uint64_t fbase = g.data_off + s.t->off;
            for (size_t done = 0; done < s.t->bytes;) {
                size_t n = std::min(PIECE, (size_t)s.t->bytes - done);
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
            ptr[s.t->name] = dst;
        }
        pending[0].wait();
        pending[1].wait();
        if (dfd >= 0) ::close(dfd);
        free(stage[0]);
        free(stage[1]);
        seconds = now_s() - t0;
        if (verbose)
            std::fprintf(stderr, "[ink] uploaded %zu tensors, %.2f GB in %zu arenas, %.1f s (%.2f GB/s)\n", slots.size(),
                         bytes / 1e9, arenas.size(), seconds, bytes / 1e9 / seconds);
    }
    uint8_t *operator[](const std::string &n) const {
        auto it = ptr.find(n);
        if (it == ptr.end()) throw std::runtime_error("weights: not on the card: " + n);
        return it->second;
    }
    bool has(const std::string &n) const { return ptr.count(n) != 0; }
};

} // namespace ink
