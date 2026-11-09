// Independent engram n-gram hash chain for DeepSeek V4.1.
// Semantics from official inference/engram.py NgramHashState (MIT):
//   compressed ids through token_map; DEAD(-1) spans and lookback past
//   sequence start collapse to pad_id; products token*multiplier (int64),
//   XOR-rolled one lookback at a time; hash of the (i+1)-gram after step i;
//   bucket = rolling % primes[layer][ngram-2][head] + offset[layer][...].
// Pure int64 xor/mod — bit-exact gatable. Primes/offsets/multipliers are
// fixture data (data/engram/), computed by gen_engram_ref.py from the
// official layout rules (next-prime chain from 16M-1, per-layer RNG
// multipliers, cumulative bucket offsets).
#pragma once
#include <cstdint>

namespace dsv41 {

inline bool is_prime_i64(int64_t v) {
    if (v < 2) return false;
    if (v % 2 == 0) return v == 2;
    for (int64_t d = 3; d <= v / d; d += 2)
        if (v % d == 0) return false;
    return true;
}

// next prime above start not in seen[0..n_seen); updates seen
inline int64_t find_next_prime(int64_t start, int64_t *seen, long long n_seen) {
    int64_t c = start + 1;
    for (;; ++c) {
        if (!is_prime_i64(c)) continue;
        bool dup = false;
        for (long long i = 0; i < n_seen; ++i) if (seen[i] == c) { dup = true; break; }
        if (!dup) return c;
    }
}

// hash ids for one sequence. tokens: raw ids[L]; mask: 0 = dead span.
// token_map[raw] -> compressed id. Writes out[L][24] per layer index li
// (out strides: out[(t*LAYER_STRIDE + li)*24 + col]).
inline void engram_hash_layer(int li, const int64_t *tokens, const uint8_t *mask, long long L,
                              const int64_t *token_map, int64_t pad_id,
                              const int64_t *mults /*[4]*/,
                              const int64_t *primes /*[3*8]*/, const int64_t *offsets /*[24]*/,
                              long long layer_stride, int64_t *out) {
    constexpr int MAX_N = 4, HEADS = 8;
    for (long long t = 0; t < L; ++t) {
        int64_t toks[MAX_N];
        for (int shift = 0; shift < MAX_N; ++shift) {
            long long src = t - shift < 0 ? 0 : t - shift;
            int64_t v = mask[src] ? token_map[tokens[src]] : -1;
            bool blocked = (t < shift) || v == -1;
            toks[shift] = blocked ? pad_id : v;
        }
        int64_t rolling = toks[0] * mults[0];
        for (int i = 1; i < MAX_N; ++i) {
            rolling ^= toks[i] * mults[i];
            for (int h = 0; h < HEADS; ++h) {
                int col = (i - 1) * HEADS + h;
                int64_t r = rolling % primes[(i - 1) * HEADS + h];
                if (r < 0) r += primes[(i - 1) * HEADS + h];  // C++ % keeps sign
                out[(t * layer_stride + li) * 24 + col] = r + offsets[col];
            }
        }
    }
}

} // namespace dsv41
