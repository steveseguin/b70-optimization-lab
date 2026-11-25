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
    // small steps (XSmall3, one row): gate|up and down
    xm::small3<1, 0>(q, nullptr, 0, 2304, 1152, 2304, 72, g, 8, nullptr, 2304, true, nullptr);
    xm::small3<1, 1>(q, nullptr, 0, 1152, 1152, 2304, 72, g, 8, nullptr, 1152, false, nullptr);
    return 0;
}
