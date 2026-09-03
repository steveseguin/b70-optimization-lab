# R182 v3 diagnostic: per-layer last-real-row trace + full-attention metadata for small prefill batches, as a custom op
# with a fake impl (the lane runs CompilationMode.VLLM_COMPILE; plain Python logging in the model forward is traced
# away by Dynamo -- v1/v2 emitted nothing). Same technique as the R110 decoder-boundary trace. Model file only.
import hashlib
p = "/opt/venv/lib/python3.12/site-packages/vllm/model_executor/models/qwen3_next.py"
s = open(p).read()
print("qwen3_next.py sha256 before:", hashlib.sha256(s.encode()).hexdigest())

OP = '''

def _r182_layer_trace_xpu(tensor: torch.Tensor, layer_index: int, stage: str) -> None:
    """R182 v3: eager body (never traced). Logs the last two real rows' abs-sums of `tensor` for prefill
    batches of <= 4 sequences, plus the full-attention metadata of layer `layer_index` when it has one."""
    try:
        from vllm.forward_context import get_forward_context
        am = get_forward_context().attn_metadata
        if not isinstance(am, dict):
            return
        n = 0
        for v in am.values():
            if hasattr(v, "num_prefills") and hasattr(v, "num_spec_decodes"):
                nseq = int(v.num_prefills) + int(v.num_decodes) + int(v.num_spec_decodes)
                if int(v.num_prefills) >= 1 and nseq <= 4 and 8 <= int(v.num_actual_tokens) <= 256:
                    n = int(v.num_actual_tokens)
                break
        if n == 0:
            return
        meta = ""
        if stage == "layer_out":
            for k, v in am.items():
                if f".layers.{layer_index}." in k and hasattr(v, "slot_mapping") and hasattr(v, "seq_lens"):
                    nr = int(v.query_start_loc.shape[0]) - 1
                    sm = v.slot_mapping[: v.num_actual_tokens]
                    meta = (
                        f" attn={k} n_reqs={nr} num_actual_tokens={v.num_actual_tokens}"
                        f" query_start_loc={v.query_start_loc[: nr + 1].tolist()}"
                        f" seq_lens={v.seq_lens[:nr].tolist()} max_query_len={v.max_query_len}"
                        f" max_seq_len={getattr(v, 'max_seq_len', None)}"
                        f" block_table={v.block_table[:nr, :6].tolist()}"
                        f" slot_head={sm[:3].tolist()} slot_tail={sm[-3:].tolist()}"
                    )
                    break
        logger.info(
            "R182 %s idx=%d n=%d rows=%d last_abs=%s prev_abs=%s%s",
            stage, layer_index, n, tensor.shape[0],
            float(tensor[n - 1].float().abs().sum()), float(tensor[n - 2].float().abs().sum()), meta,
        )
    except Exception as exc:
        logger.info("R182 %s idx=%d probe failed: %r", stage, layer_index, exc)


def _r182_layer_trace_xpu_fake(tensor: torch.Tensor, layer_index: int, stage: str) -> None:
    return


from vllm.utils.torch_utils import direct_register_custom_op as _r182_register  # noqa: E402
_r182_register(
    op_name="qwen_r182_layer_trace_xpu",
    op_func=_r182_layer_trace_xpu,
    mutates_args=["tensor"],
    fake_impl=_r182_layer_trace_xpu_fake,
)

'''
old_lg = "logger = init_logger(__name__)\n"
assert s.count(old_lg) == 1, "logger anchor"
s = s.replace(old_lg, old_lg + OP)

old_loop = '''            hidden_states, residual = layer(
                positions=positions,
                hidden_states=hidden_states,
                residual=residual,
            )
'''
new_loop = old_loop + '''            torch.ops.vllm.qwen_r182_layer_trace_xpu(hidden_states, layer_idx, "layer_out")  # R182 v3
            if residual is not None:
                torch.ops.vllm.qwen_r182_layer_trace_xpu(residual, layer_idx, "layer_residual")  # R182 v3
'''
assert s.count(old_loop) == 1, "layer loop anchor"
s = s.replace(old_loop, new_loop)

old_emb = '''        aux_hidden_states = self._maybe_add_hidden_state([], 0, hidden_states, residual)
'''
new_emb = old_emb + '''        torch.ops.vllm.qwen_r182_layer_trace_xpu(hidden_states, -1, "embed")  # R182 v3
'''
assert s.count(old_emb) == 1, "embed anchor"
s = s.replace(old_emb, new_emb)

old_norm = '''        hidden_states, _ = self.norm(hidden_states, residual)
'''
new_norm = old_norm + '''        torch.ops.vllm.qwen_r182_layer_trace_xpu(hidden_states, 999, "final_norm")  # R182 v3
'''
assert s.count(old_norm) == 1, "final norm anchor: %d" % s.count(old_norm)
s = s.replace(old_norm, new_norm)
open(p, "w").write(s)
print("R182 v3 custom-op trace inserted; sha256 after:", hashlib.sha256(s.encode()).hexdigest())
