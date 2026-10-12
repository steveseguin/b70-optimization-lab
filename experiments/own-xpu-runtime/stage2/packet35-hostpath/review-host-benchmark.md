# CPU mock issue benchmark

The benchmark calls the runtime's actual family submission functions against
an issue-only mock queue. It compares legacy construction/validation/submission
with `Device::begin_capture` followed by repeated `Device::issue`. It does not
run arithmetic, SYCL, a driver or a device, and excludes Engine plan dispatch.
A CPU front end can use fewer native-only split submissions than its device
counterpart. These numbers are host microbenchmarks, not decode speed claims.

| Family | Legacy ns/launch | Prepared ns/launch |
| --- | ---: | ---: |
| dense_r5 | 99.67 | 20.69 |
| experts_r5 | 98.31 | 10.06 |
| p25_gemv | 171.30 | 12.33 |
| p27_gemv | 172.01 | 12.29 |
| p28_gemv | 160.07 | 11.59 |
| p29_gemv | 209.32 | 8.06 |
| p27_input_prepare | 40.84 | 7.39 |
| small_gemv_fusion | 129.08 | 8.79 |
| specialised | 57.89 | 22.20 |
| round2 | 170.03 | 27.79 |
| packet18_parallel | 155.54 | 21.37 |
| combine | 26.58 | 7.60 |
| check | 52.08 | 9.83 |
| commit | 51.92 | 8.83 |

Nine measured iterations follow two warmup iterations, each with 2,048 sites.
The reported values are medians. The operation-type/pointer sequence
matches for all 14 families. The mock consumes bound pointer values but never
reads the small sentinel allocations whose arena metadata supplies production
extents. It therefore uses little anonymous memory even for large matrix shapes.
The mock uses a constant-time RTTI identity pointer in both paths; it does not
add repeated type-name hashing to the legacy side.

There were zero new/malloc/calloc/realloc calls during 294,912 measured prepared
launches. Global scalar, array and aligned `new` overloads and linker wrappers
count the application's allocation calls. Dynamically linked library internals
are not interposed; the mock issue callback makes no such allocation calls.
This is a measured application-path gate, not a claim that the SYCL runtime
allocates nothing internally.

`prepared-host-benchmark.json` contains source, binary and linked-object hashes,
CPU affinity, start load average, compiler flags and resource usage. Variations
in host scheduling remain possible; the result does not support predicting the
native device enqueue cost. The real-plan W2 enqueue loop and family timing
receipt are the device-side measurement prepared for the coordinator.

Reproduce after the host build:

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet35-hostpath/prepared_host_benchmark.py
```

The runner compiles one CPU translation unit, links the current host objects,
runs only the mock binary, and removes its temporary source/object files. It
retains the resulting binary in ignored `build/host-issue/` for its hash receipt.
