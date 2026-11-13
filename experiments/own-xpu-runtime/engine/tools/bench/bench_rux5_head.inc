// rux5: the shared head of bench_rux5.cpp (bench_rux4.cpp's includes, real GGUF rows of all 384 experts, packed rows)
#include <sycl/sycl.hpp>
#include <sycl/ext/intel/experimental/grf_size_properties.hpp>
#include <fcntl.h>
#include <unistd.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <numeric>
#include <random>
#include <sstream>
#include <string>
#include <type_traits>
#include <vector>
#include "stage2/packet3/kernels/sycl_v41.hpp"
#include "stage2/packet3/kernels/pack_v41.hpp"
#include "stage2/packet3/kernels/sycl_v41_routed_rux.hpp"
#include "stage2/packet3/kernels/sycl_v41_routed_rux4.hpp"
#include "stage2/packet3/kernels/sycl_v41_routed_rux5.hpp"
using namespace ops41sycl;
using Ty = iq3::Type;

static constexpr unsigned NEXP = 384, PAIR_ROWS = 384, DOWN_ROWS = 864;
static constexpr unsigned PAIR_R0 = 768, DOWN_R0 = 1696; // card 2's first row of each expert (gate/up, down)
static constexpr unsigned MMAX = 512;                    // tokens (real 512; tpe up to 8)
static_assert(RUGrp::MAXU >= 6 * 256, "RUGrp");
static int g_fail = 0;

static uint64_t sm64(uint64_t &s) {
    uint64_t z = (s += 0x9E3779B97F4A7C15ull);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}
template <Ty TY> uint8_t *packed_bank(sycl::queue &q, unsigned cols, size_t nrow, uint64_t seed) {
    constexpr auto L = iq3::layout(TY);
    const size_t nb = cols / L.elements, rb = nb * L.bytes, prb = pk41::packed_row_bytes(TY, cols);
    uint8_t *d = sycl::malloc_device<uint8_t>(nrow * prb, q);
    if (!d) {
        std::printf("FAIL cannot allocate %.0f MB of card memory\n", nrow * prb / 1e6);
        std::exit(1);
    }
    constexpr size_t CH = 4096;
    std::vector<uint8_t> src(rb), dst(CH * prb);
    for (size_t r0 = 0; r0 < nrow; r0 += CH) {
        const size_t n = std::min(CH, nrow - r0);
        for (size_t r = 0; r < n; ++r) {
            for (size_t i = 0; i < rb; i += 8) {
                const uint64_t v = sm64(seed);
                std::memcpy(&src[i], &v, std::min<size_t>(8, rb - i));
            }
            for (size_t b = 0; b < nb; ++b) {
                const uint16_t h = 0x1400 + (sm64(seed) & 0x3ff);
                src[b * L.bytes] = h & 255;
                src[b * L.bytes + 1] = h >> 8;
            }
            pk41::pack_row(TY, src.data(), dst.data() + r * prb, cols);
        }
        q.memcpy(d + r0 * prb, dst.data(), n * prb).wait();
    }
    return d;
}

