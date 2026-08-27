# Flash-Next TP4 MTP1 exact-recurrent configured-512 preregistration

Date: 2026-08-27

## Reason and preservation boundary

The unchanged MTP1 attempt 2 proved TP4 fit, a healthy API, complete responses,
and positive speculative acceptance, but failed exact MTP0 output parity before
timing. Its quarantined receipt is
`experiments/qwen38-flash-next-fp8-b70/data/20260827-tp4-mtp1-512-attempt2-result.json`.
This follow-up tests one mechanism-specific correction. It does not replace or
lower any MTP0 result, and a failed arm cannot produce a speed claim.

The preserved XPU component already contains an exact recurrent-state path,
but its safety gate and loop were fixed to four verifier rows. MTP1 produces
two verifier rows and two non-prefix state columns. Kernel commit
`ad25aa9f69a2171612b9c6b83dfa82c69559f9e4` changes only the positive row-count
gate and loop bound while retaining the one-request restriction. It does not
change target-only execution. The older scratch-zeroing experiment is
deliberately excluded because later evidence rejected its original attribution;
all scratch used by this two-row exact path is written before read.

Durable source delta:
`patches/qwen38-flash-next-fp8-b70/vllm-xpu-kernels/0005-Generalize-exact-GDN-replay-to-MTP-row-count.patch`
(SHA-256 `7cbadf00a334404507ea730ea8281db203d4de7613785b599aa7f9800d523a46`).

## Frozen attempt-3 identity

- the same model revision, vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`,
  TP4/EP4, eager graph-off settings, selective placement, 192-MiB cache,
  configured maximum 512, and MTP1 settings as attempt 2;
- kernel source `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- candidate runtime
  `/mnt/usb-models/qwen38-build/runtime-mtp1-exact-ad25aa9-b70`;
- `VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1` and
  `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1` are the only runtime-axis changes;
- no prefix-base, completion-barrier, graph, diagnostic-trace, placement,
  cache, precision, or scheduling change.

Launcher:
`experiments/qwen38-flash-next-fp8-b70/tools/launch-tp4-ep4-eager-mtp1-exact-512.sh`.
It must validate the candidate binary manifest and exactly one exact-mode
marker from each rank.

## Gates

1. Before endpoint launch, require the production-shape direct component gate
   at MTP1 row count 2 with two-call reuse/history and bit-exact comparison,
   plus the established four-row regression gate. A component failure stops
   the arm.
2. Require the same four-card fit, healthy API, complete responses, positive
   accepted/drafted counters, and cache-zero observations as attempt 2.
3. Run the seven short cases, fixed-set repeat16, and small needle against the
   accepted MTP0 quality JSON. Every baseline comparison must pass. The known
   inherited strict 5/7 boundary is acceptable only when the normalized outputs
   and hashes exactly match MTP0.
4. Only after parity, run the three frozen p128/o256/c1 rows. Require exact
   prompt/completion usage, nonempty text, the target output hash
   `5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0`,
   and positive MTP engagement. Report the median separately from the MTP0
   `5.221849709 tok/s` value; never supersede MTP0 merely because MTP1 is valid.
5. Preserve all raw artifacts and stop normally. If parity fails again, close
   MTP1/512 as quarantined under this design and publish no speed point.
