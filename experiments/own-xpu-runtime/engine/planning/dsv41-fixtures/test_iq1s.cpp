// Differential fixture: independent IQ1_S decoder vs reference. See README.md.
#include "iq1s_decode.hpp"
#include "test_common.hpp"

extern "C" void dequantize_row_iq1_s(const void *x, float *y, int64_t k);

int main(int argc, char **argv) {
    return dsv41fix::run_fixture<dsv41::block_iq1_s>(
        "iq1_s", 19,
        [](const dsv41::block_iq1_s *b, float *y, long long nb) { dsv41::dequantize_iq1_s(b, y, nb); },
        [](const dsv41::block_iq1_s *b, float *y, int64_t k) { dequantize_row_iq1_s(b, y, k); },
        argc, argv);
}
