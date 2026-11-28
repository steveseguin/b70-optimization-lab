// isa_xd: compiles only the one-token dense matrix-engine kernel (xmx_dense.hpp XDGroupC) so its machine code can be
// dumped and read: IGC_ShaderDumpEnable=1 IGC_DumpToCustomDir=<dir> scripts/build.sh isa_xd <out>. Nothing runs.
#include "../../src/xmx_dense.hpp"

int main(int argc, char **argv) {
    using namespace ink;
    if (argc < 6) { std::fprintf(stderr, "isa_xd: compile-only\n"); return 0; }
    sycl::queue q;
    xd::dgroupc<1, 128, 0, 4>(q, nullptr, 3072, 2304, nullptr, 2304, 1, nullptr, 3072, nullptr);
    return 0;
}
