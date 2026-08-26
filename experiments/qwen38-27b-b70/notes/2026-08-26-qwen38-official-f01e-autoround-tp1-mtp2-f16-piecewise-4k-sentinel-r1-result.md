# Current f01e AutoRound TP1 PIECEWISE/F16 MTP2 exact-4K sentinel R1

The exact-4K model result passed, with a runner defect disclosed below. On the
pinned official `f01e24f6…` image (`ac7509e2b`, vLLM `0.27.2rc1.dev77`), the
TP1 native-MTP2 PIECEWISE/F16 server measured **11.988874911178696
conventional decode tok/s** and **2941.726919991197 ms TTFT**. The separate
historical 100-event field was 12.10997465775626 tok/s.

The isolated exact request drafted 94 tokens and accepted 80
(`0.851063829787234`). Every exact-depth gate passed with 4,096 prompt tokens,
128 returned token IDs, and zero cached tokens. The candidate exactly matched
both frozen same-image TP1/MTP0 eager/F16 and clean PIECEWISE/F16 parents across
all 128 tokens (hash `3febb16e…`). The full quality battery passed: 7/7 exact
cases, 8/8 deterministic repeats, the long-context needle, 24/24 baseline
comparisons, and cache zero on all 16 quality requests. Graph identity, TP1
topology, 19-file model verification, and runtime cleanup also passed.

The original runner nevertheless omitted its preregistered cache-isolation
receipt and enforcement gate. Its terminal still says
`passed-quality-clean-sentinel`, but that terminal alone is not treated here as
proof of the cache contract and was not rewritten. A separate report-only,
post-run audit of the surviving dedicated cache tree passed: exactly the
`rank_0_0` namespace, 6 rank files, 1,364 shared files, 1,370 total files, and
173,190,178 bytes. The immutable report is `545030d1…`; its complete content
manifest is `a90d8cea…`. This is structural post-run evidence, not a claim that
the original runner enforced the gate or automatic publication authority.

Accordingly, this packet records one Grade C exact-4K candidate only through a
separate human adjudication with the defect visible. It does not edit the
family contract or website, and it authorizes no automatic publication,
descendant, replacement, inference, or LocalMaxxing submission.

The corruption exclusions remain mandatory. The current-f01e graph family has
the `dd31856f…` alternate at exact 8K, diverging at token 99 (411 versus 579).
The same-image TP1/MTP2 eager arm separately diverged at 2K token 90 (59178
versus 16539), 8K token 99 (411 versus 579), and 16K token 32 (13 versus 11).
This clean 4K result clears none of those depths or any long-context or
graph-plus-MTP descendant.

Protected decode values `71.45427094575045`, `30.329809361830037`,
`49.05894025767351`, and `71.9001988117144` remain unchanged. Raw receipts are
under
`/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp1-mtp2-f16-piecewise-4k-sentinel-20260826-r1`.
