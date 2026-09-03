# R182 v2 diagnostic (v1 gated on hidden_states.shape[0], which is padded, and never fired): per-layer last-hidden-row trace for small prefill batches (16..128 rows), plus the full-attention
# metadata (query_start_loc, seq_lens, max_query_len, block_table, slot_mapping, num_actual_tokens) read from the
# forward context for each attention layer. Eager Python (compilation mode None on this lane). Model file only:
# flash_attn.py is contract-checked. Built on the R176 probe image.
import hashlib
GATE = '\n\ndef _r182_gate():\n    """R182 v2: return num_actual_tokens when the current forward is a prefill batch of <= 4 sequences\n    (read from any GDN attention metadata in the forward context), else 0."""\n    try:\n        from vllm.forward_context import get_forward_context\n        am = get_forward_context().attn_metadata\n        if not isinstance(am, dict):\n            return 0\n        for v in am.values():\n            if hasattr(v, "num_prefills") and hasattr(v, "num_spec_decodes"):\n                nseq = int(v.num_prefills) + int(v.num_decodes) + int(v.num_spec_decodes)\n                if int(v.num_prefills) >= 1 and nseq <= 4 and 8 <= int(v.num_actual_tokens) <= 256:\n                    return int(v.num_actual_tokens)\n                return 0\n    except Exception:\n        return 0\n    return 0\n\n'
p = "/opt/venv/lib/python3.12/site-packages/vllm/model_executor/models/qwen3_next.py"
s = open(p).read()
print("qwen3_next.py sha256 before:", hashlib.sha256(s.encode()).hexdigest())
old_loop = '''            hidden_states, residual = layer(
                positions=positions,
                hidden_states=hidden_states,
                residual=residual,
            )
'''
new_loop = old_loop + '''            _r182_n = _r182_gate()  # R182 v2 probe: prefill batches of <= 4 sequences; last real row
            if _r182_n:
                try:
                    _r182_meta = ""
                    from vllm.forward_context import get_forward_context
                    _am = get_forward_context().attn_metadata
                    if isinstance(_am, dict):
                        for _k, _v in _am.items():
                            if f".layers.{layer_idx}." in _k and hasattr(_v, "slot_mapping") and hasattr(_v, "seq_lens"):
                                _n = int(_v.query_start_loc.shape[0]) - 1
                                _sm = _v.slot_mapping[: _v.num_actual_tokens]
                                _r182_meta = (
                                    f" attn={_k} n_reqs={_n} num_actual_tokens={_v.num_actual_tokens}"
                                    f" query_start_loc={_v.query_start_loc[: _n + 1].tolist()}"
                                    f" seq_lens={_v.seq_lens[:_n].tolist()} max_query_len={_v.max_query_len}"
                                    f" max_seq_len={getattr(_v, 'max_seq_len', None)}"
                                    f" block_table={_v.block_table[:_n, :6].tolist()}"
                                    f" slot_head={_sm[:3].tolist()} slot_tail={_sm[-3:].tolist()}"
                                )
                    logger.info(
                        "R182 layer_out idx=%d n=%d rows=%d h_last_abs=%s h_prev_abs=%s r_last_abs=%s%s",
                        layer_idx, _r182_n, hidden_states.shape[0],
                        float(hidden_states[_r182_n - 1].float().abs().sum()),
                        float(hidden_states[_r182_n - 2].float().abs().sum()),
                        None if residual is None else float(residual[_r182_n - 1].float().abs().sum()),
                        _r182_meta,
                    )
                except Exception as exc:
                    logger.info("R182 layer_out idx=%d probe failed: %r", layer_idx, exc)
'''
old_lg = "logger = init_logger(__name__)\n"
assert s.count(old_lg) == 1, "logger anchor"
s = s.replace(old_lg, old_lg + GATE)
assert s.count(old_loop) == 1, "layer loop anchor"
s = s.replace(old_loop, new_loop)
old_emb = '''        aux_hidden_states = self._maybe_add_hidden_state([], 0, hidden_states, residual)
'''
new_emb = old_emb + '''        _r182_n = _r182_gate()  # R182 v2 probe
        if _r182_n:
            try:
                logger.info("R182 embed n=%d rows=%d h_last_abs=%s h_prev_abs=%s", _r182_n, hidden_states.shape[0],
                            float(hidden_states[_r182_n - 1].float().abs().sum()), float(hidden_states[_r182_n - 2].float().abs().sum()))
            except Exception as exc:
                logger.info("R182 embed probe failed: %r", exc)
'''
assert s.count(old_emb) == 1, "embed anchor"
s = s.replace(old_emb, new_emb)
old_norm = '''        hidden_states, _ = self.norm(hidden_states, residual)
'''
new_norm = old_norm + '''        _r182_n = _r182_gate()  # R182 v2 probe
        if _r182_n:
            try:
                logger.info("R182 final_norm n=%d rows=%d h_last_abs=%s h_prev_abs=%s", _r182_n, hidden_states.shape[0],
                            float(hidden_states[_r182_n - 1].float().abs().sum()), float(hidden_states[_r182_n - 2].float().abs().sum()))
            except Exception as exc:
                logger.info("R182 final_norm probe failed: %r", exc)
'''
assert s.count(old_norm) == 1, "final norm anchor: %d" % s.count(old_norm)
s = s.replace(old_norm, new_norm)
open(p, "w").write(s)
print("R182 layer trace inserted; sha256 after:", hashlib.sha256(s.encode()).hexdigest())
