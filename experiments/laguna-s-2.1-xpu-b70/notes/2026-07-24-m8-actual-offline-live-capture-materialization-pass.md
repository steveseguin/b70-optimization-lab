# Laguna M8 live-capture materialization raw-parity pass

Date: 2026-07-24 America/Toronto

## Result first

The preregistered v10 actual-model gate passed every fail-closed A/B/C
invariant. The guarded target-only Breakable graph now produces exactly the
same greedy token IDs and decoded text as canonical eager execution, with
bitwise-identical raw target tensors, live attention slot routing, speculative
acceptance/bookkeeping, and all 97 collective outputs on every rank and every
eligible event.

This is a correctness component result only. It contains no timing, trace,
benchmark, throughput, record, payload, or LocalMaxxing claim.

The immutable sealed root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-1cc59f68a-20260724T201926Z
```

The approved record remains `33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.

## Exact terminal result

All three arms used one fresh offline `LLM.generate` call in separate
processes. Each reported `num_cached_tokens == 0`, 33 prompt tokens, 32
completion tokens, finish reason `length`, and the same output:

```text
token IDs  cca03973c1998dfc3255cad724577213ed01cb606cf12eb867358de16f9b9e3f
text       92105d1de6f357cac164f12b76adc090c334135477400010f3e1e810109efd0b
```

The v11 analyzer returned:

```json
{
  "status": "PASS",
  "evidence_digest": "fa24571dc06a4df7069cba138d3f61f31cc3dbbd7351b28fddb7b2f8f11dd54a",
  "nonbenchmark": true,
  "timing_claim": false,
  "pti_trace_claim": false
}
```

Every required check is true:

- A/B and B/C live attention slot routing;
- A/B and B/C target hidden, attention, sampled-token, acceptance, emitted-ID,
  and physical-KV status evidence;
- all 97 B/C collective raw outputs per event and rank;
- identical final driver token-ID lists;
- exactly zero cached tokens;
- one fresh generation per arm;
- one C capture followed only by replays.

## Raw evidence

Arm A (`incumbent-eager`) retained 60 manifests, 15 per rank, each with 201
events. Arm B (`segmented-eager`) retained 60 manifests, 15 per rank, each
with 444 events. Arm C (`segmented-graph`) retained 60 manifests, 15 per rank,
each with 446 events.

On each C rank, event 0 is the unique capture and events 1-14 are replays.
Every event uses the same exact M=8 descriptor, 146 graph segments, 145 eager
breaks, and capture count one. There is no recapture.

The v9 failure point is repaired exactly. On the first live transaction,
rank 0's captured embedding segment now provides the canonical nonzero BF16
input to the embedding all-reduce; ranks 1-3 provide their expected zero local
shards; the all-reduce output on all ranks is the canonical digest:

```text
1f3f00c08efcc9b35a9987ca87dd6aa4163a03fcc0e3d259638bfee82910fe6b
```

In v9, every rank's output at that boundary was zero. Materializing each
newly ended graph segment before its eager consumer, and the final segment
before returning, corrects the live capture without executing any eager
boundary twice. Default generic Breakable capture semantics remain unchanged.

## Cleanup and artifact state

The root is sealed mode `0500`; `analysis.json` is mode `0400`. All three
post-worker reports are empty and all three post-idle snapshots passed. No
runner, model worker, or analyzer remains. Models, RPC, caches, temporary
files, logs, and evidence stayed on internal NVMe under `/mnt/fast-ai`; the
backup USB was not used.

## Frozen identities and hashes

- main tooling:
  `1cc59f68afb32f88eb63b9b7092792a16a2b62c3`;
- preregistration:
  `7531c3aa8`;
- vLLM:
  `439975d5ae6535553c5d846a2393b0da514447e3`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- driver schema: `laguna-m8-offline-arm-v10`;
- aggregate schema: `laguna-m8-actual-offline-gate-v11`;
- raw format: `laguna-m8-raw-evidence-v2`;
- RPC paths: `m8pa-a`, `m8pa-b`, and `m8pa-c`.

Key retained hashes:

```text
a3c7ba92db7b0886930ae696dd9b8e7dadfbd3b7e77418ef22f65ce36b19b38c  identity.txt
0a5d43488c42890221200301d4f9702c01d6eeaef24bb7934c4e1912b1b0648a  analysis.json
7f08feee7cc552da397393ff37bd624675628e3be5f7cfabb78e78338631e1f7  incumbent-eager/driver.json
d898ca1dd899362ba194a9d7b4e252f0a4a6da81234baacf53018244e739507b  incumbent-eager/evidence/evidence.json
fc735c1a1efc8df457b57cd7d467f66d434467257583eea2c78be81076db8fa8  segmented-eager/driver.json
dd52950c4e48ac409c7f008a9000cd13b4dd8b20f53608a3f6a837c8438472bf  segmented-eager/evidence/evidence.json
6cbdb8f328648429bd2e0667350013cdea64329903fbbf71a242a31c25a9cf44  segmented-graph/driver.json
91c310f139de7b8d5476884d7588926ce04895b030b796abd0072089ed2b179d  segmented-graph/evidence/evidence.json
```

Machine-readable result:
`data/laguna-m8-actual-offline-live-capture-materialization-pass-20260724.json`.

## Next gate

This pass authorizes the next correctness layer, not a benchmark. Before any
timing claim, a fresh endpoint build must pass the canonical q1 teacher,
cross-start reproducibility, cache-zero, long-then-next, and rollover gates
with the graph lane enabled. Only after those pass may a fresh cold benchmark
be compared with the approved `33.89498511171744 tok/s` record.
