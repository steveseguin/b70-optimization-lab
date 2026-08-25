# b2dd9ce73d both-current zero-overlay TP1 qualification r1

Date: 2026-08-24. State: **preregistered; not launched.**

## Purpose and boundary

This is the first GPU qualification packet for the literal-current vLLM
`b2dd9ce73d` build. The 7ca predecessor closed failed-incomplete: its fresh
diagnostic completed all 25 rows, but its mandatory post-workload freshness
check detected a newer vLLM head and exited 5 before the diagnostic speed-gate
file, cache normalization, replay A, or replay B. A read-only closeout audit
found `vllm/dummy_cache` absent. 7ca changed no protected frontier and
authorized no decision or higher-topology packet. Its cache, decisions,
generated outputs, and run roots may not enter this packet.

R1 first tests the new both-current image completely untreated. It applies no
source patch, DSO, Triton decision, generated binary, compiled cache, or prior
run artifact. A complete three-arm sequence with every non-speed gate green,
whether it passes every speed floor or closes as a speed-only miss, is required
before TP1 decision compatibility may be re-derived in a separate packet. Only
a fully qualified TP1 result can authorize TP2/TP4 work. The build's
stock-kernel image is retained for separately preregistered attribution if
needed; it is not silently substituted into this packet.

## Frozen runtime and build identity

- vLLM main: `b2dd9ce73dce2ad09007d1db5c171454118981d7`, tree
  `65c93c14916a9a895c5592b8a0ba2803efc96346`, package
  `0.26.1rc1.dev1172+gb2dd9ce73.xpu`;
- XPU-kernel main: `1e90ffa672ba02f17a909da11838a4c55b199783`, tree
  `b3cf7a800eea50e0d0f6140c1c2047a074a7fcb9`, package
  `0.1.dev1+g1e90ffa67`;
