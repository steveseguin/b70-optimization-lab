// isa_mix: compiles the depth-mix kernels (fz::mix_fused_v<9> and <12>; engine labels mix_norm, mix_out, mix_save) for
// IGC_ShaderDumpEnable machine-code reads (spills, instruction and barrier counts):
//   IGC_ShaderDumpEnable=1 IGC_DumpToCustomDir=<dir> scripts/build.sh isa_mix <out>. Nothing runs.
// The call uses the arguments that both the INK_MIX_FAST fused.hpp and the one before it take, so the same file built
// against a copy of the earlier src/ gives the before / after pair.
#include <cmath>
#include "../../src/fused.hpp"
using namespace ink;
__attribute__((noinline))
sycl::event isa_mix_dispatch(sycl::queue &q, fz::MixF a, size_t ld, float *out, const fz::NormOut *no, int n, int ntok) {
    return fz::mix_fused(q, a, ld, out, no, 1e-6f, n, ntok); // instantiates mix_fused_v<9> and <12>
}
int main() { return 0; }
