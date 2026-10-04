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

B70_LM_HEAD_CHUNK_AT=head (not yet measured on the cards): `compute_logits` is the per-rank projection followed by one
card-to-card all-gather of the logits, so chunking it pays one exchange per chunk. In this mode the chunking moves
inside, to `LogitsProcessor._apply_head`, and only while a wrapped `compute_logits` call is running: the per-rank
head sees exactly the same calls of at most N rows, the chunks are concatenated on the rank, and the logits cross
the cards once per step. The gather copies bytes, so the logits are the same ones.
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


def chunked_head(inner, rows, cat, active):
    """Wrap `_apply_head(self, lm_head, hidden_states, embedding_bias)`; chunk rows only while active() is true."""
    def _apply_head(self, lm_head, hidden_states, embedding_bias=None):
        count = hidden_states.shape[0]
        if not active() or hidden_states.dim() != 2 or count <= rows:
            return inner(self, lm_head, hidden_states, embedding_bias)
        return cat([inner(self, lm_head, hidden_states[start:start + rows], embedding_bias)
                    for start in range(0, count, rows)], dim=0)
    return _apply_head


def flagged(inner, depth):
    """Run `compute_logits` once with the chunk flag raised; `depth` is a one-item list used as a counter."""
    def compute_logits(hidden_states, *args, **kwargs):
        depth[0] += 1
        try:
            return inner(hidden_states, *args, **kwargs)
        finally:
            depth[0] -= 1
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
            if at_head:
                model.compute_logits = flagged(model.compute_logits, depth)
                logger.warning('b70_lm_head_chunk: the per-rank LM head sees at most %d rows per call; one gather per step', rows)
            else:
                model.compute_logits = chunked(model.compute_logits, rows, torch.cat)
                logger.warning('b70_lm_head_chunk: compute_logits now feeds the LM head at most %d rows per call', rows)
            model._b70_lm_head_chunked = True
        return result

    at_head = os.environ.get('B70_LM_HEAD_CHUNK_AT', '').strip() == 'head'
    if at_head:
        from vllm.model_executor.layers.logits_processor import LogitsProcessor
        depth = [0]
        LogitsProcessor._apply_head = chunked_head(LogitsProcessor._apply_head, rows, torch.cat, lambda: depth[0] > 0)

    cls.load_model = load_model
    cls._b70_lm_head_chunk = True
