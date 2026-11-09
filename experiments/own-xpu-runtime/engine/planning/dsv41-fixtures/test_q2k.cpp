// Differential fixture: independent Q2_K decoder vs reference. See README.md.
#include <cstddef>
#include "q2k_decode.hpp"
#include "test_common.hpp"

extern "C" void dequantize_row_q2_K(const void *x, float *y, int64_t k);

int main(int argc, char **argv) {
    return dsv41fix::run_fixture<dsv41::block_q2_K>(
        "q2_K", 10,
        [](const dsv41::block_q2_K *b, float *y, long long nb) { dsv41::dequantize_q2_K(b, y, nb); },
        [](const dsv41::block_q2_K *b, float *y, int64_t k) { dequantize_row_q2_K(b, y, k); },
        argc, argv, offsetof(dsv41::block_q2_K, d), offsetof(dsv41::block_q2_K, dmin));
}
