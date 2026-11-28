// Compile-only smoke gate for both advertised activation builds; no GPU execution.
// From the engine directory (requires the native oneAPI/SYCL headers):
// icpx -fsycl -std=c++20 -fsyntax-only -I src -I planning/dsv41-fixtures \
//   planning/dsv41-fixtures/test_backend_v41_compile.cpp
// icpx -fsycl -std=c++20 -fsyntax-only -DOWN41_ACT_BF16 \
//   -I src -I planning/dsv41-fixtures planning/dsv41-fixtures/test_backend_v41_compile.cpp
#include "stage2/packet3/backend/backend_sycl_v41.hpp"

int main() { return 0; }
