"""27B text decode arithmetic. All allocations and operands are CPU-only.

Source keys and outstanding numerical questions are in ../README.md. This is
an independently written mathematical reference, not imported runtime code.
FP32 operations round after each torch operation; no torch.compile/autocast.
The CPU BLAS reduction is pinned by the test receipt, not asserted to be Xe's.
"""
from dataclasses import dataclass
import math
import torch

F16, BF16, F32, FP8 = torch.float16, torch.bfloat16, torch.float32, torch.float8_e4m3fn


def cpu(*xs):
    """Reject non-CPU operands without initializing or querying a device."""
    if any(x.device.type != 'cpu' for x in xs):
        raise ValueError('CPU operands required')


def tree_sum(x):
    """Last-axis FP32 sum: adjacent pairs, zero-pad odd widths at each level.

    Frozen CPU reduction; Xe subgroup reduction tree is UNVERIFIED (U3/U4).
    """
    cpu(x)
    x = x.float()
    while x.shape[-1] > 1:
        if x.shape[-1] % 2:
            x = torch.cat((x, torch.zeros_like(x[..., :1])), -1)
        x = x[..., ::2] + x[..., 1::2]
    return x.squeeze(-1)


def bucket_dot(x, y):
    """GDN [..,128] dot: 32 lanes, four consecutive K entries per lane.

    Each lane accumulates ascending K in FP32, then tree_sum over lanes.
    Matches S1's lane partition/order; uses separate mul/add, not device FMA.
    """
    cpu(x, y)
    if x.shape[-1] != 128 or y.shape[-1] != 128:
        raise ValueError('27B GDN K must be 128')
    x, y = torch.broadcast_tensors(x.float(), y.float())
    x, y = x.reshape(*x.shape[:-1], 32, 4), y.reshape(*y.shape[:-1], 32, 4)
    acc = torch.zeros_like(x[..., 0])
    for i in range(4):
        acc = acc + x[..., i] * y[..., i]
    return tree_sum(acc)


