#!/usr/bin/env python3
"""Diagnostic-only R307 acceptance tracing; device reads synchronize execution.

No functional state changes. Logs runner CPU/GPU acceptance, partial metadata,
and layer-0 handoff selection. Never use this image as qualification evidence.
"""
import pathlib
import sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '/opt/venv/lib/python3.12/site-packages')

def edit(relative, old, new):
    path = root / relative
    text = path.read_text()
    assert text.count(old) == 1, (relative, text.count(old))
    text = text.replace(old, new)
    compile(text, str(path), 'exec')
    path.write_text(text)

edit('vllm/v1/worker/gpu_model_runner.py',
'''            accepted = self._gdn_prev_step_accepted_counts(num_reqs)
            num_decode_draft_tokens[one_token_decode & (accepted > 1)] = 0
''',
'''            accepted = self._gdn_prev_step_accepted_counts(num_reqs)
            print("R308_TRACE_RUNNER", {
                "req_ids": list(self.input_batch.req_ids[:num_reqs]),
                "accepted_cpu_valid": accepted.tolist(),
                "accepted_gpu": self.num_accepted_tokens.gpu[:num_reqs].tolist(),
                "prev_drafts_cpu": self.prev_num_draft_tokens.np[:num_reqs].tolist(),
                "prev_drafts_gpu": self.prev_num_draft_tokens.gpu[:num_reqs].tolist(),
                "scheduled": num_scheduled_tokens[:num_reqs].tolist(),
                "computed_cpu": self.input_batch.num_computed_tokens_cpu[:num_reqs].tolist(),
                "computed_gpu": self.num_computed_tokens[:num_reqs].tolist(),
                "draft_counts": num_decode_draft_tokens.tolist(),
                "one_token_decode": one_token_decode.tolist(),
                "prev_mapping": self.input_batch.prev_req_id_to_index,
                "prev_positions": self.prev_positions.np[:num_reqs].tolist(),
            }, flush=True)
            num_decode_draft_tokens[one_token_decode & (accepted > 1)] = 0
''')
edit('vllm/v1/attention/backends/gdn_attn.py',
'''                partial_num_accepted = num_accepted_tokens[partial_rows]
                num_accepted_tokens = num_accepted_tokens.clone()
''',
'''                partial_num_accepted = num_accepted_tokens[partial_rows]
                print("R308_TRACE_PARTIAL", {
                    "query_lens": query_lens_cpu.tolist(),
                    "partial_rows": partial_rows.tolist(),
                    "accepted_gpu": partial_num_accepted.tolist(),
                    "state_indices": partial_state_indices.tolist(),
                }, flush=True)
                num_accepted_tokens = num_accepted_tokens.clone()
''')
edit('vllm/_xpu_ops.py',
'''    assert rows is not None and accepted is not None
    col = (accepted.to(torch.int64) - 1).clamp_(min=0)
''',
'''    assert rows is not None and accepted is not None
    if ".layers.0." in getattr(layer, "prefix", ""):
        print("R308_TRACE_HANDOFF", {
            "layer": layer.prefix,
            "accepted_gpu": accepted.tolist(),
            "state_indices": rows.tolist(),
            "conv_shape": list(conv_state.shape),
            "ssm_dtype": str(ssm_state.dtype),
            "num_actual_tokens": attn_metadata.num_actual_tokens,
            "num_spec_decodes": attn_metadata.num_spec_decodes,
        }, flush=True)
    col = (accepted.to(torch.int64) - 1).clamp_(min=0)
''')
print('R308 diagnostic acceptance trace installed')
