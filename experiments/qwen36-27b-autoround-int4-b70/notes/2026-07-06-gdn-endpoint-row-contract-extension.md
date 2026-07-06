# 2026-07-06 - GDN accepted-prefix endpoint row contract extension

Status: **contract / test guard only; no throughput claim**.

The current valid Qwen27 record remains
`65.27648650325429 tok/s` for `webhie/Qwen3.6-27B-int4-AutoRound` with runtime
target INT8 LM-head BF16 scales, MTP3/cg8, strict fresh realistic suite, and
`cached_tokens=0`.

After the prefix-base native state-table experiments were closed as invalid, the
next safe implementation step was to make the accepted-prefix state contract
less ambiguous. `scripts/check-gdn-spec-recurrent-exact.py` already verified
that synthetic SSM/conv prefix rows can be committed exactly; it now also checks
the endpoint row semantics that future native GDN/DeltaNet transactions must
honor.

Added endpoint row cases:

- full reject -> commit draft prefix `0`;
- partial reject at position `0` -> commit prefix `0`;
- partial reject after `1` or `2` accepted drafts -> commit only those accepted
  draft rows, not the target-owned replacement;
- full accept with target-owned bonus -> commit `k` draft rows, not `k + 1`;
- draft-only row -> commit the visible accepted draft count;
- shifted full accept -> commit the visible shifted draft prefix;
- suppressed bonus/replacement tails -> do not commit the suppressed
  target-owned tail.

This encodes the key invariant from the runner/sampler audit: the commit count
must be the accepted **draft prefix length**, not the scheduler-visible row
length. Target-owned bonus and replacement tokens are generated from target
logits but are not themselves verifier-row recurrent states.

Validation:

```text
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile scripts/check-gdn-spec-recurrent-exact.py
/home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-spec-recurrent-exact.py --spec-len 3
/home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-spec-recurrent-exact.py --spec-len 4
/home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-spec-recurrent-exact.py --spec-len 5
```

All three XPU runs passed with:

- `state_equal=true`;
- `output_equal=true`;
- `accepted_prefix_commit_ssm_equal=true`;
- `accepted_prefix_commit_conv_equal=true`;
- `scheduler_endpoint_cases_equal=true`;
- `scheduler_endpoint_case_count=9`;
- `old_accepted_count_path_equal=false` as expected.

Implication:

Future native commit/rollback work should run this harness before endpoint
tests. It now catches both low-level recurrent prefix equality and high-level
MTP row/accounting mistakes that previously created attractive but invalid
`66-72 tok/s` rows.

## 2026-07-06 follow-up: native prefix-base reject case guard

`scripts/check-gdn-native-spec-prefix.py` was extended to cover the missing
native prefix-base reject case:

- `full_reject_source_base_col0`: `num_accepted_tokens=[0, 0, 0]` must select
  prefix column `0`, the base/running state, not the first speculative row;
- `restart_from_varied_accepted_counts` now includes `0` in prefix-base mode
  (`[0, 1, 2]`) instead of starting at `1`.

Validation:

```text
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile scripts/check-gdn-native-spec-prefix.py
VLLM_TARGET_DEVICE=xpu PYTHONPATH=/home/steve/src/vllm-xpu-kernels:/home/steve/src/vllm \
  /home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-native-spec-prefix.py --device xpu:0 --spec-len 3
VLLM_TARGET_DEVICE=xpu PYTHONPATH=/home/steve/src/vllm-xpu-kernels:/home/steve/src/vllm \
  /home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-native-spec-prefix.py --device xpu:0 --spec-len 4 --prefix-base-state
VLLM_TARGET_DEVICE=xpu PYTHONPATH=/home/steve/src/vllm-xpu-kernels:/home/steve/src/vllm \
  /home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-native-spec-prefix.py --device xpu:0 --spec-len 5 --prefix-base-state --dtype fp16
```

All passed. In prefix-base mode the new cases reported:

- `full_reject_source_base_col0`: `source_cols=[0, 0, 0]`,
  `base_column_close=true`, `conv_prefix_close=true`,
  `ssm_prefix_close=true`;
- `restart_from_varied_accepted_counts`: `source_cols=[0, 1, 2]`,
  `base_column_close=true`, `conv_prefix_close=true`,
  `ssm_prefix_close=true`.

Conclusion: the native kernel/source-column contract can represent a reject
rollback correctly in isolation. The remaining blocker is endpoint transaction
plumbing: deriving the accepted draft-prefix count at the right boundary and
committing/rolling state without corrupting target-owned replacement/bonus
tokens or scheduler-visible output.
