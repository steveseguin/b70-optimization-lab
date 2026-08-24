# 0d7d5ed0b2 both-current zero-overlay TP1 qualification r1

Date: 2026-08-24. State: **preregistered; not launched.**

## Purpose and boundary

This is the first GPU qualification packet for the literal-current vLLM
`0d7d5ed0b2` build. The 6a9 untreated packet completed as a repeatable
speed-only miss, and its TP1 decision-overlay r1 stopped after the diagnostic;
the audited r2 never launched because vLLM advanced. None of those caches,
decisions, generated outputs, or run roots may enter this packet.

R1 first tests the new both-current image completely untreated. It applies no
source patch, DSO, Triton decision, generated binary, compiled cache, or prior
run artifact. A complete three-arm sequence with every non-speed gate green,
whether it passes every speed floor or closes as a speed-only miss, is required
before TP1 decision compatibility may be re-derived in a separate packet. Only
a fully qualified TP1 result can authorize TP2/TP4 work. The build's
stock-kernel image is retained for separately preregistered attribution if
needed; it is not silently substituted into this packet.

## Frozen runtime and build identity

- vLLM main: `0d7d5ed0b2b61da53f682534f1754fe7d0251a34`, tree
  `32a84ef59ace9ebad6200dd71d658cf986f416f1`, package
  `0.26.1rc1.dev1160+g0d7d5ed0b.xpu`;
- XPU-kernel main: `baaa05bb4e92901219a5a072dd63f2474896f6d1`, tree
  `e7e7d1063f232a383c98c1820cebb94c45b4906e`, package
  `0.1.dev1+gbaaa05bb4`;
- official nightly base/index digest:
  `sha256:3ee0ec37825cc03e866a75198e6fee2a201efb68a717852ed35737a3ae59f876`;
- stock-kernel image, retained but not run here:
  `sha256:38ec94fd09ec93e4e698aefcf02e0db37ff54c964db2ca42175db52886d14662`;
- both-current zero-overlay image:
  `sha256:bbaa702fa0fd4e1d2b9e178a61747657ec35fa5dc83655903f13925a8b83c23d`;
- build receipt SHA-256:
  `3fb8db843817624948833e53d49f41839a63703502649c9151be1c1b18e38c2e`;
- strict runner SHA-256:
  `ec86caef12471185b849a91695fd9dd9fa1e4786771b5ee717c40ff2fae24ecb`;
- hardware runner SHA-256:
  `8038015b179048662f53d7d41ead6cddc95671081942444f394d6e48ed57a6f7`;
- kernel-delta classifier and test SHA-256:
  `fef74bdb90b82fdf543be6ea36320b308aff0d0c146a3c92bcbfff334b70d1b0`
  and `b21befd70003b710027303e093915c36ce88d8fcd4eda66facfd549057e5474b`;
- host kernel and boot: `7.0.0-30-generic`,
  `086de284-0771-4269-9cb2-e064fe303e40`.

The build receipt, archived wheel, installed package, image labels, and static
import receipts must all bind the upstream optimization asset at
`vllm/model_executor/determinism/batch_invariant_configs.py` to SHA-256
`e47b18d9394c61fd105e4db51108d72fe1e68d4a2043a8ba62c0af0237453128`.
The archived wheel must also contain `determinism/__init__.py` and
`determinism/batch_invariant.py`, and must not contain either former
`model_executor/layers/batch_invariant*.py` member. Any mismatch stops before
hardware work.

## Protected performance and overlay contract

The complete protected-performance subobject remains canonical SHA-256
`e6ee2cb9908ce940087788243eac5b544c0d2831b94efa47fe6441232c740e8f`.
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
Both stay disabled and unapplied. The old TP1 38-decision candidate is evidence
only and is not an input. A slower 0d7 result is regression evidence, never
permission to overwrite a frontier.

## Frozen benchmark and quality sequence

The wrapper runs exactly once, atomically, in this order:

1. fresh-cache TP1/MTP0/F16/32K/XPU-Graph diagnostic on port `19792`, with
   the unchanged `30.2178 tok/s` floor;
2. same-cache strict natural-EOS quality replay A on port `19793`, with the
   unchanged `30.31067504052998 tok/s` floor;
3. same-cache strict natural-EOS replay B on port `19794`, with the same floor.

Every arm uses the exact both-current image, GPU 0, one request,
`FULL_AND_PIECEWISE` graph capture sizes `[1,2]`, `PYTHONHASHSEED=0`, F16 KV,
MTP off, cache-zero requests, and the fixed 25-prompt realistic suite. Primary
speed is the conventional median over the 99 inter-token intervals between
generated events 1 and 100 after TTFT. Replay A retains all seven exact cases,
the 8/8 one-hash repeat, 8K needle, 24 baseline comparisons, and full token IDs.

The ext4 cache begins absent and is created only by the diagnostic. Its complete
manifest must remain byte-identical through both strict replays. No cache or arm
may resume. Any non-speed failure stops immediately and seals the cause. A speed
miss is recorded without weakening any non-speed gate and does not short-circuit
the remaining arms; all three arms run whenever the non-speed gates stay green.

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
/home/steve/qwen38-current-main-runs/postreboot-hardware-gate-0d7d5ed0b2-20260824-086de284-venvlib-r1
/home/steve/qwen38-current-main-runs/tp1-untreated-0d7d5ed0b2-20260824-r1
```

At preregistration, both roots are absent, ports `19792`-`19794` are free, no
container or vLLM server is running, and root free space is `16,227,156 KiB`,
above the frozen `12,582,912 KiB` launch floor. The wrapper must recheck all of
these at launch. It holds the Muse lock, host lock, and all four GPU leases
across the hardware gate and every arm. There is no internal retry, overwrite,
partial-arm mode, or resume.

## Frozen interpretations and next gate

- Any complete three-arm sequence with every non-speed gate green authorizes a
  separately preregistered census of exact relative-path plus embedded
  `configs_hash` compatibility for a fresh TP1 decision packet.
- Passing all three speed gates additionally qualifies this exact 0d7
  both-current zero-overlay TP1 profile and can authorize TP2/TP4 after any
  required TP1 overlay closes. A completed speed-only miss authorizes only the
  separately versioned TP1 attribution/decision-compatibility decision; it does
  not authorize TP2/TP4 or lower a floor.
- An engine-upstream or nightly move closes 0d7 stale and requires a newest-head
  rebuild. A remote-only lab move after launch is non-gating under the frozen
  local snapshot; a local lab mutation remains terminal.
- Any other outcome is incomplete or rejected evidence under its exact cause.

After untreated TP1 and any required TP1 overlay close, proceed to TP2
zero-overlay and then a fresh 78-decision compatibility remap. TP4 follows with
zero-overlay and a fresh 152-decision remap. TP>1 MTP is retested only after the
target-only topology gate; it is not inferred fixed from the CUDA-only upstream
workspace change. Website matrix expansion remains the campaign outcome, while
optional corruption instrumentation and upstream reporting stay deferred.
