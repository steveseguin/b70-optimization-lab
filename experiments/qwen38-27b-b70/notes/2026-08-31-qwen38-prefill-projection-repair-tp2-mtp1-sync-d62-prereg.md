# D62 preregistration: post-reboot synchronized TP2/MTP1 localization

Date: 2026-08-31

D61 failed before serving when the second B70 generated CCS page faults and
Xe reported `UR_RESULT_ERROR_DEVICE_LOST`. A function-level reset did not
recover it; no further GPU work is permitted in boot
`4136985e-4d03-45f1-8ecd-5b465b32e8d1`.

D62 may run only after a different host boot ID and clean, independent basic
compute gates on both B70s. It repeats D61's frozen TP2/MTP1, eager,
M=512-projection-repair, 256-token-profile configuration, except it restores a
device synchronization immediately after each selectively repaired projection.
This is deliberate fault-localization instrumentation. If an asynchronous
projection fault recurs, it should surface at its originating call rather than
at a later allocation.

The diagnostic image also adds environment-gated begin/pass receipts and
synchronization boundaries at dummy-sampler entry, randomized hidden state,
logit projection, sampling metadata, both sampler variants, speculative
metadata, and both rejection-sampler variants. This overlay changes no tensor
value or production algorithm. The last begin receipt without a matching pass
localizes an asynchronous fault to that stage. Its image ID is
`sha256:66bcfff69c6bf49500ce564132b303b26e26793c2c7c1b75a03c47681cab7261`.
The [source patch](../patches/vllm-qwen38-dummy-sampler-stage-sync-20260831.patch),
[Dockerfile](../docker/Dockerfile.autoround-dummy-sampler-stage-sync-r1), and
[build script](../scripts/build-qwen38-dummy-sampler-stage-sync-image.sh) are
all retained in this repository. The runner requires one pass receipt per TP
rank for every declared stage before it sends a benchmark request.

The complete twelve-prompt strict workload remains mandatory. Cached tokens
must remain zero, all objective canaries must pass, repeat-8 must have one
output class, and every complete token-ID stream must equal deterministic TP2
target baseline D59r. Any new Xe reset, fault, timeout, device loss, OOM, I/O
fault, or output mismatch rejects the arm and stops GPU work.

Because D62 adds synchronization barriers and stage receipts, its speed is
diagnostic and cannot
be promoted. A clean pass authorizes exactly one fresh no-barrier MTP1 strict
replay against D59r. It does not authorize deeper MTP by itself.
