# Qwen3.8 27B Q4_K_M TP1 realistic HTTP and exact-depth result

Status: **passed and package-eligible** for this exact one-card tuple.

The pinned oneAPI 2026.1.1 reconstruction loaded a one-slot, 33,024-token,
F16-KV service on one Arc Pro B70. The fixed realistic suite passed all 12
registered output hashes with zero cached prompt tokens. Its preferred
conventional 99-interval decode median was **27.785930 tok/s** (p10
**27.458108**) and median TTFT was **262.869 ms**.

The separate exact-token HTTP fixture passed at 2K, 4K, 8K, 16K, 24K, and
32K active context. Every receipt reported the exact prompt-token count,
zero cached tokens, no truncation or context shift, and 128 returned token
IDs. At exactly 32,768 active tokens it measured **24.488129 tok/s** decode
and **50,266.550 ms** TTFT.

The depth fixture is evidence grade C: it deliberately repeats registered
tokens to make the active context exact. It measures the context shape; it
does not pretend to be representative long natural prose. The realistic
short-prompt result and exact-depth curve therefore remain separate in the
package and neither is extrapolated.

Compact evidence and raw-artifact hashes are in
[`2026-08-25-qwen38-q4km-tp1-http-depth-r1-result.json`](../data/2026-08-25-qwen38-q4km-tp1-http-depth-r1-result.json).
The preregistration and runner are stored beside this note. Raw receipts are
retained on the lab evidence volume; the compact record pins each by SHA-256.

This closes realistic-prompt HTTP speed/TTFT and exact 2K→32K service depth
for Qwen3.8 Q4 TP1. It does **not** close output-qualified concurrency or a
clean-host Intel/oneAPI install replay.