def fp8_dequant(weight, scales, out_dtype=F16):
    """E4M3 -> FP32; multiply BF16 scale[n//128,k//128] in FP32; cast once.

    S2 supplies scales as multipliers to oneDNN (despite '_inv' suffix).
    BF16 scale storage is mandatory. The intermediate F16 rounding choice
    is U1: not proof of oneDNN's fused internal scale/cast order.
    """
    cpu(weight, scales)
    if weight.dtype != FP8 or scales.dtype != BF16 or weight.ndim != 2:
        raise ValueError('E4M3 matrix and BF16 scales required')
    n, k = weight.shape
    if min(n, k) <= 0 or scales.shape != ((n+127)//128, (k+127)//128):
        raise ValueError('128x128 scale shape')
    if out_dtype not in (F16, BF16, F32):
        raise ValueError('unsupported dequant output dtype')
    expanded = scales.float().repeat_interleave(128, 0).repeat_interleave(128, 1)
    return (weight.float() * expanded[:n, :k]).to(out_dtype)


@dataclass(frozen=True)
class Linear:
    """Immutable storage view: [N,K] FP8+BF16 scales or excluded BF16 weight.

    Forward uses F16 activations/weights, FP32 CPU BLAS accumulation, F16
    output. Process 128 output channels at a time to bound temporary storage.
    No activation quantization. BLAS K reduction / device parity: U1/U2.
    """
    weight: torch.Tensor
    scales: torch.Tensor | None = None

    def __post_init__(self):
        cpu(self.weight)
        if self.weight.ndim != 2 or min(self.weight.shape) <= 0:
            raise ValueError('matrix required')
        if self.scales is None:
            if self.weight.dtype != BF16:
                raise ValueError('excluded matrix must retain BF16 storage')
        else:
            cpu(self.scales)
            n, k = self.weight.shape
            if self.weight.dtype != FP8 or self.scales.dtype != BF16 or self.scales.shape != ((n+127)//128, (k+127)//128):
                raise ValueError('FP8 / BF16 scale contract')

    def __call__(self, x):
        """Cast stored BF16 to execution F16; dot in FP32, cast each output once."""
        cpu(x)
        if x.dtype != F16 or x.shape[-1] != self.weight.shape[1]:
            raise ValueError('F16 activation with matching K required')
        out = []
        for n in range(0, self.weight.shape[0], 128):
            w = self.weight[n:n+128]
            w = w.to(F16) if self.scales is None else fp8_dequant(w, self.scales[n//128:n//128+1])
            out.append((x.float() @ w.float().T).to(F16))
        return torch.cat(out, -1)


def rmsnorm(x, weight, eps=1e-6, unit_offset=True, out_dtype=F16):
    """FP32 square -> tree mean -> +eps -> rsqrt -> x multiply -> gain -> cast.

    Decoder/final/QK/MTP use gain=1+stored_weight (S3 GemmaRMSNorm), GDN
    output norm uses ordinary gain=weight. Stored BF16 gain becomes execution
    F16 before FP32 upcast; gain-load/reduction parity remains U2/U3.
    """
    cpu(x, weight)
    if weight.dtype != BF16 or weight.shape != x.shape[-1:]:
        raise ValueError('BF16 norm weight matching last axis required')
    xf = x.float()
    variance = tree_sum(xf * xf).unsqueeze(-1) / x.shape[-1]
    gain = weight.to(F16).float()
    if unit_offset:
        gain = gain + 1.0
    return ((xf * torch.rsqrt(variance + eps)) * gain).to(out_dtype)


def residual_add(branch, residual):
    """S3: add branch and carried residual in FP32, retain FP32 residual.

    The normalized branch is F16; do not round the residual to F16 per block.
    """
    cpu(branch, residual)
    return branch.float() + residual.float()


def silu(x, out_dtype=F16):
    """FP32 x/(1+exp(-x)), then one output cast; transcendental parity U3."""
    cpu(x)
    return (x.float() / (1.0 + torch.exp(-x.float()))).to(out_dtype)


def ffn(x, gate, up, down):
    """F16 projections -> FP32 SiLU(gate)*up -> F16 -> down projection.

    No intermediate F16 SiLU rounding (fused gate/product semantics); U3.
    """
    g, u = gate(x), up(x)
    return down((silu(g, F32) * u.float()).to(F16))


def conv_step(x, history, weight):
    """Width-4 depthwise convolution, history oldest first [channels,3].

    Append current F16 input. Ascending tap FP32 multiply/add, SiLU in FP32,
    cast F16 once. Return fresh history (no in-place state mutation). S1 conv
    source fixes tap order; FMA contraction/activation remains U3/U4.
    """
    cpu(x, history, weight)
    if x.dtype != F16 or history.dtype != F16 or weight.dtype != BF16 or history.shape != (x.numel(), 3) or weight.shape != (x.numel(), 1, 4):
        raise ValueError('conv shape/dtype contract')
    window = torch.cat((history, x[:, None]), -1)
    acc = torch.zeros_like(x, dtype=F32)
    w = weight.to(F16).float().squeeze(1)
    for i in range(4):
        acc = acc + window[:, i].float() * w[:, i]
    return silu(acc), window[:, 1:].clone()


def gdn_recurrence(q, k, v, a, b, a_log, dt_bias, state):
    """S1 exact dependency order; state [48,V=128,K=128], rows [T,H,D].

    For each row: normalize Q/K in FP32 (epsilon inside sqrt); scale Q by
    1/sqrt(128); beta=sigmoid(b); decay=exp(-exp(A_log)*softplus(a+dt)).
    Decay state, dot decayed state with K, delta=(V-dot)*beta, add K*delta,
    dot updated state with Q, cast output F16, retain/write FP32 state before
    the next row. No BF16 Flash-Next state rounding. S1 uses a<20 softplus.
    Lane sums use bucket_dot; U4 covers FMA/tree/exp/sqrt machine identity.
    """
    cpu(q, k, v, a, b, a_log, dt_bias, state)
    t = q.shape[0]
    if q.shape != (t,16,128) or k.shape != q.shape or v.shape != (t,48,128) or a.shape != (t,48) or b.shape != a.shape or state.shape != (48,128,128):
        raise ValueError('27B GDN shapes')
    if any(z.dtype != F16 for z in (q,k,v,a,b)) or state.dtype != F32 or a_log.dtype != BF16 or dt_bias.dtype != BF16 or a_log.shape != (48,) or dt_bias.shape != (48,):
        raise ValueError('GDN dtype/vector contract')
    s, outputs = state.clone(), []
    # S1 A_log is a float pointer; preserve BF16 value by direct FP32 upcast.
    negative_rate = -torch.exp(a_log.float())
    dt = dt_bias.to(F16).float()
    for row in range(t):
        qr, kr = q[row].float(), k[row].float()
        qr = qr / torch.sqrt(bucket_dot(qr,qr).unsqueeze(-1) + 1e-6)
        qr = qr * (1.0 / math.sqrt(128))
        kr = kr / torch.sqrt(bucket_dot(kr,kr).unsqueeze(-1) + 1e-6)
        qr, kr = qr.repeat_interleave(3,0), kr.repeat_interleave(3,0)
        av = a[row].float() + dt
        sp = av.clone()
        mask = av < 20.0
        sp[mask] = torch.log(1.0 + torch.exp(av[mask]))
        decay = torch.exp(negative_rate * sp)
        beta = 1.0 / (1.0 + torch.exp(-b[row].float()))
        s = s * decay[:,None,None]
        prediction = bucket_dot(s, kr[:,None,:])
        delta = (v[row].float() - prediction) * beta[:,None]
        s = s + kr[:,None,:] * delta[:,:,None]
        outputs.append(bucket_dot(s, qr[:,None,:]).to(F16))
    return torch.stack(outputs), s


def gdn(x, w, history, state):
    """Serial rows: projections, conv, recurrence, ordinary gated RMS, output.

    Input/output [T,5120]; FP32 state and F16 conv history are returned.
    GDN output gain is NOT unit-offset; normalize then SiLU(z), one F16 cast.
    """
    cpu(x, history, state)
    if x.ndim != 2 or x.shape[1] != 5120:
        raise ValueError('27B hidden=5120')
    qkv, z = w['qkv'](x), w['z'](x).reshape(-1,48,128)
    a, b = w['a'](x), w['b'](x)
    convolved = []
    for row in qkv:
        c, history = conv_step(row, history, w['conv'])
        convolved.append(c)
    c = torch.stack(convolved)
    q, k, v = c.split([2048,2048,6144], -1)
    y, state = gdn_recurrence(q.reshape(-1,16,128), k.reshape(-1,16,128), v.reshape(-1,48,128), a,b,w['A_log'],w['dt_bias'],state)
    y = rmsnorm(y,w['norm'],unit_offset=False,out_dtype=F32) * silu(z,F32)
    return w['out'](y.to(F16).flatten(1)), history, state


def rope(x, positions):
    """Text-only split-half RoPE on first 64/256 dims, theta=1e7 (S4).

    Equal text positions on all MRoPE axes reduce to ordinary frequencies.
    FP32 angle/sin/cos -> F16 tables; FP32 products/subtract/add -> F16.
    U5: certified table casting and fusion. Non-text positions unsupported.
    """
    cpu(x, positions)
    if x.dtype != F16 or x.shape[-1] != 256 or positions.shape != (x.shape[0],) or positions.dtype != torch.int64 or bool((positions < 0).any()):
        raise ValueError('text RoPE shape/dtype/position')
    freq = 1.0 / (10000000.0 ** (torch.arange(32, dtype=F32, device='cpu') / 32))
    angle = positions.float()[:,None] * freq[None,:]
    c, s = angle.cos().to(F16).float()[:,None,:], angle.sin().to(F16).float()[:,None,:]
    left, right = x[...,:32].float(), x[...,32:64].float()
    rotated = torch.cat((left*c-right*s, right*c+left*s), -1).to(F16)
    return torch.cat((rotated,x[...,64:]),-1)


def attention(x, w, positions, kv):
    """27B Q24/KV4/D256; Q projection interleaves Q/gate per head (S4).

    Q/K unit-offset RMS -> RoPE -> append F16 K/V -> causal serial rows.
    FP32 QK matmul /16, max-subtracted exp, tree denominator, FP32 PV;
    F16 attention output -> swish gate (contract) -> F16 -> output projection.
    U5 covers device softmax/reduction/casts and swish vs older sigmoid source.
    """
    cpu(x, positions, *kv)
    if x.ndim != 2 or x.shape[1] != 5120 or any(t.dtype != F16 for t in kv) or kv[0].shape != kv[1].shape or kv[0].shape[1:] != (4,256):
        raise ValueError('attention/KV contract')
    qg = w['q'](x).reshape(-1,24,512)
    q, gate = qg[...,:256], qg[...,256:]
    k, v = w['k'](x).reshape(-1,4,256), w['v'](x).reshape(-1,4,256)
    q, k = rope(rmsnorm(q,w['q_norm']), positions), rope(rmsnorm(k,w['k_norm']), positions)
    keys, values = torch.cat((kv[0],k),0), torch.cat((kv[1],v),0)
    outputs = []
    for row in range(x.shape[0]):
        end = kv[0].shape[0] + row + 1
        kh = keys[:end].repeat_interleave(6,1).transpose(0,1).float()
        vh = values[:end].repeat_interleave(6,1).transpose(0,1).float()
        score = torch.matmul(q[row,:,None,:].float(),kh.transpose(1,2)).squeeze(1) * (1.0/16)
        ex = torch.exp(score-score.max(-1,keepdim=True).values)
        prob = ex / tree_sum(ex).unsqueeze(-1)
        out = torch.matmul(prob[:,None,:],vh).squeeze(1).to(F16)
        outputs.append((out.float()*silu(gate[row],F32)).to(F16).flatten())
    return w['out'](torch.stack(outputs)), (keys,values)


def decoder_layer(branch, residual, w, kind, cache, positions=None):
    """S3 residual scheduling: merge previous branch before input norm;
    attention -> FP32 residual merge -> post norm -> FFN. Return branch and
    carried residual separately, avoiding an extra F16 residual rounding.
    """
    r = branch if residual is None else residual_add(branch,residual)
    x = rmsnorm(r,w['input_norm'])
    if kind == 'gdn':
        y, history, state = gdn(x,w['attention'],*cache)
        cache = (history,state)
    elif kind == 'attention':
        y, cache = attention(x,w['attention'],positions,cache)
    else:
        raise ValueError('unsupported layer kind')
    r = residual_add(y,r)
    x = rmsnorm(r,w['post_norm'])
    return ffn(x,**w['ffn']), r, cache


def target_head(branch, residual, norm_weight, head):
    """Merge FP32 residual, unit-offset final RMS -> F16 full target head.

    No shortlist; caller supplies the full [248320,5120] target matrix in
    production. Smaller synthetic heads are allowed for arithmetic fixtures.
    """
    return head(rmsnorm(residual_add(branch,residual),norm_weight))


def stable_argmax(logits):
    """Lowest token index wins exact ties (including +/-0); reject NaNs.

    +/-infinity is allowed. No tolerance-based ties. Comparator tie policy U6.
    """
    cpu(logits)
    if logits.shape[-1] == 0 or bool(torch.isnan(logits).any()):
        raise ValueError('empty vocabulary or NaN logits')
    return torch.argmax(logits,dim=-1)


def mtp_forward(hidden, embedding, w, positions, kv, head):
    """S5: norm embedding first, norm hidden, concatenate [embedding,hidden],
    BF16-stored merge Linear -> full-attention decoder -> final MTP norm/head.
    Returns normalized draft hidden, proposal logits and fresh KV. Embedding
    and full head are shared with target; no acceptance or shortlist logic.
    U7 covers certified merge/residual/proposal boundary and source identity.
    """
    e = rmsnorm(embedding,w['embedding_norm'])
    h = rmsnorm(hidden,w['hidden_norm'])
    merged = w['fc'](torch.cat((e,h),-1))
    branch, residual, kv = decoder_layer(merged,None,w['layer'],'attention',kv,positions)
    h = rmsnorm(residual_add(branch,residual),w['norm'])
    return h, head(h), kv
