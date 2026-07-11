# Contribution And Result Verification

This repository welcomes useful optimization evidence without treating every
reported number as independently verified. Review is manual and task-specific.

## Hardware Scope

Intel XPU is the present focus. The maintainer can directly test Intel Arc Pro
B70 configurations, so B70 is the reference lab—not an eligibility boundary.
Arc Pro B50, B60, B65, B70, other Intel Arc, and relevant portable contributions
are welcome.

A result keeps the hardware identity on which it was measured. Running its
patch on B70 establishes a separate B70 observation; it does not confirm the
original score on B50, B60, B65, another Arc GPU, or non-Intel hardware.

## Required Result Packet

Every performance or quality claim should identify:

- contributor and source/PR URL;
- source base commit, candidate commit, and patch or checksum;
- GPU model/count/VRAM and interconnect;
- OS/kernel, driver, compiler, accelerator runtime, and important libraries;
- model repository/path and exact revision;
- weight, KV, activation, and draft-model quantization where applicable;
- engine/runtime commit and local patches;
- exact command, environment variables, and diagnostic flags;
- prompt/output/context lengths, batch size, concurrency, and request count;
- cold/warm state, graph/compile state, and cache policy;
- speculative-decoding configuration and accepted-token policy;
- metric definition, repeats, dispersion, TTFT, and throughput;
- quality gate, inputs, acceptance threshold, and result;
- JSON/log paths or durable public links;
- the closest known-good result and the complete intentional delta.

Missing fields should be marked unknown rather than guessed. Results with
materially different identities belong in separate comparison groups.

## Evidence Levels

| Label | Meaning |
|---|---|
| `community-reported` | Contributor evidence has not been independently reproduced here. |
| `B70-tested` | The patch ran on the local B70 lab; the submitted score may not have been reproduced. |
| `B70-verified` | The result and quality gate were produced in the reference B70 lab, either as maintainer work or an independent reproduction. |
| `matching-hardware verified` | Independently reproduced on the hardware class named in the claim. |
| `invalid` | The stated claim failed identity, quality, provenance, or reproduction checks. |
| `superseded` | Retained for history but replaced by stronger or newer evidence. |

These labels describe evidence, not contributor trustworthiness. Patch review
status should be recorded separately from benchmark status.

## Review Procedure

1. **Protect current work.** Read the current handoff and map, inspect running
   jobs and dirty trees, and keep the active Qwen 27B INT4 TP=2 lane and its
   external runtimes out of scope.
2. **Establish provenance.** Record authorship, source, commits, third-party
   licenses, and the contributor's right-to-submit statement.
3. **Inspect safely.** Review the full diff before execution. Do not expose
   credentials, use unnecessary privilege, modify services, or run unexplained
   binaries/downloaders.
4. **Isolate.** Use disposable source/build trees, environments, ports, and
   result directories. Do not clean or reuse active modified runtime trees.
5. **Verify the baseline.** Re-run the closest matching known-good setup in the
   same window when feasible and investigate identity drift before interpreting
   a speed change.
6. **Gate correctness first.** Start small, then run the model-specific quality
   gate. Precision, cache, prompt, speculation, or acceptance changes create a
   different quality class unless equivalence is demonstrated.
7. **Compare performance.** Match workload and metric definitions, alternate
   run order where practical, retain repeats, and report variance and failures.
8. **Preserve and classify.** Keep patches, commands, logs, JSON, negative
   results, limitations, and the final evidence label in durable repository
   locations.

Reviewers may stop at any stage when a submission is unsafe, inadequately
licensed, missing essential identity, impractical to test, or outside current
capacity. Such work can remain community-reported if it is still useful and
clearly labeled.

## Scoreboard And Publication

A repository scoreboard is a compact map of expected performance and evidence,
not a universal ranking. It should link to full result packets and show model
revision, quantization/quality class, hardware/count, engine, benchmark shape,
metric, quality outcome, evidence level, patch, artifacts, and contributor.
Only like-for-like rows should be ordered by score.

LocalMaxxing is an additional downstream destination for eligible verified
records. A LocalMaxxing row neither replaces repository evidence nor makes an
otherwise incomparable or unverified result valid.
