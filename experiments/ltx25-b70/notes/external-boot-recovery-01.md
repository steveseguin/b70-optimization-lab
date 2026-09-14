# External boot recovery and resumed native work

2026-09-14. At resumption, boot identity changed from the recorded faulted boot
`39a36df1-8b22-498e-b74a-28384839a024` to
`8e4b1b65-1c38-47bb-8ca5-e4fd6bbdf94a`. Historical processes95931/96119/102144
were absent, no8188 server listened, approximately123GiB RAM was available and
all four B70 PCI functions/render nodes were present. The agent did not reboot
the computer, reset a driver or change host power/swap/cache settings.

The old fault remained in place throughout the explicit recovery diagnostic.
`scripts/check-external-boot-recovery-01.py` is a one-use diagnostic bound to
the observed new boot and exact old fault hash, not an automatic recovery loop
or general override. It acquired the host/benchmark/four-device locks, required
no container/render owner, checked current-boot kernel faults and memory, then
ran the existing launcher's small copy/compute operation once per card under
Torch2.14.0+xpu with strict determinism. All four passed; its process exited
normally. A subsequent locked passive check confirmed released render nodes
and a clean current-boot journal.

The root operator then moved the old fault byte-for-byte to
`external-boot-recovery-01/historical-FAULT.json` and recorded
`recovery-admission.json` linking its hash, old/new boot, native health receipt
and admission rationale. This resolves only the old admission hold. The
incident's cause remains unproven; a new fault must halt subsequent requests.
The old failed campaign and all its artifacts remain untouched.

## Native decoder gate

With exclusive locks held, the prepared
`scripts/test-na-mask-extent-native.py --device xpu:3` completed10 small mask
and6 small attention cases. All original/candidate/repeated candidate outputs
were byte-exact and finite, for BF16 and F32. Strict deterministic mode was
enabled. The post-exit kernel log was clean and render ownership cleared.
The exact receipt is `na-mask-native-xpu-01.json` in the recovery evidence.
This is the first native qualification of the extent-expression change; it
does not establish full-sized tiling, full-clip correctness, speed or streaming.
Installed Comfy Kitchen source remains unchanged.

## Persistent compiler server

The packet03 copied launcher passed its startup check and then started once as
PID6502, directory `encoder-server-compiler-03`. Its own four-card native
preflight passed, after-import strict determinism was restored, and the identity
endpoint exactly matched the startup file. The queue was empty before the new
campaign. Manifest:
`9ecd5f9863289e00a934c1f4f400582092f37d0ee92035512fc095773ad02980`.

The new [naming-only client](compiler-screen-v2-naming.md) accepts an explicit
campaign name, preserving all original model/source/quality gates. Five stdlib
AST/CLI tests passed. It started `compiler-screen-02`, a bounded nine-request
eager/compiled/restored experiment on native block24 with original control
encoder, nativeBF16,8+3 steps,256x256 and25frames/24fps. Campaign01 is protected.
This note records admission/startup, not the experiment outcome: inspect current
progress/results before any further GPU action. No full-clip or speed result is
claimed merely from starting the server.

External evidence root:
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/external-boot-recovery-01`.
Selected original receipts, server startup identity and compressed journals are
preserved in `data/external-boot-recovery-01/`. The previous handoff commit
`c3225bcc0`, whose first push failed during the faulted boot's DNS failure,
has now pushed successfully.
