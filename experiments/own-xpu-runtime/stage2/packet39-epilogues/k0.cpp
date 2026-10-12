// K0 and G4 deliberately use a byte-identical executable image.
// build_native.py compiles timing.cpp once and copies p39-timing to p39-k0.
// The coordinator wrapper passes --compile-smoke for K0; timing.cpp then builds
// the same executable bundles and returns without submitting any kernels.
// This file is documentation only, not a separately compiled translation unit.
