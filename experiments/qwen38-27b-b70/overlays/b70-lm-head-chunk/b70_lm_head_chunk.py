"""Feed the output layer at most N rows per call (research overlay). Enabled with B70_LM_HEAD_CHUNK_ROWS=<N>, N >= 1.

Why: the 2026-10-04 kernel census on the shipped R310 image (data/2026-10-04-fp8-multiuser/census/) found every
body GEMM of this lane row-invariant across all batch sizes and positions, and exactly one kernel that is not: the
LM head (K=5120, N=124160 per rank). Its per-row result is bitwise the same for 1 to 4 rows and changes in the last
bit from 5 rows up (classes {1-4}, {5-8}, {12-48}, {59-128}, ...). A lone user is always in the first class. With
five or more users decoding together the logits move by one ulp and an exact tie can fall the other way.

What this does: `model.compute_logits(hidden)` is called from the model runner in plain Python, once per step, with
one row per request being sampled. This wraps it so the head sees at most N rows per call and concatenates the
results. With N <= 4 every call is in the single-user class, so each row's logits are the ones it would get alone.
No arithmetic is changed. Cost: the head is read once per chunk (about 1.1 ms per extra chunk per rank).
"""
import os


def chunked(inner, rows, cat):
    def compute_logits(hidden_states, *args, **kwargs):
        count = hidden_states.shape[0]
        if count <= rows:
            return inner(hidden_states, *args, **kwargs)
        parts = [inner(hidden_states[start:start + rows], *args, **kwargs) for start in range(0, count, rows)]
        if any(part is None for part in parts):
            return inner(hidden_states, *args, **kwargs)
        return cat(parts, dim=0)
    return compute_logits


def register():
    value = os.environ.get('B70_LM_HEAD_CHUNK_ROWS', '').strip()
    if not value or int(value) < 1:
        return
    rows = int(value)
    import torch
    from vllm.logger import init_logger
    from vllm.v1.worker import gpu_model_runner as module

    logger = init_logger('b70_lm_head_chunk')
    cls = module.GPUModelRunner
    if getattr(cls, '_b70_lm_head_chunk', False):
        return
    original = cls.load_model

    def load_model(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        model = self.model
        if not getattr(model, '_b70_lm_head_chunked', False):
            model.compute_logits = chunked(model.compute_logits, rows, torch.cat)
            model._b70_lm_head_chunked = True
            logger.warning('b70_lm_head_chunk: compute_logits now feeds the LM head at most %d rows per call', rows)
        return result

    cls.load_model = load_model
    cls._b70_lm_head_chunk = True
