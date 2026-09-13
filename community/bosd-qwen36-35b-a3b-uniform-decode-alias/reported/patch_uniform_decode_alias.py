#!/usr/bin/env python3
"""Reject shape-aliased prefills in uniform-decode classification.

Adopts upstream vllm-project/vllm PR #53059 (fix for issue #53051) for the
XPU GDN lane. GPUModelRunner._is_uniform_decode classifies a batch as uniform
decode by shape only; with spec decode (uniform_decode_query_len = 1 +
num_spec_tokens), any prefill scheduling exactly that many tokens per request
aliases the uniform-decode shape, is dispatched into the uniform-decode
cudagraph, and replays capture-time metadata with null/stale GDN state indices
-> recurrent-state write silently skipped -> zeroed state -> degenerate
single-token walls (!!!!!, 0000, oooo) after real multi-session dwell.

Fix: after the shape test passes, additionally require every request to be past
its prompt (num_computed_tokens_cpu[:n] >= num_prompt_tokens[:n]). Needs `self`,
so the method stops being a staticmethod; the sole call site already uses
`self._is_uniform_decode(...)`, so no call-site change is required.

Idempotent + fail-loud, same contract as patch_mtp_nightly.py / patch_boundary.py.
"""
from __future__ import annotations

import importlib.util
import sys

MARKER = "B70_UNIFORM_DECODE_ALIAS_GUARD"

OLD = '''    @staticmethod
    def _is_uniform_decode(
        max_num_scheduled_tokens: int,
        uniform_decode_query_len: int,
        num_tokens: int,
        num_reqs: int,
        force_uniform_decode: bool | None = None,
    ) -> bool:
        """
        Checks if it's a decode batch with same amount scheduled tokens
        across all requests.
        """
        return (
            (
                (max_num_scheduled_tokens == uniform_decode_query_len)
                and (num_tokens == max_num_scheduled_tokens * num_reqs)
            )
            if force_uniform_decode is None
            else force_uniform_decode
        )
'''

NEW = '''    def _is_uniform_decode(
        self,
        max_num_scheduled_tokens: int,
        uniform_decode_query_len: int,
        num_tokens: int,
        num_reqs: int,
        force_uniform_decode: bool | None = None,
    ) -> bool:
        """
        Checks if it's a decode batch with same amount scheduled tokens
        across all requests.
        """
        # B70_UNIFORM_DECODE_ALIAS_GUARD (vllm #53051 / PR #53059): the shape
        # test alone misclassifies prefills that alias the spec-decode shape
        # (uniform_decode_query_len = 1 + num_spec_tokens). Dispatching such a
        # prefill into the uniform-decode cudagraph replays stale metadata with
        # null GDN state indices, silently skipping the recurrent-state write
        # and corrupting output. A batch is only uniform decode if every
        # request is already past its prompt.
        if force_uniform_decode is not None:
            return force_uniform_decode
        if not (
            max_num_scheduled_tokens == uniform_decode_query_len
            and num_tokens == max_num_scheduled_tokens * num_reqs
        ):
            return False
        input_batch = self.input_batch
        return bool(
            (
                input_batch.num_computed_tokens_cpu[:num_reqs]
                >= input_batch.num_prompt_tokens[:num_reqs]
            ).all()
        )
'''


def main() -> None:
    spec = importlib.util.find_spec("vllm.v1.worker.gpu_model_runner")
    if spec is None or not spec.origin:
        sys.exit("[alias-patch] gpu_model_runner module not found")
    path = spec.origin
    src = open(path).read()

    if MARKER in src:
        print(f"[alias-patch] already patched: {path}")
        return
    if OLD not in src:
        sys.exit(f"[alias-patch] anchor not found — _is_uniform_decode changed in {path}")

    new_src = src.replace(OLD, NEW, 1)
    if new_src.count(MARKER) != 1:
        sys.exit("[alias-patch] replacement produced wrong marker count")
    open(path, "w").write(new_src)
    # verify it re-imports cleanly enough to at least byte-compile
    compile(new_src, path, "exec")
    print(f"[alias-patch] patched {path}")


if __name__ == "__main__":
    main()
