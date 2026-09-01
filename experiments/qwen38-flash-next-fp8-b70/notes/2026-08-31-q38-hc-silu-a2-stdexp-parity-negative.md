# Qwen3.8 Flash-Next HC-SiLU A2 parity negative

Date: 2026-08-31
Status: bounded correctness negative; no timing or endpoint claim

A2 tested the minimal `sycl::exp` to `std::exp` arithmetic correction under the
new health-gated lifecycle. It stopped at the fail-fast BF16 region before the
complete exhaustive, profile, timing, or endpoint phases. The first reported
non-NaN mismatch was:

```text
input_bits=0x41be reference_bits=0x40bd candidate_bits=0x40be
```

The `std::exp` attribution is therefore rejected. This exact HC-SiLU candidate
remains default-off and unpromoted; no speed observation was produced.

The lifecycle close was clean. Four-card compute/free-memory passed before and
after the arm, with postflight minimum free fraction
`0.9907877285184958`; host memory and swap recovered, the bounded journal scan
was empty, and the evidence manifest verifies. This is an arithmetic negative,
not a host or B70 health failure. Under the active policy, it does not consume
the boot and does not require a reboot before independent work.

Evidence is preserved at
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260831-q38-hc-silu-a2-stdexp`.
The structured result is
[`20260831-q38-hc-silu-a2-stdexp-parity-negative.json`](../data/20260831-q38-hc-silu-a2-stdexp-parity-negative.json).
Protected TP4 MTP0 `5.515783 tok/s` and MTP4 `20.727176 tok/s` results are
unchanged.
