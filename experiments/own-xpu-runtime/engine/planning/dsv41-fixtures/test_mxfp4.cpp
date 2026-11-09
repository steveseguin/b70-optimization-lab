// Differential fixture: independent MXFP4 decoder vs reference.
// Real bytes from the sha256-verified dspark Q8_0/draft file (type 39).
#include <cstring>
#include "mxfp4_decode.hpp"
#include "test_common.hpp"

extern "C" void dequantize_row_mxfp4(const void *x, float *y, int64_t k);

int main(int argc, char **argv) {
    const char *path = "/mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf";
    const char *argv2[2] = {argv[0], argc > 1 ? argv[1] : path};
    return dsv41fix::run_fixture<dsv41::block_mxfp4>(
        "mxfp4", 39,
        [](const dsv41::block_mxfp4 *b, float *y, long long nb) { dsv41::dequantize_mxfp4(b, y, nb); },
        [](const dsv41::block_mxfp4 *b, float *y, int64_t k) { dequantize_row_mxfp4(b, y, k); },
        2, const_cast<char **>(argv2), SIZE_MAX, SIZE_MAX, 32,
        // E8M0 byte: keep exponents in 100..139 (2^-27..2^12*0.5); random
        // bytes would hit e=255 (NaN) or overflow products to inf
        [](dsv41::block_mxfp4 &b) { b.e = (uint8_t)(100 + (dsv41fix::rng() % 40)); });
}
