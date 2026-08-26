# Embedded-Q8 MTP3 exact-depth R2 depth-zero failure

R2 passed the corrected runtime-closure gate and loaded the control MTP0 server,
then llama-server rejected the literal empty `input_ids` request with HTTP 400:
`"prompt" must not be empty`. No generation completed, no candidate server was
started, and no matrix cell exists.

Cleanup passed: no forced kill, the port closed, GPU0 returned idle, and there
was no server survivor. The raw terminal receipt SHA-256 is
`cc9852aa95afa5441eb48b99601e5490c5c4098c3807501f3a690719d3fa117f`.
The R2 root remains immutable.

R3 must not pretend that llama-server accepted an empty prompt. Its x=0 point
means **zero active tokens before the request**, followed by one explicit
ordinary prompt token. Token ID `90` is frozen directly from the first token of
the pinned 2K exact-depth fixture; it is not an inferred BOS or other special
token. The receipt must report `usage.prompt_tokens=1`, cache zero, and the
minimal-token disclosure. The 2K through 32K points retain their original
exact-token fixtures and semantics unchanged.
