# Correction to the receipts in this directory

These files are copied verbatim from `/mnt/fast-ai/bench-results/fp8-stock-gdn-20260919/`
(2026-09-19 14:42-15:04 EDT). Two of them carry a conclusion the data does not support, and are
kept unedited because they are receipts:

* `campaign.log`, last line before the fault:
  *"the `_xpu_C` rebuild moved the no-MTP outputs; candidate fix is an r313 rebuild against the
  pinned CUTLASS revision 87f6850 (variant-c toolchain), then the full acceptance again"*
* `verdict.json`: `"verdict": "DIFFERS"` with `"exact": "0/12"`

**The measurements are correct; that conclusion is not.** The stock arm differed on all 12
prompts *and* ran at 12.219 tok/s against the lab arm's 19.236 -- the lab arm is 57 % faster. A
ULP-level rounding difference in one kernel cannot move decode speed by half, so the two arms did
not run the same FP8 GEMM kernels at all: the lab images carry the oneDNN W8A16 fixed-K patches
(r137a / r137b / r221) and the r309 shapes, and the pristine `vllm/vllm-openai-xpu` image does
not. The comparison is therefore **not comparable** and says nothing about the GDN / `_xpu_C`
rebuild question, in either direction. No r313 rebuild follows from it.

`run-20260918-fp8-stock-gdn-check.py` was corrected the same day: an all-prompts-differ result
with a speed gap above 20 % now reports `NOT COMPARABLE: different GEMM kernels` and prints what
a real GDN isolation would need. Re-running the campaign would produce the corrected verdict from
the same numbers.

The lab's lossless definition is unaffected: every shipped gate compares a candidate against a
reference produced by the *same image*.

Full write-up: [`../../notes/2026-09-16-fp8-review-findings.md`](../../notes/2026-09-16-fp8-review-findings.md),
section "Stock-vs-lab GDN check (September 19)".

`FAULT-HALT.json`, `service-state.json`, `service-server.log` and `service-kernel.log` belong to
the *next* step, the two-card service restore that faulted at 15:03:46 -- see
[`../../notes/2026-09-19-gpu-fault-service-start.md`](../../notes/2026-09-19-gpu-fault-service-start.md).
