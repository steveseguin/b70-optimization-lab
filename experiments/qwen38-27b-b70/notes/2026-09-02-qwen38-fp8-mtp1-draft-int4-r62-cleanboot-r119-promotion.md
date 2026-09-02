# Qwen3.8 FP8 TP2 R62 clean-boot promotion R119

Date: 2026-09-02

Status: **promoted for the scoped single-user workload; universal prompt-shape and concurrency determinism remain withheld**.

R119 replayed the retained R62 draft-only INT4 vocabulary-head treatment after
a host reboot. The target verifier stayed FP16. Before the first model launch,
both B70s passed an independent Level Zero matrix multiply and the pair passed
a two-rank XCCL barrier/all-reduce. The new boot contained no Xe fault, CAT
error, reset, coredump, timeout, or device-loss signature.

Two independently compiled servers used separate empty vLLM caches and the
digest-pinned R62 image. Each ran the frozen 12-prompt, six-class, natural-512
suite with zero cached tokens and canaries before and after:

| attempt | class-balanced decode | vs MTP0 oracle | vs sibling |
| --- | ---: | ---: | ---: |
| A | `54.622918 tok/s` | 12/12 complete arrays exact | 12/12 exact |
| B | `54.226288 tok/s` | 12/12 complete arrays exact | 12/12 exact |
| center | **`54.424603 tok/s`** | — | `0.7288%` range |

The center is **`+5.0504%`** over the qualified `51.808087 tok/s` incumbent.
Both attempts exceeded the frozen 99% per-attempt floor, and the center exceeded
the preregistered 3% material-uplift gate. Both-rank server markers explicitly
confirmed that only the drafter used INT4 and the target verifier remained
FP16. Graceful teardown was followed by the same per-card compute and two-card
XCCL checks; both passed, the kernel journal was clean, and no lane container
remained.

The separate medium-prefill probe tightened the public determinism boundary.
Five identical requests were sent at each prompt length. The 100- and 300-token
controls were bitwise repeatable. At 168, 200, 224, and 250 tokens, all five
logprob arrays differed. The 168-token case also returned two distinct 64-token
streams. Therefore the earlier observation that tokens happened to remain
stable across this window no longer holds for R62. This is a user-visible
single-request determinism defect, not only a batching artifact.

Decision: R62 replaces the prior single-user headline for the fixed
48-78-token-prompt suite at **`54.424603 tok/s`**. It is not a universal
determinism claim. Prefills in the roughly 168-256-row window and all
token-identity concurrency claims remain excluded until W8A16 is row-invariant
and repeat-deterministic. The package also remains a candidate portable
reproduction until an independent supported host repeats installation, build,
and validation.

Reproduction and evidence:

- [preregistration](../data/2026-09-02-qwen38-fp8-mtp1-draft-int4-r62-cleanboot-r119-prereg.json)
- [structured result](../data/2026-09-02-qwen38-fp8-mtp1-draft-int4-r62-cleanboot-r119-result.json)
- [R62 implementation report](2026-09-01-qwen38-fp8-mtp1-draft-int4-r62-diagnostic.md)
- [W8A16 kernel census and runtime-M experiment](2026-09-02-qwen38-fp8-mtp1-c2-identity-review-kernel-census-cr1.md)
- [R62 build](../../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/build-draft-int4-r62-image.sh)
- [R62 launcher](../scripts/run-20260901-qwen38-fp8-mtp1-draft-int4-r62-server.sh)
