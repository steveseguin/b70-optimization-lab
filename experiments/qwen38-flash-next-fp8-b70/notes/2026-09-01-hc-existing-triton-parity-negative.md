# Qwen3.8 Flash-Next FP8 existing HC Triton parity result

Date: 2026-09-01
Status: component speed positive; exactness negative

The Qwen4Exp HC module currently uses multi-operation Torch fallbacks on XPU
even though Triton implementations exist for its grouped norm, SiLU, gate mix,
combine, and combine-norm stages. Direct M1 screens showed large isolated
latency reductions, ranging from `60.240%` to `90.301%`.

Those timings are not promotable. The stronger parity ladder found that the
candidate SiLU differs from Torch for BF16 input bits `0x41be` (`0x40bd`
versus `0x40be` output), while randomized production-shaped gate-mix and
grouped-norm inputs differ by as much as `0.0078125`. Combine and combine-norm
had already failed the initial seed. Intel libdevice `exp` and `torch.compile`
did not restore exactness.

The temporary opt-in dispatch was reverted completely; the vLLM tree is clean
and no model or protected result changed. This closes direct substitution of
the existing kernels under the lane's bit-exact rule. A future implementation
would need to reproduce the Torch arithmetic order and rounding rather than
merely call the existing fast path.

Structured result:
[`../data/20260901-hc-existing-triton-parity-negative.json`](../data/20260901-hc-existing-triton-parity-negative.json).
