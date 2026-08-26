# Qwen3.8 Q8_0-weight/Q8_0-KV cache64 graph sentinel closeout

Status: **failed, closed negative**. No site or performance cells are
authorized, and no protected result or LocalMaxxing row changes.

The two fresh arms first completed the exact same 8K request. Graph off/cache0
measured `15.618717159021681` conventional decode tok/s and graph on/cache64
measured `15.36081896962535`. Both gates passed with 128 output tokens,
`cached_tokens=0`, and exact token-ID, text, usage, and returned-prompt parity.
Those are diagnostic sentinel measurements only; the failed full-quality gate
prevents publication.

The graph-off control then passed the complete Qwen3.8 battery: 7/7 exact
cases, two stable repeats, the 27.2K requested long-context needle, and ten
cache-zero requests. The graph-on candidate reached the long-context request,
processed through 8192 prompt tokens, and aborted in the SYCL FlashAttention
buffer path. The server reported that a queue wait cannot occur while a
command graph is recording, specifically `qptr->wait()` from `ensure_half` in
`fattn-buffers.cpp:23`. The client consequently received a remote disconnect.

Because the process aborted, it emitted neither a terminal graph summary nor
`graph-evidence.json`; the atomic quality result was also never created. These
absences are part of the negative, not missing evidence to reconstruct. Both
arms nevertheless cleaned up with a closed port, idle render node, no server
survivor, and no forced kill. No terminal receipt exists.

This closes the current Q8_0-weight/Q8_0-KV TP1/MTP0 cache64 command-graph
full-quality and seven-depth curve design. It does not weaken the already
passed Q8_0-KV graph-off curve, and it says nothing about F16 KV, other weight
quantizations, TP2/TP4, speculation, or a materially different graph fix. The
result JSON preserves the exact 18-file raw inventory, byte sizes, and hashes.
