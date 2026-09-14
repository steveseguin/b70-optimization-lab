# Official 27B FP8: public quickstart replay

The recommended package now has one pinned launch path for **two B70s, one
active user, fixed MTP1, and 33,024 total tokens**. The public-source replay
passed the full strict output check and all six practical requests, then stopped
cleanly with the documented command. This pass changed the packaging and
instructions; it did not introduce a runtime optimization.

[Start here](../../../packages/qwen38-27b-fp8-tp2-b70/README.md) ·
[Public details](https://neural.download/models/qwen38-27b-fp8-vllm-tp2-asrock-b70.html) ·
[Structured results](../data/2026-09-14-fp8-flagship/summary.json) ·
[Evidence manifest](../data/2026-09-14-fp8-flagship/manifest.json) ·
[Test plan](2026-09-14-fp8-flagship-prereg.md).

## What was reproduced

The source archive was downloaded anonymously from GitHub at commit
`3bcfc8b230d18c42c9092352714a2afee8263f18` into a new directory with no Git
worktree. The helper and both clients ran from that downloaded source. An
anonymous public image pull resolved the exact digest. Existing Docker layers
and model files were reused; all model files passed fresh direct and ordinary
hash checks. The new serving-state directory began with an empty compile cache.
The image contract verified all 17 runtime files and the kernel identity.

The captured runtime environment and every vLLM argument match the already
qualified 32K-input profile, apart from its client-facing model alias. Container
RAM and memory-plus-swap limits match too. The runtime is R304, image
`sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2`,
with official model revision `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`.
FP16 activations, native KV, full-vocabulary draft-only INT4 head, batch 4,096,
one sequence, prefix cache off, V1 runner and the qualified compile settings
are unchanged. The shared runtime's public build closure is
[`chains.r304`](../../../repro/qwen38-27b-autoround-int4-b70/publication-manifest.json).

One server ran for this session. Model verification, loading and initial
compilation took about 3 minutes 20 seconds before readiness on this host.
The helper's status reported a healthy API while running. The exact recorded
container was stopped once; the final status reports it absent. No restart,
new optimization, driver reset, reboot, or power/memory-setting change occurred.
Small compute/XCCL checks on both GPUs passed before and after the session,
and the full kernel-journal review found no GPU fault. The separate four-card
LTX work was preserved.

## Acceptance results

The unchanged fixed 12-prompt/six-class natural-512 suite passed its output
validity and cache-zero gates and its canaries. **All 12 complete token arrays
matched the qualified R304 reference.** Class-balanced writing speed was
**54.201 output tokens/s**, versus 54.818 for the earlier short-capacity reference
(−1.12%). This is a single additional replay with different configured capacity;
it is not a matched optimization comparison or new speed qualification.

Three supplied chat tasks were each sent twice, sequentially, with greedy
sampling, reasoning disabled, a 256-token answer cap, and no cached input.
All six finished naturally, passed their objective checks, and produced exact
repeated text and complete token arrays.

| Task | What was checked | Actual input tokens | Answer tokens | HTTP first-token wait, two requests |
| --- | --- | ---: | ---: | --- |
| Conversation | Retain the prior plan while changing the guest count | 129 | 37 | 156 / 124 ms |
| Code | Correct an inclusive-range bug and its example result | 122 | 44 | 119 / 117 ms |
| Document | Extract approved dates, budget, owner and risks | 182 | 74 | 140 / 131 ms |

The conversation test supplies a fixed previous exchange; it is not a prolonged
interactive chat. Code is parsed for validation and never executed. The document
is a short supplied brief, not a 32K retrieval test. HTTP first-token wait includes
transport overhead and is **not server prefill time**. No prefill value is inferred
from these requests. The earlier 4K-capacity prefill measurements and higher-draft
historical decode records keep their original identities.

## Package and publication changes

- One foreground Python helper supplies start, API status, and exact-owned stop.
  It fixes the qualified configuration, rejects competing GPU ownership and
  external runtime overrides, records identity/logs, monitors faults, and never
  automatically restarts.
- Preflight/pull metadata and the Compose renderer now pin the same public image.
  Compose uses the recommended context, batching, sequence and V1-runner settings;
  the helper is the replayed lifecycle path.
- Package and canonical READMEs lead with the recommended setup. Older image
  builders and faster draft records remain available as historical material.
  The root README, catalog, homepage entry point and generated details page agree.
- CPU lifecycle, practical-client, renderer and guide tests pass. Desktop/mobile
  page checks cover graphs, exact-value tables, copy controls, links, overflow
  and JavaScript-disabled access. The first CI attempt caught a stale generated
  README table after its label changed; regeneration corrected it.

The evidence archive retains full practical requests and raw SSE, strict outputs
and reference, container/source identity, model verification, health logs, stop
receipts and validation results. Verify it without a GPU:

```bash
python3 experiments/qwen38-27b-b70/scripts/collect-fp8-flagship-evidence.py
```

## Remaining limits

This is a clean source/state-directory replay on the existing lab host, not a
fresh Intel driver/Docker installation, an independent-host replay, or a fresh
31 GB model download. Three tasks repeated twice do not establish broad quality,
long-context retrieval accuracy, multi-user output identity, or multi-hour
stability. The package remains `candidate-portable-repro`.

The unrelated historical Flash-Next tooling still has 231 reported frozen-pin
mismatches; none was repinned for this package. The FP8 packet's new source and
evidence hashes are checked independently.
