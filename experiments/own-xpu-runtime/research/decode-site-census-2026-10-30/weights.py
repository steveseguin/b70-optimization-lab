#!/usr/bin/env python3
"""Weight bytes per engine site role, from the loader placement (GGUF tensor bytes as stored; the engine's device weight
bytes equal them: rank 0 24.653 GB, rank 1 30.06 GB in the census runs' logs). CPU only. Routed experts are bytes per
expert (tensor bytes / 512)."""
from pathlib import Path

PLACEMENT = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/loader/placement.tsv')
GGML = {0: 'F32', 1: 'F16', 8: 'Q8_0', 12: 'Q4_K', 13: 'Q5_K', 14: 'Q6_K', 18: 'IQ3_XXS', 20: 'IQ4_NL', 21: 'IQ3_S', 22: 'IQ2_S',
        23: 'IQ4_XS', 30: 'BF16', 42: 'type42'}


def tensors():
    out = {}
    for line in PLACEMENT.read_text().splitlines():
        f = line.split()
        out[f[1]] = dict(type=GGML.get(int(f[3]), f[3]), bytes=int(f[5]), dims=[int(x) for x in f[9:9 + int(f[8])]])
    return out


T = tensors()


def is_qsa(layer):
    return f'blk.{layer}.attn_q.weight' in T


# role -> tensors read by that site (fused partners included: the trace has no separate gdn.b / qsa.ik / hc.*.inject /
# shared_gate launches; their tensors are read by the fused site)
DENSE = {
    'gdn.qkv': ['attn_qkv'], 'gdn.z': ['attn_gate'], 'gdn.a': ['ssm_alpha', 'ssm_beta'],
    'qsa.qgate': ['attn_q'], 'qsa.k': ['attn_k'], 'qsa.v': ['attn_v'], 'qsa.iq': ['indexer.q_proj', 'indexer.k_proj'],
    'hc.a.low': ['hc_attn_down'], 'hc.a.gate': ['hc_attn_up', 'hc_attn_inject'], 'hc.f.low': ['hc_ffn_down'],
    'hc.f.gate': ['hc_ffn_up', 'hc_ffn_inject'], 'router': ['ffn_gate_inp', 'ffn_gate_inp_shexp'],
    'shexpgate': ['ffn_gate_shexp'], 'shexpup': ['ffn_up_shexp'], 'shexpdown': ['ffn_down_shexp'],
}
EXPERT = {'expsgate': 'ffn_gate_exps', 'expsup': 'ffn_up_exps', 'expsdown': 'ffn_down_exps'}


def role_bytes(role, layer):
    """(bytes, formats) a site of `role` in `layer` reads at one row; experts: bytes per expert."""
    if role == 'attention':
        names = ['attn_output'] if is_qsa(layer) else ['ssm_out']
    elif role in DENSE:
        names = DENSE[role]
    elif role in EXPERT:
        t = T[f'blk.{layer}.{EXPERT[role]}.weight']
        return t['bytes'] / t['dims'][2], [t['type']]
    elif role == 'ple.key':
        return T['blk.1.ple_key.weight']['bytes'], ['BF16']
    elif role == 'ple.value':
        return T['blk.1.ple_value.weight']['bytes'], ['BF16']
    elif role == 'logits':
        return T['output.weight']['bytes'], [T['output.weight']['type']]
    elif role in ('final.low', 'final.gate'):
        n = 'output_hc_down.weight' if role == 'final.low' else 'output_hc_up.weight'
        return T[n]['bytes'], [T[n]['type']]
    else:
        return 0, []
    total, types = 0, []
    for n in names:
        t = T.get(f'blk.{layer}.{n}.weight')
        if t:
            total += t['bytes']; types.append(t['type'])
    return total, types


if __name__ == '__main__':
    for layer in (0, 3, 23, 24):
        for role in list(DENSE) + ['attention'] + list(EXPERT):
            b, ty = role_bytes(role, layer)
            if b:
                print(layer, role, int(b), ty)
