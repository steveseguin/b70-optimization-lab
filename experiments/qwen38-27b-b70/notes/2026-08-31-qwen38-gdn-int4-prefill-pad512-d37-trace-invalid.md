# Qwen3.8 packaged GDN pad D37 trace attempt

D37 was stopped after two processes and is **technical-invalid**. The selected
stage tracer replaces `forward_xpu` at the target call and reconstructs its
projections directly. It therefore bypassed the packaged repair precisely at
the boundary being tested. No determinism, quality, or performance conclusion
is permitted from this attempt.

D37r uses a non-invasive wrapper: it calls the packaged `forward_xpu` first,
unchanged, then hashes only its input and returned output. The synchronization
occurs after the operation and cannot select or replace its implementation.
