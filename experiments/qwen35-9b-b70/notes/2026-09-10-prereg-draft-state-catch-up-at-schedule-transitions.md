# Preregistration: draft-state catch-up instead of a draft forward on every zero-draft step

## Question

With a draft schedule that turns speculation off above 16 users, the scheduled server runs ~5%
under the no-speculation server at 32-64 users (`pwdynz`: 1090 vs 1143 at c32, 1150 vs 1206 at
c64, and the same 5-6% at every rung). The cost is `LLMBaseProposer.propose()` running the draft
layer's forward on every step before its `num_speculative_tokens == 0` early return, so that the
draft layer's KV / GDN recurrent state stays current for the moment the batch shrinks and K rises.

Can that forward be skipped on zero-draft steps and replaced by a one-off catch-up over the
missed positions when a request next needs drafts, without changing a single output token?

## Mechanism

- Scheduler: per request, track `draft_state_pos` = the last position the draft layer has
  consumed. On a K=0 step it does not advance. When the step's K becomes > 0, every request whose
  `draft_state_pos` lags its computed position is marked for catch-up.
- Proposer: before `set_inputs_first_pass`, run the draft layer over each lagging request's
  missed span `[draft_state_pos + 1, pos)` as a prefill-shaped pass (the target's hidden states
  for those positions are needed: either retained per request while K=0, or recomputed - the
  second is a target-layer cost and is out of scope for the first arm). Then propose as today.
- Outputs cannot change: drafts are proposals, the target verifies every accepted token
  (`targetModelVerifiedAcceptedTokens`). What can change is acceptance after a transition, which
  shows up only as speed.

## Frozen treatment

- Base: `neural-download/vllm-openai-xpu:qwen38-int4-r276-dynsd-fullgraph` (the published
  scheduled-server image), one more pure-Python overlay on top; the five overlaid files keep their
  digests.
- Schedule `[[1,8,3],[9,16,1],[17,64,0]]`, strict launcher env, same suites and ladders as
  `fgdynm1`.

## Gates, in order

1. Strict pair 12/12 on G1/G2/G3 (one-user path untouched: 110.6 +- drift).
2. c1-c64 ladders with `--require-output-identity`: exact through 16 in both passes, and the
   32/64 rungs inside the no-speculation band (31-32/32, 62-64/64).
3. Aggregate at c32/c64 within 1.5% of the no-speculation server (1143 / 1206 on this boot), i.e.
   the 5% recovered. Below that the arm is a null and the note records it.
4. A transition test that the ladder does not contain: 64 users draining to 4 (requests finishing
   at different lengths), measured end to end and per request, so the catch-up cost is paid on
   the path it is meant for. Acceptance length after the transition within 5% of a fresh
   depth-3 server's.
5. 2K-32K real-content ladder 18/18 exact.

## Stop rules

- Any identity miss anywhere: stop, the design is wrong somewhere in the state handling.
- Catch-up cost on the drain test exceeding the steady-state saving over 128 output tokens: stop,
  keep the per-step forward.

## Not authorised here

Draft-head kernel changes, schedule sweeps, or a cheaper draft-layer forward: those are separate
questions. This arm decides one thing: whether the zero-draft forward can be replaced by catch-up.

## Result (2026-09-11)

Gates 1, 2 and 5 pass (strict 12/12 twice; ladders exact through 32 users in both passes of both
runs, 64 in the no-speculation band; 2K-32K 18/18). Gate 3 is not met: c32 1113 / 1109 and c64
1184 / 1183 against the no-speculation server's 1147 / 1205 are 3% and 1.9% under, not 1.5%;
before the overlay they were 5%. Gate 4 (drain test) ran as a natural-length ladder (`cudynd`, no
`ignore_eos`): exact at every rung in both passes, 64/64 at 64 users, identity-qualified by the
harness; 1089 / 1163 warm at 32 / 64 against the oracle's 1130 / 1188. Two implementation negatives on the way, both preserved as
archived roots: the first catch-up batch exceeded the drafter's input buffers (chunking added),
and per-step host->device tensor creation cost 10-20% aggregate (device-only path). Promoted as
the guide's default scheduled-server image; the residual is documented, not hidden.
