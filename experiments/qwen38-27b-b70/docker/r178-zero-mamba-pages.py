# R178 fix candidate: zero the Mamba/GDN state pages (conv + ssm) of newly allocated blocks.
# Upstream KVBlockZeroer skips non-AttentionSpec groups, so a recycled GDN state page keeps the previous
# request's state (including whatever a discarded async extra step wrote) and the XPU kernel is handed it raw.
p = "/opt/venv/lib/python3.12/site-packages/vllm/v1/worker/gpu_model_runner.py"
s = open(p).read()
old = '''    def _zero_block_ids(self, block_ids: list[int]) -> None:
        """Zero the KV cache memory for the given block IDs."""
        if hasattr(self, "_kv_block_zeroer"):
            self._kv_block_zeroer.zero_block_ids(block_ids)
'''
assert s.count(old) == 1
new = '''    def _zero_block_ids(self, block_ids: list[int]) -> None:
        """Zero the KV cache memory for the given block IDs."""
        if hasattr(self, "_kv_block_zeroer"):
            self._kv_block_zeroer.zero_block_ids(block_ids)
        self._zero_mamba_pages(block_ids)

    def _zero_mamba_pages(self, block_ids: list[int]) -> None:
        """R178: also zero the Mamba/GDN state pages (conv_state, ssm_state) of
        newly allocated blocks. KVBlockZeroer only handles AttentionSpec groups,
        so a recycled state page otherwise keeps the previous occupant's state."""
        if not block_ids:
            return
        layers = getattr(self, "_r178_mamba_layers", None)
        if layers is None:
            layers = []
            for group in self.kv_cache_config.kv_cache_groups:
                if not isinstance(group.kv_cache_spec, MambaSpec):
                    continue
                for name in group.layer_names:
                    if name in self.runner_only_attn_layers:
                        continue
                    layer = self.compilation_config.static_forward_context.get(name)
                    kv = getattr(layer, "kv_cache", None)
                    if isinstance(kv, (tuple, list)) and len(kv) >= 2:
                        layers.append(layer)
            self._r178_mamba_layers = layers
            logger.info("R178 zeroing Mamba/GDN state pages for %d layers on new blocks", len(layers))
        if not layers:
            return
        idx = torch.tensor(block_ids, dtype=torch.int64, device=self.device)
        for layer in layers:
            for state in layer.kv_cache[:2]:
                state.index_fill_(0, idx, 0)
'''
s = s.replace(old, new)
assert "MambaSpec" in s.split("def _zero_block_ids")[0], "MambaSpec import missing"
open(p, "w").write(s)
print("R178 mamba page zeroing inserted")
