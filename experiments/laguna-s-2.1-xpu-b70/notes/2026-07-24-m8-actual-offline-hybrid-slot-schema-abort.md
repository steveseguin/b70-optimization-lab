# Laguna M8 actual-model gate: hybrid slot-schema abort

Date: 2026-07-24 America/Toronto

Status: sealed post-generation instrumentation/schema abort in the
incumbent-eager arm. The one fresh `LLM.generate` call returned and its
cache-zero check passed, but low-level evidence aggregation failed before
`driver.json` or `evidence.json` was written. This is not an A/B/C quality or
performance result.

## Frozen identity

- approved record: LocalMaxxing `cmrx6p5dv001bo4017hb7sixz` at
  `33.89498511171744 tok/s`;
- v4 gate tooling:
  `6e478a38aaae548d225ffbce2a9b6d2e693e4efc`;
- v4 preregistration:
  `22b6edcd994028167ceca8c829e87b3c357a2313`;
- reviewed vLLM:
  `00d3c7faa3a73f08246a70c7280eed633ec2441b`;
- frozen kernel descendant:
  `4772f727590c51b72add79350b913d098cf67872`;
- sealed run root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-6e478a38a-20260724T164716Z`.

Retained SHA-256:

```text
d18d052ba2af8e35a6fe34c59fc3463daea986d8efc76f1fa5984c739a7bb32e  identity.txt
69e3cf14500205b33fe6b427935073e7f5305dd34fda8e8445197bafbd334d77  incumbent-eager/stdout.log
dfe9ba321e376a3ce835bde48ed6f319a4e438eb4ebdf8c8c4459c9285bdea0b  incumbent-eager/stderr.log
c468e1aa5c9a1b6ddd99fe5f569c0fe8ca7358525dbccbbec41a25bc487b4fa4  incumbent-eager/pre-idle.json
72bbab5640e11ca0e5b9f6c88c8e81480ab34858256fb070a83f32dde4adc7aa  incumbent-eager/post-idle.json
```

The run root and all `m8p4-{a,b,c}` RPC bases are sealed and will never be
reused.

## What happened

Arm A used the approved true-eager identity, loaded the target and DFlash from
internal ext4, and cleared the prior target-hidden instrumentation defect.
Fifteen M=8 verifier events completed on every rank. Each rank retained 201
events per verifier, giving 60 manifests, 12,060 event sidecars, and 11,640
raw tensor binaries. Target hidden, logits, sampling, acceptance, and
post-bookkeeping events are present. Two verifier events accepted all seven
drafts.

`LLM.generate` returned exactly one output. The driver then observed
`num_cached_tokens == 0` and called the low-level aggregator. The aggregator
stopped on the first rank/event:

```text
attention slot mapping differs from logical key
```

No `driver.json`, `evidence.json`, or final `analysis.json` exists. The exact
returned 32-token driver list was therefore not durably captured. Concatenated
rank-0 post-bookkeeping evidence contains 33 internal emitted IDs because the
last speculative verifier crossed the 32-token request limit; its canonical
JSON SHA-256 is
`8e172c115a13f41a48de4f81bd6b82ce4d8895276f9f4cd10855e0349cbb5332`.
That recorder-derived stream is retained only as diagnostic evidence and must
not be claimed as the returned completion.

## Root cause

Laguna uses hybrid KV-cache groups. `_get_slot_mappings` constructs one live
mapping per cache group and assigns each mapping to its member layers.
Attention correctly records the mapping resolved for its own layer. The v1
logical key instead hashed `next(iter(slot_mappings.values()))`, which happened
to be layer 0, and the analyzer incorrectly required all 48 layers to match
that one hash.

The first rank/event contains three legitimate `torch.int64[8]` mappings:

- layers 0, 4, ..., 44 use
  `2cade9ee11fea09637f166a5c7100c7d87f4727ae37acc2dbcf459b439ce6509`;
- 18 sliding layers use
  `055dea0028863b4e4716175d5e5226c9ce78a6a711fa08632b8ced10cfb3c2cb`;
- the other 18 sliding layers use
  `1bbb1e9b9763c538903a1489234998418a84c388a52dcebdfbe6e4c9ffe939a3`.

The same layer routing is present on all ranks. A read-only compatibility
analysis that changed only the false scalar-slot assertion successfully
validated all 15 events on all four ranks, with normalized digest
`b3b1a48290dd45ee3fe7077cc17a18c47e9458279e69bcf5cf54d359a8b2d7fe`.
That diagnostic does not convert this sealed v1 root into a passing gate.

## Cleanup and decision

All workers exited, pre/post worker inventories are empty, and strict post-arm
XPU idle passed on devices 0-3. The resource tracker retained one shared-memory
warning, but no worker or XPU context remained. The 278 MiB sealed root is on
`/dev/nvme0n1p2` ext4 below `/mnt/fast-ai`; no external USB path was used. B
and C did not start.

Classify this root as
`post_generate_instrumentation_abort_on_invalid_single_slot_schema`.
It proves the DFlash tuple fix works in the actual model, but it does not prove
A/B/C parity and authorizes no timing or submission.

Continuation requires an explicit raw-evidence v2 schema: the logical key must
carry an ordered 48-layer live slot-signature vector; every layer's Q/K/V/O
records must match that vector entry; the target-hidden record must not claim
one arbitrary attention slot; and A/B/C must compare the routing vector
separately from raw attention bytes. Unit tests and independent audit precede
a fresh vLLM/tooling commit, `m8p5` paths, and v5 preregistration.

The approved LocalMaxxing record remains unchanged.
