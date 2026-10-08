# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project
"""Model-runner state for Qwen4Exp PLE inputs."""

from typing import Any

import torch
import torch.nn as nn

from vllm.config import VllmConfig
from vllm.v1.worker.gpu.input_batch import InputBatch
from vllm.v1.worker.gpu.mm.encoder_cache import EncoderCache
from vllm.v1.worker.gpu.model_states.mamba_hybrid import MambaHybridModelState
from vllm.v1.worker.gpu.states import RequestState


class Qwen4ExpModelState(MambaHybridModelState):
    """Add rollback-safe PLE n-gram context to the model inputs."""

    def __init__(
        self,
        vllm_config: VllmConfig,
        model: nn.Module,
        encoder_cache: EncoderCache | None,
        device: torch.device,
    ) -> None:
        super().__init__(vllm_config, model, encoder_cache, device)
        config = self.model_config.hf_text_config
        self.uses_ngram_embedding = bool(config.ple_layer_ids)
        if not self.uses_ngram_embedding:
            self.ngram_context_len = 0
            self.ngram_eos_token_id = 0
            return

        if vllm_config.parallel_config.pipeline_parallel_size > 1:
            raise RuntimeError(
                "N-gram PLE embedding currently requires "
                "pipeline_parallel_size=1 because non-first pipeline ranks do "
                "not receive the raw input_ids required by PLE. Please run "
                "with PP=1."
            )

        self.ngram_context_len = int(config.ngram_size) - 1
        if self.ngram_context_len <= 0:
            raise ValueError("N-gram embedding requires context length >= 1.")
        self.ngram_eos_token_id = int(config.eos_token_id)
        # PLE runs inside captured regions, so these buffers keep a fixed shape
        # and address as the active request count changes between replays.
        self.ngram_context = torch.full(
            (self.max_num_reqs, self.ngram_context_len),
            self.ngram_eos_token_id,
            dtype=torch.int32,
            device=self.device,
        )
        self.ngram_context_offsets = torch.arange(
            -self.ngram_context_len,
            0,
            dtype=torch.int64,
            device=self.device,
        )
        self.ple_query_start_loc = torch.zeros(
            self.max_num_reqs + 1,
            dtype=torch.int32,
            device=self.device,
        )

    def _prepare_ngram_context(
        self,
        input_batch: InputBatch,
        req_states: RequestState,
    ) -> torch.Tensor:
        num_reqs = input_batch.num_reqs
        context = self.ngram_context
        context.fill_(self.ngram_eos_token_id)
        if num_reqs == 0:
            return context

        request_indices = input_batch.idx_mapping[:num_reqs].long()
        context_end = req_states.num_computed_tokens.gpu[request_indices].long()
        token_indices = context_end.unsqueeze(1) + self.ngram_context_offsets
        valid_tokens = token_indices >= 0
        token_indices.clamp_min_(0)
        context_tokens = req_states.all_token_ids.gpu[
            request_indices.unsqueeze(1), token_indices
        ]
        context[:num_reqs].copy_(
            torch.where(
                valid_tokens,
                context_tokens,
                context_tokens.new_full((), self.ngram_eos_token_id),
            )
        )
        return context

    def prepare_inputs(
        self,
        input_batch: InputBatch,
        req_states: RequestState,
    ) -> dict[str, Any]:
        model_inputs = super().prepare_inputs(input_batch, req_states)
        if not self.uses_ngram_embedding:
            return model_inputs
        # B70 0013b: the lookahead reads the next prefill chunk's tokens
        # from here in b70_pre_forward (same step, same stream).
        self._b70_req_states = req_states

        num_reqs_padded = input_batch.num_reqs_after_padding
        query_start_loc = self.ple_query_start_loc
        query_start_loc[: num_reqs_padded + 1].copy_(input_batch.query_start_loc)
        # Represent unused capacity as trailing zero-length requests.
        query_start_loc[num_reqs_padded + 1 :].copy_(input_batch.query_start_loc[-1])
        model_inputs.update(
            query_start_loc=query_start_loc,
            ngram_context=self._prepare_ngram_context(input_batch, req_states),
        )
        return model_inputs

    def _b70_nvme_modules(self) -> list[nn.Module]:
        """PLE n-gram modules served by the B70 0013 host path (cached)."""
        modules = getattr(self, "_b70_nvme_cached", None)
        if modules is None:
            from .ngram_embedding import Qwen4ExpNGramEmbedding

            modules = [
                module
                for module in self.model.modules()
                if isinstance(module, Qwen4ExpNGramEmbedding)
                and module._b70_nvme_active
            ]
            self._b70_nvme_cached = modules
            if modules:
                self._b70_nvme_stage = torch.empty(
                    self.max_num_tokens + self.max_num_reqs * self.ngram_context_len,
                    dtype=torch.int32,
                    pin_memory=True,
                )
                self._b70_lookahead_on = any(m.b70_nvme_lookahead_on for m in modules)
                if self._b70_lookahead_on:
                    import os

                    self._b70_lookahead_tokens = int(
                        os.environ.get("B70_PLE_INT8_NVME_LOOKAHEAD_TOKENS", "0")
                        or self.max_num_tokens
                    )
                    # Next-chunk tokens plus the ngram context before each chunk.
                    self._b70_lookahead_stage = torch.empty(
                        self._b70_lookahead_tokens
                        + self.max_num_reqs * self.ngram_context_len,
                        dtype=torch.int32,
                        pin_memory=True,
                    )
        return modules

    def _b70_lookahead_plan(self, input_batch: InputBatch):
        """0013b: predict next step's prefill chunks and queue the D2H of
        their tokens (plus the ngram_context_len tokens before each) into a
        pinned stage, on the current stream, before the hook's sync."""
        from .ple_nvme import current_chunk_keys, plan_next_chunks

        num_reqs = input_batch.num_reqs
        idx = input_batch.idx_mapping_np[:num_reqs]
        computed = input_batch.num_computed_tokens_np[:num_reqs]
        scheduled = input_batch.num_scheduled_tokens[:num_reqs]
        prefill_len = input_batch.prefill_len_np[:num_reqs]
        keys = current_chunk_keys(idx, computed, scheduled, prefill_len)
        if not input_batch.has_prefill:
            return keys, []
        plan = plan_next_chunks(idx, computed, scheduled, prefill_len,
                                self._b70_lookahead_tokens)
        all_tokens = self._b70_req_states.all_token_ids.gpu
        stage = self._b70_lookahead_stage
        ctx_len = self.ngram_context_len
        spans = []
        offset = 0
        for req_idx, start, end in plan:
            lo = max(0, start - ctx_len)
            count = end - lo
            stage[offset : offset + count].copy_(
                all_tokens[req_idx, lo:end], non_blocking=True
            )
            spans.append((req_idx, start, end, offset, start - lo))
            offset += count
        return keys, spans

    def _b70_lookahead_submit(self, modules, spans) -> None:
        """0013b: build the predicted chunks' (tokens, qsl, ctx) on the host
        (after the sync) and hand them to each module's lookahead."""
        import numpy as np

        if not spans:
            return
        staged = self._b70_lookahead_stage.numpy()
        ctx_len = self.ngram_context_len
        eos = self.ngram_eos_token_id
        tokens = []
        context = np.full((len(spans), ctx_len), eos, dtype=np.int64)
        qsl = np.zeros(len(spans) + 1, dtype=np.int64)
        keys = set()
        for i, (req_idx, start, end, offset, before) in enumerate(spans):
            # Same rule as _prepare_ngram_context: positions < 0 are EOS.
            if before:
                context[i, ctx_len - before :] = staged[offset : offset + before]
            tokens.append(staged[offset + before : offset + before + end - start])
            qsl[i + 1] = qsl[i] + (end - start)
            keys.add((req_idx, start))
        flat = np.concatenate(tokens).astype(np.int64)
        for module in modules:
            module.b70_nvme_lookahead_submit(frozenset(keys), flat, qsl, context)

    def b70_pre_forward(
        self,
        input_batch: InputBatch,
        model_inputs: dict[str, Any],
        full_graph: bool,
    ) -> None:
        """B70 0013: resolve the PLE rows on the host before the forward.

        Called by the V2 runner just before "Run model", on real batches only
        (never on dummy/profile/capture runs). One D2H of the real tokens and
        n-gram context (int32, a few KB) and one sync, which waits for the
        previous step's sampling (the decode token exists only on the
        device); the n-gram ids are then computed on the host (bit-exact,
        ple_nvme.host_ngram_ids), resolved against the row cache, the misses
        read from NVMe, and the gather launched into the static
        _prefetch_buffer. No-op unless B70_PLE_INT8_NVME is active.
        """
        if not self.uses_ngram_embedding:
            return
        modules = self._b70_nvme_modules()
        if not modules:
            return
        import time

        num_tokens = input_batch.num_tokens
        num_reqs = input_batch.num_reqs
        ctx_len = self.ngram_context_len
        stage = self._b70_nvme_stage
        input_ids = model_inputs["input_ids"]
        if input_ids is None:
            input_ids = input_batch.input_ids
        stage[:num_tokens].copy_(input_ids[:num_tokens], non_blocking=True)
        stage[num_tokens : num_tokens + num_reqs * ctx_len].copy_(
            model_inputs["ngram_context"][:num_reqs].reshape(-1), non_blocking=True
        )
        lookahead_keys = None
        spans = []
        if self._b70_lookahead_on:
            lookahead_keys, spans = self._b70_lookahead_plan(input_batch)
        stream_mod = getattr(torch, input_ids.device.type)
        stream_mod.current_stream().synchronize()
        # The GPU is idle from here until the gather + forward are launched:
        # this is the per-step bubble the stats report.
        t_start = time.perf_counter()
        staged = stage.numpy()
        tokens = staged[:num_tokens]
        context = staged[num_tokens : num_tokens + num_reqs * ctx_len].reshape(
            num_reqs, ctx_len
        )
        query_start_loc = input_batch.query_start_loc_np[: num_reqs + 1]
        num_tokens_padded = input_batch.num_tokens_after_padding
        for module in modules:
            module.b70_nvme_pre_forward(
                tokens,
                query_start_loc,
                context,
                num_tokens_padded,
                full_graph,
                t_start,
                lookahead_keys=lookahead_keys,
            )
        if spans:
            # After the gather launch: the lookahead thread works while the
            # forward of this step runs.
            self._b70_lookahead_submit(modules, spans)

    def prepare_dummy_inputs(
        self,
        num_reqs: int,
        num_tokens: int,
    ) -> dict[str, Any]:
        model_inputs = super().prepare_dummy_inputs(num_reqs, num_tokens)
        if not self.uses_ngram_embedding:
            return model_inputs

        query_start_loc = self.ple_query_start_loc
        query_start_loc[0] = 0
        tokens_per_req, num_extra_tokens = divmod(num_tokens, num_reqs)
        query_lens = torch.full(
            (num_reqs,),
            tokens_per_req,
            dtype=query_start_loc.dtype,
            device=query_start_loc.device,
        )
        if num_extra_tokens > 0:
            query_lens[-num_extra_tokens:] += 1
        torch.cumsum(query_lens, dim=0, out=query_start_loc[1 : num_reqs + 1])
        query_start_loc[num_reqs + 1 :].fill_(num_tokens)

        ngram_context = self.ngram_context
        ngram_context.fill_(self.ngram_eos_token_id)
        model_inputs.update(
            query_start_loc=query_start_loc,
            ngram_context=ngram_context,
        )
        return model_inputs


__all__ = ["Qwen4ExpModelState"]
