// Differential fixture: independent IQ2_XS decoder vs reference. See README.md.
#include "iq2xs_decode.hpp"
#include "test_common.hpp"

extern "C" void dequantize_row_iq2_xs(const void *x, float *y, int64_t k);

int main(int argc, char **argv) {
    return dsv41fix::run_fixture<dsv41::block_iq2_xs>(
        "iq2_xs", 17,
        [](const dsv41::block_iq2_xs *b, float *y, long long nb) { dsv41::dequantize_iq2_xs(b, y, nb); },
        [](const dsv41::block_iq2_xs *b, float *y, int64_t k) { dequantize_row_iq2_xs(b, y, k); },
        argc, argv);
}
