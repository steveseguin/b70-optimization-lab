# Packet118 boundaries

- Exactly two compositions. No ancestor Cartesian sweep.
- N=80,128 is fixed by packet114's non-benchmark preregistration. No retuning.
- Smoke all twelve cold 64-token prompts before composite execution.
- Composite control is packet103 bundle5, not bundle6.
- Both lanes must beat both controls by at least 1.0%; identical selections
  cannot establish a gain. All target tokens must match iq3-p49-split32-v1.
- Different prefix selections may have different acceptance; repeats of one
  selection must remain deterministic. Report acceptance separately.
- Never import resource-setting CPU code into a device job. Both native exec
  boundaries require unlimited address space and unchanged inherited limits.
- Keep the target verifier and BF16 KV unchanged. No new head allocation.
- The private draft-prefix accessor cannot be called from a shape fixture;
  check the runtime's emitted prefix receipt and actual allocation census.
- No CPU pass or 64/128-token screen is a strict512 promotion claim.

[CPU closeout](CPU-PREPARATION-CLOSEOUT.md).
