# R176: GDN state-slot probe on the depth-2 phantom pass

Date: 2026-09-03 18:03-18:10 EDT, boot 88f0984f (clean). Image `qwen38-fp8-mtp2-state-slot-probe-r176`
(`sha256:85c287a7...`; its `_xpu_ops.py` is `4a996f86...`, the R176 logging block on R171, verified by diff; the
first attempt at 17:42 aborted on the R156 hash in the chain script). Results:
`/mnt/fast-ai/bench-results/qwen38-fp8-r156-mtp2-phantom-state-slot-20260903-r176/query-mtp1/` (server.log has
36,678 `R176` lines; probe active for layer 0 and batches of <= 4 sequences).

## Pass result

Same as R165/R167/R178: row 32 (`cache-c032`, 33rd request) starts `[60, 271, 3833]`, 63/64 vs the MTP0 oracle.
The probe did not perturb the phantom.

## What the layer-0 GDN kernel received (TP0 and TP1 agree on indices)

- Every prefill after the first arrives with `has_initial_state=[False]` and a **non-zero** conv/ssm page:
  abs-sums of order 1.6e4 (conv) and 0.5e6-1.4e6 (ssm) on every one of the 63 later requests. Only request 1
  saw a zero page. So Mamba/GDN pages are never zeroed on this lane (confirms the reading of `KVBlockZeroer`).
- The main state page alternates between block 1 and block 10 from request to request; each request's decode
  steps run with spec pages (10, 9, 8) or (1, 0, ...) in `spec_state`, `num_accepted_tokens` 1-3.
- Request 32 (`evidence-c031`) ran on pages 10/9/8 to its end; request 33 (`cache-c032`) prefilled on page 1,
  whose previous occupant was request 31, not request 32. The discarded async extra step of request 32 wrote pages
  10/9/8. The page handed to the phantom request was therefore not written by the discarded step.
- The stale content on page 1 at request 33's prefill (conv 16626, ssm 1.10e6 on TP0) is in the same range as
  every other request's stale page. Nothing abnormal in magnitude at layer 0.

## Reading

Stale GDN state is universal on this lane, and 62 of 63 stale-page prefills produce oracle-exact output, so "a
recycled unzeroed page" is not sufficient for the phantom, and the page that reaches request 33 was not the one
the discarded step wrote. Two possibilities remain, and R180 (zero the actual Mamba pages on allocation)
separates them: if the phantom vanishes, the XPU GDN prefill reads the initial state despite
`has_initial_state=False` under a condition that only request 33's history meets (then the kernel flag handling
is the bug, and R180 is a workaround); if it persists, the stale state page is not the source and the async
extra step's effect must be on something else that request 33 inherits (attention pages before/after the zeroer
runs, the draft head's scratch, or the async-step token bookkeeping), and the next probe must log those.
