// Differential fixture: independent engram hash chain vs the numpy/torch
// reference dump (data/engram/, generator gen_engram_ref.py; real layout
// params from config.json, synthetic token_map, seeded ids with dead spans).
// Pure int64 — gate is BIT-EXACT. Also re-derives the prime table with my
// own next-prime and requires equality with the dumped primes.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include "engram_hash.hpp"

static std::vector<int64_t> loadi(const std::string &p, size_t n) {
    std::vector<int64_t> v(n);
    FILE *f = std::fopen(p.c_str(), "rb");
    if (!f || std::fread(v.data(), 8, n, f) != n) { std::fprintf(stderr, "read %s\n", p.c_str()); std::exit(1); }
    std::fclose(f); return v;
}

int main(int argc, char **argv) {
    const std::string dir = argc > 1 ? argv[1] : "data/engram";
    auto primes  = loadi(dir + "/primes.bin", 2 * 24);
    auto offsets = loadi(dir + "/offsets.bin", 2 * 24);
    auto mults   = loadi(dir + "/mults.bin", 2 * 4);
    auto token_map = loadi(dir + "/token_map.bin", 129280);
    auto ids     = loadi(dir + "/ids.bin", 512);
    auto hashes  = loadi(dir + "/hashes.bin", 512 * 2 * 24);
    auto padv    = loadi(dir + "/pad.bin", 1);
    std::vector<uint8_t> mask(512);
    {
        FILE *f = std::fopen((dir + "/mask.bin").c_str(), "rb");
        if (!f || std::fread(mask.data(), 1, 512, f) != 512) { std::fprintf(stderr, "read mask\n"); return 1; }
        std::fclose(f);
    }
    const int64_t pad_id = padv[0];

    // 1) re-derive the prime chain independently
    {
        std::vector<int64_t> seen;
        bool ok = true;
        for (int li = 0; li < 2 && ok; ++li)
            for (int ng = 0; ng < 3 && ok; ++ng) {
                int64_t current = 16000000 - 1;
                for (int h = 0; h < 8; ++h) {
                    current = dsv41::find_next_prime(current, seen.data(), (long long)seen.size());
                    seen.push_back(current);
                    if (current != primes[(li * 3 + ng) * 8 + h]) {
                        std::fprintf(stderr, "FAIL prime[%d][%d][%d]: mine=%lld ref=%lld\n",
                                     li, ng, h, (long long)current, (long long)primes[(li*3+ng)*8+h]);
                        ok = false;
                    }
                }
            }
        if (!ok) return 1;
        std::printf("OK   prime chain: 48 primes re-derived exactly\n");
    }

    // 2) hash chain, both layers, bit-exact
    std::vector<int64_t> mine(512 * 2 * 24);
    for (int li = 0; li < 2; ++li)
        dsv41::engram_hash_layer(li, ids.data(), mask.data(), 512,
                                 token_map.data(), pad_id,
                                 mults.data() + li * 4,
                                 primes.data() + li * 24, offsets.data() + li * 24,
                                 2, mine.data());
    long long diffs = 0;
    for (size_t i = 0; i < mine.size(); ++i)
        if (mine[i] != hashes[i]) {
            if (diffs < 3)
                std::fprintf(stderr, "FAIL hash[%zu] (t=%zu li=%zu col=%zu): mine=%lld ref=%lld\n",
                             i, i / 48, (i / 24) % 2, i % 24, (long long)mine[i], (long long)hashes[i]);
            ++diffs;
        }
    if (diffs) { std::fprintf(stderr, "FAIL: %lld hash diffs\n", (long long)diffs); return 1; }
    std::printf("OK   hash chain: %zu ids bit-exact (512 tokens x 2 layers x 24 cols)\n", mine.size());
    std::printf("FIXTURE_PASS engram_hash\n");
    return 0;
}
