// Shared differential gate body for the dsv41 dequant fixtures.
// Synthetic random blocks + real GGUF tensor blocks, bit-exact vs reference.
#pragma once
#include <cstdint>
#include <cstdio>
#include <cmath>
#include <cstring>
#include <fcntl.h>
#include <functional>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
#include "gguf_locate.hpp"

namespace dsv41fix {

inline uint64_t rng_state = 0x9e3779b97f4a7c15ull;
inline uint64_t rng() {
    rng_state ^= rng_state << 13; rng_state ^= rng_state >> 7; rng_state ^= rng_state << 17;
    return rng_state;
}

template <typename Block>
bool compare(const char *what, const Block *blk, long long nb, long long elems_per_block,
             const std::function<void(const Block *, float *, long long)> &ours,
             const std::function<void(const Block *, float *, int64_t)> &ref) {
    std::vector<float> a(nb * elems_per_block), b(nb * elems_per_block);
    ours(blk, a.data(), nb);
    ref(blk, b.data(), nb * elems_per_block);
    long long nonfinite = 0;
    for (size_t i = 0; i < a.size(); ++i)
        if (!std::isfinite(a[i]) || !std::isfinite(b[i])) ++nonfinite;
    if (nonfinite) {
        std::fprintf(stderr, "FAIL %s: %lld non-finite values (NaN-masked comparison is not a gate)\n",
                     what, nonfinite);
        return false;
    }
    if (std::memcmp(a.data(), b.data(), a.size() * 4) != 0) {
        for (size_t i = 0; i < a.size(); ++i)
            if (std::memcmp(&a[i], &b[i], 4) != 0) {
                std::fprintf(stderr, "FAIL %s: value %zu (block %zu elem %zu): ours=%a ref=%a\n",
                             what, i, i / elems_per_block, i % elems_per_block, a[i], b[i]);
                return false;
            }
    }
    std::printf("OK   %s: %lld blocks, %lld values bit-exact\n", what, nb, nb * elems_per_block);
    return true;
}

template <typename Block>
int run_fixture(const char *name, uint32_t type_id,
                const std::function<void(const Block *, float *, long long)> &ours,
                const std::function<void(const Block *, float *, int64_t)> &ref,
                 int argc, char **argv, size_t d_offset = 0, size_t dmin_offset = SIZE_MAX,
                 long long elems_per_block = 256,
                 const std::function<void(Block &)> &extra_sanitize = nullptr) {
    std::vector<Block> syn(4096);
    for (auto &b : syn) {
        auto *raw = (uint16_t *)&b;
        for (size_t i = 0; i < sizeof(Block) / 2; ++i) raw[i] = (uint16_t)rng();
        // force fp16 super-scales finite (exp 5, random mantissa) so the
        // gate compares meaningful values instead of identical NaN payloads
        if (d_offset != SIZE_MAX)
            *(uint16_t *)((char *)&b + d_offset) = (uint16_t)(0x1400 | (rng() & 0x3ff));
        if (dmin_offset != SIZE_MAX)
            *(uint16_t *)((char *)&b + dmin_offset) = (uint16_t)(0x1400 | (rng() & 0x3ff));
        if (extra_sanitize) extra_sanitize(b);
    }
    if (!compare<Block>("synthetic x4096", syn.data(), 4096, elems_per_block, ours, ref)) return 1;

    const char *path = argc > 1 ? argv[1]
        : "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-00002-of-00006.gguf";
    int fd = open(path, O_RDONLY);
    if (fd < 0) { perror("open"); return 1; }
    struct stat st; fstat(fd, &st);
    const uint8_t *map = (const uint8_t *)mmap(nullptr, st.st_size, PROT_READ, MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) { perror("mmap"); return 1; }
    if (std::memcmp(map, "GGUF", 4) != 0) { std::fprintf(stderr, "not gguf\n"); return 1; }
    long long nb = 0;
    const uint8_t *t = find_first_of_type(map, st.st_size, type_id, (uint32_t)elems_per_block, sizeof(Block), &nb);
    if (!t) { std::fprintf(stderr, "no tensor of type %u found for %s\n", type_id, name); return 1; }
    if (nb > 512) nb = 512;
    int rc = compare<Block>("real gguf x512", (const Block *)t, nb, elems_per_block, ours, ref) ? 0 : 1;
    munmap((void *)map, st.st_size);
    close(fd);
    if (rc == 0) std::printf("FIXTURE_PASS %s\n", name);
    return rc;
}

} // namespace dsv41fix
