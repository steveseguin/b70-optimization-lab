// isa_xe: compiles only the ESIMD kernels (xmx_esimd.hpp) the engine uses, for IGC_ShaderDumpEnable machine-code counts
// and to check that they compile alone (IGC 2026.1 crashed on one form). Nothing runs.
#include "../../src/xmx_esimd.hpp"
using namespace ink;
int main(int argc, char **argv) {
    if (argc > 1) return 0;
    Device dev(1);
    xd::EJobs jb;
    xd::dgroupej<1, 128, true, true>(dev.q, jb, 2304, 1);
    xd::dgroupej<2>(dev.q, jb, 2304, 2);
    xd::dgroupej<4>(dev.q, jb, 2304, 3);
    xd::dgroupej<8>(dev.q, jb, 2304, 5);
    return 0;
}
