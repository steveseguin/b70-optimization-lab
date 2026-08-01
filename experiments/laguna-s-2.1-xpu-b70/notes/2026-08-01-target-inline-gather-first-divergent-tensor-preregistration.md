# Laguna target inline-gather first-divergent-tensor trace

Date: 2026-08-01 America/Toronto

Status: **preregistered; diagnostic only. No score or speed claim is
authorized.**

## Motivation

The protected BF16-KV record remains `125.4619731637751 tok/s`, 13/13 exact,
with target topology `146/145` and draft topology `14/13`. Capturing a prefix of
24 target all-gathers produces the expected `122/121` target topology but first
changes request-0 output token 331 during the frozen 512-token gate. Prefix 48
is exact for one 512-token request but changes request 1 token 0. These lifetime
results show that slot-local synthetic equality is insufficient; they do not
identify the first model tensor corrupted by replay.

## Diagnostic treatment

Use one new diagnostic vLLM worktree based on the prefix-bisection source. Run
two fresh services from that same source and the protected native kernel build:

- control: target inline gathers off, target topology `146/145`;
- candidate: target inline gathers on with prefix limit 24 and no skipped slot,
  target topology `122/121`.

Both arms retain BF16 KV, width 12, DFlash depth 11, segmented/inline DFlash,
the exact current target stack, the frozen request-0 prompt, and every sampling
parameter. Both arms enable the same parity instrumentation. The probe must be
target-only (`num_hidden_layers == 48`), use an explicit NVMe artifact root,
and select one fixed verifier row consistently for input token, position,
embedding, every layer boundary, detailed layer-0 stages, hidden state, and
logits. It must not disable the layer-0 fused QKNorm/RoPE path unless the
separate return-stage diagnostic is explicitly active.

The known request-0 mismatch is output index 331: candidate token `72` versus
teacher token `372`. That token is produced from verifier row 0 with absolute
position `420` and input token `20253`. Each fresh arm therefore makes exactly
one dump selected by `expected_position=420`, `expected_input_id=20253`, and
`parity_row=0`. Position and input ID select the request call; startup/profile
call counts are not used. The trigger is removed on every success or failure
path. Legacy row `-1` behavior remains unchanged.

## Ordered gate

1. Implement only configurable artifact-root, target-only, fixed-row selection,
   and fused-QKNorm/RoPE preservation when return-stage is unset. Preserve the
   selector-off/default behavior. Pass Ruff, compileall, focused tests, and
   source inspection before any service start.
2. First run the prefix-24 candidate to 340 output tokens. Require the already
   established first mismatch exactly at request-0 token 331, `cached_tokens=0`,
   real speculation, exact `122/121` and `14/13` topology, four complete rank
   packets at position 420/input 20253, and clean teardown. If instrumentation
   removes or moves that mismatch, stop: the probe is perturbative and cannot
   localize this defect.
3. Run the matched selector-off control once from the same diagnostic source.
   Require q=1 exactness through 340 tokens, `146/145` and `14/13`, four complete
   packets at the same position/input, and clean teardown.
4. Search BF16 bit patterns on all ranks in explicit model order: input and
   embedding; for each layer, attention norm/residual, detailed layer-0
   attention stages, attention output, post-attention norm/residual, MLP output,
   layer hidden/residual; then final norm/residual, hidden state, and selected
   logits row. Report the first difference. For layers after 0, an attention or
   MLP boundary names the subpath, not yet its local producer versus collective.
5. If the first position-420 difference indicates earlier KV-state corruption,
   separately preregister fresh one-dump arm pairs at the known preceding cycle
   starts: position/input `(418,405)`, `(414,377)`, then `(412,330)`. Never dump
   an earlier call in the same request because synchronization may mask a race.
6. Any hang, device/collective error, missing execution marker, incomplete
   packet, or dirty teardown stops the experiment. Do not reset, reload,
   unbind, FLR, delete shared memory, or reboot.

## Decision rule

A matched first divergent tensor authorizes one separately preregistered repair
at that boundary. No endpoint integration is authorized by this trace. If the
first difference precedes a captured gather, or the instrumentation changes the
known output failure, close the inline-gather route until a less perturbative
probe exists.
