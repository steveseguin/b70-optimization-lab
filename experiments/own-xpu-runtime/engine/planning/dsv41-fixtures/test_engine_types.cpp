// Three-way gate: the engine's iq3::decode branches for the dsv41 types
// (Q2_K, IQ2_XXS, IQ2_XS, IQ1_S, MXFP4) vs the reference ggml decoders,
// on synthetic blocks and real sha256-verified GGUF bytes.
// Together with test_q2k/test_iq2xxs/test_iq2xs/test_iq1s/test_mxfp4
// (independent decoders vs reference) this proves
// fixture == engine == reference on every tested byte pattern.
#include <cstdint>
#include "test_common.hpp"
#include "q2k_decode.hpp"
#include "iq2xs_decode.hpp"
#include "iq1s_decode.hpp"
#include "mxfp4_decode.hpp"
#include "stage2/packet2/kernels/math.hpp"

extern "C" void dequantize_row_q2_K(const void *x, float *y, int64_t k);
extern "C" void dequantize_row_iq2_xxs(const void *x, float *y, int64_t k);
extern "C" void dequantize_row_iq2_xs(const void *x, float *y, int64_t k);
extern "C" void dequantize_row_iq1_s(const void *x, float *y, int64_t k);
extern "C" void dequantize_row_mxfp4(const void *x, float *y, int64_t k);

template <typename Block, iq3::Type T>
static void engine_decode(const Block *b, float *y, long long nb) {
    const long long elems = iq3::layout(T).elements;
    for (long long n = 0; n < nb; ++n, ++b, y += elems)
        for (long long i = 0; i < elems; ++i)
            y[i] = iq3::decode(T, (const uint8_t *)b, (uint32_t)i);
}

int main(int argc, char **argv) {
    int rc = 0;
    rc |= dsv41fix::run_fixture<dsv41::block_q2_K>(
        "engine_q2k", 10, engine_decode<dsv41::block_q2_K, iq3::Type::Q2_K>,
        [](const dsv41::block_q2_K *b, float *y, int64_t k) { dequantize_row_q2_K(b, y, k); },
        argc, argv, 80, 82);
    rc |= dsv41fix::run_fixture<dsv41::block_iq2_xxs>(
        "engine_iq2xxs", 16, engine_decode<dsv41::block_iq2_xxs, iq3::Type::IQ2_XXS>,
        [](const dsv41::block_iq2_xxs *b, float *y, int64_t k) { dequantize_row_iq2_xxs(b, y, k); },
        argc, argv, 0);
    rc |= dsv41fix::run_fixture<dsv41::block_iq2_xs>(
        "engine_iq2xs", 17, engine_decode<dsv41::block_iq2_xs, iq3::Type::IQ2_XS>,
        [](const dsv41::block_iq2_xs *b, float *y, int64_t k) { dequantize_row_iq2_xs(b, y, k); },
        argc, argv, 0);
    rc |= dsv41fix::run_fixture<dsv41::block_iq1_s>(
        "engine_iq1s", 19, engine_decode<dsv41::block_iq1_s, iq3::Type::IQ1_S>,
        [](const dsv41::block_iq1_s *b, float *y, int64_t k) { dequantize_row_iq1_s(b, y, k); },
        argc, argv, 0);
    const char *dspark = "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf";
    const char *argv2[2] = {argv[0], argc > 1 ? argv[1] : dspark};
    rc |= dsv41fix::run_fixture<dsv41::block_mxfp4>(
        "engine_mxfp4", 39, engine_decode<dsv41::block_mxfp4, iq3::Type::MXFP4>,
        [](const dsv41::block_mxfp4 *b, float *y, int64_t k) { dequantize_row_mxfp4(b, y, k); },
        2, const_cast<char **>(argv2), SIZE_MAX, SIZE_MAX, 32,
        [](dsv41::block_mxfp4 &b) { b.e = (uint8_t)(100 + (dsv41fix::rng() % 40)); });
    if (rc == 0) std::printf("FIXTURE_PASS engine_types\n");
    return rc;
}
