# Two-card FP8: acceptance session re-collected after the warm-up change

The September 14 flagship packet pins the sha256 of every source it used, including
`packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py`. On September 15 that helper gained one untimed warm-up completion
before it reports the server ready ([cold-start note](2026-09-15-fp8-cold-start-warmup.md)), so the frozen packet no
longer matched the working tree and the site's `validate` job failed on every push from 13:43 UTC onward.

**Fix: run the bounded acceptance session again with the current helper, and freeze a new packet.** The September 14
packet stays exactly as it was.

## What ran (September 16, 2026)

Same shape as the original session, from public sources at the pushed commit `2c8a2a6b2`:

1. Host snapshot, XPU/XCCL health preflight.
2. Anonymous GitHub archive download; the five pinned files matched the working tree byte for byte.
3. One owned two-card server through `serve.py start` on the public digest-pinned R304 image.
4. The fixed 12-prompt strict suite plus canaries, compared with the qualified R304 MTP1 reference.
5. Six practical chat requests (conversation, code, document; each twice).
6. Documented status, one graceful `serve.py stop`, post-stop status, health postflight, host snapshot.

## Result

| Check | Result |
| --- | --- |
| Strict outputs vs the qualified reference | 12/12 exact |
| Strict decode | 54.879 tok/s (reference 54.818, +0.11%) |
| Canaries, cache zero, natural-quality gate | pass |
| Practical requests | 6/6 pass, both repeats token-identical |
| Runtime vs the qualified 32K container | image, arguments and environment match |
| Owned clean stop, post-stop absence | pass |
| GPU faults | none |

All twelve gates in the packet pass. Evidence:
[data/2026-09-16-fp8-flagship](../data/2026-09-16-fp8-flagship/) (77 files), raw root
`/mnt/fast-ai/bench-results/qwen-fp8-flagship-20260916`. The verifier's default packet now points at this directory.

**Lesson:** editing a package script invalidates any frozen evidence that pins it. Check
`collect-*-evidence.py` source lists before changing a published helper, and run the full `guides.yml` step list
locally rather than the publication subset.
