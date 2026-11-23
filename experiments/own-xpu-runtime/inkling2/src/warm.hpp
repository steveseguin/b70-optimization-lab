#pragma once
// warm: read weight bytes into the card's L2 cache ahead of the matrix kernel that needs them. It runs on a second
// queue while the main queue runs latency-bound kernels (norms, mixes, attention of one token), when the memory is
// otherwise idle. It writes nothing the engine reads (sink only on an impossible value), so results are unchanged;
// only the time of the next matrix kernel changes.
#include <sycl/sycl.hpp>
#include <algorithm>
#include <cstdint>

namespace ink::fz {

struct WarmSet {
    static constexpr int MAX = 10;
    const uint8_t *p[MAX] = {}; size_t n[MAX] = {}; int k = 0;
    void add(const uint8_t *ptr, size_t bytes) {
        if (ptr && bytes >= 32 && k < MAX) { p[k] = ptr; n[k] = bytes; ++k; }
    }
};

// the reads of work-item gid of N (device side)
inline void warm_part(const WarmSet &s, size_t gid, size_t N, uint32_t *sink) {
    uint32_t acc = 0;
    for (int r = 0; r < s.k; ++r) {
        const uint32_t *w = (const uint32_t *)s.p[r];
        const size_t np = s.n[r] / 32;
        size_t i = gid;
        for (; i + 3 * N < np; i += 4 * N) {
            const uint32_t a0 = w[i * 8], a1 = w[(i + N) * 8], a2 = w[(i + 2 * N) * 8], a3 = w[(i + 3 * N) * 8];
            acc ^= a0 ^ a1 ^ a2 ^ a3;
        }
        for (; i < np; i += N) acc ^= w[i * 8];
    }
    if (acc == 0x9e3779b9u) sink[0] = acc;
}
// bytes [off, off + bytes) of s (its ranges one after another)
inline WarmSet warm_range(const WarmSet &s, size_t off, size_t bytes) {
    WarmSet o;
    for (int r = 0; r < s.k && bytes >= 32; ++r) {
        if (off >= s.n[r]) { off -= s.n[r]; continue; }
        const size_t n = std::min(s.n[r] - off, bytes);
        o.add(s.p[r] + off, n);
        bytes -= n;
        off = 0;
    }
    return o;
}
inline WarmSet warm_head(const WarmSet &s, size_t bytes) { return warm_range(s, 0, bytes); }
// extra work-groups a latency-bound kernel can carry (Warm{} = none)
struct Warm { WarmSet s; int nwg = 0; uint32_t *sink = nullptr; };

// one 4-byte read per 32-byte piece; consecutive work-items read consecutive pieces (a sub-group covers 512 bytes)
inline sycl::event warm(sycl::queue &q, const WarmSet &s, const sycl::event *dep, uint32_t *sink, int nwg) {
    return q.submit([&](sycl::handler &h) {
        if (dep) h.depends_on(*dep);
        h.parallel_for(sycl::nd_range<1>((size_t)nwg * 256, 256), [=](sycl::nd_item<1> it) {
            warm_part(s, it.get_global_id(0), it.get_global_range(0), sink);
        });
    });
}

} // namespace ink::fz
