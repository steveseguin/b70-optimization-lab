# MiniMax Router-Fusion Candidate-Repair Negative

Date: 2026-05-20

No source patch was promoted from this screen.

## Finding

The existing `minimax_m2_candidate_repair_topk` path can reproduce exact
MiniMax top-k weights and ids when given all 256 experts, but it is not a viable
router-linear replacement:

- 1 decode token: `0.032211 ms` current linear vs `0.609194 ms` repair
- 2 decode tokens: `0.022275 ms` current linear vs `0.523925 ms` repair
- 4 decode tokens: `0.022450 ms` current linear vs `0.656969 ms` repair

The all-expert repair kernel is useful for correctness audits and small
candidate-set repair, not for full router fusion.

## Reproduction Sketch

Use the vLLM XPU venv with llm-scaler custom kernels on `PYTHONPATH`, allocate
random XPU tensors for `x`, `w`, and `e_score_bias`, compare:

```python
torch.nn.functional.linear(x.float(), w)
```

against:

```python
minimax_m2_candidate_repair_topk(
    x, torch.arange(256, device="xpu").repeat(tokens, 1),
    w, e_score_bias, 8, True)
```

Correctness is checked by matching top-k ids and top-k weights after applying
the MiniMax sigmoid-plus-bias router rule.