- official nightly base/index digest:
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`;
- lab build commit and tree: `52a4d01c588472fc06694efe78026cfbbb110bfe`,
  `25efbd429cf54e28e58e4403c85fb1f2399ea2c3`;
- stock-kernel image, retained but not run here:
  `sha256:a07fca9185f67bb3ccce0d56e2a7be7edc98b0bc90cd98d4c24df13faa8cf6b7`;
- both-current zero-overlay image:
  `sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296`;
- vLLM wheel and source-archive SHA-256:
  `9b59f828266d135dcd1fdf4c868cc3ece0e90cbf393556ae9a61ca5e03b35feb`
  and `063d303afd4ae834b63b7f3d24245c013be937d81146010511dd183b1711dec8`;
- build receipt SHA-256:
  `d56dc84c1137d741042b2e295c6b1f6a40bf28a3c56e0c52761dd725e3a5caa0`;
- 14-file archive manifest and frozen source-identity SHA-256:
  `67d13159a6ec66f1bd17288bef07632be09f963419252f50d47208dc99869997`
  and `2a0ee74968dd68ba15b31eeef3e404807d125e6e52a0e96d25e8b955bd4ae0a0`;
- sealed storage-rotation record SHA-256:
  `60a3961d2d1ab007101d5a61794db9ff9e32ea8542594402fa958dbf89654b90`;
- builder and Dockerfile SHA-256:
  `fbc431ed3ee7d5abbf2b952f6733341171b3b84214b0e9cee7d3e052ea404d59`
  and `440da02c5438ce76da10e49f665ea9bb3dff6cf1a5c5e2accab2b0612e0e6ead`;
- XPU-kernel wheel SHA-256:
  `f3d999060c11ad6db5b4033d50d19c6b665492380075480d041ec4ee58fdfeb6`;
- reused Rust extension and frontend SHA-256:
  `7cb3df775d2183d2c1a7d3025a8f49b9a79548d157993969fc0c49f46c725c52`
  and `a415187153b2a8b10683494c7b22472158b487c69023713313542d4bc09c4c92`;
- stock and both-current static-preflight SHA-256:
  `ffe674d972ab2f97404d8461d934e6933872b07da52df8de2208678f8ed56949`
  and `27de929702874236160ba59ff7ec69de54b3f79e7d12fbfd792360e739193f09`;
- strict runner SHA-256:
  `ec86caef12471185b849a91695fd9dd9fa1e4786771b5ee717c40ff2fae24ecb`;
- hardware runner SHA-256:
  `8038015b179048662f53d7d41ead6cddc95671081942444f394c6e48ed57a6f7`;
- kernel-delta classifier and test SHA-256:
  `fef74bdb90b82fdf543be6ea36320b308aff0d0c146a3c92bcbfff334b70d1b0`
  and `b21befd70003b710027303e093915c36ce88d8fcd4eda66facfd549057e5474b`;
- host kernel and boot: `7.0.0-30-generic`,
  `086de284-0771-4269-9cb2-e064fe303e40`.

The build receipt, archived wheel, package receipts, image labels, and static
import receipts bind the upstream optimization asset at
`vllm/model_executor/determinism/batch_invariant_configs.py` to SHA-256
`e47b18d9394c61fd105e4db51108d72fe1e68d4a2043a8ba62c0af0237453128`.
The archived wheel contains `determinism/__init__.py`,
`determinism/batch_invariant.py`, `models/qwen3_5.py`, and
`models/qwen3_5_mtp.py`, and contains neither former
`model_executor/layers/batch_invariant*.py` member. The builder's static gates,
receipt equality check, and complete 14-file archive checksum battery passed.
That static result does not waive ordinary model-load, runtime-source, canary,
quality, graph, or performance gates.

The storage record is
[`2026-08-24-qwen38-09fd-1e90-prebuild-storage-rotation.json`](../data/2026-08-24-qwen38-09fd-1e90-prebuild-storage-rotation.json)
at `60a3961d2d1ab007101d5a61794db9ff9e32ea8542594402fa958dbf89654b90`.
It proves the prebuild archive-before-delete rotation preserved every captured
speed and both accepted decision bundles, removed only three exact superseded
or unqualified image IDs plus two archived build roots, and had zero running
containers before and after. It predates the b2dd build and is not evidence
about b2dd image retention; the wrapper verifies both exact b2dd IDs itself.

The predecessor inputs are the immutable 7ca closure record at SHA-256
`a0bf4971bf42276b198547b04bb183bbfc8372058b673b7082d49270da851d37`
and its paired note at
`b83aabd9d2b72f8b0c80a6162fe24059e4992ac1fe4338acc6def3cfa4464331`.
Their classification is
`failed-incomplete-stale-during-control-fresh-diagnostic-postflight`;
they are evidence-only frozen inputs, never a reusable cache or qualification.

## b2dd upstream provenance

B2dd is nine vLLM commits after 7ca. The range adds CI reporting and timeout
changes, BailingMoeV3 and LFM2-VL fixes, an XD-RoPE multimodal prefix-cache
fix, Qwen3-Next fused QK-norm/MRoPE work, sparse-MLA XPU metadata
synchronization, a NIXL/Mamba ordering fix, and a routed-experts docstring-only
change. The bounded path review found no direct modification to this lane's
`qwen3_5.py`, `qwen3_5_mtp.py`, batch-invariance configuration, XPU graph
capture, or dense Qwen3.5 target path. Prefix caching and multimodal inputs are
disabled here; Qwen3-Next is not this model and its new optimized path is
CUDA-only; sparse MLA is not this dense Qwen3.5 attention path. Kernel 1e90 is
the direct successor to baaa and changes paged-decode work splitting for head
dimensions 512 and 576, while this model uses head dimension 256. The DSO and
complete source identity are still different, so model-load, quality, graph,
and performance gates remain mandatory.

## Protected performance and overlay contract

The complete protected-performance subobject remains canonical SHA-256
`e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f`;
the whole protected manifest remains
`4eb3eeb81e40099a64ba0444743074e6b044295ff566c1abc11d864902abb454`.
The following list is deliberately non-exhaustive; the canonical subobject also
protects every dated support value, including the stock TP4 strict
`71.9001988117144 tok/s` high and qualified 0ecc TP1 strict
`30.324297716696414 / 30.325970521145816 tok/s` pair. In particular, this
packet may not lower or relabel:

- TP1 diagnostic/high `30.2178 / 30.2569 tok/s` and strict floor
  `30.31067504052998 tok/s`;
- TP2 diagnostic/high `48.8301 / 48.950458800865434 tok/s` and strict floor
  `49.01965141150585 tok/s`;
- TP4 diagnostic/high `71.5488 / 71.6741 tok/s`, strict floor
  `71.29326283364946 tok/s`, or repeat-high requirement
  `71.39843006187554 tok/s`;
- the TP2 decision-overlay observations
  `49.05894025767351 / 49.00935245117815 tok/s`;
- the accepted TP4 decision-overlay observations
  `71.72254506718171 / 71.35287190161719 / 71.45427094575045 tok/s`.

The preserved TP2 78-decision bundle must remain exact at manifest SHA-256
`65c574c24d24804d250e5179e9a202ec9e77e8c5740cea121b7660d8ee854757`.
The accepted TP4 152-decision bundle must remain exact at
`a2df36339567d2619e024351deeca98970ebf92497db0148eac0de7dd5df3ba2`.
Both stay disabled and unapplied. The old TP1 decision candidate is evidence
only and is not an input. A slower b2dd result is regression evidence, never
permission to overwrite a frontier.

## Frozen benchmark and quality sequence

The wrapper runs exactly once, atomically, in this order:

1. fresh-cache TP1/MTP0/F16/32K/XPU-Graph diagnostic on port `19812`, with
   the unchanged `30.2178 tok/s` floor;
2. same-cache strict natural-EOS quality replay A on port `19813`, with the
   unchanged `30.31067504052998 tok/s` floor;
3. same-cache strict natural-EOS replay B on port `19814`, with the same floor.

Every arm uses the exact both-current image, GPU 0, one request,
`FULL_AND_PIECEWISE` graph capture sizes `[1,2]`, `PYTHONHASHSEED=0`, F16 KV,
MTP off, cache-zero requests, and the fixed 25-prompt realistic suite. Primary
speed is the conventional median over the 99 inter-token intervals between
generated events 1 and 100 after TTFT. Replay A retains all seven exact cases,
the 8/8 one-hash repeat, 8K needle, 24 baseline comparisons, and full token IDs.
Batch-sharded sampling remains at its exact-source default `false` and is never
enabled. No batch-invariance mode, prior decision, or prior cache is imported.

A speed miss is recorded without weakening any non-speed gate and does not
short-circuit later arms; all three arms run whenever the non-speed gates stay
green. No cache or arm may resume.

## Preserved cache normalization

The ext4 control-cache root begins absent and is created only by the diagnostic.
After the fresh workload and arm cleanup pass, but before the packet's
canonical regular-file and directory manifests are frozen, the wrapper must:

1. assert `control-cache/vllm/dummy_cache` is absent and not a symlink;
2. create exactly that directory as a real `root:root` mode-0755 directory;
3. verify it is empty and contains no file, symlink, or special node;
4. freeze the successor's complete regular-file and directory manifests, and
   require the regular-file manifest to be byte-identical to the diagnostic's
   sealed post-workload file manifest;
5. require both canonical manifests to remain exact before and after replay A
   and replay B, while separately requiring `dummy_cache` to remain real,
   root-owned, mode 0755, and empty.

This normalization is unchanged from the audited 7ca wrapper. It creates no
regular file, imports no cache content, changes no server argument or timed
workload, and does not weaken full-tree immutability. If upstream creates the
directory earlier, changes its ownership/mode, or places anything in it, the
packet fails closed rather than adapting the rule.

## Preserved stale provenance classification

The shared strict runner and all source-freshness gates remain unchanged. The
wrapper retains the 7ca reporting-only classification: when an arm exits
exactly 5 and its sealed `final.status` is exactly `stale-before-promotion`, it
records a semantic failure reason containing that arm and exit code before the
ordinary campaign failure seal runs. Exit 5 with a missing or different status,
or any other unrecognized nonzero pair, receives an explicit unrecognized-exit
reason and still fails closed. It does not turn stale evidence into a pass,
skip an arm, change freshness policy, or alter performance behavior.

## Hardware, model, source, and repository gates

Before the model arms, the exact fourteen-test corrected-root-NVMe classifier
battery and fresh hardware gate must pass. The gate retains four-device
identity/compute, peer read, four-rank XCCL all-reduce, coherent runtime,
SMART/ext4/root-NVMe checks, raw journal preservation, taint, selector/mask,
lock handoff, repo postflight, and cleanup. At most one exact known 21-line
corrected Samsung root-NVMe block is separately classifiable; any mutation,
fragment, second block, Xe/GPU event, reset, timeout, filesystem error, or other
reject line fails closed.

Every arm directly and ordinarily verifies all 19 model files, uses the exact
receipt/image/source identity, returns exact canary `14` with zero cached
tokens, and leaves no container, listener, process group, or render-node holder.
Live vLLM, XPU-kernel, and nightly identities are hard gates before and after
every arm.

At launch, the lab tree must be clean `main`, equal to its local tracking ref
and live `origin/main`. The wrapper then freezes that exact local commit in its
immutable input snapshot. During the atomic window the shared runner uses
`LAB_REMOTE_FRESHNESS_POLICY=frozen-local`: local status, branch, commit, frozen
inputs, hardware evidence, and engine upstreams remain hard gates, while an
unrelated later remote-only lab documentation push is recorded at close and is
not allowed to invalidate otherwise immutable running evidence. No local agent
may edit, commit, switch, or mutate this repository during the campaign.

## Atomic cap and fresh roots

R1 may be invoked once only as `...qualification.sh all`, using these exact
non-overridable roots:

```text
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-b2dd9ce73d-20260824-086de284-venvlib-r1
/home/steve/qwen38-current-main-runs/tp1-untreated-b2dd9ce73d-20260824-r1
```

At initial packet drafting both roots were absent and ports `19812`-`19814`
were free. A read-only post-build check measured `17,226,896 KiB` root free,
above the unchanged `12,582,912 KiB` launch floor. The prebuild storage record
preserves all protected evidence and documents zero running containers before
and after that rotation; it does not replace the wrapper's live checks. The
wrapper must recheck both exact image IDs, roots, ports, capacity, containers,
processes, source freshness, and every other preflight immediately at launch.
It holds the Muse lock, host lock, and all four GPU leases across the hardware
gate and every arm. There is no internal retry, overwrite, partial-arm mode,
or resume.

## Frozen interpretations and next gate

- Any complete three-arm sequence with every non-speed gate green authorizes a
  separately preregistered census of exact relative-path plus embedded
  `configs_hash` compatibility for a fresh TP1 decision packet.
- Passing all three speed gates additionally qualifies this exact b2dd
  both-current zero-overlay TP1 profile and can authorize TP2/TP4 after any
  required TP1 overlay closes. A completed speed-only miss authorizes only the
  separately versioned TP1 attribution/decision-compatibility decision; it does
  not authorize TP2/TP4 or lower a floor.
- An engine-upstream or nightly move closes b2dd stale and requires a newest-head
  rebuild. A remote-only lab move after launch is non-gating under the frozen
  local snapshot; a local lab mutation remains terminal.
- A `dummy_cache` precreation mismatch or later cache file/directory divergence
  is a non-speed failure. It may not be waived as expected upstream behavior.
- Any other outcome is incomplete or rejected evidence under its exact cause.

After untreated TP1 and any required TP1 overlay close, proceed to TP2
zero-overlay and then a fresh 78-decision compatibility remap. TP4 follows with
zero-overlay and a fresh 152-decision remap. TP>1 MTP is retested only after the
target-only topology gate. Website matrix expansion remains the campaign
outcome; optional corruption instrumentation and upstream reporting stay
deferred.
