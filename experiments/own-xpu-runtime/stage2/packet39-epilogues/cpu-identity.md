# CPU identity evidence

No device ran. `cpu_gates.py` builds `cpu_gate.cpp` with GCC and icpx, placing the same precise floating-point flags on compilation and linking, then starts each executable twice in fresh processes. Each process performs 360 whole-chain fixtures, 2,600 required finite/control byte comparisons, 648 separate nonfinite comparisons, and 1,800 rejected hostile bindings. Totals: 1,440 fixtures, 10,400 required byte comparisons, 2,592 nonfinite comparisons and 7,200 guard rejections. All required comparisons and guard rejections pass. The finite output hash is `f6cefd04029194fc` in all four processes. This FNV64 hash is a repeat fingerprint, not a cryptographic identity; binary/source SHA-256 values are in `cpu-gates.json`.

The overall exact gate is **false** because GCC records 18 nonfinite mismatches per repeat. They are retained without NaN tolerance, replacement or canonicalization. icpx records zero for the same fixtures. The candidate's nonfinite bytes repeat across both compilers; the selected unfused activation reference has different NaN operand propagation under GCC. This does not certify all-input exactness. The inherited finite contract and failed nonfinite diagnostics remain separate, as in packet29 `NONFINITE-GEMV.md`.

| Kind (`Kind` integer) | Format (GGUF type), K, split | Required checks per process | Nonfinite mismatches GCC / icpx |
|---|---|---:|---:|
| Expert gate/up activation (0) | IQ2_S (22), 2560, 1 | 216 | 6 / 0 |
| Expert gate/up activation (0) | IQ3_S (21), 2560, 1 | 216 | 6 / 0 |
| Expert down status (1) | IQ4_NL (20), 640, 1 | 216 | 0 / 0 |
| HC low activation (2) | Q8_0 (8), 10240, 4 | 216 | 0 / 0 |
| Shared up activation (3) | Q6_K (14), 2560, 4 | 216 | 3 / 0 |
| Shared up activation (3) | Q8_0 (8), 2560, 1 | 216 | 3 / 0 |
| Attention combine (4) | Q6_K (14), 6144, 4 | 216 | 0 / 0 |
| Shared down blend/combine (5) | Q8_0 (8), 640, 1 | 216 | 0 / 0 |
| GDN QKV convolution (6) | Q6_K (14), 2560, 1 | 216 | 0 / 0 |
| GDN QKV convolution (6) | Q8_0 (8), 2560, 1 | 216 | 0 / 0 |
| Paired expert checks only (7) | IQ2_S (22), 2560, 1 | 216 | 0 / 0 |
| Paired expert checks only (7) | IQ3_S (21), 2560, 1 | 216 | 0 / 0 |

Eight additional checks compare the BF16 boundary functions at rounding ties, signed zero, infinities and NaN payloads. Rows 1, 3 and 17 test odd row tails. K remains a complete admitted format-block length; the runtime does not admit odd quantized K. Scenarios cover valid routes, invalid expert IDs, partial routes, overflowing row offsets, inactive execution, preexisting sticky error 7, negative position and position equal to capacity. Invalid routes are strict required cases even though their raw GEMV output is canonical NaN. An invalid route suppresses the whole activation tensor, including valid slots. Separate poisoned arithmetic fixtures supply NaN payloads and opposing infinities on valid routes.

Required observables are raw GEMV output, paired output, epilogue output, four residual streams, convolution history, both status buffers, sticky error and active flag. The unfused CPU tails invoke original packet29 `ng::cpu` for activations and convolution, and original `Core` equations for shared blend and stream combine. GEMV bodies are the imported measured row bodies with their unchanged adjacent-32-lane tree, or unchanged four-part tree with `(p0+p1)+(p2+p3)`. The selected HC/shared rows4 dispatch performs this finish inside its existing work-group; attention retains its separate finish kernel. The two fixture arms share the GEMV lane emulator; these tests independently check the inserted tail against original tail equations, not an independent requalification of packet28/33 GEMV arithmetic. The host full-model token-plan gate is separately recorded; these fixtures do not replace it.

The native binding guard rejects null/misaligned operands, bad row stride, 32-bit source-offset overflow, bad shape/count, missing or invalid context capacity, and writable alias overlap. In-place residual streams and convolution history are intentional; all other writes are disjoint from GEMV read operands and each other. Allocation extents remain the caller's responsibility. The `one` scalar for shared mixture is the runtime's immutable `1.f` buffer.

The activation-fused routed native epilogue validates all routes with a subgroup vote before any row can emit activation. It does not scan/reduce serially or add local storage/barriers. Sticky errors use relaxed atomic compare-exchange from 0 to 1, so inactive execution and prior nonzero errors retain their exact bytes. The status-only down and paired-expert candidates need no global vote: each invalid slot's row zero can set sticky directly, and no subsequent activation output is written inside those kernels. Split-four epilogues attach to the existing in-kernel rows4 finish for HC/shared projections, or the pre-existing separate finish for attention; their GEMV partial sums and rounding remain unchanged. Shared gate/up uses the actual selected p28 dense body and rows4 geometry; GDN uses the measured p33 dense segment body.

Rebuild and repeat with:

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet39-epilogues/cpu_gates.py
```

The script exits successfully after recording a completed finite gate and separate nonfinite failures. Read `finite_and_control_passed`, `passed`, and the per-class diagnostic counts independently; a zero script exit is not an all-input identity claim.
