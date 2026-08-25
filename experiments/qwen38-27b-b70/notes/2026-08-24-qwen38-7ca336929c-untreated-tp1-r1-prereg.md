# 7ca336929c both-current zero-overlay TP1 qualification r1

Date: 2026-08-24. State: **preregistered; not launched.**

## Purpose and boundary

This is the first GPU qualification packet for the literal-current vLLM
`7ca336929c` build. The d154 predecessor closed failed-incomplete: its fresh
diagnostic passed, strict replay A completed a fast, quality-clean workload but
detected a newer vLLM head at postflight, and replay B never started. Post-close
audit also found that replay A added one expected empty `vllm/dummy_cache`
directory after the directory manifest had been frozen. D154 changed no
protected frontier and authorized no decision or higher-topology packet. Its
cache, decisions, generated outputs, and run roots may not enter this packet.

R1 first tests the new both-current image completely untreated. It applies no
source patch, DSO, Triton decision, generated binary, compiled cache, or prior
run artifact. A complete three-arm sequence with every non-speed gate green,
whether it passes every speed floor or closes as a speed-only miss, is required
before TP1 decision compatibility may be re-derived in a separate packet. Only
a fully qualified TP1 result can authorize TP2/TP4 work. The build's
stock-kernel image is retained for separately preregistered attribution if
needed; it is not silently substituted into this packet.

## Frozen runtime and build identity

- vLLM main: `7ca336929c169fee1210dd5293029d78811fba27`, tree
  `af3fde0a669bcd73274ff9e2cfd410ea69c92ee6`, package
  `0.26.1rc1.dev1163+g7ca336929.xpu`;
- XPU-kernel main: `baaa05bb4e92901219a5a072dd63f2474896f6d1`, tree
  `e7e7d1063f232a383c98c1820cebb94c45b4906e`, package
  `0.1.dev1+gbaaa05bb4`;
