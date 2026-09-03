# R171: trace the logits row selection at small-batch steps (diagnostic only; applied on top of R170).
import re
p = "/opt/venv/lib/python3.12/site-packages/vllm/v1/worker/gpu_model_runner.py"
s = open(p).read()
old = """                sample_hidden_states = hidden_states[logits_indices]
                logits = self.model.compute_logits(sample_hidden_states)
            else:
                # Rare case."""
assert s.count(old) == 1, s.count(old)
new = """                sample_hidden_states = hidden_states[logits_indices]
                logits = self.model.compute_logits(sample_hidden_states)
                if self.input_batch.num_reqs <= 4 and spec_decode_metadata is None:
                    _nr = self.input_batch.num_reqs
                    _li = logits_indices.tolist()
                    _rows = []
                    for _i in _li:
                        _cand = [_r for _r in (_i - 1, _i) if 0 <= _r < hidden_states.shape[0]]
                        _lg = self.model.compute_logits(hidden_states[_cand]).float()
                        _top = torch.topk(_lg, 2, dim=-1)
                        _rows.append([(_r, _top.indices[_k].tolist(), [round(_v, 3) for _v in _top.values[_k].tolist()]) for _k, _r in enumerate(_cand)])
                    logger.info("R171 logits_rows step=%s req_ids=%s num_scheduled=%s logits_indices=%s query_start_loc.gpu=%s query_start_loc.cpu=%s rows(top2 per candidate row)=%s",
                                getattr(self, "_r170_step", None), list(self.input_batch.req_ids), num_scheduled_tokens,
                                _li, self.query_start_loc.gpu[: _nr + 1].tolist(), self.query_start_loc.np[: _nr + 1].tolist(), _rows)
            else:
                # Rare case."""
s = s.replace(old, new)
open(p, "w").write(s)
print("R171 trace inserted")