// ---- real GGUF expert rows: all 384 experts x card 2's rows [r0, r0 + rows), packed --------------------------
static const char *GGUF_DIR = "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS";
struct GgufT {
    std::string file;
    uint64_t off = 0;
    uint32_t type = 0;
    uint64_t ne[3] = {1, 1, 1};
};
static bool gguf_find(const std::string &name, GgufT &out) {
    for (int part = 1; part <= 6; ++part) {
        char fn[512];
        std::snprintf(fn, sizeof fn, "%s/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-%05d-of-00006.gguf", GGUF_DIR, part);
        const int fd = open(fn, O_RDONLY);
        if (fd < 0) continue;
        std::vector<uint8_t> h((size_t)32 << 20);
        const ssize_t n = pread(fd, h.data(), h.size(), 0);
        close(fd);
        if (n < 64 || std::memcmp(h.data(), "GGUF", 4)) continue;
        const uint8_t *p = h.data() + 4, *end = h.data() + n;
        auto rd = [&](auto &v) { std::memcpy(&v, p, sizeof v); p += sizeof v; };
        uint32_t ver;
        uint64_t nt, nkv;
        rd(ver), rd(nt), rd(nkv);
        static const int tsz[13] = {1, 1, 2, 2, 4, 4, 4, 1, -1, -1, 8, 8, 8};
        uint64_t align = 32;
        bool bad = false;
        for (uint64_t i = 0; i < nkv && !bad; ++i) {
            uint64_t kl;
            rd(kl);
            const std::string key((const char *)p, kl);
            p += kl;
            uint32_t t;
            rd(t);
            if (t == 8) { uint64_t m; rd(m); p += m; }
            else if (t == 9) {
                uint32_t et;
                uint64_t m;
                rd(et), rd(m);
                if (et == 8) for (uint64_t j = 0; j < m; ++j) { uint64_t sl; rd(sl); p += sl; }
                else p += m * tsz[et];
            } else {
                if (key == "general.alignment" && t == 4) { uint32_t a; std::memcpy(&a, p, 4); align = a; }
                p += tsz[t];
            }
            if (p > end) bad = true;
        }
        if (bad) continue;
        bool found = false;
        GgufT g;
        for (uint64_t i = 0; i < nt && p < end; ++i) {
            uint64_t nl;
            rd(nl);
            const std::string tn((const char *)p, nl);
            p += nl;
            uint32_t nd;
            rd(nd);
            uint64_t dims[4] = {1, 1, 1, 1};
            for (uint32_t d = 0; d < nd; ++d) rd(dims[d]);
            uint32_t ty;
            uint64_t off;
            rd(ty), rd(off);
            if (tn == name) {
                found = true;
                g.file = fn, g.type = ty, g.off = off;
                for (int d = 0; d < 3; ++d) g.ne[d] = dims[d];
            }
        }
        if (!found) continue;
        g.off += ((size_t)(p - h.data()) + align - 1) / align * align;
        out = g;
        return true;
    }
    return false;
}
template <Ty TY> static uint8_t *real_bank_all(sycl::queue &q, const std::string &name, unsigned cols, unsigned r0, unsigned rows) {
    GgufT g;
    if (!gguf_find(name, g)) { std::printf("  real: %s not found\n", name.c_str()); return nullptr; }
    if (g.ne[0] != cols || g.type != (uint32_t)TY || g.ne[1] < r0 + rows || g.ne[2] < NEXP) {
        std::printf("  real: %s type %u shape %llu x %llu x %llu does not fit\n", name.c_str(), g.type,
                    (unsigned long long)g.ne[0], (unsigned long long)g.ne[1], (unsigned long long)g.ne[2]);
        return nullptr;
    }
    constexpr auto L = iq3::layout(TY);
    const size_t rb = (size_t)cols / L.elements * L.bytes, prb = pk41::packed_row_bytes(TY, cols);
    constexpr unsigned CH = 32; // experts per host chunk
    std::vector<uint8_t> hw((size_t)rows * rb), hp((size_t)CH * rows * prb);
    uint8_t *d = sycl::malloc_device<uint8_t>((size_t)NEXP * rows * prb, q);
    if (!d) return nullptr;
    const int fd = open(g.file.c_str(), O_RDONLY);
    if (fd < 0) { sycl::free(d, q); return nullptr; }
    for (unsigned e0 = 0; e0 < NEXP; e0 += CH) {
        for (unsigned e = e0; e < e0 + CH; ++e) {
            const uint64_t off = g.off + ((uint64_t)e * g.ne[1] + r0) * rb;
            if (pread(fd, hw.data(), hw.size(), (off_t)off) != (ssize_t)hw.size()) { close(fd); sycl::free(d, q); return nullptr; }
            for (unsigned r = 0; r < rows; ++r)
                pk41::pack_row(TY, hw.data() + (size_t)r * rb, hp.data() + ((size_t)(e - e0) * rows + r) * prb, cols);
        }
        q.memcpy(d + (size_t)e0 * rows * prb, hp.data(), hp.size()).wait();
    }
    close(fd);
    return d;
}

static double ev_us(const sycl::event &e) {
    return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
            e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
}
