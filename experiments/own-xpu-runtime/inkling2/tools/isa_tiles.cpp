// isa_tiles: compiles only the hot prompt kernels (NVFP4 expert tiles, attention tiles) so their machine code can be
// dumped and read: IGC_ShaderDumpEnable=1 IGC_DumpToCustomDir=<dir> scripts/build.sh isa_tiles <out>. Nothing runs.
#include <cmath>
#include "../src/tok_tiles.hpp"
#include "../src/fused.hpp"
#include "../src/attn_tiles.hpp"

int main(int argc, char **argv) {
    using namespace ink;
    if (argc < 2) { std::fprintf(stderr, "isa_tiles: compile-only (pass any argument to launch nothing)\n"); return 0; }
    sycl::queue q;
    const uint8_t *A = nullptr; float *f = nullptr; const float *cf = nullptr; const sycl::half *h = nullptr;
    MoeGroups g;
    SituOp so{nullptr, nullptr, 8.0f, 4.0f, nullptr, 1152};
    sycl::nd_range<2> nr(sycl::range<2>(1, 16), sycl::range<2>(1, 16));
    if (argc > 5) { // never true in practice: keeps the kernels in the binary
        q.submit([&](sycl::handler &hd) {
            sycl::local_accessor<float, 1> la(NV4_LUT, hd);
            hd.parallel_for(nr, SlotPairG<pl::NVFP4P, SituOp, 2, true, true>{A, A, 0, 0, 1152, 2304, g, cf, so, f, 1, la});
        });
        q.submit([&](sycl::handler &hd) {
            sycl::local_accessor<float, 1> la(NV4_LUT, hd);
            hd.parallel_for(nr, SlotPairG2<pl::NVFP4P, SituOp, 2, true, true, true, false>{{}, A, A, 0, 0, 1152, 2304, g, cf, so, f, 1, la});
        });
        q.submit([&](sycl::handler &hd) { // the engine's gate|up (two tiles, 4 rows)
            sycl::local_accessor<float, 1> la(NV4_LUT, hd);
            hd.parallel_for(nr, SlotPairG2<pl::NVFP4P, SituOp, 2, true, true, false, false>{{}, A, A, 0, 0, 1152, 2304, g, cf, so, f, 1, la});
        });
        q.submit([&](sycl::handler &hd) { // gate|up 8 rows (NG 4), one tile at a time
            sycl::local_accessor<float, 1> la(NV4_LUT, hd);
            hd.parallel_for(nr, SlotPairG2<pl::NVFP4P, SituOp, 4, true, true, false, false>{{}, A, A, 0, 0, 1152, 2304, g, cf, so, f, 1, la});
        });
        q.submit([&](sycl::handler &hd) { // the engine's down (4 rows, tables)
            sycl::local_accessor<float, 1> la(NV4_LUT, hd);
            hd.parallel_for(nr, SlotRowsG2<pl::NVFP4P, 4, false, false, true>{{}, A, 0, 0, 2304, 1152, g, cf, f, 2304, 1, la});
        });
        q.parallel_for(nr, SlotRowsG<pl::NVFP4P, 2>{A, 0, 0, 2304, 1152, g, cf, f, 2304, 1});
        fz::attn_scores_tile<8, 3, 4>(q, cf, h, cf, cf, 16, 0, 64, 24, 8, 128, 1024, 0, 1.0f, f, 1024);
        fz::attn_pv_tile_part<4, 3, 4>(q, cf, 1024, h, 1024, 0, 64, 24, 8, 128, 0, f, 8);
    }
    return 0;
}
