// isa_xmx: compiles only the matrix-engine expert kernel (xmx_moe.hpp) so its machine code can be dumped and read:
// IGC_ShaderDumpEnable=1 IGC_DumpToCustomDir=<dir> scripts/build.sh isa_xmx <out>. Nothing runs.
#include "../../src/xmx_moe.hpp"

int main(int argc, char **argv) {
    using namespace ink;
    if (argc < 6) { std::fprintf(stderr, "isa_xmx: compile-only\n"); return 0; }
    sycl::queue q;
    MoeGroups g;
    xm::Super st;
    st.sm = 4;
    // ISA_ONE: one kernel only (dumps are 1.5-4 GB per build with all of them)
    if (argc > 6) {
        xm::prod2<4, 4, 4, 0>(q, nullptr, 0, 2304, 1152, 72, g, st, 1, nullptr, xm::ActOp{}, nullptr, nullptr, 0);
        xm::small3<1, 0>(q, nullptr, 0, 2304, 1152, 2304, 72, g, 8, nullptr, 2304, true, nullptr);
        xm::small3<1, 1>(q, nullptr, 0, 1152, 1152, 2304, 72, g, 8, nullptr, 1152, false, nullptr);
    }
    // one token, one sub-group over all inputs, 8 steps of cache prefetch (gate|up)
    xm::full_prod<1, 0, 4, 2, 128, 8, 1>(q, nullptr, 0, 2304, 1152, 2304, g, 8, nullptr, 2304, true, xm::ActOp{}, nullptr, 1152, nullptr, 0);
    return 0;
}
