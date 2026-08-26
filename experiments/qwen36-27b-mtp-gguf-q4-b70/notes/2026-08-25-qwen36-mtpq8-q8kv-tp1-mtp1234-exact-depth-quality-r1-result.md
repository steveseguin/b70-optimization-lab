# Qwen 3.6 embedded-Q8 Q8KV MTP1/2/3/4 expansion R1 result

Classification: failed global cross-KV seal, with useful partial quality and
performance evidence preserved. Nothing in this result is publication or
protected-speed authority.

The preregistered aggregate gate correctly failed. The fresh Q8KV MTP0 control
did not match the inherited F16 sealed output at x0, 2K, or 24K. At x0 and 24K
all four speculative routes did match the fresh Q8KV control, so those failures
are specifically cross-KV seal failures. At 2K there is an additional local
split: the fresh Q8KV control produced `e11b5a31...`, MTP1 produced the
inherited F16 hash `15ae8933...`, and MTP2/3/4 all produced `6177d779...`.
No root cause is inferred.

Across the 28 candidate cells, 24 matched the fresh Q8KV control, 17 matched
the inherited F16 seal, and 16 satisfied both preregistered parity conditions.
All 35 exact-depth requests were cache-zero. Drafting engaged and conserved in
all 28 candidate cells, and every MTP1/2/3/4 quality battery passed four exact
canaries, two stable repeats, and the approximately 27.2K-actual needle with
all seven battery requests uncached. All five independent server lifetimes
cleaned up normally.

Observed serving decode ranges were 8.938–16.986 tok/s for MTP0,
13.526–28.593 for MTP1, 25.460–35.075 for MTP2, 27.315–39.292 for MTP3,
and 26.704–40.278 for MTP4. These measurements are retained as negative/partial
research evidence only; they do not authorize matrix cells or replace any
featured, primary, protected, F16, record, or LocalMaxxing value.

The raw root is
`/mnt/fast-ai/bench-results/qwen36-mtpq8-q8kv-tp1-mtp1234-exact-depth-quality-20260825-r1`.
Its terminal receipt SHA is
`a793930bc2d4a244c2c45bd5663e095bb109f6f13e3a1361823be71d84520bbf`,
identity SHA is
`6f022df0ab44ca57e36d0563bce4cb391d4cd80a483adb324fce5d12da8a69f6`,
and the 133-file inventory is sealed at
`773ddfa27438272666a4b90b484a24021251884bcecb78feb64b41607b304a62`.
Any salvage or rerun needs a separately preregistered Q8KV-local seal and an
explicit interpretation of the 2K three-way split.
