# Combined candidate correctness run preparation

This is an additive adaptation of the frozen attention operating coordinator.
`adaptation.patch` retains the exact changes. `prepare.py` materializes the
unchanged original serving adapter and baseline suite with the new binary,
combined allocation ledger and both attention/QKV flags. Old operating sources
remain frozen. The native protocol, RESET, owner cleanup and physical monitor
remain inherited.

One persistent rank pair executes the original two disjoint eight-token warmups
and all twelve unchanged prompt pairs at cap128, retaining original balanced
mode order. Each of the 26 requests receives a full RESET. Every measured arm
must match the original independently audited baseline tokens and complete
target state before the next request; early EOS is retained. Prompt00 target-only
is the first gate. No retry, hard kill or automatic restoration is added.

The combined logical device forecasts are 30,947,490,698 bytes on rank0 and
29,824,495,508 on rank1. Initial available RAM admission adds 382,730,240 bytes
relative to the original baseline (attention94,371,840 plus QKV288,358,400).
The inherited state budget includes the initial blank dump:27 dumps totaling
6,316,056,364 bytes with the metadata allowance, plus the2GiB external reserve.
Root must independently confirm recovered filesystem record capacity before
launch. No archival or pruning is performed by this coordinator.

`python3 -B once.py --plan` is read-only and requires the completed native build,
actual selector CPU proof, frozen Q6 arithmetic and actual three-case micro,
unchanged attention scale authority and source-bound independent review.
Root creates/adopts the fixed private control directory and owns `--run PLAN`:

- unit:`gsq-attention-qkv-p33-a.service`
- control:`/home/steve/own-xpu-runtime-results/gsq-attention-qkv-p33-a.control`
- evidence:`/mnt/usb-models/own-xpu-runtime-results/gsq-attention-qkv-p33-a`

Full target equality is a qualification gate, not a model-quality evaluation.
Timings remain descriptive separate-session observations; there is no fair
end-to-end speed claim or promotion from this run alone.
