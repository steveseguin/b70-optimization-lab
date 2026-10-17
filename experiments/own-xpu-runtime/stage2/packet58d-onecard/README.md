# Packet58d: repair post-load pinned-slab lifetimes

Copied from frozen packet58c. KD loaded all 48 layers, then rejected
`cache-table-staging`: its pinned-slab category requires transfer lifetime,
but the caller requested process lifetime. `cache-route-readback` had the
same error farther along the path. Both now request transfer lifetime.
The category plan and strict arena check stay unchanged. Errors now identify
the label, category and requested/planned lifetimes.

[Allocation audit](ALLOCATION-AUDIT.md) lists every engine allocation call site
and the complete three-allocation post-load sequence. KV, scratch, workspace
and the output head are allocated before the final weight upload.

The CPU test executes the actual engine cache setup with the full KD metadata,
144 expert-bank handles and 48 route sources, using bounded mock backing.
It checks both old requests fail, the three corrected requests succeed, all
tables publish, and teardown drains cleanly. It does not load model payloads.
The [source-bound gate](evidence/postload-allocation-cpu.json) is mandatory in
the seal and queue plan. Host and device artifacts are freshly compiled on CPU;
no device binary is executed during preparation.

Memory admission, the memory fence, pinned accounting, BF16 KV and arithmetic
`iq3-p49-split32-v1` are unchanged. Device correctness, fit and speed remain
pending. No services or host settings are changed.

[CPU build commands](CPU-BUILD.md), [coordinator queue](WINDOW.md),
[closeout](CPU-PREPARATION-CLOSEOUT.md),
[task note](../../../../notes/2026-10-17-own-runtime-packet58d.md).

Copied older evidence retains its original identity. In particular,
`evidence/inherited58c-unchanged-native.json` describes the previous wrapper-only
repair, not this rebuild. The original packet58c and its runtime evidence remain
untouched; [failure copies and hashes](evidence/58c-kd/source-manifest.json) retain
the relevant failure receipts in this packet too.
