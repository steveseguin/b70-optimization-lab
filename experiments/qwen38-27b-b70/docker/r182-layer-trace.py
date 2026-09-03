# R182 diagnostic: per-layer last-hidden-row trace for small prefill batches (16..128 rows), plus the full-attention
# metadata (query_start_loc, seq_lens, max_query_len, block_table, slot_mapping, num_actual_tokens) read from the
# forward context for each attention layer. Eager Python (compilation mode None on this lane). Model file only:
# flash_attn.py is contract-checked. Built on the R176 probe image.
import hashlib
p = "/opt/venv/lib/python3.12/site-packages/vllm/model_executor/models/qwen3_next.py"
s = open(p).read()
print("qwen3_next.py sha256 before:", hashlib.sha256(s.encode()).hexdigest())
old_loop = '''            hidden_states, residual = layer(
                positions=positions,
                hidden_states=hidden_states,
                residual=residual,
            )
'''
new_loop = old_loop + '''            if 16 <= hidden_states.shape[0] <= 128:  # R182 probe: prefill-sized small batches only
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
                        "R182 layer_out idx=%d n=%d h_last_abs=%s h_prev_abs=%s r_last_abs=%s%s",
                        layer_idx, hidden_states.shape[0],
                        float(hidden_states[-1].float().abs().sum()),
                        float(hidden_states[-2].float().abs().sum()),
                        None if residual is None else float(residual[-1].float().abs().sum()),
                        _r182_meta,
                    )
                except Exception as exc:
                    logger.info("R182 layer_out idx=%d probe failed: %r", layer_idx, exc)
'''
assert s.count(old_loop) == 1, "layer loop anchor"
s = s.replace(old_loop, new_loop)
old_emb = '''        aux_hidden_states = self._maybe_add_hidden_state([], 0, hidden_states, residual)
'''
new_emb = old_emb + '''        if 16 <= hidden_states.shape[0] <= 128:  # R182 probe
            try:
                logger.info("R182 embed n=%d h_last_abs=%s h_prev_abs=%s", hidden_states.shape[0],
                            float(hidden_states[-1].float().abs().sum()), float(hidden_states[-2].float().abs().sum()))
            except Exception as exc:
                logger.info("R182 embed probe failed: %r", exc)
'''
assert s.count(old_emb) == 1, "embed anchor"
s = s.replace(old_emb, new_emb)
old_norm = '''        hidden_states, _ = self.norm(hidden_states, residual)
'''
new_norm = old_norm + '''        if 16 <= hidden_states.shape[0] <= 128:  # R182 probe
            try:
                logger.info("R182 final_norm n=%d h_last_abs=%s h_prev_abs=%s", hidden_states.shape[0],
                            float(hidden_states[-1].float().abs().sum()), float(hidden_states[-2].float().abs().sum()))
            except Exception as exc:
                logger.info("R182 final_norm probe failed: %r", exc)
'''
assert s.count(old_norm) == 1, "final norm anchor: %d" % s.count(old_norm)
s = s.replace(old_norm, new_norm)
open(p, "w").write(s)
print("R182 layer trace inserted; sha256 after:", hashlib.sha256(s.encode()).hexdigest())
