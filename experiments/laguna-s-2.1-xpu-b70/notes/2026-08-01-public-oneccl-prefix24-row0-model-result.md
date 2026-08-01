# Laguna public-oneCCL prefix-24 row-0 model result

Date: 2026-08-01 America/Toronto

Status: **PASS; non-scored model diagnostic only.**

## Result

The checksum-pinned public oneCCL runtime repaired the exact captured-gather
failure in the real Laguna TP4 model. A matched selector-off control and
prefix-24 candidate both completed the preregistered 2x400-token smoke exactly
against the q=1 teacher, with zero cached tokens and identical speculation
counts. The candidate reduced the target graph topology from `146/145` to
`122/121` on all four ranks; the draft remained `14/13`.

At the diagnostic trigger (verifier position 420, input token 20253), every one
of the 402 compared tensors was bitwise equal between control and candidate on
every rank. This includes the layer-0 O-projection gathered output that the
installed runtime had corrupted on ranks 1-3. The old request-0 token-331
failure (`72` instead of teacher token `372`) is gone.

This establishes model-level correctness for the prefix-24 treatment at the
trigger and validates the runtime mechanism. It is not a throughput result and
does not yet establish full-suite or long-lived-service exactness.

## Frozen identity

- vLLM diagnostic tree: `3b68edc7501c546b03994ea8b6d6fa7bf23cc088`;
- XPU kernels: `99886d783372e621941228250091dc8ebdc1595d`;
- public oneCCL parent: `b52f40c07f0b140e6aba87548c80720a350a9827`;
- public libccl: `4ceafd15c03ce46f11eeaf91781a92afebd3cecf`;
- mapped library SHA256: `43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700`;
- kernels SHA256: `0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9`;
- model: Laguna S 2.1 INT4, TP4+EP4, BF16 KV, exact width 12;
- DFlash: depth 11, segmented graph with inline attention;
- selector treatment: first 24 of 96 target BF16 all-gathers captured inline;
- scored measurement: `false`.

All four workers in both arms exclusively mapped the pinned public library.
Both services passed strict teardown and post-stop idle checks. No reset,
driver reload, shared-memory deletion, FLR, or reboot was used.

## Artifacts

Control:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-public4ce-control-row0-parity-20260801T205042Z
```

Candidate:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-public4ce-prefix24-row0-parity-20260801T205835Z
```

Comparison:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/evidence/
laguna-public4ce-prefix24-row0-parity-20260801T2110Z/parity-comparison.json
```

Comparison SHA256:
`92334468f056ed791f467fc9c8068db4b560e80ef682e4bc0d4178f88b542c2f`.

The structured summary is
[`data/laguna-public-oneccl-prefix24-model-gate-20260801.json`](../../../data/laguna-public-oneccl-prefix24-model-gate-20260801.json).

## Transferable learning

For XPU graph-captured collectives, a successful capture and stable topology
do not prove replay correctness. Test a changing-input producer, the collective
output, and the first consumer on every rank. If the installed communication
runtime predates graph support, a newer pinned runtime can be a correctness
fix—not merely a performance tune. Prove it first with a minimal transaction,
then with a model-level first-divergent-tensor oracle, and only then expand the
service lifetime or score it.

## Next gate

Preregister one non-scored 13x512 service-lifetime exactness run for prefix 24
under this same pinned runtime. A pass can authorize a separately gated wider
prefix/full-96 treatment. Do not score or promote the runtime until the full
exactness gate passes and the runtime is represented in a new immutable
runtime lock.
