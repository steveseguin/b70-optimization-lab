# Evidence-reader review

Read-only reviewer: `/root/p58y_readonly_review`, 2026-10-18.
The reviewer did not modify sources or launch a device.

Three findings were fixed before the analysis milestone:

- Use Decimal ratio comparisons at the exact +3% gain/drift boundary.
- Rewrite Markdown as well as JSON on refusal, so an invalid rerun cannot
  leave a previous successful ranking visible.
- Require the exact eight predecessor receipts, then verify hashes, clean
  stages, boot/build identity, order and the stored pause timestamp.

Each has a synthetic regression test. The reviewer reread the fixes and
reported no remaining concrete blocker in the reviewed changes. The review
also checked the 99-interval selection, class-balanced metric and treatment
of unavailable miss/device timing. Device data and causal validation remain
pending; this review supplies neither.
