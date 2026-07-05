# 2026-07-05 - Draft INT4 GDN state: prefix-count and native serial flags no-win

## Context

Target lane: `webhie/Qwen3.6-27B-int4-AutoRound` on one B70 with the current
record-family target runtime INT8 LM-head BF16 scales plus draft INT4 LM-head
(`VLLM_XPU_DRAFT_LM_HEAD_INT4=1`, group 128, BF16 scales), MTP3, graph off, and
`--no-async-scheduling` for state debugging.

The fast draft-INT4 path has a real throughput signal, but normal native GDN
state handling is invalid on repeat quality: partial reject / block reuse can
drop or double-process the state boundary. ReplaySSM fixes quality but falls to
about `62 tok/s`, below the current valid `65.276 tok/s` webhie/BF16-scale
record.

## Prefix-state-count patch is invalid

Patch snapshot:

- `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-prefix-state-count-invalid-plus-trace-20260705.patch`
- SHA256: `94d9d41f98b6198a143f643d1d41322df34959cf6da0b1bdcaa59e1698de4187`

Result artifact:

- `data/qwen36-27b-autoround-int4-b70-baselines/trace-qwen27-draftint4-prefixstate-nograph-20260705T145553Z`

The patch changed the non-align GDN accepted-state count on partial-reject rows
from the visible accepted output count to the matching draft-prefix length. It
made repeat16 stable and the suite reported `pass_all=true`, but the text was
wrong:

```text
blue, green red yellow
```

Baseline/intent for the color canary is:

```text
blue, green, red, yellow
```

The trace shows rows like `accepted_count=2`, `prefix_count=1`,
`scheduled_spec_ids=[11,3565,11]`, and `accepted_row=[11,5983]`. Selecting the
prefix count chooses a state that is too early; the next verifier row then loses
the comma boundary. This is a stable wrong answer, not a quality fix.

The live vLLM source was cleaned after this run: the prefix-count gate was
removed from `gpu_model_runner.py`; the patch remains only as a preserved
negative artifact.

Important harness lesson: `scripts/qwen36-text-quality-suite.py` checks repeat
hash stability, not an explicit expected color answer. For this lane, focused
probes must use either `--baseline-json` against the current record-family
quality file or an explicit expected-text check so stable wrong text cannot pass.

## Native serial / prefill replay flags did not recover correctness

Probe root:

- `data/qwen36-27b-autoround-int4-b70-baselines/gdn-native-flag-probes-20260705T150308Z`

Common setup:

- model: `webhie/Qwen3.6-27B-int4-AutoRound` snapshot
  `f5750c90b3776db658594df5fe8051098226dd8e`
- `QWEN36_27B_ENABLE_XPU_GRAPH=0`
- `VLLM_EXTRA_ARGS='--no-async-scheduling'`
- `NUM_SPECULATIVE_TOKENS=3`
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`
- `VLLM_XPU_LM_HEAD_INT8=1`
- `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`
- `VLLM_XPU_DRAFT_LM_HEAD_INT4=1`
- `VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128`
- `VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16`
- quality probe: repeat16, skip long context, baseline JSON parity against the
  known webhie INT8-LM-head quality artifact.

Results:

| Label | Extra flags | Outcome |
| --- | --- | --- |
| `serial-basic` | `VLLM_XPU_GDN_NATIVE_SPEC_DECODE_SERIAL=1` | invalid; repeat stable but wrong `blue, green red yellow`; JSON canary malformed. |
| `exact-replay-default` | serial + `PREFILL_SEQUENCE=1`, `PREFILL_OUTPUT_DECODE_STATE=1`, `PREFILL_REPLAY_EXACT_SERIAL_STATE=1`, `PREFILL_EXACT_REPLAY_NATIVE_DECODE=1` | invalid; repeat stable but wrong `blue, green red yellow`; JSON canary malformed. |
| `exact-replay-offset-post` | exact replay plus `PREFILL_EXACT_STATE_OFFSET_PLUS_ONE=1`, `GDN_SPEC_STATE_OFFSET_PLUS_ONE=1`, non-align postprocess enabled, zero-accept backup enabled | invalid; exact cases pass and repeat is stable, but repeat output is `blue, green, red` and baseline parity fails. |
| `prefill-columns-prefixes` | serial + prefill-sequence output replay columns/prefixes | no-win; acceptance collapsed to zero and the probe was stopped before completion. |

No LocalMaxxing submission. No promoted speed claim.

## Current conclusion

Existing environment/config flags do not provide a fast valid normal-MTP GDN
state fix. The remaining credible path is code-level: understand and repair the
native packed `gdn_attention_spec_decode` state-column contract for partial
reject / replacement rows, or build a cheaper exact state-tape/replay path than
ReplaySSM.

Do not repeat:

- prefix-count accepted-state correction;
- scheduler replay / placeholder accounting hacks;
- native serial/prefill replay flag roulette without a new code change or a
  specific trace hypothesis.
