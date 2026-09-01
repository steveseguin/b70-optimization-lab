# D64 preregistration: TP2/MTP1 decoder-stage localization

Date: 2026-08-31

D63 disabled the projection repair but reproduced the TP2/MTP1 profile-run
device loss. It is formally inconclusive under its frozen receipt rule because
the launcher-set `/instrument` `PYTHONPATH` caused the `vllm` console script to
import the unpatched site-package runner instead of the diagnostic image's
patched `/workspace/vllm` source. That identity bug explains the zero sampler
receipts and must not be hidden or retroactively relaxed. Both B70s returned to
normal and passed independent compute after teardown.

D64 uses immutable diagnostic image
`sha256:a1454ebe9adc227b0dc5eb867c2b9a58ca12cc2594a41c4f070118d6f04cc13c`,
layered on D63's exact image. It
retains the dummy-sampler barriers and adds synchronized begin/pass receipts to
every Qwen3-Next decoder layer at entry, after input normalization, after any
input collective, after the attention/GDN mixer, after any output collective,
after post-attention normalization, after MLP, and at exit. The runtime
`PYTHONPATH` is explicitly `/workspace/vllm:/instrument`; startup logs must
therefore name `/workspace/vllm` and provide the receipts. Projection repair
remains disabled. TP2, MTP depth 1, eager mode, max-batched-tokens 256, model,
device order, and memory bounds remain unchanged.

This is startup-only and serves no benchmark request. The first begin receipt
without a matching pass receipt names the synchronization that exposed the
immediately preceding asynchronous operation. A clean startup requires all
decoder and sampler boundaries to pass on both ranks, two endpoint health
checks, clean teardown, and a quiet kernel delta. Missing source identity,
receipt ambiguity, or cleanup failure is inconclusive. One launch only; no
performance, quality, determinism, acceptance, or promotion claim is allowed.
