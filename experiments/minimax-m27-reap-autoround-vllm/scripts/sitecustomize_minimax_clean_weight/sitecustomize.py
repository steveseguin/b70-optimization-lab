"""Runtime-only MiniMax clean-weight owner shim.

This keeps vLLM source untouched while testing stale MiniMax AOT graphs that
expect q/k RMSNorm clean weights on the owning module, not just the Parameter.
"""

from __future__ import annotations


def _patch_minimax_clean_weight_owner() -> None:
    try:
        from vllm.model_executor.layers.mamba.linear_attn import (
            MiniMaxText01RMSNormTP,
        )
    except Exception:
        return

    if getattr(MiniMaxText01RMSNormTP, "_sitecustomize_owner_patch", False):
        return

    original_init = MiniMaxText01RMSNormTP.__init__
    original_weight_loader = MiniMaxText01RMSNormTP.weight_loader

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._minimax_clean_weight_cpu = None
        self._minimax_clean_weight_xpu = None
        self.weight._minimax_owner_norm = self

    def patched_weight_loader(param, loaded_weight, *args, **kwargs):
        original_weight_loader(param, loaded_weight, *args, **kwargs)
        owner_norm = getattr(param, "_minimax_owner_norm", None)
        if owner_norm is None:
            return
        clean_weight_cpu = getattr(param, "_minimax_clean_weight_cpu", None)
        if clean_weight_cpu is not None:
            owner_norm._minimax_clean_weight_cpu = clean_weight_cpu
        clean_weight_xpu = getattr(param, "_minimax_clean_weight_xpu", None)
        if clean_weight_xpu is not None:
            owner_norm._minimax_clean_weight_xpu = clean_weight_xpu

    MiniMaxText01RMSNormTP.__init__ = patched_init
    MiniMaxText01RMSNormTP.weight_loader = staticmethod(patched_weight_loader)
    MiniMaxText01RMSNormTP._sitecustomize_owner_patch = True


_patch_minimax_clean_weight_owner()
