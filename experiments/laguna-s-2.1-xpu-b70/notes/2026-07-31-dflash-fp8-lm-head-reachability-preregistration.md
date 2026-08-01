# Laguna DFlash FP8 draft LM-head reachability preregistration

Date: 2026-07-31 America/Toronto

Status: **preregistered; source integration not yet authorized beyond tests**.

## Premise and reachability finding

The confirmed BF16-KV record is `124.64241272122038 tok/s` conventional and
uses `VLLM_XPU_LAGUNA_DFLASH_FP8_W8A16=1`. Runtime logs prove that all 31
DFlash dense projections are converted to FP8 W8A16, but contain no
`Prepared separate Laguna DFlash FP8 W8A16 draft LM head` marker.

The record source already implements a separate FP8 draft LM head, but attaches
its preparation hook to
`vllm/v1/worker/gpu/spec_decode/dflash/utils.py`. The active XPU runtime uses
`vllm/v1/spec_decode/llm_base_proposer.py`; the record log proves that this
legacy proposer performs the live LM-head sharing. Therefore the existing
draft LM-head optimization is unreachable on the measured path. This is a
source reachability defect, not evidence that the FP8 LM head is fast.

The local TP-sharded draft LM head is a `(25088, 3072)` vocabulary projection
executed for DFlash proposal rows. Unlike the rejected micro-fusions, it is a
large matrix multiply and is therefore eligible for a component gate.

## Frozen candidate design

- start from vLLM
  `58608c6361f1a958a7e933bed0be8c88c35aa26e` and XPU kernels
  `69e8ad9119a9cc70c3906b82be6254dd0160f00e`;
- add a new default-off selector
  `VLLM_XPU_LAGUNA_DFLASH_FP8_LM_HEAD` that requires the existing broad FP8
  DFlash contract;
- after the active legacy proposer shares the target LM head, invoke the
  existing independent draft-head conversion only for the Laguna DFlash
  class;
- fail closed when selected if the live object lacks the hook, the target head
  was not shared, the target is not the expected unquantized bias-free local
  shape, conversion aliases or mutates the target, or the resulting draft head
  lacks the FP8 identity marker;
- emit an unambiguous per-rank runtime marker containing the live proposer and
  head types and local shapes;
- selector-off execution must remain byte-for-byte source-equivalent at the
  call site and retain the shared BF16 target head;
- target model, target precision, BF16 KV, verifier width 12, DFlash depth 11,
  prompts, teacher, sampling, topology, cache and scoring policy remain frozen.

## Gates and stop rules

1. Focused CPU tests must prove selector-off inertness, selector-on invocation
   through the active legacy proposer, target immutability/non-aliasing, and a
   fail-closed missing-hook/type path.
2. On one B70, compare the real local `(25088, 3072)` BF16 incumbent LM-head
   multiply with the existing FP8 W8A16 head for the actual DFlash proposal row
   count. Record absolute medians, output shapes/dtypes, weight identities and
   top-1 agreement. Component output need not be bitwise equal because draft
   proposals are verified by the unchanged target; it must be finite and the
   FP8 path must be materially faster in absolute time.
3. Only if component timing is materially positive may one bounded non-scored
   runtime smoke be run. Require the new marker on all four ranks, non-flat
   draft acceptance, target/draft topology invariants, cache zero, final
   canonical-q1 token/text exactness, and clean teardown.
4. Only if the smoke indicates positive cycle economics may exactly one strict
   cold 13-prompt endpoint leg be run. Report its first valid score even if it
   loses. Require 13/13 token/text exactness, cache zero, target `146/145` and
   draft `14/13` on all four ranks, one invocation per prompt, 72-second
   pre/post idle intervals and all-zero cleanup.
5. Stop immediately on selector ambiguity, target mutation, NaN/Inf, runtime
   identity drift, acceptance collapse, exactness loss, topology drift, host
   instability or teardown failure. No retry, reboot, reset, metric change,
   prompt filtering, warmup, cached/history reuse or LocalMaxxing submission is
   authorized by this preregistration.

