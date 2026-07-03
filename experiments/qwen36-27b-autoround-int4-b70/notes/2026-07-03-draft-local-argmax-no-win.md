# 2026-07-03 Draft local-argmax reduction no-win

This experiment tested proposer-side `use_local_argmax_reduction` for
`Intel/Qwen3.6-27B-int4-AutoRound` MTP3 on one B70.

## Patch

Patch artifact:
`patches/qwen36-27b-autoround-int4-b70/vllm-qwen-mtp-get-top-tokens-no-win-20260703.patch`

The patch added `get_top_tokens()` to the active Qwen MTP draft classes:

- `vllm/model_executor/models/qwen3_5_mtp.py` (`Qwen3_5MTP`) -- required by
  this model's active drafter;
- `vllm/model_executor/models/qwen3_next_mtp.py` (`Qwen3NextMTP`) -- same
  interface for the adjacent Qwen3.6 Next MTP class.

The candidate was launched with:

```bash
QWEN36_27B_ENABLE_MTP=0 \
VLLM_EXTRA_ARGS='--speculative-config {"method":"qwen3_next_mtp","num_speculative_tokens":3,"use_local_argmax_reduction":true}' \
scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

The first launch failed before readiness because only `Qwen3NextMTP` had been
patched, while the runtime active draft class was `Qwen3_5MTP`:

```text
ValueError: use_local_argmax_reduction is enabled but draft model Qwen3_5MTP does not implement get_top_tokens().
```

After patching `Qwen3_5MTP`, the server log confirmed the path was active:

```text
Using local argmax reduction for draft token generation (communication: O(2*tp_size) vs O(vocab_size)).
```

## Results

Single strict run:

- file:
  `data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-draftlocalargmax-realistic128-chat-tokenids-qwensuite-20260703T112005Z.json`;
- strict fresh gate passed, `cached_tokens=0`;
- median `53.23708215473174 tok/s`, p10 `48.15080672332966`, mean
  `54.47978198678919`.

This was within the known same-recipe variance band, so it was not enough to
decide. Baseline replay variance before this test:

- rows: `54.861`, `53.992`, `53.522`, `53.608 tok/s`;
- mean `53.99584685782235`, stdev `0.6119857889353565`, range `2.48%` of mean.

Same-window GPU crossover:

| wave | lane | GPU | median tok/s | status |
| --- | --- | ---: | ---: | --- |
| 1 | control | 1 | `53.02176645851218` | pass, cached0 |
| 1 | candidate | 2 | `53.13250987571284` | pass, cached0 |
| 1 | candidate | 3 | `52.940718791436524` | pass, cached0 |
| 2 | candidate | 1 | `52.84480172428497` | pass, cached0 |
| 2 | control | 2 | `53.05857607133146` | pass, cached0 |
| 2 | control | 3 | `52.978319261221316` | pass, cached0 |

Combined same-window means:

- controls: `53.01955393035499 tok/s`;
- candidates: `52.97267679714478 tok/s`;
- candidate delta: `-0.08841480121049017%`.

Decision: **no-win / flat**. The effect is far below the observed variance
floor and does not justify keeping the patch active.

## GPU0 note

The long-lived GPU0 control server on port `19410` was probed during this
same-window test and hit:

```text
RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)
```

Do not use that failed live-server attempt in performance comparisons. Future
baseline reconfirmation should start a fresh server after confirming the device
is healthy.

## Interpretation

Like exact target argmax-only verification, draft local-argmax reduction does
not move the TP1 result because `get_top_tokens()` still pays the LM-head work.
The real bottleneck remains the AutoRound/INC LM-head top-1 / verifier cost,
not communication or sampler plumbing.
