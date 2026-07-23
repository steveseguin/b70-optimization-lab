# Laguna routed-W1 N128 A1 device-lost incident

Date: 2026-07-23 America/Toronto

Status: the original N128 endpoint campaign is permanently closed as an
`infrastructure_abort_after_measurement_start`. It is not performance evidence,
must not receive B1/B2/A2 legs, and cannot produce a payload or submission.

Structured incident manifest:
`data/laguna-s-2.1-w1-n128-device-lost-incident-20260723.json`.

## What happened

The frozen A1 control started under the registered root:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-endpoint-abba-8936aac-c59aaad-20260723T093923Z
```

The service passed source/model/runtime preflight, became healthy, and captured
its pre-suite metrics. Prompt 0 then entered the streaming
`/v1/chat/completions` path. The access log contains the stream-open `200` and
terminal `500`, while the scheduler dump identifies only prompt 0. Partial
device compute or streaming may have occurred; this was not a zero-generation
preflight failure.

At 06:27:52 local time, XPU index 2 / TP2 / EP2
(`0000:43:00.0`, `/dev/dri/card0`) suffered a BCS kernel-job timeout, Xe
devcoredump, and GT reset. Repeated VM-job timeouts followed. The worker raised:

```text
UR_RESULT_ERROR_DEVICE_LOST
```

The failing host-to-device handoff was
`prepare_next_token_ids_padded -> backup_next_token_ids.copy_to_gpu`. The
engine stopped making progress and ultimately returned HTTP 500. After this
was confirmed from the read-only log, the exact runner process received TERM
instead of waiting for the client's 30-minute timeout. Its trap performed
bounded service shutdown and post-stop proof successfully:

```text
original_status=143
stop_status=0
poststop_proof_status=0
final_status=143
```

No vLLM process, listening service, or GPU client remained.

## Why there is no benchmark result

The failed root has:

- no `bench.json`;
- an empty `bench.stdout`;
- no metrics-after artifact;
- no teacher comparison or canary artifact;
- no evidence manifest or valid leg chain;
- no B1, B2, or A2 directory;
- no phase/full analysis; and
- no LocalMaxxing payload or response.

Therefore it exposes no completed row timing, headline throughput, quality
result, or candidate observation. It must never be mixed with steady-state
speed evidence.

## Recovery and restart integrity

All original artifacts are preserved and SHA-256-bound in the structured
incident manifest. The failed root is immutable and permanently closed.

A new run is permitted only as one separately preregistered recovery campaign,
not as a continuation or replacement leg inside the old root. Its lineage must
disclose one invalid aborted control service start before the four possible
valid A1/B1/B2/A2 starts.

Before that campaign:

1. perform no candidate or model-generation diagnostic;
2. validate all four devices with stable discovery, per-card compute, peer
   reads, exact four-rank XCCL reduction, and a known-good N64 component oracle;
3. reject recovery on any new real Xe timeout, reset, coredump, TLB, GuC, CT,
   or AER event;
4. wait at least 60 seconds with no device client; and
5. make the new A1 control the first post-recovery model generation.

The new A1 is also the mandatory adjacent clean no-change control after a
device-lost incident. If it fails to complete all 13 unique prompts with exact
teacher equality, zero cached tokens, exact request accounting, canaries, and
clean shutdown, the lane closes: no B1 and no third campaign.

The recovery runner/analyzer must independently rehash this incident manifest
and every retained failed-root artifact, require the specified artifacts and
later legs to remain absent, pin the recovery evidence, and surface the aborted
start in final eligibility/publication evidence. All original treatment,
A-B-B-A, exactness, freshness, causal, variance, and record-floor gates remain
unchanged.

## No-reboot recovery result

The automatic-reset recovery path was tested without starting a model service
or executing the N128 candidate:

- verbose SYCL enumeration returned all four stable Level Zero devices;
- oneAPI 2026 peer-memory stress passed across four devices;
- fresh-process allocation, arithmetic, copy, and synchronization passed on
  every physical card;
- N64-only production-fixture calls completed on every card;
- one corrected four-rank XCCL check returned exact `4.0` on every rank; and
- the kernel log contained no new real timeout, reset, coredump, TLB, GuC, CT,
  or AER reject event after failed-campaign cleanup.

That was not reproducible. The formal captured XCCL repeat segfaulted local
rank 1 inside oneCCL's Arc all-reduce path. This is a recovery failure even
though it did not trigger another kernel reset.

The capture wrapper then exposed a separate evidence bug: it wrote
`xccl_status=0` after the failed command because fail-fast handling was absent.
That file and the original manifest are retained unchanged but explicitly
invalid. The additive disposition and final manifest are:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-device-lost-recovery-20260723T103343Z/no-reboot-validation/DISPOSITION.md
SHA256 4e6b9eed5414a51aebeef681d0e4715835366dbb14d98b56d104906722e210f4

/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/w1-n128-device-lost-recovery-20260723T103343Z/no-reboot-validation/evidence-v2.sha256
SHA256 ba5a5cc5197306aefc410f45120365d8feb26c183a9c02bc7ce8de74c8666255
```

Disposition: stop the no-reboot path. Do not retry XCCL, do not register or
start a new endpoint campaign in this boot, and do not run A1. A full host
reboot and fresh post-reboot recovery gate are now mandatory.
