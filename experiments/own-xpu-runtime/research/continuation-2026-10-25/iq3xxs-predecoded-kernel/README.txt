Scratch candidate only: canonical source and allocation policy are unchanged.
Host fixture (run after active timing completes):
g++ -std=c++20 -O2 -ffp-contract=off -I/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/src test_host.cpp -o test_host
./test_host
GPU integration: include kernel.hpp and invoke submit<false> on packed weights,
submit<true> on expand(...) bytes, using identical expert IDs and input vectors.
Parent owns SYCL compilation and GPU access. No GPU build or test performed here.
Keep compiler FP settings identical to active engine; never enable fast math.
Production route validation/census remain required; this is a kernel candidate.

SC117 metadata: 34 tensors, each 512 experts x 640 rows x 2560 columns.
Each tensor: 321126400 packed bytes -> 871628800 candidate bytes.
Placement cuts 0/8/21/34/48: tensor counts 4/10/8/12.
Replacement increases memory by 2202009600/5505024000/4404019200/6606028800 bytes.
Must replace packed allocation, or select a budgeted subset. Keeping both can
exceed the conservative 28 GB device floor on the final card.
Historical 60 -> 51.5 us no-grid experiment saves 0.289 ms per 34-call pass;
this candidate also removes parity/index decode but triples traffic. No measured
speed claim. Multiply measured per-pass savings by actual target passes/output.

Standalone GPU comparison (parent owns execution):
/opt/intel/oneapi/compiler/2026.0/bin/icpx -std=gnu++20 -O2 -g0 -fno-fast-math -ffp-contract=off -fsycl -fdenormal-fp-math=ieee -foffload-fp32-prec-div -foffload-fp32-prec-sqrt -I/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/src bench.cpp -Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib -o bench
ONEAPI_DEVICE_SELECTOR=level_zero:0 ./bench
Use the coordinator's selected device index/environment instead of 0 if needed.
Bound: 896 kernel launches, 64 route cases, 409600 bitwise output checks, 6 paired
timing samples alternating order, approximately 1.2 GB weights on host and device.
Host steady-clock times batches then waits; no profiling queue, flush, or graph.
Cooperative 60-second deadline and SIGINT/SIGTERM checks run between drained
batches. This is not a hard wall-clock bound if a device wait stalls. No external
kill wrapper, reset, or retry loop. The previous timeout recommendation was wrong.
Reports measured per-call difference x 34 as target-pass savings, not output speed.
