# Qwen3.8 Q8 distributed greedy argmax experiment

Status: **closed, exact but performance-neutral, not promoted**.

## Objective

The accepted TP2 graph leaves the final vocabulary logits split evenly across
the two B70s. Ordinary backend sampling brings the complete vocabulary result
back through the meta path before selecting the token. This experiment tested
whether each GPU could select its own winner and exchange only two token/logit
pairs.

The candidate is deliberately narrow:

- it is opt-in with GGML_META_DISTRIBUTED_ARGMAX=1;
- llama-server must use --backend-sampling and the request must opt in;
- it accepts only strict greedy chains whose filters preserve argmax;
- penalties, grammar, bias, positive temperature, and other unsupported
  samplers fail closed to the ordinary CPU path;
- equal logits choose the lower global token ID, matching ordinary argmax.

The SYCL operation compares the two already-computed shard winners and writes
the global token ID to both outputs. It does not rescan the 248,320-entry
vocabulary. The activation marker for this model is:

    SYCL distributed ARGMAX active: shards=[124160,124160] rows=1

## Safety and build

The source is the accepted Qwen3.8 Q8 direct-Q8 stack based on mndodd commit
4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126, plus the five-file incremental
patch linked below. Git diff checking and a clean patch-application check both
passed.

The Release build used oneAPI 2026.1, BMG-G31 AOT, Intel SYCL, F16 support and
Level Zero API support. Graph, DNN, and host-memory fallback were disabled. It
ran under a 6 GiB build cap at -j2, peaked at 3.7 GiB, and used no swap.

The endpoint retained the accepted target-only runtime: level_zero:1,0,
SYCL0/SYCL1, equal tensor split, F16 KV, FlashAttention, b1024/ub256, 8K
context, one slot, cache RAM zero, context checkpoints zero, fit off, reasoning
off, and no MTP, DFlash, draft model, response reuse, or speculation.

## Position-balanced endpoint result

The fixed 12-prompt cold suite ran in the order control 1, candidate 1,
candidate 2, control 2. Every one of the 48 requests reported zero cached
tokens. All four complete 12-output hash lists were identical.

| Arm | Primary tok/s | Full after-TTFT tok/s | Wall tok/s | TTFT ms |
| --- | ---: | ---: | ---: | ---: |
| control 1 | 35.841542 | 35.648997 | 35.140790 | 183.661 |
| candidate 1 | 36.016654 | 35.901675 | 35.414970 | 198.502 |
| candidate 2 | 36.072154 | 36.009612 | 35.445651 | 197.905 |
| control 2 | 36.288690 | 36.017298 | 35.516607 | 182.330 |

Mean of the two run medians:

| Metric | Control | Candidate | Delta |
| --- | ---: | ---: | ---: |
| primary tokens 1-100 after TTFT | 36.065116 | 36.044404 | **-0.057%** |
| full output after TTFT | 35.833147 | 35.955643 | +0.342% |
| full wall rate | 35.328699 | 35.430310 | +0.288% |
| TTFT | 182.995 ms | 198.204 ms | **+8.311% worse** |

The primary result is neutral, the small full-output movement is within the
matched run spread, and the extra cross-queue synchronization measurably hurts
TTFT. This is not a promotion candidate.

## Reasoning-mode provenance correction

This replay exposed a documentation mismatch in the earlier Q8 package. The
stored promoted speed capture has reasoning output containing the think tag,
while the current launcher explicitly uses reasoning off. The older rate
remains a valid target-only measurement, but it is not the exact reasoning-off
reproduction identity.

This packet therefore records the current reasoning-off 12-hash oracle and two
fresh matched control runs. Future Qwen3.8 records must state reasoning mode in
both the command and result packet.

## Reproduce the candidate

Restore the accepted Qwen3.8 Q8 source snapshot first, then apply the
incremental patch:

    base64 -d experiments/qwen38-27b-b70/patches/q8-distributed-greedy-argmax-neutral-20260816.diff.gz.b64 | gzip -dc > /tmp/q38-distributed-argmax.patch
    git apply --check /tmp/q38-distributed-argmax.patch
    git apply /tmp/q38-distributed-argmax.patch

The decoded patch SHA-256 must be:

    bd587d91fdea7508f89450d09da795fc5e0ee1d0f2b2698138d8a9d455d0cd3d

Use the accepted reproduction launcher with the candidate build, append
--backend-sampling to llama-server, and export:

    GGML_META_DISTRIBUTED_ARGMAX=1

For the benchmark request, add:

    {"backend_sampling":true}

The complete metrics, binary hashes, result-file hashes, output oracle, build
identity, and runtime settings are in
[the structured packet](../data/2026-08-16-q8-distributed-greedy-argmax-neutral.json).

## Decision

Do not enable this path in the promoted Qwen3.8 package and do not update the
model-board rate. Preserve it as exact mechanism evidence and a closed
optimization door. A future attempt should remove the cross-queue
synchronization or fuse winner selection into an existing final-kernel
dependency; merely moving the same synchronization will not justify another
full suite.
