# R294: a shortlisted draft lm_head. The MTP draft passes score every one of the 248,320 vocabulary rows to pick one
# argmax token, and on the 9B that projection was measured at 28% of the decode step even as a draft-only INT4 copy
# (experiments/qwen35-9b-b70/notes/2026-09-09-the-draft-lm-head-is-28-percent-of-the-step.md). A draft only
# proposes; the target verifies every token with its own full FP16 head, so a draft head that scores a shortlist of
# rows cannot change any output - a draft whose true argmax lies outside the shortlist is simply rejected. With
# VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=<file of token ids, one per line> the draft-only INT4 copy is built from those rows
# only (per tensor-parallel shard: the ids that fall in the shard's range), and its logits are scattered back into a
# full-width tensor filled with -inf so the proposer's argmax and the TP all-gather see the usual shape. Shortlist
# files shipped at /opt/draft-shortlists/ are token-frequency lists from the lab's own text corpus
# (draft-shortlists/build-shortlist.py). Off unless the variable is set.
import hashlib, pathlib
p = pathlib.Path("/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/vocab_parallel_embedding.py")
s = p.read_text()

old = '''        num_tokens, hidden = weight.shape
        packed_k = hidden // 8
'''
new = '''        # R294: optional shortlist of vocabulary rows for the draft-only copy.
        _r294_path = os.environ.get("VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST", "").strip()
        _r294_local = None
        _r294_full_rows = weight.shape[0]
        if _r294_path:
            import logging as _r294_logging
            _ids = sorted({int(t) for t in open(_r294_path).read().split() if t.strip()})
            _si = getattr(layer, "shard_indices", None)
            _start = getattr(_si, "org_vocab_start_index", 0) if _si is not None else 0
            _end = getattr(_si, "org_vocab_end_index", weight.shape[0]) if _si is not None else weight.shape[0]
            _local = [t - _start for t in _ids if _start <= t < _end]
            if not _local:
                _local = [0]  # a shard with no shortlist rows still needs one row so the GEMM has a shape
            _r294_local = torch.tensor(_local, dtype=torch.long, device=weight.device)
            _r294_logging.getLogger("vllm").info(
                "R294 draft shortlist: %d ids from %s, %d in this shard [%d, %d) of %d rows",
                len(_ids), _r294_path, len(_local), _start, _end, weight.shape[0])
            weight = weight.index_select(0, _r294_local)
        num_tokens, hidden = weight.shape
        packed_k = hidden // 8
'''
assert s.count(old) == 1, "anchor 1"
s = s.replace(old, new)

old2 = '''        draft_layer._xpu_draft_int4_group_size = group_size
        draft_layer._xpu_draft_int4_enabled = True
        return draft_layer
'''
new2 = '''        draft_layer._xpu_draft_int4_group_size = group_size
        draft_layer._xpu_draft_int4_enabled = True
        if _r294_local is not None:
            draft_layer.register_buffer("_xpu_draft_shortlist_local", _r294_local, persistent=False)
            draft_layer._xpu_draft_shortlist_full_rows = _r294_full_rows
        return draft_layer
'''
assert s.count(old2) == 1, "anchor 2"
s = s.replace(old2, new2)

old3 = '''            return logits.reshape(
                x_contiguous.shape[:-1] + (layer._xpu_draft_int4_weight_t.shape[1],)
            )
'''
new3 = '''            _sl = getattr(layer, "_xpu_draft_shortlist_local", None)
            if _sl is not None:
                # R294: scatter the shortlist logits into a full-width row of -inf.
                full = torch.full(
                    (logits.shape[0], layer._xpu_draft_shortlist_full_rows),
                    float("-inf"), dtype=logits.dtype, device=logits.device)
                full.index_copy_(1, _sl, logits)
                return full.reshape(x_contiguous.shape[:-1] + (layer._xpu_draft_shortlist_full_rows,))
            return logits.reshape(
                x_contiguous.shape[:-1] + (layer._xpu_draft_int4_weight_t.shape[1],)
            )
'''
assert s.count(old3) == 1, "anchor 3"
s = s.replace(old3, new3)
p.write_text(s)
print("R294 draft shortlist inserted; vocab_parallel_embedding.py sha256", hashlib.sha256(s.encode()).hexdigest())
