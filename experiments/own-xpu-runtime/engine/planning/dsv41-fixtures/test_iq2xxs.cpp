// Differential fixture: Own Xe independent IQ2_XXS decoder vs the reference
// ggml dequantize_row_iq2_xxs (compiled from the pinned llama.cpp clone,
// advisory reference only). Requires bit-exact float equality on:
//   1. 4096 pseudo-random synthetic blocks (full codebook/sign coverage)
//   2. 512 real blocks from the verified local UD-IQ2_XXS shard 2
//      (first IQ2_XXS tensor located via the GGUF header, mmap read-only)
// Build/run: see README.md. CPU-only; no GPU, no engine admission.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <fcntl.h>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
#include "iq2xxs_decode.hpp"
#include "gguf_locate.hpp"

extern "C" void dequantize_row_iq2_xxs(const void *x, float *y, int64_t k);

static uint64_t rng_state = 0x9e3779b97f4a7c15ull;
static uint64_t rng() {
    rng_state ^= rng_state << 13; rng_state ^= rng_state >> 7; rng_state ^= rng_state << 17;
    return rng_state;
}

static bool compare(const char *what, const dsv41::block_iq2_xxs *blk, long long nb) {
    std::vector<float> a(nb * 256), b(nb * 256);
    dsv41::dequantize_iq2_xxs(blk, a.data(), nb);
    dequantize_row_iq2_xxs(blk, b.data(), nb * 256);
    for (size_t i = 0; i < a.size(); ++i)
        if (!std::isfinite(a[i]) || !std::isfinite(b[i])) {
            std::fprintf(stderr, "FAIL %s: non-finite value at %zu (NaN payloads are not a gate)\n", what, i);
            return false;
        }
    if (std::memcmp(a.data(), b.data(), a.size() * 4) != 0) {
        for (size_t i = 0; i < a.size(); ++i)
            if (std::memcmp(&a[i], &b[i], 4) != 0) {
                std::fprintf(stderr, "FAIL %s: first diff at value %zu (block %zu elem %zu): ours=%a ref=%a\n",
                             what, i, i / 256, i % 256, a[i], b[i]);
                return false;
            }
    }
    std::printf("OK   %s: %lld blocks, %lld values bit-exact\n", what, nb, nb * 256);
    return true;
}

int main(int argc, char **argv) {
    // 1) synthetic coverage
    std::vector<dsv41::block_iq2_xxs> syn(4096);
    for (auto &b : syn) {
        b.d = (uint16_t)(0x1400 | (rng() & 0x3ff));  // finite fp16 scale; NaN payloads must not mask
        for (auto &q : b.qs) q = (uint16_t)rng();
    }
    if (!compare("synthetic x4096", syn.data(), 4096)) return 1;

    // 2) real GGUF bytes
    const char *path = argc > 1 ? argv[1]
        : "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-00002-of-00006.gguf";
    int fd = open(path, O_RDONLY);
    if (fd < 0) { perror("open"); return 1; }
    struct stat st; fstat(fd, &st);
    const uint8_t *map = (const uint8_t *)mmap(nullptr, st.st_size, PROT_READ, MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) { perror("mmap"); return 1; }
    if (std::memcmp(map, "GGUF", 4) != 0) { std::fprintf(stderr, "not gguf\n"); return 1; }
    long long nb = 0;
    const uint8_t *t = dsv41fix::find_first_of_type(map, st.st_size, 16, 256, 66, &nb);
    if (!t) { std::fprintf(stderr, "no IQ2_XXS tensor found\n"); return 1; }
    long long blocks = nb;
    if (blocks > 512) blocks = 512;
    int rc = compare("real gguf x512", (const dsv41::block_iq2_xxs *)t, blocks) ? 0 : 1;
    munmap((void *)map, st.st_size);
    close(fd);
    if (rc == 0) std::printf("FIXTURE_PASS\n");
    return rc;
}
