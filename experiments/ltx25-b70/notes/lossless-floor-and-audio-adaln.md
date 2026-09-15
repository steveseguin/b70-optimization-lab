# The lossless floor, and why decode overlap is now a necessary condition

*2026-09-15. Shapes from the checkpoint header, rates from
[`scripts/gemm-peak-probe.py`](../scripts/gemm-peak-probe.py), equivalence from
[`scripts/rms-adaln-equivalence-probe.py`](../scripts/rms-adaln-equivalence-probe.py).*

## Where the clip stands

Steady state, with the text encode excluded because the prompt is fixed and a
continuous stream encodes it once:

| Stage | Time |
| --- | ---: |
| Sampler (344 + 368) | 1.93 s |
| Video decode (374) | 0.53 s |
| Audio decode (358) | 0.18 s |
| Save video (75) | 0.13 s |
| **Per clip** | **2.77 s** |

The budget is **1.042 s** (25 frames at 24 fps).

## The floor, computed rather than guessed

A transformer block holds **737.5 MB** (386.7 M bf16 parameters, from the
checkpoint header). The sampler runs **11 forwards** over 48 blocks, so it must
read 48 x 737.5 MB = **35.4 GB per forward**, 389 GB per clip. At the measured
**527.8 GB/s** copy roofline that is **67 ms per forward, 0.74 s per clip**, and
no lossless change can go below it: the weights must be read, and their
arithmetic may not be reordered.

Measured block region is about 1.58 s, so the sampler runs at **2.1x its own
floor**, with roughly 0.84 s of non-GEMM work on top.

**Now add the decode.** Even with a *perfect* sampler at 0.74 s:

> 0.74 s (sampler floor) + 0.71 s (video + audio decode) = **1.45 s > 1.042 s**

So on this hardware, with this checkpoint and these rules, **the goal is
unreachable while decode runs after sampling, no matter how good the sampler
gets.** Decoding clip N concurrently with sampling clip N+1 stops being an
optimisation and becomes a necessary condition. It is also the one large lever
that is lossless by construction: it changes no arithmetic at all, only when
work is scheduled. The decoder already lives on xpu:3 while the sampler uses
xpu:0 and xpu:1, so the hardware concurrency exists; what blocks it is ComfyUI's
single-threaded prompt worker.

## A smaller, proven lever: the audio path's adaLN

The block applies adaptive layer norm asymmetrically. The **video** path uses a
fused kernel at four sites:

```python
vx_scaled = comfy.quant_ops.ck.rms_adaln(vx, vscale_mlp, vshift_mlp)
```

while the **audio** path spells the same thing out at every site, as four
kernels instead of one:

```python
ax_scaled = comfy.ldm.common_dit.rms_norm(ax) * (1 + ascale_mlp) + ashift_mlp
```

The fused kernel is **bitwise equal** to the unfused sequence -- verified at the
audio shape `[1, 26, 2048]` and both video shapes `[1, 256, 4096]` and
`[1, 64, 4096]`, comparing raw bits, so the swap is admissible under this lane's
rules rather than merely close.

The audio stream costs 0.78-0.88 ms per block, 24-29% of it, on **26 tokens**,
and its GEMMs already read weights at 619.8 GB/s -- above the copy roofline.
Its cost is therefore the *number* of small kernels, each paying a launch floor
even inside a graph. Five audio adaLN sites at three saved kernels each is about
15 launches per block, worth an estimated **~0.05 s per clip**. Small, but real,
proven exact, and it attacks the right quantity.

Note one wrinkle: `ax_norm3 = rms_norm(ax)` is computed once and shared by the
a2v and v2a sites. Switching both to the fused kernel recomputes the norm twice
but removes six other launches, and makes `ax_norm3` dead.
