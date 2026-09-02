# Qwen3.8 Flash-Next HC gate-mix exact-staged A1: XPU exactness negative (2026-09-02)

Date: 2026-09-02 10:03 EDT, boot `67848b88-c7c7-452a-bef1-124364a300b9`
(BIOS 2.4a, root SSD Gen4 x4 under the validated clearance)
Status: negative; the candidate is rejected at the frozen exactness gate and
does not advance

## What ran

`tools/run-q38-hc-gate-mix-exact-staged-a1.sh` with the explicit one-B70
authorization. Every admission gate passed: clearance receipt
`6746f060...` validated live, four-B70 topology, `level_zero:0` selected with
one visible XPU, vLLM `cbc3cb58...`, Python `3.12.13`, Torch `2.11.0+xpu`,
immutable staging of the gate (`3af1fd48...`) and core (`02989e1f...`), zero
corrected-event baseline. The single C-A-A-C gate invocation then failed
closed at its first exactness assertion:

```
AssertionError: eager candidate: output differs at call 0; max_abs=0.00048828125
```

`gate.exit-code` 1, `final-health.json` `failed_closed` with
`failure_reason = component gate failed with exit 1`, corrected-event and
root-port deltas 0. Evidence:
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-hc-gate-mix-exact-staged-a1/`.

## Interpretation

The candidate kept Torch's sigmoid, multiply, and mean and changed only the
staging: BF16 state promoted inside the FP32 multiply and the final BF16
conversion performed by a BF16 `out=` tensor on the FP32 mean. On CPU that
was byte-exact across all 65,280 finite BF16 state encodings, 15 seed/scale
cells, and 100 changing inputs. On XPU the very first eager call already
differs by one BF16 unit in the last place at the output magnitude
(`2^-11`), so the XPU implementation of the promoted multiply and/or the
`out=`-typed reduction does not round identically to the explicit
cast-then-compute reference. CPU parity is therefore not transferable
evidence for this class of change on this backend; the lab's XPU exactness
gate did its job.

No timing was collected and no production path changed. The candidate's
CPU packet, runner, and tests remain tracked as the record of the attempt.
Any future gate-mix work must either keep the explicit FP32 materializations
or prove exactness with an XPU-side kernel-level argument first; the
whole-Triton replacement was already rejected earlier for a `0.0078125`
difference, so both known shortcuts on this path are now closed.
