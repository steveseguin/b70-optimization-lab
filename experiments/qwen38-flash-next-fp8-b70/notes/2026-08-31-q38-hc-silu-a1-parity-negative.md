# Qwen3.8 Flash-Next HC-SiLU A1 parity negative

Date: 2026-08-31
Status: bounded correctness negative; no endpoint or timing claim

A1 stopped at the first exhaustive-BF16 mismatch, exactly as preregistered.
Chunk `0x4100–0x423f` contained one non-NaN output bit-pattern mismatch between
the native candidate and the frozen Torch reference. No dispatch, profile,
timing, or full-model endpoint phase followed.

The failure is arithmetic rather than a device/runtime fault. All four B70s
passed the bounded exact-compute and free-memory postflight, the minimum free
fraction was `0.9907876089003552`, and the captured kernel-journal fault-match
file is empty. Host memory and swap also recovered above their frozen floors.

Source audit identified one precise candidate mechanism in the implementation
contract; A2 is the frozen test of that attribution.
This environment runs Torch `2.11.0+xpu` at Git
`70d99e998b4955e0049d13a98d77ae1b14db1f45`, which pins torch-xpu-ops
`de4f698b84142e660d5238e02e067182e39641ca`. Its float sigmoid uses
`one / (one + std::exp(-a))`; A1 used `sycl::exp`. A2 therefore changes only
that expression and the required `<cmath>` include. It does not change the
dispatch contract, queue, launch geometry, scaling, multiplication, BF16
conversion, or compiler policy.

Evidence is preserved under
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260831-q38-hc-silu-a1`.
The structured result is
`data/20260831-q38-hc-silu-a1-parity-negative.json`. A1 remains unpromoted,
the current boot remains consumed by its attempted state, and the protected
TP4 MTP0 `5.515783 tok/s` and MTP4 `20.727176 tok/s` results are unchanged.
