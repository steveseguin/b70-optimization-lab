# 342b r2 closed stale before launch

Date: 2026-08-24. Status: **closed stale before launch; never launched.**

The fresh-root r2 packet passed its static, safety, evidence, and preservation
audits, but it had not yet been committed or invoked. The final freshness
audit at `2026-08-24T18:51:31Z` resolved live vLLM `main` to
`6a9c69fa851389dcf1ee5d3a2363e27af665d26d`, not the frozen
`342b8ebd8bd4595826f29ff95dfc48679a03a95a` build identity. XPU-kernel main
remained `baaa05bb4e92901219a5a072dd63f2474896f6d1`, the official nightly
digest remained
`sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`,
and lab `main`, local `origin/main`, and live `origin/main` remained
`6f133e653b033618c068e1c8f8ef7a660a19045b`.

The successor is the direct child of 342b. Its single commit is
`[Attention][Spec Decode] Support varlen trtllm-gen decode for adaptive
verification (#52157)`, changing only
`tests/kernels/attention/test_flashinfer_trtllm_attention.py` and
`vllm/v1/attention/backends/flashinfer.py` (138 insertions, 7 deletions).
No Qwen- or XPU-named path, lab build recipe, or preserved decision payload
changed.
The commit is speculative-decode-adjacent, however, so its semantic relevance
must be assessed on the successor rather than waived. Literal-current policy
therefore requires a fresh zero-overlay rebuild and qualification.

The r2 wrapper was never invoked. Both exact roots remain absent, ports
`19773`-`19775` are unbound, Docker has no running container, and there is no
r2 hardware-gate, model, canary, benchmark, quality, cache, or GPU result.
This closeout is not performance or quality evidence and changes no protected
speed.

Keep the exact preregistration and wrapper as stale provenance. The r2 wrapper
is mechanically identical to the audited r1 wrapper after only the declared
attempt, preregistration, fresh-root, and port substitutions. Its diagnostic
floor remains `30.2178 tok/s`; its strict floor remains
`30.31067504052998 tok/s`. It must never be invoked, repinned, resumed, or
relabelled for the successor.

R1 remains sealed failed-incomplete with 70/70 hardware, 178/178 campaign, and
21/21 input-manifest checks. Its diagnostic `30.337988469031558 tok/s` and
quality-clean strict A `30.295550825778708 tok/s` remain dated evidence; strict
B does not exist. TP2 and TP4 are not authorized. All 78 TP2 decision files and
all 152 accepted TP4 decision files reverified byte-for-byte, and neither was
applied to the 342b zero-overlay images.

The structured closeout is
[`2026-08-24-qwen38-342b8ebd8b-r2-stale-before-launch.json`](../data/2026-08-24-qwen38-342b8ebd8b-r2-stale-before-launch.json).
The next action is a fresh build from live vLLM 6a9c69f or any newer successor,
exact-current XPU kernels, and the live nightly digest. Re-resolve all three
again immediately before and after the build. Only a full TP1 pass can
authorize separately preregistered TP2 and then TP4 qualification; compatible
accepted decisions stay versioned and are remapped into fresh caches rather
than discarded.
