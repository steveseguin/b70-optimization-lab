// Engram gather gate: independent Q5_K decode + row-addressed gather on the
// REAL 135.2GB per_layer_token_embd table (shard 6, 768,022,850 rows x 256,
// one 176B Q5_K block per row).
//   1. synthetic differential vs reference (finite scales, no NaN masking)
//   2. gather 8 rows at ids produced by the engram hash fixture
//      (data/engram/hashes.bin, layer-0 columns), decode mine vs reference
//      bit-exact, all values finite
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
#include "q5k_decode.hpp"
#include "test_common.hpp"

extern "C" void dequantize_row_q5_K(const void *x, float *y, int64_t k);

int main(int argc, char **argv) {
    const char *shard = argc > 1 ? argv[1]
        : "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/UD-IQ2_XXS/DeepSeek-V4.1-Flash-1017-UD-IQ2_XXS-00006-of-00006.gguf";
    const std::string dir = argc > 2 ? argv[2] : "data/engram";

    // 1) synthetic differential
    {
        std::vector<dsv41::block_q5_K> syn(4096);
        for (auto &b : syn) {
            auto *raw = (uint16_t *)&b;
            for (size_t i = 0; i < sizeof(b) / 2; ++i) raw[i] = (uint16_t)dsv41fix::rng();
            b.d = (uint16_t)(0x1400 | (dsv41fix::rng() & 0x3ff));
            b.dmin = (uint16_t)(0x1400 | (dsv41fix::rng() & 0x3ff));
        }
        if (!dsv41fix::compare<dsv41::block_q5_K>("q5_K synthetic x4096", syn.data(), 4096, 256,
                [](const dsv41::block_q5_K *b, float *y, long long nb) { dsv41::dequantize_q5_K(b, y, nb); },
                [](const dsv41::block_q5_K *b, float *y, int64_t k) { dequantize_row_q5_K(b, y, k); }))
            return 1;
    }

    // 2) real gather at hash-fixture row ids
    int fd = open(shard, O_RDONLY);
    if (fd < 0) { perror("open"); return 1; }
    struct stat st; fstat(fd, &st);
    const uint8_t *map = (const uint8_t *)mmap(nullptr, st.st_size, PROT_READ, MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) { perror("mmap"); return 1; }
    if (std::memcmp(map, "GGUF", 4) != 0) { std::fprintf(stderr, "not gguf\n"); return 1; }
    long long nb = 0;
    const uint8_t *t = dsv41fix::find_first_of_type(map, st.st_size, 13, 256, 176, &nb);
    if (!t) { std::fprintf(stderr, "no Q5_K tensor\n"); return 1; }
    std::printf("table rows: %lld\n", nb);

    std::vector<int64_t> hashes(512 * 48);
    {
        FILE *f = std::fopen((dir + "/hashes.bin").c_str(), "rb");
        if (!f || std::fread(hashes.data(), 8, hashes.size(), f) != hashes.size()) { std::fprintf(stderr, "read hashes\n"); return 1; }
        std::fclose(f);
    }
    // 8 layer-0 ids spread across the token stream (cols 0..23 of li=0)
    int64_t rows[8];
    for (int i = 0; i < 8; ++i) {
        rows[i] = hashes[(i * 61) * 48 + (i * 7) % 24];  // t stride 48 (2 layers x 24 cols), li=0
        if (rows[i] < 0 || rows[i] >= nb) { std::fprintf(stderr, "row id %lld out of range\n", (long long)rows[i]); return 1; }
    }
    bool ok = true;
    for (int i = 0; i < 8 && ok; ++i) {
        const dsv41::block_q5_K *blk = (const dsv41::block_q5_K *)(t + rows[i] * 176);
        float a[256], b[256];
        dsv41::dequantize_q5_K(blk, a, 1);
        dequantize_row_q5_K(blk, b, 256);
        long long nf = 0;
        for (int j = 0; j < 256; ++j) if (!std::isfinite(a[j]) || !std::isfinite(b[j])) ++nf;
        if (nf || std::memcmp(a, b, sizeof a)) {
            std::fprintf(stderr, "FAIL gather row %lld (nonfinite=%lld)\n", (long long)rows[i], nf);
            ok = false;
        } else {
            std::printf("OK   gather row %9lld: 256 values bit-exact, finite\n", (long long)rows[i]);
        }
    }
    munmap((void *)map, st.st_size);
    close(fd);
    if (ok) std::printf("FIXTURE_PASS engram_gather\n");
    return ok ? 0 : 1;
}
