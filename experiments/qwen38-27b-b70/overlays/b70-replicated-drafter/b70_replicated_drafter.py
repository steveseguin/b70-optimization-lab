"""Replicated MTP drafter for two-card serving (research overlay). Enabled with B70_REPLICATED_DRAFTER=1.

Under tensor parallelism the Qwen3-Next MTP drafter is sharded like the target: its embedding lookup, its fc and
MLP projections and its logits each need a cross-card collective, five draft passes per step. Everything in the
drafter except its attention layer is small (a few hundred MB unsharded), so this overlay builds a second, unsharded
copy of the drafter with a one-rank tensor-parallel group, transplants its embedding, fc and MLP into the served
drafter, prepares the draft-only INT4 shortlist head from the unsharded lm_head, and runs the logits computation
under the one-rank group. The attention layer stays sharded (its KV cache must share the target's page layout), so
one allreduce per draft pass remains instead of four. Every rank computes the same full logits from the same inputs,
so the drafts are identical across ranks and the verifier is untouched; outputs are unchanged by construction.
"""
import contextlib
import os


def register():
    if os.environ.get('B70_REPLICATED_DRAFTER', '').strip() != '1':
        return
    import torch
    import torch.distributed as dist
    from vllm.logger import init_logger
    from vllm.distributed import parallel_state as ps
    from vllm.v1.spec_decode import llm_base_proposer as lbp

    logger = init_logger('b70_replicated_drafter')
    Proposer = lbp.SpecDecodeBaseProposer
    if getattr(Proposer, '_b70_replicated_drafter', False):
        return
    state = {'solo': None}

    @contextlib.contextmanager
    def solo_tp():
        real = ps._TP
        ps._TP = state['solo']
        try:
            yield
        finally:
            ps._TP = real

    @contextlib.contextmanager
    def scratch_static_context(*configs):
        """Layer constructors register themselves by name and refuse duplicates; build the second copy into scratch dicts."""
        saved = []
        for cc in configs:
            saved.append((cc, cc.static_forward_context))
            cc.static_forward_context = {}
        try:
            yield
        finally:
            for cc, ctx in saved:
                cc.static_forward_context = ctx

    orig_load_model = Proposer.load_model
    orig_get_model = Proposer._get_model
    orig_share_embeddings = Proposer._maybe_share_embeddings
    orig_share_lm_head = Proposer._maybe_share_lm_head

    def load_model(self, target_model):
        real = ps.get_tp_group()
        if real.world_size < 2:
            return orig_load_model(self, target_model)
        if state['solo'] is None:
            world = ps.get_world_group()
            backend = dist.get_backend(world.device_group)
            state['solo'] = ps.init_model_parallel_group([[r] for r in range(world.world_size)], world.local_rank, backend,
                                                         group_name='b70_solo_tp')
            logger.warning('b70_replicated_drafter: one-rank tensor-parallel group ready (rank %d of %d)', real.rank_in_group, real.world_size)
        return orig_load_model(self, target_model)

    def _get_model(self):
        model = orig_get_model(self)
        if state['solo'] is None:
            return model
        configs = [self.vllm_config.compilation_config]
        draft_cfg = self._create_draft_vllm_config()
        if draft_cfg.compilation_config is not configs[0]:
            configs.append(draft_cfg.compilation_config)
        with solo_tp(), scratch_static_context(*configs):
            full = orig_get_model(self)
        # Transplant the selected unsharded pieces; the attention layer always keeps the served (sharded) copy.
        # B70_REPLICATED_DRAFTER_PARTS (default embed,fc,mlp,head): replicating the MLP doubles its compute per card
        # (comm-3: exact but 86.7 vs 90.4 tok/s), so the lighter selections leave it sharded.
        parts = {p.strip() for p in os.environ.get('B70_REPLICATED_DRAFTER_PARTS', 'embed,fc,mlp,head').split(',') if p.strip()}
        state['parts'] = parts
        if 'embed' in parts:
            model.model.embed_tokens = full.model.embed_tokens
        if 'fc' in parts:
            model.model.fc = full.model.fc
        if 'mlp' in parts:
            for served, whole in zip(model.model.layers, full.model.layers):
                served.mlp = whole.mlp
        if 'head' in parts:
            model._b70_full_lm_head = full.lm_head
            orig_compute_logits = model.compute_logits

            def compute_logits(hidden_states, spec_step_idx=0):
                with solo_tp():
                    return orig_compute_logits(hidden_states, spec_step_idx)

            model.compute_logits = compute_logits
        del full
        torch.xpu.empty_cache()
        logger.warning('b70_replicated_drafter: parts %s; embedding tp %d, fc tp %d, mlp tp %d, head %s',
                       sorted(parts), model.model.embed_tokens.tp_size, model.model.fc.tp_size,
                       model.model.layers[0].mlp.down_proj.tp_size, 'unsharded' if 'head' in parts else 'shared shard')
        return model

    def _maybe_share_embeddings(self, target_language_model):
        if state['solo'] is None or 'embed' not in state.get('parts', ()):
            return orig_share_embeddings(self, target_language_model)
        logger.warning('b70_replicated_drafter: keeping the drafter\'s own unsharded embedding (not sharing the target shard)')

    def _maybe_share_lm_head(self, target_language_model):
        if state['solo'] is None or 'head' not in state.get('parts', ()):
            return orig_share_lm_head(self, target_language_model)
        head = self.model._b70_full_lm_head
        draft_int4 = os.environ.get('VLLM_XPU_DRAFT_LM_HEAD_INT4', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
        if draft_int4:
            quant_method = getattr(head, 'quant_method', None)
            prepare = getattr(quant_method, 'make_xpu_int4_draft_copy', None)
            if not callable(prepare):
                from vllm.model_executor.layers.vocab_parallel_embedding import UnquantizedEmbeddingMethod
                weight = getattr(head, 'weight', None)
                if weight is not None and weight.dtype in (torch.float16, torch.bfloat16):
                    prepare = getattr(UnquantizedEmbeddingMethod(), 'make_xpu_int4_draft_copy', None)
            if not callable(prepare):
                raise RuntimeError('draft INT4 requested but the unsharded head cannot prepare a draft-only copy')
            with solo_tp():
                head = prepare(head)
            if head is None:
                raise RuntimeError('draft INT4 requested but no draft-only head was prepared')
            del self.model._b70_full_lm_head
            torch.xpu.empty_cache()
            logger.warning('b70_replicated_drafter: draft-only INT4 head prepared from the unsharded lm_head')
        else:
            logger.warning('b70_replicated_drafter: unsharded FP16 draft head kept')
        if hasattr(self.model, 'lm_head'):
            del self.model.lm_head
        self.model.lm_head = head
        inner = getattr(self.model, 'model', None)
        layers = getattr(inner, 'layers', None) if inner is not None else None
        if layers is not None:
            items = layers.values() if isinstance(layers, torch.nn.ModuleDict) else layers
            for layer in items:
                sh = getattr(layer, 'shared_head', None)
                if sh is not None and hasattr(sh, 'head'):
                    del sh.head
                    sh.head = head

    Proposer.load_model = load_model
    Proposer._get_model = _get_model
    Proposer._maybe_share_embeddings = _maybe_share_embeddings
    Proposer._maybe_share_lm_head = _maybe_share_lm_head
    Proposer._b70_replicated_drafter = True
    logger.warning('b70_replicated_drafter: installed')
