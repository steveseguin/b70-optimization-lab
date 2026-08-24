# 7797 r2 closed stale before launch

Date: 2026-08-24. Status: **closed stale before launch; never launched.**

The fail-closed r2 classifier and one-shot TP1 packet passed three independent
audits, were committed as `eba4a9d10`, and were pushed to clean `main`. The
separate post-push freshness gate then resolved live vLLM `main` to
`6648eb118d77ad001a411cf52f9c6c4719476c83`, not the frozen
`7797b6022c129b862e45ae6aed08822e65d1bccb` build identity. XPU-kernel main
remained `baaa05bb4e92901219a5a072dd63f2474896f6d1`, and the official nightly
digest remained
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`.

The successor is one direct commit after 7797. Its only source change removes
a duplicate `VLLM_USE_DEEP_GEMM` predicate in
`vllm/model_executor/warmup/kernel_warmup.py`; the called support function still
checks that variable, and XPU does not support the DeepGEMM path. No Qwen,
GDN, XPU, graph, speculative-decode, distributed, dependency, or build file
changed, and no accepted Qwen overlay has a textual conflict. That bounds the
forward-port risk but does not waive the newest-head rebuild.

The qualification wrapper was not invoked. Both exact r2 roots are absent,
ports `19764`-`19766` are unbound, Docker has no running container, no model or
canary started, and no hardware gate, benchmark, quality request, or GPU work
ran. This is not correctness, quality, or performance evidence. It changes no
protected speed.

The complete structured closeout is
[`2026-08-24-qwen38-7797b6022c-r2-stale-before-launch.json`](../data/2026-08-24-qwen38-7797b6022c-r2-stale-before-launch.json).
Keep the exact audited r2 preregistration, wrapper, classifier, test, and
runners as stale provenance; do not repin, invoke, resume, or relabel them for
the successor.

R1 remains independently sealed at 64/64 hardware-gate and 70/70 campaign
manifest entries. The TP2 78-decision and accepted TP4 152-decision artifacts
remain checksum-valid, separately versioned, disabled, and unapplied. No
accepted optimization has been discarded or silently baked into the 7797
zero-overlay image.

The next action is a fresh zero-overlay build from the literal newest vLLM
head, exact-current XPU-kernel head, and live official nightly digest. A new
qualification packet must be derived from the audited r2 safety repair only
after that successor build identity is sealed. Accepted decision overlays may
then be remapped only where relative paths and embedded config hashes remain
compatible, into fresh caches with full TP2/TP4 requalification.
