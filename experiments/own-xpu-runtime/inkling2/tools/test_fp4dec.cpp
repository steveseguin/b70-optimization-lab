// test_fp4dec: the matrix-engine kernels' NVFP4 decode (xm::decode_raw: an E2M1 code moved into a half, codes 0, 1, 8
// and 9 on half subnormals, converted on the card, times the UE4M3 scale x 2^15, top 16 bits) against the CPU
// (fp4_int(c) x ue4m3_bits(scale), exact): every code at every one of the 16 places x all 256 scale bytes.
// Reports value mismatches and zero-sign differences separately (the card writes -0 for code 8; formats.hpp's int
// product gives +0).   test_fp4dec <card>
#include <cstdio>
#include <vector>
#include "../src/xmx_moe.hpp"

using namespace ink;

int main(int argc, char **argv) {
    const int card = argc > 1 ? std::atoi(argv[1]) : 3;
    auto devs = sycl::device::get_devices(sycl::info::device_type::gpu);
    sycl::queue q(devs.at(card));
    uint32_t *o = sycl::malloc_device<uint32_t>(256 * 8 * 16, q);
    // lane ln, place i: code (ln + i) & 15; byte i = place i's code | place (8 + i)'s code << 4
    q.parallel_for(sycl::nd_range<1>(256 * 16, 16), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(16)]] {
         const int sc = (int)it.get_group(0), ln = (int)it.get_local_id(0);
         uint64_t cw = 0;
         for (int i = 0; i < 8; ++i) {
             const uint64_t lo = (uint64_t)((ln + i) & 15), hi = (uint64_t)((ln + 8 + i) & 15);
             cw |= (lo | hi << 4) << (8 * i);
         }
         xm::decode_raw(xm::Raw{cw, (uint32_t)sc}, o + (size_t)sc * 128 + ln, 16);
     }).wait();
    std::vector<uint32_t> h(256 * 128);
    q.memcpy(h.data(), o, h.size() * 4).wait();
    long bad = 0, zsign = 0, n = 0;
    for (int sc = 0; sc < 256; ++sc)
        for (int ln = 0; ln < 16; ++ln)
            for (int j = 0; j < 8; ++j) {
                const uint32_t w = h[(size_t)sc * 128 + j * 16 + ln];
                for (int hlf = 0; hlf < 2; ++hlf) {
                    const int place = 2 * j + hlf, c = (ln + place) & 15;
                    const float ref = (float)pl::fp4_int(c) * pl::ue4m3_bits((uint8_t)sc);
                    uint32_t rb;
                    std::memcpy(&rb, &ref, 4);
                    const uint16_t want = (uint16_t)(rb >> 16), got = (uint16_t)(hlf ? w >> 16 : w & 0xffff);
                    ++n;
                    if (want == got) continue;
                    if ((want & 0x7fff) == 0 && (got & 0x7fff) == 0) { ++zsign; continue; }
                    if (bad < 8) std::printf("  scale 0x%02x code %d: card 0x%04x cpu 0x%04x\n", sc, c, got, want);
                    ++bad;
                }
            }
    std::printf("%ld values: %ld differ, %ld only in the sign of zero\n", n, bad, zsign);
    return bad != 0;
}
