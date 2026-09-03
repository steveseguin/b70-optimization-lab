# R172 diagnostic: log block ids of new requests and the per-step zeroing list (on top of R171).
p = "/opt/venv/lib/python3.12/site-packages/vllm/v1/worker/gpu_model_runner.py"
s = open(p).read()
old = """        if scheduler_output.new_block_ids_to_zero:
            self._zero_block_ids(scheduler_output.new_block_ids_to_zero)
"""
assert s.count(old) == 1
new = """        if len(scheduler_output.num_scheduled_tokens) <= 4:
            logger.info("R172 step_blocks new_block_ids_to_zero=%s new_reqs=%s cached_new_block_ids=%s num_scheduled_tokens=%s",
                        scheduler_output.new_block_ids_to_zero,
                        [(r.req_id, r.block_ids, r.num_computed_tokens) for r in scheduler_output.scheduled_new_reqs],
                        getattr(scheduler_output.scheduled_cached_reqs, "new_block_ids", None),
                        dict(scheduler_output.num_scheduled_tokens))
""" + old
s = s.replace(old, new)
open(p, "w").write(s)
print("R172 trace inserted")
