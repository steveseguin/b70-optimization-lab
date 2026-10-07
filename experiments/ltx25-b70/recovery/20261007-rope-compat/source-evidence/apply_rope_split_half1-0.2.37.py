def apply_rope_split_half1(x: torch.Tensor, freqs_cis: torch.Tensor) -> torch.Tensor:
    t = x
    # Let products upcast the input without allocating a full-size copy.
    if torch.promote_types(x.dtype, freqs_cis.dtype) != freqs_cis.dtype:
        t = x.to(freqs_cis.dtype)
    if freqs_cis.ndim == 2:
        freqs_cis = freqs_cis.unsqueeze(0)
    diagonal = freqs_cis.diagonal(dim1=-2, dim2=-1).movedim(-1, -2)
    out = t.unflatten(-1, (2, -1)) * diagonal
    half = x.shape[-1] // 2
    out[..., 0, :].addcmul_(t[..., half:], freqs_cis[..., 0, 1])
    out[..., 1, :].addcmul_(t[..., :half], freqs_cis[..., 1, 0])
    return out.reshape(x.shape).type_as(x)
