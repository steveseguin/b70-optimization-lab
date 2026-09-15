#!/usr/bin/env python3
"""Op-level check of the b70_gdn_head_groups overlay against the fused XPU gdn_attention op.

Operator diagnostic only. For one-card Qwen3.8-27B GDN widths, fresh prefill
(has_initial_state False) followed by a second chunk that continues from the
cached state (has_initial_state True): run the fused op several times and the
grouped overlay path several times on identical inputs and state caches. Reports
whether the grouped path repeats bitwise, whether it equals the most common fused
result, and whether z / conv_state / ssm_state match exactly.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path

import torch

K_HEADS, V_HEADS, HEAD_K, HEAD_V, KERNEL, SLOTS = 16, 48, 128, 128, 4, 3


def digest(tensors):
    h = hashlib.sha256()
    for t in tensors:
        h.update(t.detach().contiguous().cpu().view(torch.uint8).numpy().tobytes())
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--overlay', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--repeats', type=int, default=12)
    args = ap.parse_args()
    import vllm  # noqa: F401
    import vllm._xpu_ops  # noqa: F401
    import vllm_xpu_kernels._xpu_C  # noqa: F401
    from vllm.model_executor.layers.mamba.mamba_utils import MambaStateShapeCalculator

    spec = importlib.util.spec_from_file_location('b70_gdn_head_groups', args.overlay)
    overlay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(overlay)
    dev = torch.device('xpu:0')
    fused = torch.ops._xpu_C.gdn_attention
    conv_shape, ssm_shape = MambaStateShapeCalculator.gated_delta_net_state_shape(1, K_HEADS, V_HEADS, HEAD_K, HEAD_V,
                                                                                  KERNEL, 0)
    report = dict(schema='neural.download.qwen38-gdn-head-groups-op-check.v1', cases=[])
    for n1, n2 in ((2048, 2048), (4096, 1024), (512, 3000)):
        gen = torch.Generator().manual_seed(n1 * 7 + n2)
        r = lambda s, d, sc: (torch.randn(s, generator=gen) * sc).to(d).to(dev)  # noqa: E731
        cw, alog, dtb = r((10240, KERNEL), torch.float16, 0.2), r((V_HEADS,), torch.float32, 0.5), r((V_HEADS,), torch.float16, 0.5)
        chunks = [(r((n, 16384), torch.float16, 0.5), r((n, 96), torch.float16, 0.5), n, his)
                  for n, his in ((n1, False), (n2, True))]
        slot = torch.tensor([1], dtype=torch.int32, device=dev)

        def run(grouped):
            conv_state = torch.zeros((SLOTS, *conv_shape), dtype=torch.float16, device=dev)
            ssm_state = torch.zeros((SLOTS, *ssm_shape), dtype=torch.float32, device=dev)
            conv_state[0].fill_(0.25)
            ssm_state[2].fill_(-0.5)  # neighbouring slots must stay untouched
            outputs = []
            for qkvz, ba, n, his in chunks:
                out = torch.zeros((n, V_HEADS, HEAD_V), dtype=torch.float16, device=dev)
                z = torch.empty_like(out)
                kw = dict(conv_state=conv_state, ssm_state=ssm_state, conv_weights=cw, conv_bias=None,
                          activation='silu', A_log=alog, dt_bias=dtb, num_prefills=1, num_decodes=0,
                          num_spec_decodes=0, has_initial_state=torch.tensor([his], device=dev),
                          non_spec_query_start_loc=torch.tensor([0, n], dtype=torch.int32, device=dev),
                          non_spec_token_indx=None, non_spec_state_indices_tensor=slot, spec_query_start_loc=None,
                          spec_token_indx=None, spec_state_indices_tensor=None, num_accepted_tokens=None,
                          num_actual_tokens=n, tp_size=1, reorder_input=True)
                if grouped:
                    overlay.grouped_gdn_attention(out, z, qkvz, ba, K_HEADS, V_HEADS, HEAD_K, HEAD_V, groups=2, **kw)
                else:
                    fused(out, z, qkvz, ba, K_HEADS, V_HEADS, HEAD_K, HEAD_V, **kw)
                torch.xpu.synchronize()
                outputs.append(dict(core=digest([out]), z=digest([z])))
            outputs.append(dict(conv_state=digest([conv_state]), ssm_state=digest([ssm_state])))
            return json.dumps(outputs, sort_keys=True)

        fused_runs = collections.Counter(run(False) for _ in range(args.repeats))
        grouped_runs = collections.Counter(run(True) for _ in range(args.repeats))
        fused_mode = fused_runs.most_common(1)[0][0]
        grouped_only = next(iter(grouped_runs)) if len(grouped_runs) == 1 else None
        case = dict(chunks=[n1, n2], fused_distinct=len(fused_runs), grouped_distinct=len(grouped_runs),
                    grouped_equals_fused_mode=grouped_only == fused_mode,
                    fused_mode_count=fused_runs[fused_mode],
                    grouped=json.loads(next(iter(grouped_runs))), fused_mode=json.loads(fused_mode))
        report['cases'].append(case)
        print(json.dumps({k: v for k, v in case.items() if k not in ('grouped', 'fused_mode')}), flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
