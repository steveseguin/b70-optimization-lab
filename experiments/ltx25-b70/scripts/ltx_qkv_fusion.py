"""Fuse projections that share an input into one GEMM, where that is bit-exact.

The block reaches only 61.5% of its weight-read roofline because it issues many
small GEMMs, each paying roughly 28 us of fixed overhead for a few microseconds
of work. Projections that consume the same tensor can be stacked into a single
matrix, which keeps every output element's K reduction identical but changes the
GEMM shape -- and a changed shape can change the kernel. So each group was
measured at every token count its site sees, and only groups exact at all of them
are fused here. Notably the [heads, K] gate projection is NOT included: adding it
breaks exactness even where the same stack without it is exact.

No weight values change. The originals are retained so restore is exact.
"""
import hashlib
from pathlib import Path

import torch
import torch.nn.functional as F

from ltx_graph_capture import require

# site attribute on the block, the projections to stack, and why it qualifies
GROUPS = (
    ('audio_attn1', ('to_q', 'to_k', 'to_v'), 'audio self-attention: q, k and v all consume x'),
    ('audio_attn2', ('to_k', 'to_v'), 'audio text cross-attention: k and v consume the context'),
    ('audio_to_video_attn', ('to_k', 'to_v'), 'a2v: k and v consume the audio stream'),
    ('video_to_audio_attn', ('to_k', 'to_v'), 'v2a: k and v consume the video stream'),
)


def bit_equal(a, b):
    require(a.dtype == b.dtype and a.shape == b.shape, 'Fused output changed dtype or shape')
    if a.dtype in (torch.bfloat16, torch.float16):
        return torch.equal(a.view(torch.int16), b.view(torch.int16))
    if a.dtype == torch.float32:
        return torch.equal(a.view(torch.int32), b.view(torch.int32))
    return torch.equal(a, b)


class FusedGroup:
    """One stacked GEMM standing in for several projections of a block."""

    def __init__(self, block, site, names):
        module = getattr(block, site)
        self.site, self.names = site, names
        self.linears = [getattr(module, n) for n in names]
        for linear in self.linears:
            require(type(linear).__name__.endswith('Linear'), 'Expected a Linear projection')
            require(not getattr(linear, 'comfy_cast_weights', False),
                    'Refusing to fuse a projection that casts its weights')
            require(not getattr(linear, 'weight_function', None) and
                    not getattr(linear, 'bias_function', None),
                    'Refusing to fuse a projection carrying weight or bias functions')
            require(linear.weight.dtype == torch.bfloat16, 'Native BF16 projections required')
        base = self.linears[0].weight
        require(all(l.weight.shape[1] == base.shape[1] for l in self.linears),
                'Stacked projections must share an input width')
        require(all(l.weight.device == base.device for l in self.linears), 'Projections span devices')
        self.device = base.device
        self.widths = [l.weight.shape[0] for l in self.linears]
        self.weight = torch.cat([l.weight for l in self.linears], dim=0).contiguous()
        biases = [l.bias for l in self.linears]
        require(all((b is None) == (biases[0] is None) for b in biases), 'Mixed bias presence in a group')
        self.bias = None if biases[0] is None else torch.cat(biases, dim=0).contiguous()
        self.originals = [l.forward for l in self.linears]
        self._stash = None
        self._proved = set()

    # -- the stand-ins ------------------------------------------------------
    def _compute(self, x):
        out = F.linear(x, self.weight, self.bias)
        chunks, offset = [], 0
        for width in self.widths:
            chunks.append(out[..., offset:offset + width])
            offset += width
        signature = (tuple(x.shape), str(x.dtype), str(x.device), tuple(x.stride()))
        if signature not in self._proved:
            # Prove the fusion bit-for-bit against the separate projections, once
            # per shape, before any of its output is used.
            for chunk, original in zip(chunks, self.originals):
                require(bit_equal(chunk, original(x)),
                        f'Fused {self.site}.{"+".join(self.names)} differs from the separate '
                        f'projections at shape {tuple(x.shape)}; refuse fusion')
            self._proved.add(signature)
        self._stash = (x, chunks)
        return chunks

    def first(self, x):
        return self._compute(x)[0]

    def later(self, index):
        def call(x):
            stash = self._stash
            require(stash is not None and stash[0] is x,
                    f'{self.site}.{self.names[index]} saw a different input than the fused group; '
                    'the projection call order assumed by fusion does not hold')
            return stash[1][index]
        return call

    def install(self):
        self.linears[0].forward = self.first
        for i in range(1, len(self.linears)):
            self.linears[i].forward = self.later(i)

    def restore(self):
        for linear, original in zip(self.linears, self.originals):
            require(vars(linear).get('forward') is not None, 'Projection is not shadowed')
            del linear.forward
        self._stash = None
        self.weight = None
        self.bias = None

    def report(self):
        return {'site': self.site, 'projections': list(self.names), 'widths': self.widths,
                'input_width': int(self.linears[0].weight.shape[1]),
                'device': str(self.device), 'proved_shapes': len(self._proved)}


def install(patcher):
    """Fuse every qualifying group in all 48 blocks."""
    from ltx_graph_capture import validate_patcher
    diffusion, _ = validate_patcher(patcher)
    blocks = diffusion.transformer_blocks
    groups, bytes_added = [], 0
    for index, block in enumerate(blocks):
        for site, names, _why in GROUPS:
            require(hasattr(block, site), f'Block {index} has no {site}')
            group = FusedGroup(block, site, names)
            group.install()
            bytes_added += group.weight.numel() * group.weight.element_size()
            if group.bias is not None:
                bytes_added += group.bias.numel() * group.bias.element_size()
            groups.append((index, group))
    return groups, bytes_added


def restore(groups):
    for _index, group in groups:
        group.restore()


def summary(groups, bytes_added):
    sites = {}
    for index, group in groups:
        sites.setdefault(group.site, {'blocks': 0, 'projections': list(group.names),
                                      'widths': group.widths, 'proved_shapes': 0})
        sites[group.site]['blocks'] += 1
        sites[group.site]['proved_shapes'] = max(sites[group.site]['proved_shapes'], len(group._proved))
    return {'fused_groups': len(groups), 'sites': sites,
            'gemms_removed_per_block': sum(len(n) - 1 for _s, n, _w in GROUPS),
            'fused_weight_bytes': bytes_added,
            'fused_weight_GiB': round(bytes_added / 2**30, 3),
            'gate_projection_excluded': 'adding the [heads, K] gate to a stack breaks exactness even '
                                        'where the same stack without it is exact'}