- official nightly base/index digest:
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`;
- lab build commit and tree: `52a84620b4244a0e685b768f213c5de744ca21ac`,
  `023cf954e3c0cf43f09f40d8d2ca0996fb85f262`;
- stock-kernel image, retained but not run here:
  `sha256:6043c332c753604a827f75c07f480998c1330e9e722b3120a8e6b3c47f74fc6c`;
- both-current zero-overlay image:
  `sha256:b7bc798035552130e96f3649c21541f1b40fa3c5db0558631e44e461297196a4`;
- vLLM wheel and source-archive SHA-256:
  `84c3a92c9ae421e153a835cd6b66a73f3dc4b6f0317097b29650fbcc7bda6abd`
  and `cd02fc69f71c422faf4d1b40631ae34194a442b2f370af5a7c335f688171f760`;
- build receipt SHA-256:
  `e090d5a7694ffa6f595d84e6adc38a3da6cd33020e5c7f4d96ae678ecd146622`;
- 14-file archive manifest and frozen source-identity SHA-256:
  `6f146518cf10167c7d34e8ca6dab1b133bb6cbca698984917cff72f97ef30863`
  and `e215141578bd8abd16edda382be622a2af00597e7f319910a66cd089904e8cf0`;
- sealed storage-rotation record SHA-256:
  `ed5d77bb12910ceaf0121c905ed6b597976a743f0e0eec4cc69f857f1622eab0`;
- builder and Dockerfile SHA-256:
  `cb1260b00c877420bd847adcebd022504b6ed58643ec8c5740ff8336dd8f549a`
  and `440da02c5438ce76da10e49f665ea9bb3dff6cf1a5c5e2accab2b0612e0e6ead`;
- XPU-kernel wheel SHA-256:
  `7b886fa814469aef8904118729f31f2fe77559f3c5219bd0ecf799a904387483`;
- reused Rust extension and frontend SHA-256:
  `7cb3df775d2183d2c1a7d3025a8f49b9a79548d157993969fc0c49f46c725c52`
  and `a415187153b2a8b10683494c7b22472158b487c69023713313542d4bc09c4c92`;
- stock and both-current static-preflight SHA-256:
  `010cd0b04b372c8b7db534a21dd032fc3dbcad00f60b7ec2e3c65d8062023e53`
  and `10a8696060b483dd6ab30e6857964d789f3379e9247612287d8303bb730d529e`;
- strict runner SHA-256:
  `ec86caef12471185b849a91695fd9dd9fa1e4786771b5ee717c40ff2fae24ecb`;
- hardware runner SHA-256:
  `8038015b179048662f53d7d41ead6cddc95671081942444f394c6e48ed57a6f7`;
- kernel-delta classifier and test SHA-256:
  `fef74bdb90b82fdf543be6ea36320b308aff0d0c146a3c92bcbfff334b70d1b0`
  and `b21befd70003b710027303e093915c36ce88d8fcd4eda66facfd549057e5474b`;
- host kernel and boot: `7.0.0-30-generic`,
  `086de284-0771-4269-9cb2-e064fe303e40`.

The build receipt, archived wheel, installed package, image labels, and static
import receipts bind the upstream optimization asset at
`vllm/model_executor/determinism/batch_invariant_configs.py` to SHA-256
`e47b18d9394c61fd105e4db51108d72fe1e68d4a2043a8ba62c0af0237453128`.
The archived wheel contains `determinism/__init__.py`,
`determinism/batch_invariant.py`, `models/qwen3_5.py`, and
`models/qwen3_5_mtp.py`, and contains neither former
`model_executor/layers/batch_invariant*.py` member. The independent complete
source/wheel/receipt artifact audit passed and is durably acknowledged by the
sealed storage-rotation record. That static result does not waive ordinary
model-load, runtime-source, canary, quality, or performance gates.

The storage record is
[`2026-08-24-qwen38-d154d90d6c-storage-rotation.json`](../data/2026-08-24-qwen38-d154d90d6c-storage-rotation.json)
at `ed5d77bb12910ceaf0121c905ed6b597976a743f0e0eec4cc69f857f1622eab0`.
It proves the two exact d154 image IDs were removed only after external evidence
and the successor audit passed, both 7ca images remained exact, running
containers were zero before and after, and protected performance/overlay and
runtime/launcher state did not change.

The predecessor inputs are the immutable d154 closure record at SHA-256
`00a2ced82c7787417a1e7205323ffdb530da3d84b9092939501727c85392de37`
and its paired note at
`9c176d2eb3fe33741c55bac53745b2b8b3784d6c336a85fa2ce2e6e04dad9eb4`.
Their classification is
`failed-incomplete-stale-during-strict-replay-a-postflight-with-posthoc-cache-directory-divergence`;
they are evidence-only frozen inputs, never a reusable cache or qualification.

## 7ca upstream provenance

7ca is the direct child of `a0f1b9ad`, itself the direct child of d154. A0f
changes one CI-test tolerance. The 7ca commit removes ten deprecated model
architectures and associated registrations, tests, examples, and docs: 46
changed paths, 49 insertions, and 6,620 deletions relative to a0f. The direct
path diff does not touch Qwen3.5, Qwen3.5-MTP, determinism/batch invariance, or
XPU source files. The independent artifact audit confirmed the static packet;
model-load and quality gates remain mandatory.

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
only and is not an input. A slower 7ca result is regression evidence, never
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

## Successor-only cache normalization

The ext4 control-cache root begins absent and is created only by the diagnostic.
After the fresh workload and arm cleanup pass, but before the successor's
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

This normalization is the only cache-harness change. It creates no regular
file, imports no cache content, changes no server argument or timed workload,
and does not weaken full-tree immutability. If upstream creates the directory
earlier, changes its ownership/mode, or places anything in it, the packet fails
closed rather than adapting the rule.

## Successor-only stale provenance classification

The shared strict runner and all source-freshness gates remain unchanged. The
successor wrapper may add one reporting-only classification: when an arm exits
exactly 5 and its sealed `final.status` is exactly `stale-before-promotion`, it
records a semantic failure reason containing that arm and exit code before the
ordinary campaign failure seal runs. Exit 5 with a missing or different status,
or any other unrecognized nonzero pair, receives an explicit unrecognized-exit
reason and still fails closed. This fixes the d154 outer label
`unclassified wrapper or command failure`; it does not turn stale evidence into
a pass, skip an arm, change freshness policy, or alter performance behavior.

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
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-7ca336929c-20260824-086de284-venvlib-r1
/home/steve/qwen38-current-main-runs/tp1-untreated-7ca336929c-20260824-r1
```

At initial packet drafting both roots were absent and ports `19812`-`19814`
were free. The subsequent sealed storage rotation records zero running
containers before and after, both 7ca image IDs retained, and root free space
restored to `14,081,388 KiB`, above the unchanged `12,582,912 KiB` launch
floor. The capacity, privileged container-idle, and independent artifact-audit
preconditions are closed. The wrapper must recheck roots, ports, capacity,
containers, processes, source freshness, and every other preflight immediately
at launch. It holds the Muse lock, host lock, and all four GPU leases across the
hardware gate and every arm. There is no internal retry, overwrite, partial-arm
mode, or resume.

## Frozen interpretations and next gate

- Any complete three-arm sequence with every non-speed gate green authorizes a
  separately preregistered census of exact relative-path plus embedded
  `configs_hash` compatibility for a fresh TP1 decision packet.
- Passing all three speed gates additionally qualifies this exact 7ca
  both-current zero-overlay TP1 profile and can authorize TP2/TP4 after any
  required TP1 overlay closes. A completed speed-only miss authorizes only the
  separately versioned TP1 attribution/decision-compatibility decision; it does
  not authorize TP2/TP4 or lower a floor.
- An engine-upstream or nightly move closes 7ca stale and requires a newest-head
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
