// isa_wo_mr: compiles only the kernels INK_WO_MR_PE / INK_WO_MR_TAIL touch, for IGC_ShaderDumpEnable machine code (the
// tail's mul / xor / add where VC would otherwise fuse a mad, spill counts at MR 2 / 4 / 8) and to check that they
// compile alone. The 2-8-token kernels carry the tail in their own code (no new kernel): xd::dgroupej<2>, <4>, <8>; the
// producers carry the parts' stores: attn_win_fused<3, 3, 2> / <3, 3, 1>, attn_flash_sum's six forms. The one-token
// kernels are listed to compare them with the unpatched build's (their code is meant to be the same). Nothing runs.
#include <cmath>
#include "../../src/xmx_esimd.hpp"
#include "../../src/attn_flash.hpp"
using namespace ink;
__attribute__((noinline))
void isa_wo_mr_probe(sycl::queue &q, xd::EJobs jb, xd::EjTail tl, PeOut pe, int cols, int mst) {
    xd::dgroupej<1, 128, true, true>(q, jb, cols, 1);
    xd::dgroupej<1, 128, true, false>(q, jb, cols, 1);
    xd::dgroupej<2>(q, jb, cols, mst, tl);
    xd::dgroupej<4>(q, jb, cols, mst, tl);
    xd::dgroupej<8>(q, jb, cols, mst, tl);
    xd::wo_q8<false>(q, nullptr, 2304, nullptr, nullptr);
    xd::wo_q8<true>(q, nullptr, 2304, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, 1.0f);
    fz::attn_win_fused<3, 3, 2>(q, nullptr, nullptr, nullptr, nullptr, 16, nullptr, nullptr, 0, 1, 24, 8, 128, 1024, 1024, 1.0f, 0, nullptr,
                                0, nullptr, true, pe);
    fz::attn_win_fused<3, 3, 1>(q, nullptr, nullptr, nullptr, nullptr, 16, nullptr, nullptr, 0, 3, 24, 8, 128, 1024, 1024, 1.0f, 0, nullptr,
                                0, nullptr, true, pe);
    fz::attn_flash_sum(q, nullptr, nullptr, 1, 0, 1, 24, 128, nullptr, nullptr, nullptr, 0, nullptr, 0, 0, nullptr, pe);
}
int main() { return 0; }
