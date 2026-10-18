# Packet58f artifact retention

The copied 4,194,304-byte rope.bf16 is required by the source-relative native
loader. Restore from frozen packet58e/rope.bf16 and verify SHA-256
92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390.
It is a runtime input, not a generated cache.

Source and evidence copies preserve frozen 58e and the failed 58c history.
parent58e-source-manifest.json identifies the exact copied source files.
evidence/58c-supervisor retains the raw samples used for the conservative seed;
their source-manifest.json pins their bytes. No historical evidence was removed.

build/ is ignored, regenerable compilation scratch, bounded below 1.5 GB.
build.py uses installed compilers and retained local fixture inputs, including
packet45-merged3/build/fusion-rope.hpp. This is not a clean-build public recipe.
Only this packet's own temporary CPU fixture directories are removed by tests.
