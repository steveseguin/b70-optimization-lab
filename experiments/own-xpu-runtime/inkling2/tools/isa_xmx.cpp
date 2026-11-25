// isa_xmx: compiles only the matrix-engine expert kernel (xmx_moe.hpp) so its machine code can be dumped and read:
// IGC_ShaderDumpEnable=1 IGC_DumpToCustomDir=<dir> scripts/build.sh isa_xmx <out>. Nothing runs.
#include "../src/xmx_moe.hpp"

int main(int argc, char **argv) {
    using namespace ink;
    if (argc < 6) { std::fprintf(stderr, "isa_xmx: compile-only\n"); return 0; }
    sycl::queue q;
    MoeGroups g;
    xm::Super st;
    st.sm = 4;
    xm::prod2<4, 4, 4, 0>(q, nullptr, 0, 2304, 1152, 72, g, st, 1, nullptr, xm::ActOp{}, nullptr, nullptr, 0);
    xm::prod2<4, 4, 8, 0>(q, nullptr, 0, 2304, 1152, 72, g, st, 1, nullptr, xm::ActOp{}, nullptr, nullptr, 0);
    return 0;
}
